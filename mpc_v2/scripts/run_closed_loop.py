"""Run the rebuilt deterministic chiller+TES closed-loop controller."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yaml

from mpc_v2.core.controller import controller_from_mode
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCState, UnsupportedFeatureError, load_yaml, parse_timestamp
from mpc_v2.core.metrics import compute_episode_metrics
from mpc_v2.core.plant import PlantParams, next_room_temp_c
from mpc_v2.core.tes_model import TESModel, TESParams


def run_closed_loop(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    case_id: str = "tes_mpc_rebuild_smoke",
    steps: int | None = None,
    output_root: str | Path | None = None,
    pv_error_sigma: float = 0.0,
    seed: int | None = None,
    controller_mode: str = "mpc",
    tariff_multiplier: float = 1.0,
    outdoor_offset_c: float = 0.0,
    pv_scale: float | None = None,
    demand_charge_rate: float | None = None,
    demand_charge_basis: str | None = None,
    demand_charge_multiplier: float = 1.0,
    horizon_steps_override: int | None = None,
    w_terminal: float | None = None,
    w_spill: float | None = None,
    w_cycle: float | None = None,
    w_peak_slack: float | None = None,
    soc_target: float | None = None,
    initial_soc: float | None = None,
    peak_cap_kw: float | None = None,
    peak_cap_ratio: float | None = None,
    peak_cap_reference_kw: float | None = None,
    tariff_template: str | None = None,
    tariff_gamma: float | None = None,
    cp_uplift: float | None = None,
    float_share: float | None = None,
    dr_enabled: bool | None = None,
    dr_event_type: str | None = None,
    dr_reduction_frac: float | None = None,
    dr_start_hour: float | None = None,
    dr_duration_hours: float | None = None,
    dr_event_day_index: int | None = None,
    dr_event_start_timestamp: str | None = None,
    dr_baseline_kw: float | None = None,
    dr_compensation_cny_per_kwh: float | None = None,
    truncate_horizon_to_episode: bool | None = None,
) -> Path:
    """Run one closed-loop scenario and write the public output contract."""

    _reject_advanced_options(
        demand_charge_rate=demand_charge_rate,
        demand_charge_basis=demand_charge_basis,
        demand_charge_multiplier=demand_charge_multiplier,
        w_peak_slack=w_peak_slack,
        peak_cap_kw=peak_cap_kw,
        peak_cap_ratio=peak_cap_ratio,
        peak_cap_reference_kw=peak_cap_reference_kw,
        tariff_template=tariff_template,
        tariff_gamma=tariff_gamma,
        cp_uplift=cp_uplift,
        float_share=float_share,
        dr_enabled=dr_enabled,
        dr_event_type=dr_event_type,
        dr_reduction_frac=dr_reduction_frac,
        dr_start_hour=dr_start_hour,
        dr_duration_hours=dr_duration_hours,
        dr_event_day_index=dr_event_day_index,
        dr_event_start_timestamp=dr_event_start_timestamp,
        dr_baseline_kw=dr_baseline_kw,
        dr_compensation_cny_per_kwh=dr_compensation_cny_per_kwh,
    )

    cfg = load_yaml(config_path)
    if horizon_steps_override is not None:
        cfg["time"]["horizon_steps"] = int(horizon_steps_override)
    if w_terminal is not None:
        cfg.setdefault("objective", {})["w_terminal"] = float(w_terminal)
    if w_spill is not None:
        cfg.setdefault("objective", {})["w_spill"] = float(w_spill)
    if w_cycle is not None:
        cfg.setdefault("objective", {})["w_cycle"] = float(w_cycle)
    if soc_target is not None:
        cfg["tes"]["soc_target"] = float(soc_target)
    if initial_soc is not None:
        cfg["tes"]["initial_soc"] = float(initial_soc)
    if pv_scale is not None:
        cfg.setdefault("economics", {})["pv_scale"] = float(pv_scale)
    cfg.setdefault("runtime", {})["truncate_horizon_to_episode"] = bool(truncate_horizon_to_episode)

    dt_hours = float(cfg["time"]["dt_hours"])
    horizon_steps = int(cfg["time"]["horizon_steps"])
    n_steps = int(steps if steps is not None else cfg["time"]["default_closed_loop_steps"])
    synthetic = cfg.get("synthetic", {})
    start_ts = parse_timestamp(synthetic.get("start_timestamp", "2025-07-01 00:00:00"))
    root = Path(output_root or cfg["paths"]["output_root"])
    run_dir = _unique_run_dir(root, case_id)
    run_dir.mkdir(parents=True, exist_ok=False)

    tes = TESParams.from_config(cfg["tes"])
    plant = PlantParams.from_config(cfg)
    tes_model = TESModel(tes, dt_hours)
    forecast_builder = ForecastBuilder.from_config(cfg)
    controller, tes_available = controller_from_mode(controller_mode, cfg)

    soc = float(tes.initial_soc)
    room_temp = float(plant.room_initial_temp_c)
    seed_value = int(seed if seed is not None else synthetic.get("seed", 7))
    pv_scale_value = float(cfg.get("economics", {}).get("pv_scale", 1.0))
    records: list[dict[str, Any]] = []
    solver_rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for step in range(n_steps):
        now = start_ts + timedelta(minutes=15 * step)
        horizon = min(horizon_steps, n_steps - step) if truncate_horizon_to_episode else horizon_steps
        forecast = forecast_builder.build(
            now,
            horizon_steps=horizon,
            pv_error_sigma=pv_error_sigma,
            seed=seed_value + step,
            it_load_kw=float(synthetic.get("it_load_kw", 18000.0)),
            outdoor_base_c=float(synthetic.get("outdoor_base_c", 29.0)),
            outdoor_amplitude_c=float(synthetic.get("outdoor_amplitude_c", 6.0)),
            outdoor_offset_c=outdoor_offset_c,
            tariff_multiplier=tariff_multiplier,
            pv_scale=pv_scale_value,
            wet_bulb_depression_c=float(synthetic.get("wet_bulb_depression_c", 4.0)),
        )
        state = MPCState(soc=soc, room_temp_c=room_temp)
        state.validate()
        solution = controller.solve(state, forecast, tes_available=tes_available)
        action = solution.first_action(tes)
        soc_after = (
            tes_model.next_soc(soc, action.q_ch_tes_kw_th, action.q_dis_tes_kw_th)
            if tes_available
            else soc
        )
        room_after = next_room_temp_c(room_temp, forecast.outdoor_temp_forecast_c[0], plant, dt_hours)
        step_cost = action.plant_power_kw
        step_cost = solution.grid_import_kw[0] * forecast.price_forecast[0] * dt_hours
        record = {
            "timestamp": now.isoformat(sep=" "),
            "step": step,
            "controller_mode": controller_mode,
            "soc": soc,
            "soc_after_update": soc_after,
            "room_temp_c": room_temp,
            "outdoor_temp_c": float(forecast.outdoor_temp_forecast_c[0]),
            "it_load_kw": float(forecast.it_load_forecast_kw[0]),
            "pv_actual_kw": float(forecast.pv_forecast_kw[0]),
            "price_cny_per_kwh": float(forecast.price_forecast[0]),
            "q_ch_tes_kw_th": action.q_ch_tes_kw_th,
            "q_dis_tes_kw_th": action.q_dis_tes_kw_th,
            "q_chiller_kw_th": action.q_chiller_kw_th,
            "q_load_kw_th": action.q_load_kw_th,
            "plant_power_kw": action.plant_power_kw,
            "grid_import_kw": float(solution.grid_import_kw[0]),
            "pv_spill_kw": float(solution.pv_spill_kw[0]),
            "step_cost": float(step_cost),
            "u_ch": action.u_ch,
            "u_dis": action.u_dis,
            "u_signed": action.u_signed,
            "mode_index": action.mode_index,
            "fallback": int(solution.fallback),
            "solver_status": solution.status,
        }
        records.append(record)
        solver_rows.append(
            {
                "timestamp": record["timestamp"],
                "step": step,
                "status": solution.status,
                "objective_value": solution.objective_value,
                "fallback": int(solution.fallback),
                "horizon_steps": horizon,
            }
        )
        soc = soc_after
        room_temp = room_after

    monitor = pd.DataFrame.from_records(records)
    solver = pd.DataFrame.from_records(solver_rows)
    summary = compute_episode_metrics(monitor, cfg)
    summary["case_id"] = case_id
    summary["config_path"] = str(config_path)

    monitor.to_csv(run_dir / "monitor.csv", index=False)
    monitor.to_csv(run_dir / "timeseries.csv", index=False)
    solver.to_csv(run_dir / "solver_log.csv", index=False)
    pd.DataFrame.from_records(events, columns=["event_id", "event_type", "start_timestamp", "end_timestamp"]).to_csv(
        run_dir / "events.csv", index=False
    )
    pd.DataFrame([summary]).to_csv(run_dir / "summary.csv", index=False)
    (run_dir / "episode_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_effective_config(run_dir, cfg, config_path, case_id, controller_mode, n_steps)
    return run_dir


def _reject_advanced_options(**values: Any) -> None:
    unsupported = []
    for name, value in values.items():
        if value in {None, False}:
            continue
        if name == "demand_charge_multiplier" and float(value) == 1.0:
            continue
        unsupported.append(name)
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise UnsupportedFeatureError(
            f"rebuilt MPC v1 intentionally does not implement advanced matrix/DR/peak features yet: {names}"
        )


def _unique_run_dir(root: Path, case_id: str) -> Path:
    run_dir = root / case_id
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{case_id}_{suffix:02d}"
        suffix += 1
    return run_dir


def _write_effective_config(
    run_dir: Path,
    cfg: dict[str, Any],
    config_path: str | Path,
    case_id: str,
    controller_mode: str,
    steps: int,
) -> None:
    effective = dict(cfg)
    effective["run"] = {
        "config_path": str(config_path),
        "case_id": case_id,
        "controller_mode": controller_mode,
        "closed_loop_steps": steps,
        "rebuild_version": "mpc_v1_minimal",
    }
    with (run_dir / "config_effective.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(effective, fh, sort_keys=False, allow_unicode=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--case-id", default="tes_mpc_rebuild_smoke")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--output-root")
    parser.add_argument("--controller-mode", default="mpc", choices=["no_tes", "rbc", "mpc", "mpc_no_tes"])
    parser.add_argument("--horizon-steps", type=int)
    parser.add_argument("--pv-error-sigma", type=float, default=0.0)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--tariff-multiplier", type=float, default=1.0)
    parser.add_argument("--outdoor-offset-c", type=float, default=0.0)
    parser.add_argument("--pv-scale", type=float)
    parser.add_argument("--initial-soc", type=float)
    parser.add_argument("--soc-target", type=float)
    parser.add_argument("--w-terminal", type=float)
    parser.add_argument("--w-spill", type=float)
    parser.add_argument("--w-cycle", type=float)
    parser.add_argument("--truncate-horizon-to-episode", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_dir = run_closed_loop(
        config_path=args.config,
        case_id=args.case_id,
        steps=args.steps,
        output_root=args.output_root,
        controller_mode=args.controller_mode,
        horizon_steps_override=args.horizon_steps,
        pv_error_sigma=args.pv_error_sigma,
        seed=args.seed,
        tariff_multiplier=args.tariff_multiplier,
        outdoor_offset_c=args.outdoor_offset_c,
        pv_scale=args.pv_scale,
        initial_soc=args.initial_soc,
        soc_target=args.soc_target,
        w_terminal=args.w_terminal,
        w_spill=args.w_spill,
        w_cycle=args.w_cycle,
        truncate_horizon_to_episode=args.truncate_horizon_to_episode,
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
