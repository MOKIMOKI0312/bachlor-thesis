"""Run the Phase 3 PV-TES technical sizing matrix."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from mpc_v2.core.io_schemas import load_yaml, parse_timestamp
from mpc_v2.phase3_sizing.metrics import (
    add_marginal_metrics,
    add_relative_metrics,
    apply_critical_peak_uplift,
    compute_case_metrics,
)
from mpc_v2.phase3_sizing.pv_scaling import scale_pv_profile
from mpc_v2.phase3_sizing.recommendation import add_recommendation_columns
from mpc_v2.phase3_sizing.scenario_builder import build_scenario_matrix, scenario_manifest_frame
from mpc_v2.phase3_sizing.tes_scaling import build_tes_config


def run_phase3_pv_tes_matrix(
    config_path: str | Path,
    locations_path: str | Path,
    output_root: str | Path,
    location_filter: str | None = None,
    include_stress_uplift: bool = False,
    parallel: int = 1,
) -> Path:
    """Run Phase 3 scenarios and write per-run and summary artifacts."""

    phase3_cfg = load_yaml(config_path)
    locations_cfg = load_yaml(locations_path)
    output_root = Path(output_root)
    summary_dir = output_root / "summary"
    runs_dir = output_root / "runs"
    summary_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    missing = _find_missing_location_data(locations_cfg, location_filter)
    if missing:
        report = summary_dir / "missing_data_report.md"
        report.write_text(_missing_report(missing), encoding="utf-8")
        raise FileNotFoundError(f"missing Phase 3 input data; see {report}")

    scenarios = build_scenario_matrix(
        phase3_cfg,
        locations_cfg,
        output_root=output_root,
        location_filter=location_filter,
        include_stress_uplift=include_stress_uplift,
    )
    manifest = scenario_manifest_frame(scenarios)
    manifest.to_csv(summary_dir / "scenario_manifest.csv", index=False)

    location_map = {str(item["id"]): item for item in locations_cfg["locations"]}
    rows: list[dict[str, Any]] = []
    status_by_id: dict[str, str] = {}
    errors: dict[str, str] = {}
    for scenario in scenarios:
        run_dir = scenario.run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            timeseries, effective_cfg, solver_log = _simulate_scenario(
                phase3_cfg=phase3_cfg,
                location_cfg=location_map[scenario.location_id],
                scenario=scenario,
                parallel_requested=parallel,
            )
            timeseries.to_csv(run_dir / "timeseries.csv", index=False)
            solver_log.to_csv(run_dir / "solver_log.csv", index=False)
            (run_dir / "config_effective.yaml").write_text(
                yaml.safe_dump(effective_cfg, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            metrics = compute_case_metrics(
                timeseries=timeseries,
                dt_hours=float(phase3_cfg["simulation"]["dt_hours"]),
                tes_capacity_mwh_th=scenario.tes_capacity_mwh_th,
                soc_min=float(phase3_cfg["tes"]["soc_min"]),
                soc_max=float(phase3_cfg["tes"]["soc_max"]),
                max_signed_du=float(phase3_cfg["controller"]["max_signed_du"]),
            )
            row = {
                "scenario_id": scenario.scenario_id,
                "location_id": scenario.location_id,
                "pv_capacity_mwp": scenario.pv_capacity_mwp,
                "tes_capacity_mwh_th": scenario.tes_capacity_mwh_th,
                "critical_peak_uplift": scenario.critical_peak_uplift,
                "critical_peak_window_set": scenario.critical_peak_window_set,
                "controller": scenario.controller,
                "run_dir": str(run_dir),
                "status": "completed",
                **metrics,
            }
            (run_dir / "episode_summary.json").write_text(
                json.dumps(_json_ready(row), indent=2),
                encoding="utf-8",
            )
            rows.append(row)
            status_by_id[scenario.scenario_id] = "completed"
        except Exception as exc:
            status_by_id[scenario.scenario_id] = "failed"
            errors[scenario.scenario_id] = str(exc)
            (run_dir / "error.txt").write_text(str(exc), encoding="utf-8")

    manifest["status"] = manifest["scenario_id"].map(status_by_id).fillna("failed")
    manifest.to_csv(summary_dir / "scenario_manifest.csv", index=False)
    if errors:
        (summary_dir / "failed_cases.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = add_relative_metrics(summary)
        summary = add_marginal_metrics(summary)
        summary, recommendations = add_recommendation_columns(summary, phase3_cfg.get("recommendation", {}))
    else:
        recommendations = pd.DataFrame()
    summary.to_csv(summary_dir / "phase3_summary.csv", index=False)
    recommendations.to_csv(summary_dir / "phase3_capacity_recommendations.csv", index=False)
    _write_phase3_docs(summary, recommendations, output_root)

    if errors:
        raise RuntimeError(f"{len(errors)} Phase 3 scenarios failed; see {summary_dir / 'failed_cases.json'}")
    return output_root


def _simulate_scenario(
    phase3_cfg: dict[str, Any],
    location_cfg: dict[str, Any],
    scenario,
    parallel_requested: int,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    dt_hours = float(phase3_cfg["simulation"]["dt_hours"])
    episode_days = int(phase3_cfg["simulation"]["episode_days"])
    steps = int(round(episode_days * 24 / dt_hours))
    start_ts = parse_timestamp(phase3_cfg["simulation"].get("start_timestamp", "2025-07-01 00:00:00"))
    timestamps = pd.DatetimeIndex([start_ts + timedelta(hours=dt_hours * i) for i in range(steps)])
    window_name = str(phase3_cfg["critical_peak"].get("default_window_set", "evening"))
    windows = phase3_cfg["critical_peak"]["window_sets"][window_name]

    pv_base = _align_series(_load_series(location_cfg["pv_profile_20mwp"], ["power_kw", "pv_kw"]), timestamps)
    pv_kw = scale_pv_profile(
        pv_base,
        base_capacity_mwp=float(phase3_cfg["pv"]["reference_mwp"]),
        target_capacity_mwp=float(scenario.pv_capacity_mwp),
    )
    load = _load_load_profile(location_cfg["load_profile"], timestamps)
    weather = _load_weather(location_cfg["weather_profile"], timestamps)
    price_path = location_cfg.get("price_profile", phase3_cfg.get("price", {}).get("profile"))
    if not price_path:
        raise ValueError(f"location {location_cfg['id']} has no price_profile")
    price_base = _align_series(_load_series(price_path, ["price_usd_per_mwh", "price_currency_per_mwh", "price"]), timestamps)
    price, cp_flag = apply_critical_peak_uplift(price_base, float(scenario.critical_peak_uplift), windows)

    base_cfg = load_yaml(phase3_cfg.get("base_config", "mpc_v2/config/base.yaml"))
    tes_base = dict(base_cfg["tes"])
    tes_base.update(
        {
            "q_tes_abs_max_kw_th": float(phase3_cfg["tes"]["q_tes_abs_max_kw_th"]),
            "initial_soc": float(phase3_cfg["tes"]["soc_initial"]),
            "soc_initial": float(phase3_cfg["tes"]["soc_initial"]),
            "soc_planning_min": float(phase3_cfg["tes"]["soc_min"]),
            "soc_planning_max": float(phase3_cfg["tes"]["soc_max"]),
            "soc_target": float(phase3_cfg["tes"]["soc_target"]),
        }
    )
    tes_cfg = build_tes_config(
        tes_base,
        capacity_mwh_th=float(scenario.tes_capacity_mwh_th),
        q_abs_max_kw_th=float(phase3_cfg["tes"]["q_tes_abs_max_kw_th"]),
    )

    rows = _kim_lite_relaxed_proxy(
        timestamps=timestamps,
        it_load_kw=load["it_load_kw"],
        base_facility_kw=load.get("base_facility_kw"),
        chiller_cooling_kw=load.get("chiller_cooling_kw"),
        outdoor_temp_c=weather["outdoor_temp_c"],
        outdoor_wetbulb_c=weather.get("outdoor_wetbulb_c"),
        zone_temp_c=weather.get("zone_temp_c"),
        pv_kw=pv_kw,
        price=price,
        price_base=price_base,
        cp_flag=cp_flag,
        tes_cfg=tes_cfg,
        phase3_cfg=phase3_cfg,
        location_cfg=location_cfg,
        cp_uplift=float(scenario.critical_peak_uplift),
    )
    timeseries = pd.DataFrame(rows)
    solver_log = pd.DataFrame(
        {
            "timestamp": timeseries["timestamp"],
            "step": timeseries["step"],
            "solve_status": "kim_lite_relaxed_proxy",
            "solve_time_s": 0.0,
            "objective_value": np.nan,
            "mip_gap": np.nan,
        }
    )
    effective = {
        "scenario_id": scenario.scenario_id,
        "location_id": scenario.location_id,
        "pv_capacity_mwp": float(scenario.pv_capacity_mwp),
        "tes_capacity_mwh_th": float(scenario.tes_capacity_mwh_th),
        "critical_peak_uplift": float(scenario.critical_peak_uplift),
        "critical_peak_windows": windows,
        "controller": phase3_cfg["controller"],
        "tes_effective": tes_cfg,
        "parallel_requested": int(parallel_requested),
        "data_boundary": location_cfg.get("data_boundary", "configured CSV profiles"),
        "epw_path": location_cfg.get("epw_path"),
        "energyplus_baseline_timeseries": location_cfg.get("energyplus_baseline_timeseries"),
    }
    return timeseries, effective, solver_log


def _kim_lite_relaxed_proxy(
    timestamps: pd.DatetimeIndex,
    it_load_kw: pd.Series,
    base_facility_kw: pd.Series | None,
    chiller_cooling_kw: pd.Series | None,
    outdoor_temp_c: pd.Series,
    outdoor_wetbulb_c: pd.Series | None,
    zone_temp_c: pd.Series | None,
    pv_kw: pd.Series,
    price: pd.Series,
    price_base: pd.Series,
    cp_flag: pd.Series,
    tes_cfg: dict[str, Any],
    phase3_cfg: dict[str, Any],
    location_cfg: dict[str, Any],
    cp_uplift: float,
) -> list[dict[str, Any]]:
    facility_cfg = load_yaml(phase3_cfg.get("base_config", "mpc_v2/config/base.yaml"))["facility"]
    base_pue = float(facility_cfg["base_pue"]) + float(location_cfg.get("pue_offset", 0.0))
    temp_coeff = float(facility_cfg["outdoor_temp_coeff_per_c"])
    ref_temp = float(facility_cfg["reference_outdoor_c"])
    cop_charge = float(facility_cfg.get("cop_charge", 5.2))
    cop_discharge = float(facility_cfg.get("cop_discharge_equiv", 5.0))
    capacity_kwh = float(tes_cfg["capacity_kwh_th"])
    qmax = float(tes_cfg["q_tes_abs_max_kw_th"])
    eta_ch = float(tes_cfg.get("eta_ch", 0.94))
    eta_dis = float(tes_cfg.get("eta_dis", 0.92))
    loss_per_h = float(tes_cfg.get("lambda_loss_per_h", 0.002))
    soc = float(tes_cfg.get("initial_soc", tes_cfg.get("soc_initial", 0.5)))
    soc_min = float(phase3_cfg["tes"]["soc_min"])
    soc_max = float(phase3_cfg["tes"]["soc_max"])
    soc_target = float(phase3_cfg["tes"]["soc_target"])
    dt = float(phase3_cfg["simulation"]["dt_hours"])
    max_du = float(phase3_cfg["controller"]["max_signed_du"])
    signed_u = 0.0
    enabled = bool(tes_cfg.get("enabled", True)) and capacity_kwh > 0 and qmax > 0
    median_price = float(price_base.median())
    terminal_steps = int(round(72 / dt))
    if base_facility_kw is not None:
        base_peak_kw = float(base_facility_kw.max())
        peak_discharge_threshold_kw = float(base_facility_kw.quantile(0.995))
    else:
        base_peak_kw = np.nan
        peak_discharge_threshold_kw = np.nan
    rows: list[dict[str, Any]] = []

    for step, ts in enumerate(timestamps):
        it_kw = float(it_load_kw.loc[ts])
        outdoor_c = float(outdoor_temp_c.loc[ts])
        pue = max(1.01, base_pue + temp_coeff * (outdoor_c - ref_temp))
        if base_facility_kw is not None:
            base_facility = max(0.0, float(base_facility_kw.loc[ts]))
        else:
            base_facility = it_kw * pue
        cooling_kw = float(chiller_cooling_kw.loc[ts]) if chiller_cooling_kw is not None else np.nan
        wetbulb_c = float(outdoor_wetbulb_c.loc[ts]) if outdoor_wetbulb_c is not None else np.nan
        zone_c = float(zone_temp_c.loc[ts]) if zone_temp_c is not None else np.nan
        pv = max(0.0, float(pv_kw.loc[ts]))
        cp = int(cp_flag.loc[ts])
        hour = ts.hour + ts.minute / 60.0
        target_u = 0.0
        if enabled:
            if cp and cp_uplift > 0 and soc > soc_min + 0.005:
                target_u = -1.0
            elif (
                np.isfinite(peak_discharge_threshold_kw)
                and base_facility >= peak_discharge_threshold_kw
                and soc > soc_min + 0.02
            ):
                target_u = -0.75
            elif 9.5 <= hour < 15.75 and soc < soc_max - 0.01:
                pv_pressure = min(1.0, max(0.25, pv / max(base_facility, 1.0)))
                target_u = 0.50 + 0.35 * pv_pressure
            elif hour < 7.0 and float(price_base.loc[ts]) <= median_price and soc < max(soc_target + 0.05, 0.55):
                target_u = 0.45
            elif hour >= 20.0:
                if soc < soc_target - 0.005:
                    target_u = 0.65
                elif soc > soc_target + 0.02:
                    target_u = -0.35
            elif (not cp) and step >= len(timestamps) - terminal_steps:
                if soc < soc_target - 0.005:
                    target_u = 0.65
                elif soc > soc_target + 0.02:
                    target_u = -0.35

            lower = signed_u - max_du
            upper = signed_u + max_du
            signed_u = float(np.clip(target_u, lower, upper))
            q_ch = max(0.0, signed_u) * qmax
            q_dis = max(0.0, -signed_u) * qmax
            charge_soc_limit = soc_max
            if hour >= 20.0 or step >= len(timestamps) - terminal_steps:
                charge_soc_limit = min(soc_max, soc_target + 0.02)
            max_q_ch = max(0.0, (charge_soc_limit - soc) * capacity_kwh / max(eta_ch * dt, 1e-9))
            discharge_soc_limit = soc_min
            if hour >= 20.0 or step >= len(timestamps) - terminal_steps:
                discharge_soc_limit = max(soc_min, soc_target)
            max_q_dis = max(0.0, (soc - discharge_soc_limit) * eta_dis * capacity_kwh / dt)
            q_ch = min(q_ch, max_q_ch)
            q_dis = min(q_dis, max_q_dis)
            if np.isfinite(base_peak_kw) and q_ch > 0:
                current_grid_without_charge = max(0.0, base_facility - q_dis / cop_discharge - pv)
                terminal_recovery = step >= len(timestamps) - terminal_steps
                charge_peak_guard_kw = base_peak_kw if terminal_recovery else 0.98 * base_peak_kw
                max_q_ch_by_peak_guard = max(0.0, (charge_peak_guard_kw - current_grid_without_charge) * cop_charge)
                q_ch = min(q_ch, max_q_ch_by_peak_guard)
            soc_next = (1.0 - loss_per_h * dt) * soc + eta_ch * q_ch * dt / capacity_kwh - q_dis * dt / (
                eta_dis * capacity_kwh
            )
            soc_next = float(np.clip(soc_next, soc_min, soc_max))
        else:
            q_ch = 0.0
            q_dis = 0.0
            soc_next = soc
            signed_u = 0.0

        facility_kw = max(0.0, base_facility + q_ch / cop_charge - q_dis / cop_discharge)
        grid_kw = max(0.0, facility_kw - pv)
        spill_kw = max(0.0, pv - facility_kw)
        pv_used_kw = max(0.0, pv - spill_kw)
        grid_balance_error = grid_kw - spill_kw - facility_kw + pv
        rows.append(
            {
                "timestamp": ts.isoformat(sep=" "),
                "step": step,
                "it_load_kw": it_kw,
                "outdoor_temp_c": outdoor_c,
                "outdoor_wetbulb_c": wetbulb_c,
                "zone_temp_c": zone_c,
                "base_facility_kw": base_facility,
                "baseline_chiller_cooling_kw": cooling_kw,
                "facility_power_kw": facility_kw,
                "pv_kw": pv,
                "pv_used_kw": pv_used_kw,
                "pv_spill_kw": spill_kw,
                "grid_import_kw": grid_kw,
                "price_base_currency_per_mwh": float(price_base.loc[ts]),
                "price_currency_per_mwh": float(price.loc[ts]),
                "critical_peak_flag": cp,
                "q_tes_ch_kw_th": q_ch,
                "q_tes_dis_kw_th": q_dis,
                "Q_tes_net_kw_th": q_ch - q_dis,
                "signed_tes_u": signed_u,
                "soc": soc,
                "soc_next": soc_next,
                "grid_balance_error_kw": grid_balance_error,
            }
        )
        soc = soc_next
    return rows


def _load_series(path: str | Path, value_columns: list[str]) -> pd.Series:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"{path} must contain timestamp")
    value_col = next((col for col in value_columns if col in frame.columns), None)
    if value_col is None:
        raise ValueError(f"{path} must contain one of {value_columns}")
    timestamps = pd.to_datetime(frame["timestamp"])
    values = pd.to_numeric(frame[value_col], errors="raise").astype(float)
    series = pd.Series(values.to_numpy(), index=timestamps).sort_index()
    if series.empty:
        raise ValueError(f"{path} is empty")
    if series.index.has_duplicates:
        series = series.groupby(level=0).mean()
    return series


def _load_load_profile(path: str | Path, timestamps: pd.DatetimeIndex) -> dict[str, pd.Series]:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"{path} must contain timestamp")
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.set_index("timestamp").sort_index()
    out: dict[str, pd.Series] = {}
    if "it_load_kw" in frame.columns:
        out["it_load_kw"] = _align_series(frame["it_load_kw"], timestamps)
    elif "load_kw" in frame.columns:
        out["it_load_kw"] = _align_series(frame["load_kw"], timestamps)
    else:
        raise ValueError(f"{path} must contain it_load_kw or load_kw")
    for optional in ("base_facility_kw", "chiller_cooling_kw", "chiller_electricity_kw"):
        if optional in frame.columns:
            out[optional] = _align_series(frame[optional], timestamps)
    return out


def _load_weather(path: str | Path, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns or "outdoor_temp_c" not in frame.columns:
        raise ValueError(f"{path} must contain timestamp and outdoor_temp_c")
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.set_index("timestamp").sort_index()
    columns = {"outdoor_temp_c": _align_series(frame["outdoor_temp_c"], timestamps)}
    for optional in ("outdoor_wetbulb_c", "zone_temp_c"):
        if optional in frame.columns:
            columns[optional] = _align_series(frame[optional], timestamps)
    return pd.DataFrame(columns)


def _align_series(series: pd.Series, timestamps: pd.DatetimeIndex) -> pd.Series:
    series = pd.to_numeric(series, errors="raise").astype(float).sort_index()
    aligned = series.reindex(series.index.union(timestamps)).sort_index().ffill().bfill().reindex(timestamps)
    if aligned.isna().any():
        raise ValueError("aligned series contains NaN")
    aligned.index = timestamps
    return aligned


def _find_missing_location_data(locations_cfg: dict[str, Any], location_filter: str | None) -> list[tuple[str, str, str]]:
    allowed = None
    if location_filter:
        allowed = {item.strip() for item in location_filter.split(",") if item.strip()}
    missing: list[tuple[str, str, str]] = []
    for location in locations_cfg.get("locations", []):
        location_id = str(location.get("id"))
        if allowed is not None and location_id not in allowed:
            continue
        for key in ("weather_profile", "pv_profile_20mwp", "load_profile", "price_profile"):
            if key not in location:
                missing.append((location_id, key, "<not configured>"))
                continue
            path = Path(location[key])
            if not path.exists():
                missing.append((location_id, key, str(path)))
    return missing


def _missing_report(missing: list[tuple[str, str, str]]) -> str:
    lines = [
        "# Phase 3 Missing Data Report",
        "",
        "The runner does not silently skip missing location data.",
        "",
        "| location_id | field | path |",
        "|---|---|---|",
    ]
    for location_id, key, path in missing:
        lines.append(f"| {location_id} | {key} | `{path}` |")
    return "\n".join(lines) + "\n"


def _write_phase3_docs(summary: pd.DataFrame, recommendations: pd.DataFrame, output_root: Path) -> None:
    shared_names = {"pilot_nanjing", "full_matrix", "full_year_matrix"}
    docs_dir = output_root.parent / "docs" if output_root.name in shared_names else output_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "phase3_methods.md").write_text(_methods_doc(), encoding="utf-8")
    (docs_dir / "phase3_results_summary.md").write_text(_results_doc(summary), encoding="utf-8")
    (docs_dir / "phase3_capacity_recommendation.md").write_text(
        _recommendation_doc(recommendations),
        encoding="utf-8",
    )


def _methods_doc() -> str:
    return """# Phase 3 Methods

