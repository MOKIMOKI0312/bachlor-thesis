"""Run Phase 3 PV-TES sizing scenarios with online MPC+EnergyPlus coupling."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.phase3_sizing.energyplus_online import write_scenario_model
from mpc_v2.phase3_sizing.metrics import (
    add_marginal_metrics,
    add_relative_metrics,
    compute_case_metrics,
    critical_peak_flags,
)
from mpc_v2.phase3_sizing.pv_scaling import scale_pv_profile
from mpc_v2.phase3_sizing.recommendation import add_recommendation_columns
from mpc_v2.phase3_sizing.scenario_builder import build_scenario_matrix, scenario_manifest_frame


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = REPO_ROOT / "Nanjing-DataCenter-TES-EnergyPlus" / "model" / "Nanjing_DataCenter_TES.epJSON"
DEFAULT_RUNNER_MODULE = "Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc"


def run_phase3_online_mpc_ep_matrix(
    config_path: str | Path,
    locations_path: str | Path,
    output_root: str | Path,
    location_filter: str | None = None,
    pv_capacity_filter: str | None = None,
    tes_capacity_filter: str | None = None,
    critical_peak_uplift_filter: str | None = None,
    record_start_step: str | int | None = None,
    include_stress_uplift: bool = False,
    max_steps_override: int | None = None,
    scenario_limit: int | None = None,
    skip_existing: bool = False,
) -> Path:
    """Run online EnergyPlus scenarios and write Phase 3 artifacts."""

    phase3_cfg = load_yaml(config_path)
    locations_cfg = load_yaml(locations_path)
    output_root = Path(output_root)
    summary_dir = output_root / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = output_root / "inputs"
    models_dir = output_root / "models"
    raw_dir = output_root / "raw"
    for path in (inputs_dir, models_dir, raw_dir):
        path.mkdir(parents=True, exist_ok=True)

    missing = _find_missing_online_data(locations_cfg, location_filter)
    if missing:
        report = summary_dir / "missing_data_report.md"
        report.write_text(_missing_report(missing), encoding="utf-8")
        raise FileNotFoundError(f"missing online Phase 3 input data; see {report}")

    scenarios = build_scenario_matrix(
        phase3_cfg,
        locations_cfg,
        output_root=output_root,
        location_filter=location_filter,
        include_stress_uplift=include_stress_uplift,
    )
    scenarios = _filter_scenarios(
        scenarios,
        pv_capacity_filter=pv_capacity_filter,
        tes_capacity_filter=tes_capacity_filter,
        critical_peak_uplift_filter=critical_peak_uplift_filter,
    )
    if scenario_limit is not None:
        scenarios = scenarios[: int(scenario_limit)]
    manifest = scenario_manifest_frame(scenarios)
    manifest["engine"] = "mpc_energyplus_online"
    manifest.to_csv(summary_dir / "scenario_manifest.csv", index=False)

    location_map = {str(item["id"]): item for item in locations_cfg["locations"]}
    rows: list[dict[str, Any]] = []
    status_by_id: dict[str, str] = {}
    errors: dict[str, str] = {}
    for scenario in scenarios:
        run_dir = Path(scenario.run_dir)
        case_dir = run_dir / "mpc"
        if skip_existing and (run_dir / "episode_summary.json").exists():
            row = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
            rows.append(row)
            status_by_id[scenario.scenario_id] = "completed"
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            location_cfg = location_map[scenario.location_id]
            effective = _prepare_effective_inputs(
                phase3_cfg=phase3_cfg,
                location_cfg=location_cfg,
                scenario=scenario,
                inputs_dir=inputs_dir,
                models_dir=models_dir,
            )
            _run_energyplus_case(
                phase3_cfg=phase3_cfg,
                location_cfg=location_cfg,
                scenario=scenario,
                effective=effective,
                run_dir=run_dir,
                raw_dir=raw_dir / scenario.scenario_id,
                record_start_step=record_start_step,
                max_steps_override=max_steps_override,
            )
            timeseries = _online_timeseries_from_monitor(
                case_dir / "monitor.csv",
                windows=effective["critical_peak_windows"],
            )
            timeseries.to_csv(run_dir / "timeseries.csv", index=False)
            if (case_dir / "solver_log.csv").exists():
                pd.read_csv(case_dir / "solver_log.csv").to_csv(run_dir / "solver_log.csv", index=False)
            else:
                pd.DataFrame().to_csv(run_dir / "solver_log.csv", index=False)
            metrics = compute_case_metrics(
                timeseries=timeseries,
                dt_hours=float(phase3_cfg["simulation"]["dt_hours"]),
                tes_capacity_mwh_th=scenario.tes_capacity_mwh_th,
                soc_min=float(phase3_cfg["tes"]["soc_min"]),
                soc_max=float(phase3_cfg["tes"]["soc_max"]),
                max_signed_du=float(phase3_cfg["controller"]["max_signed_du"]),
            )
            summary = _read_json(case_dir / "summary.json")
            row = {
                "scenario_id": scenario.scenario_id,
                "location_id": scenario.location_id,
                "pv_capacity_mwp": scenario.pv_capacity_mwp,
                "tes_capacity_mwh_th": scenario.tes_capacity_mwh_th,
                "critical_peak_uplift": scenario.critical_peak_uplift,
                "critical_peak_window_set": scenario.critical_peak_window_set,
                "controller": scenario.controller,
                "engine": "mpc_energyplus_online",
                "run_dir": str(run_dir),
                "status": "completed",
                "energyplus_exit_code": int(summary.get("exit_code", 0)),
                "temp_violation_ratio_gt27c": float(summary.get("temp_violation_ratio_gt27c", np.nan)),
                "temp_violation_hours_gt27c": float(summary.get("temp_violation_hours_gt27c", np.nan)),
                "zone_temp_max_c": float(summary.get("zone_temp_max_c", np.nan)),
                **metrics,
            }
            (run_dir / "config_effective.yaml").write_text(
                yaml.safe_dump(effective, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            (run_dir / "episode_summary.json").write_text(json.dumps(_json_ready(row), indent=2), encoding="utf-8")
            rows.append(row)
            status_by_id[scenario.scenario_id] = "completed"
        except Exception as exc:  # noqa: BLE001 - scenario runner must preserve failed case evidence
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

    if errors:
        raise RuntimeError(f"{len(errors)} online MPC+EP scenarios failed; see {summary_dir / 'failed_cases.json'}")
    return output_root


def _prepare_effective_inputs(
    phase3_cfg: dict[str, Any],
    location_cfg: dict[str, Any],
    scenario,
    inputs_dir: Path,
    models_dir: Path,
) -> dict[str, Any]:
    window_name = str(phase3_cfg["critical_peak"].get("default_window_set", "evening"))
    windows = phase3_cfg["critical_peak"]["window_sets"][window_name]
    pv_base = _load_series(location_cfg["pv_profile_20mwp"], ["power_kw", "pv_kw"])
    pv_scaled = scale_pv_profile(
        pv_base,
        base_capacity_mwp=float(phase3_cfg["pv"]["reference_mwp"]),
        target_capacity_mwp=float(scenario.pv_capacity_mwp),
    )
    pv_path = inputs_dir / "pv" / f"{scenario.scenario_id}_pv.csv"
    _write_series_csv(pv_scaled, pv_path, "power_kw")
    price_base = _load_series(location_cfg["price_profile"], ["price_usd_per_mwh", "price_currency_per_mwh", "price"])
    cp_flags = critical_peak_flags(price_base.index, windows).reindex(price_base.index).astype(int)
    price_cp = price_base * (1.0 + float(scenario.critical_peak_uplift) * cp_flags.astype(float))
    price_path = inputs_dir / "price" / f"{scenario.scenario_id}_price.csv"
    _write_series_csv(price_cp, price_path, "price_usd_per_mwh")
    q_abs = float(phase3_cfg["tes"]["q_tes_abs_max_kw_th"]) if float(scenario.tes_capacity_mwh_th) > 0 else 0.0
    model_path = models_dir / f"{scenario.scenario_id}.epJSON"
    write_scenario_model(DEFAULT_MODEL, model_path, scenario.tes_capacity_mwh_th, q_abs)
    return {
        "scenario_id": scenario.scenario_id,
        "location_id": scenario.location_id,
        "engine": "mpc_energyplus_online",
        "pv_capacity_mwp": float(scenario.pv_capacity_mwp),
        "tes_capacity_mwh_th": float(scenario.tes_capacity_mwh_th),
        "critical_peak_uplift": float(scenario.critical_peak_uplift),
        "critical_peak_windows": windows,
        "pv_csv": str(pv_path),
        "price_csv": str(price_path),
        "model": str(model_path),
        "weather": location_cfg["epw_path"],
        "baseline_timeseries": location_cfg["energyplus_baseline_timeseries"],
        "tes_q_abs_max_kw_th": q_abs,
    }


def _run_energyplus_case(
    phase3_cfg: dict[str, Any],
    location_cfg: dict[str, Any],
    scenario,
    effective: dict[str, Any],
    run_dir: Path,
    raw_dir: Path,
    record_start_step: str | int | None,
    max_steps_override: int | None,
) -> None:
    dt_hours = float(phase3_cfg["simulation"]["dt_hours"])
    steps = int(round(int(phase3_cfg["simulation"]["episode_days"]) * 24 / dt_hours))
    if max_steps_override is not None:
        steps = int(max_steps_override)
    record_start = record_start_step
    if record_start is None:
        record_start = phase3_cfg["simulation"].get("record_start_step", 0)
    cmd = [
        sys.executable,
        "-m",
        DEFAULT_RUNNER_MODULE,
        "--controller",
        "mpc",
        "--max-steps",
        str(steps),
        "--record-start-step",
        str(record_start),
        "--weather",
        str(effective["weather"]),
        "--model",
        str(effective["model"]),
        "--baseline-timeseries",
        str(effective["baseline_timeseries"]),
        "--price-csv",
        str(effective["price_csv"]),
        "--pv-csv",
        str(effective["pv_csv"]),
        "--selected-output-root",
        str(run_dir),
        "--raw-output-dir",
        str(raw_dir),
        "--horizon-steps",
        str(int(phase3_cfg["simulation"].get("horizon_steps", 48))),
        "--mode-integrality",
        str(phase3_cfg["controller"].get("mode_integrality", "relaxed")),
        "--max-signed-du",
        str(float(phase3_cfg["controller"].get("max_signed_du", 1.0))),
        "--tes-capacity-mwh-th",
        str(float(scenario.tes_capacity_mwh_th)),
        "--tes-q-abs-max-kw-th",
        str(float(effective["tes_q_abs_max_kw_th"])),
        "--scenario-id",
        scenario.scenario_id,
        "--case-metadata-json",
        json.dumps(
            {
                "scenario_id": scenario.scenario_id,
                "location_id": scenario.location_id,
                "pv_capacity_mwp": float(scenario.pv_capacity_mwp),
                "tes_capacity_mwh_th": float(scenario.tes_capacity_mwh_th),
                "critical_peak_uplift": float(scenario.critical_peak_uplift),
                "critical_peak_windows": effective["critical_peak_windows"],
                "reserve_tes_for_critical_peak": bool(
                    phase3_cfg["controller"].get("reserve_tes_for_critical_peak", False)
                ),
                "engine": "mpc_energyplus_online",
                "location_data_boundary": location_cfg.get("data_boundary", ""),
            }
        ),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    (run_dir / "command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    (run_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"EnergyPlus online runner failed with exit code {result.returncode}: {result.stderr[-2000:]}")


def _online_timeseries_from_monitor(path: Path, windows: list[list[float]]) -> pd.DataFrame:
    monitor = pd.read_csv(path)
    timestamps = pd.to_datetime(monitor["timestamp"])
    cp_flag = critical_peak_flags(timestamps, windows).to_numpy(dtype=int)
    facility = pd.to_numeric(monitor["facility_electricity_kw"], errors="raise").astype(float)
    pv = pd.to_numeric(monitor["pv_kw"], errors="raise").astype(float).clip(lower=0.0)
    grid = pd.to_numeric(monitor["grid_import_kw"], errors="raise").astype(float).clip(lower=0.0)
    spill = (pv - facility).clip(lower=0.0)
    tes_set = pd.to_numeric(monitor.get("tes_set_written", 0.0), errors="coerce").fillna(0.0).astype(float)
    q_ch = pd.to_numeric(monitor["tes_source_side_kw"], errors="raise").astype(float).abs()
    q_dis = pd.to_numeric(monitor["tes_use_side_kw"], errors="raise").astype(float).abs()
    q_net = q_ch - q_dis
    out = pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "step": pd.to_numeric(monitor["step"], errors="raise").astype(int),
            "facility_power_kw": facility,
            "grid_import_kw": grid,
            "pv_kw": pv,
            "pv_spill_kw": spill,
            "pv_used_kw": (pv - spill).clip(lower=0.0),
            "price_currency_per_mwh": pd.to_numeric(monitor["price_per_kwh"], errors="raise").astype(float) * 1000.0,
            "critical_peak_flag": cp_flag,
            "q_tes_ch_kw_th": q_ch,
            "q_tes_dis_kw_th": q_dis,
            "Q_tes_net_kw_th": q_net,
            "signed_tes_u": -tes_set,
            "soc": pd.to_numeric(monitor["soc"], errors="raise").astype(float),
            "zone_temp_c": pd.to_numeric(monitor["zone_temp_c"], errors="raise").astype(float),
            "outdoor_temp_c": pd.to_numeric(monitor["outdoor_drybulb_c"], errors="raise").astype(float),
            "grid_balance_error_kw": grid - spill - facility + pv,
        }
    )
    return out


def _load_series(path: str | Path, value_columns: list[str]) -> pd.Series:
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"{path} must contain timestamp")
    value_col = next((col for col in value_columns if col in frame.columns), None)
    if value_col is None:
        raise ValueError(f"{path} must contain one of {value_columns}")
    values = pd.to_numeric(frame[value_col], errors="raise").astype(float)
    return pd.Series(values.to_numpy(), index=pd.to_datetime(frame["timestamp"])).sort_index()


def _write_series_csv(series: pd.Series, path: Path, column_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"timestamp": series.index.astype(str), column_name: series.to_numpy(dtype=float)}).to_csv(path, index=False)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_missing_online_data(locations_cfg: dict[str, Any], location_filter: str | None) -> list[tuple[str, str, str]]:
    allowed = None
    if location_filter:
        allowed = {item.strip() for item in location_filter.split(",") if item.strip()}
    missing: list[tuple[str, str, str]] = []
    for location in locations_cfg.get("locations", []):
        location_id = str(location.get("id"))
        if allowed is not None and location_id not in allowed:
            continue
        for key in ("epw_path", "energyplus_baseline_timeseries", "pv_profile_20mwp", "price_profile"):
            if key not in location:
                missing.append((location_id, key, "<not configured>"))
                continue
            path = Path(location[key])
            if not path.exists():
                missing.append((location_id, key, str(path)))
    return missing


def _filter_scenarios(
    scenarios: list[Any],
    pv_capacity_filter: str | None,
    tes_capacity_filter: str | None,
    critical_peak_uplift_filter: str | None,
) -> list[Any]:
    pv_allowed = _float_filter(pv_capacity_filter)
    tes_allowed = _float_filter(tes_capacity_filter)
    cp_allowed = _float_filter(critical_peak_uplift_filter)

    def keep(scenario: Any) -> bool:
        return (
            _matches_float_filter(scenario.pv_capacity_mwp, pv_allowed)
            and _matches_float_filter(scenario.tes_capacity_mwh_th, tes_allowed)
            and _matches_float_filter(scenario.critical_peak_uplift, cp_allowed)
        )

    return [scenario for scenario in scenarios if keep(scenario)]


def _float_filter(text: str | None) -> tuple[float, ...] | None:
    if text is None or not str(text).strip():
        return None
    return tuple(float(item.strip()) for item in str(text).split(",") if item.strip())


def _matches_float_filter(value: float, allowed: tuple[float, ...] | None) -> bool:
    if allowed is None:
        return True
    return any(abs(float(value) - item) <= 1e-9 for item in allowed)


def _missing_report(missing: list[tuple[str, str, str]]) -> str:
    lines = [
        "# Phase 3 Online MPC+EP Missing Data Report",
        "",
        "| location_id | field | path |",
        "|---|---|---|",
    ]
    for location_id, key, path in missing:
        lines.append(f"| {location_id} | {key} | `{path}` |")
    return "\n".join(lines) + "\n"


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
    parser.add_argument("--config", default="mpc_v2/config/phase3_pv_tes_sizing_online.yaml")
    parser.add_argument("--locations", default="mpc_v2/config/phase3_locations.yaml")
    parser.add_argument("--output-root", default="results/phase3_pv_tes_sizing/full_matrix_online_mpc_ep")
    parser.add_argument("--location-filter", default=None)
    parser.add_argument("--pv-capacity-filter", default=None)
    parser.add_argument("--tes-capacity-filter", default=None)
    parser.add_argument("--critical-peak-uplift-filter", default=None)
    parser.add_argument("--record-start-step", default=None)
    parser.add_argument("--include-stress-uplift", action="store_true")
    parser.add_argument("--max-steps-override", type=int, default=None)
    parser.add_argument("--scenario-limit", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    print(
        run_phase3_online_mpc_ep_matrix(
            config_path=args.config,
            locations_path=args.locations,
            output_root=args.output_root,
            location_filter=args.location_filter,
            pv_capacity_filter=args.pv_capacity_filter,
            tes_capacity_filter=args.tes_capacity_filter,
            critical_peak_uplift_filter=args.critical_peak_uplift_filter,
            record_start_step=args.record_start_step,
            include_stress_uplift=args.include_stress_uplift,
            max_steps_override=args.max_steps_override,
            scenario_limit=args.scenario_limit,
            skip_existing=args.skip_existing,
        )
    )


if __name__ == "__main__":
    main()
