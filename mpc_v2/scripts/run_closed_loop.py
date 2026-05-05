"""Run a deterministic synthetic/replay closed loop for MPC v2."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.facility_model import FacilityModel, FacilityParams
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCState, load_yaml, parse_timestamp
from mpc_v2.core.metrics import compute_episode_metrics
from mpc_v2.core.room_model import RoomModel, RoomParams
from mpc_v2.core.tes_model import TESModel, TESParams


def run_closed_loop(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    case_id: str = "tes_mpc_smoke",
    steps: int | None = None,
    output_root: str | Path | None = None,
    pv_error_sigma: float = 0.0,
    seed: int | None = None,
    controller_mode: str = "mpc",
    tariff_multiplier: float = 1.0,
    outdoor_offset_c: float = 0.0,
) -> Path:
    """Run closed-loop validation and write monitor/solver/summary outputs."""

    cfg = load_yaml(config_path)
    dt_hours = float(cfg["time"]["dt_hours"])
    horizon_steps = int(cfg["time"]["horizon_steps"])
    n_steps = int(steps if steps is not None else cfg["time"]["default_closed_loop_steps"])
    root = Path(output_root or cfg["paths"]["output_root"])
    run_dir = root / case_id
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{case_id}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)

    tes_params = TESParams.from_config(cfg["tes"])
    room_params = RoomParams.from_config(cfg["room"])
    facility_params = FacilityParams.from_config(cfg["facility"])
    tes_model = TESModel(tes_params, dt_hours=dt_hours)
    room_model = RoomModel(room_params, dt_hours=dt_hours)
    facility_model = FacilityModel(facility_params)
    forecast_builder = ForecastBuilder(
        cfg["paths"]["pv_csv"],
        cfg["paths"]["price_csv"],
        facility_model=facility_model,
        room_model=room_model,
        dt_hours=dt_hours,
    )
    controller = EconomicTESMPCController.from_config(cfg)

    synthetic = cfg.get("synthetic", {})
    start_ts = parse_timestamp(synthetic.get("start_timestamp", "2025-07-01 00:00:00"))
    it_load_kw = float(synthetic.get("it_load_kw", 18000.0))
    outdoor_base_c = float(synthetic.get("outdoor_base_c", 29.0))
    outdoor_amplitude_c = float(synthetic.get("outdoor_amplitude_c", 6.0))
    seed_value = int(seed if seed is not None else synthetic.get("seed", 7))

    soc = tes_params.initial_soc
    room_temp_c = room_params.initial_room_temp_c
    prev_q_ch = 0.0
    prev_q_dis = 0.0
    monitor_rows: list[dict[str, Any]] = []
    solver_rows: list[dict[str, Any]] = []

    for step in range(n_steps):
        now = start_ts + timedelta(minutes=15 * step)
        forecast = forecast_builder.build(
            now_ts=now,
            horizon_steps=horizon_steps,
            pv_error_sigma=pv_error_sigma,
            seed=seed_value + step,
            it_load_kw=it_load_kw,
            outdoor_base_c=outdoor_base_c,
            outdoor_amplitude_c=outdoor_amplitude_c,
            outdoor_offset_c=outdoor_offset_c,
            tariff_multiplier=tariff_multiplier,
        )
        actual = forecast_builder.actual_at(
            now_ts=now,
            it_load_kw=it_load_kw,
            outdoor_base_c=outdoor_base_c,
            outdoor_amplitude_c=outdoor_amplitude_c,
            outdoor_offset_c=outdoor_offset_c,
            tariff_multiplier=tariff_multiplier,
        )
        fallback_used = False
        predicted_room_temp = room_temp_c
        predicted_soc = soc
        objective_value = 0.0
        solve_status = "baseline"
        solve_time_s = 0.0
        mip_gap = None

        if controller_mode == "no_tes":
            q_ch = 0.0
            q_dis = 0.0
        elif controller_mode == "mpc":
            try:
                state = MPCState(
                    soc=soc,
                    room_temp_c=room_temp_c,
                    prev_q_ch_tes_kw_th=prev_q_ch,
                    prev_q_dis_tes_kw_th=prev_q_dis,
                )
                action, solution = controller.compute_action(state, forecast)
                if solution.status in {"infeasible", "unbounded", "solver_error"}:
                    raise RuntimeError(f"unusable MILP solution status: {solution.status}")
                q_ch = action.q_ch_tes_kw_th
                q_dis = action.q_dis_tes_kw_th
                solve_status = solution.status
                solve_time_s = solution.solve_time_s
                mip_gap = solution.mip_gap
                objective_value = solution.objective_value
                predicted_room_temp = float(solution.room_temp_c[1])
                predicted_soc = float(solution.soc[1])
            except Exception as exc:
                q_ch = 0.0
                q_dis = 0.0
                solve_status = "fallback"
                fallback_used = True
                objective_value = float("nan")
                mip_gap = None
                solver_error = str(exc)
        else:
            raise ValueError(f"unsupported controller_mode: {controller_mode}")

        actual_base_facility = float(actual.base_facility_kw[0])
        actual_pv = float(actual.pv_forecast_kw[0])
        grid_import_kw, pv_spill_kw, facility_power_kw = facility_model.grid_and_spill_kw(
            actual_base_facility,
            q_ch_tes_kw_th=q_ch,
            q_dis_tes_kw_th=q_dis,
            pv_kw=actual_pv,
        )
        pue = facility_power_kw / max(1e-9, float(actual.it_load_forecast_kw[0]))
        monitor_rows.append(
            {
                "timestamp": now.isoformat(sep=" "),
                "step": step,
                "scenario_id": case_id,
                "controller_type": controller_mode,
                "outdoor_temp_c": float(actual.outdoor_temp_forecast_c[0]),
                "it_load_kw": float(actual.it_load_forecast_kw[0]),
                "pv_actual_kw": actual_pv,
                "pv_forecast_kw": float(forecast.pv_forecast_kw[0]),
                "price_currency_per_mwh": float(actual.price_forecast[0]),
                "base_facility_kw": actual_base_facility,
                "base_cooling_kw_th": float(actual.base_cooling_kw_th[0]),
                "q_ch_tes_kw_th": q_ch,
                "q_dis_tes_kw_th": q_dis,
                "grid_import_kw": grid_import_kw,
                "pv_spill_kw": pv_spill_kw,
                "room_temp_c": room_temp_c,
                "predicted_room_temp_c": predicted_room_temp,
                "soc": soc,
                "predicted_soc": predicted_soc,
                "facility_power_kw": facility_power_kw,
                "pue": pue,
                "fallback_used": fallback_used,
            }
        )
        solver_row = {
            "timestamp": now.isoformat(sep=" "),
            "step": step,
            "solve_status": solve_status,
            "objective_value": objective_value,
            "solve_time_s": solve_time_s,
            "mip_gap": mip_gap,
        }
        if fallback_used:
            solver_row["solver_error"] = solver_error
        solver_rows.append(solver_row)

        if controller_mode == "no_tes":
            next_soc = soc
        else:
            next_soc = tes_model.next_soc(soc, q_ch, q_dis)
        soc = min(1.0, max(0.0, next_soc))
        room_temp_c = room_model.next_temperature(
            room_temp_c=room_temp_c,
            outdoor_temp_c=float(actual.outdoor_temp_forecast_c[0]),
            it_load_kw=float(actual.it_load_forecast_kw[0]),
            base_cooling_kw_th=float(actual.base_cooling_kw_th[0]),
            q_dis_tes_kw_th=q_dis,
        )
        prev_q_ch = q_ch
        prev_q_dis = q_dis

    monitor = pd.DataFrame(monitor_rows)
    solver_log = pd.DataFrame(solver_rows)
    monitor.to_csv(run_dir / "monitor.csv", index=False)
    solver_log.to_csv(run_dir / "solver_log.csv", index=False)
    summary = compute_episode_metrics(
        monitor=monitor,
        solver_log=solver_log,
        scenario_id=case_id,
        controller_type=controller_mode,
        dt_hours=dt_hours,
        temp_min_c=float(cfg["temperature"]["min_c"]),
        temp_max_c=float(cfg["temperature"]["max_c"]),
        soc_physical_min=tes_params.soc_physical_min,
        soc_physical_max=tes_params.soc_physical_max,
        tes_capacity_kwh_th=tes_params.capacity_kwh_th,
    )
    (run_dir / "episode_summary.json").write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--case-id", default="tes_mpc_smoke")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--pv-error-sigma", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--controller-mode", default="mpc", choices=["mpc", "no_tes"])
    parser.add_argument("--tariff-multiplier", type=float, default=1.0)
    parser.add_argument("--outdoor-offset-c", type=float, default=0.0)
    args = parser.parse_args()
    run_dir = run_closed_loop(
        config_path=args.config,
        case_id=args.case_id,
        steps=args.steps,
        output_root=args.output_root,
        pv_error_sigma=args.pv_error_sigma,
        seed=args.seed,
        controller_mode=args.controller_mode,
        tariff_multiplier=args.tariff_multiplier,
        outdoor_offset_c=args.outdoor_offset_c,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