This phase evaluates a technical recommended capacity range, not an economic optimum.

- PV capacity scan: 0, 10, 20, 40, and 60 MWp.
- TES capacity scan: 0, 9, 18, 36, and 72 MWh_th.
- Critical peak uplift: explicit 16:00 <= hour < 20:00 window with delta = 0.2 in the main matrix.
- Data boundary: real EPW weather drives annual EnergyPlus no-control baseline profiles; PV uses PVGIS 20 MWp profiles; price uses the Jiangsu 2025 TOU curve.
- Controller boundary: Kim-lite relaxed MPC-style dispatch over EnergyPlus-derived annual load/weather profiles with signed TES ramping and fixed TES power.
- Recommendation rule: choose the smallest PV-TES pair meeting 90% of the maximum CP suppression and peak-reduction effects while retaining PV self-consumption and SOC acceptability.
- Limitation: technical recommendation only, no CAPEX, no LCOE, no NPV, and no economic optimum.
"""


def _results_doc(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "# Phase 3 Results Summary\n\nNo completed scenarios were available.\n"
    active = summary[summary["critical_peak_uplift"] > 0]
    lines = ["# Phase 3 Results Summary", ""]
    for location_id, group in active.groupby("location_id"):
        max_cp = group["critical_peak_suppression_ratio"].max(skipna=True)
        max_peak = group["peak_reduction_ratio"].max(skipna=True)
        min_self = group["pv_self_consumption_ratio"].min(skipna=True)
        max_coverage = group["pv_facility_load_coverage_ratio"].max(skipna=True)
        negative_cases = int((group["critical_peak_suppression_ratio"] < 0).sum())
        diminishing_cases = int(group.get("diminishing_return_after_this_capacity", pd.Series(False)).astype(bool).sum())
        pv_self_by_capacity = group.groupby("pv_capacity_mwp")["pv_self_consumption_ratio"].mean(numeric_only=True)
        pv_self_declines = bool(len(pv_self_by_capacity.dropna()) >= 2 and pv_self_by_capacity.dropna().iloc[-1] < pv_self_by_capacity.dropna().iloc[0])
        no_tes_cp = group[group["tes_capacity_mwh_th"] == 0]["critical_peak_suppression_ratio"].max(skipna=True)
        with_tes_cp = group[group["tes_capacity_mwh_th"] > 0]["critical_peak_suppression_ratio"].max(skipna=True)
        tes_improves_cp = bool(pd.notna(with_tes_cp) and pd.notna(no_tes_cp) and with_tes_cp > no_tes_cp)
        tes0_self = group[group["tes_capacity_mwh_th"] == 0]["pv_self_consumption_ratio"].mean(skipna=True)
        tespos_self = group[group["tes_capacity_mwh_th"] > 0]["pv_self_consumption_ratio"].mean(skipna=True)
        tes_self_delta = float(tespos_self - tes0_self) if pd.notna(tes0_self) and pd.notna(tespos_self) else float("nan")
        lines.extend(
            [
                f"## {location_id}",
                "",
                f"- Maximum CP suppression ratio: {max_cp:.3f}.",
                f"- Maximum peak reduction ratio: {max_peak:.3f}.",
                f"- Minimum PV self-consumption ratio in the scan: {min_self:.3f}.",
                f"- Maximum PV facility-load coverage ratio: {max_coverage:.3f}.",
                f"- TES capacity marginal-return markers: {diminishing_cases} cases flagged after a TES capacity step.",
                f"- PV self-consumption declines with larger PV capacity: {pv_self_declines}.",
                f"- TES improves CP suppression relative to no-TES cases: {tes_improves_cp}.",
                f"- Mean TES effect on PV self-consumption ratio: {tes_self_delta:.4f}.",
                f"- Negative CP suppression cases: {negative_cases}; these are reported rather than hidden.",
                "- Negative or weak cases indicate control-boundary or recharge-penalty behavior, not investment findings.",
                "",
            ]
        )
    return "\n".join(lines)


def _recommendation_doc(recommendations: pd.DataFrame) -> str:
    lines = [
        "# Phase 3 Capacity Recommendation",
        "",
        "The values below are a technical recommended capacity range basis, not an economic optimum.",
        "",
    ]
    if recommendations.empty:
        lines.append("No recommendation rows were generated.")
        return "\n".join(lines) + "\n"
    for _, row in recommendations.iterrows():
        pv = float(row["recommended_pv_mwp"])
        tes = float(row["recommended_tes_mwh_th"])
        lines.extend(
            [
                f"## {row['location_id']}",
                "",
                f"- Recommended PV: around {pv:g} MWp.",
                f"- Recommended TES: around {tes:g} MWh_th.",
                f"- Basis: CP suppression {row['cp_suppression_ratio']:.3f}, peak reduction {row['peak_reduction_ratio']:.3f}, PV self-consumption {row['pv_self_consumption_ratio']:.3f}.",
                "- Larger PV/TES capacities are not automatically recommended because marginal technical gains diminish and no CAPEX model is included.",
                "- This is distinct from economic optimum sizing, which would require investment and lifecycle cost data.",
                "",
            ]
        )
    return "\n".join(lines)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/phase3_pv_tes_sizing.yaml")
    parser.add_argument("--locations", default="mpc_v2/config/phase3_locations.yaml")
    parser.add_argument("--output-root", default="results/phase3_pv_tes_sizing")
    parser.add_argument("--location-filter", default=None)
    parser.add_argument("--include-stress-uplift", action="store_true")
    parser.add_argument("--parallel", type=int, default=1)
    args = parser.parse_args()
    print(
        run_phase3_pv_tes_matrix(
            config_path=args.config,
            locations_path=args.locations,
            output_root=args.output_root,
            location_filter=args.location_filter,
            include_stress_uplift=args.include_stress_uplift,
            parallel=args.parallel,
        )
    )


if __name__ == "__main__":
    main()
