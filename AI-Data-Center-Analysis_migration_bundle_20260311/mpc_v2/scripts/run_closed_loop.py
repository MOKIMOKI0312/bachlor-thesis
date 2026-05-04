"""Run a synthetic/replay closed loop for economic MPC v2."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import load_yaml, parse_timestamp
from mpc_v2.core.metrics import compute_episode_metrics
from mpc_v2.core.mpc_problem_milp import MPCState
from mpc_v2.core.pue_model import PUEModel, PUEParams
from mpc_v2.core.room_model import RoomModel, RoomParams
from mpc_v2.core.tes_model import TESModel, TESParams


def run_closed_loop(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    case_id: str = "tes_mpc_synthetic_smoke",
    steps: int | None = None,
    output_root: str | Path | None = None,
    pv_perturbation: str = "nominal",
    seed: int | None = None,
    controller_mode: str = "mpc",
    tariff_multiplier: float = 1.0,
    outdoor_offset_C: float = 0.0,
) -> Path:
    """Run a synthetic closed loop and write monitor/solver/summary outputs."""

    cfg = load_yaml(config_path)
    dt_h = float(cfg["time"]["dt_h"])
    if abs(dt_h - 0.25) > 1e-9:
        raise ValueError(f"dt_h must be 0.25, got {dt_h}")
    horizon_steps = int(cfg["time"]["horizon_steps"])
    n_steps = int(steps if steps is not None else cfg["time"]["default_closed_loop_steps"])
    root = Path(output_root or cfg["paths"]["output_root"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"{case_id}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    tes_params = TESParams.from_config(cfg["tes"])
    room_params = RoomParams.from_config(cfg["room"])
    pue_params = PUEParams.from_config(cfg["pue"])
    tes_model = TESModel(tes_params, dt_h=dt_h)
    room_model = RoomModel(room_params, dt_h=dt_h)
    pue_model = PUEModel(pue_params)
    forecast_builder = ForecastBuilder(cfg["paths"]["pv_csv"], cfg["paths"]["price_csv"], pue_model, dt_h=dt_h)
    controller = EconomicTESMPCController.from_config(cfg)

    synthetic = cfg.get("synthetic", {})
    start_ts = parse_timestamp(synthetic.get("start_timestamp", "2025-07-01 00:00:00"))
    ite_power_kw = float(synthetic.get("ite_power_kw", 18000.0))
    outdoor_base_C = float(synthetic.get("outdoor_base_C", 29.0))
    outdoor_amp_C = float(synthetic.get("outdoor_amplitude_C", 6.0))
    seed_value = int(seed if seed is not None else synthetic.get("seed", 7))

    soc = tes_params.initial_soc
    room_temp = room_params.initial_temperature_C
    prev_net = 0.0
    monitor_rows: list[dict[str, Any]] = []
    solver_rows: list[dict[str, Any]] = []

    for step in range(n_steps):
        now = start_ts + timedelta(minutes=15 * step)
        forecast = forecast_builder.build(
            now,
            horizon_steps=horizon_steps,
            pv_perturbation=pv_perturbation,  # type: ignore[arg-type]
            seed=seed_value + step,
            ite_power_kw=ite_power_kw,
            outdoor_base_C=outdoor_base_C,
            outdoor_amplitude_C=outdoor_amp_C,
            outdoor_offset_C=outdoor_offset_C,
            base_cooling_kw=room_params.base_cooling_kw,
            tariff_multiplier=tariff_multiplier,
        )
        if controller_mode == "no_tes":
            q_ch = 0.0
            q_dis = 0.0
            solution_status = "baseline"
            solve_time = 0.0
            mip_gap = None
            objective_value = 0.0
            p_grid = max(0.0, forecast.base_facility_kw[0] - forecast.pv_kw[0])
            p_spill = max(0.0, forecast.pv_kw[0] - forecast.base_facility_kw[0])
        else:
            state = MPCState(room_temperature_C=room_temp, tes_soc=soc, previous_net_action_kw=prev_net)
            action, solution = controller.compute_action(state, forecast)
            q_ch = action.tes_charge_kwth
            q_dis = action.tes_discharge_kwth
            solution_status = solution.status
            solve_time = solution.solve_time_s
            mip_gap = solution.mip_gap
            objective_value = solution.objective_value
            p_grid = float(solution.P_grid[0])
            p_spill = float(solution.P_spill[0])

        facility_power = pue_model.facility_kw(ite_power_kw, forecast.outdoor_drybulb_C[0], q_ch, q_dis)
        pue_actual = facility_power / max(1e-9, ite_power_kw)
        monitor_rows.append(
            {
                "timestamp": now.isoformat(sep=" "),
                "step": step,
                "price_usd_per_mwh": forecast.price_usd_per_mwh[0],
                "pv_kw": forecast.pv_kw[0],
                "outdoor_drybulb_C": forecast.outdoor_drybulb_C[0],
                "ite_power_kw": ite_power_kw,
                "facility_power_kw": facility_power,
                "P_grid_kw": p_grid,
                "P_spill_kw": p_spill,
                "air_temperature_C": room_temp,
                "tes_soc": soc,
                "tes_charge_kwth": q_ch,
                "tes_discharge_kwth": q_dis,
                "tes_capacity_kwh": tes_params.effective_capacity_kwh,
                "pue_actual": pue_actual,
            }
        )
        solver_rows.append(
            {
                "timestamp": now.isoformat(sep=" "),
                "step": step,
                "status": solution_status,
                "solve_time_s": solve_time,
                "mip_gap": mip_gap,
                "objective_value": objective_value,
            }
        )

        soc = tes_model.next_soc(soc, q_ch, q_dis)
        room_temp = room_model.next_temperature(
            room_temp,
            forecast.outdoor_drybulb_C[0],
            ite_power_kw,
            forecast.base_cooling_kw[0],
            q_dis,
        )
        prev_net = q_ch - q_dis

    monitor = pd.DataFrame(monitor_rows)
    solver_log = pd.DataFrame(solver_rows)
    monitor.to_csv(run_dir / "monitor.csv", index=False)
    solver_log.to_csv(run_dir / "solver_log.csv", index=False)
    summary = compute_episode_metrics(
        monitor,
        solver_log,
        case_id=case_id,
        dt_h=dt_h,
        temp_min_C=float(cfg["temperature"]["min_C"]),
        temp_max_C=float(cfg["temperature"]["max_C"]),
        soc_min_phys=tes_params.soc_min_phys,
        soc_max_phys=tes_params.soc_max_phys,
    )
    (run_dir / "episode_summary.json").write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--case-id", default="tes_mpc_synthetic_smoke")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--pv-perturbation", default="nominal", choices=["nominal", "g05", "g10", "g20"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--controller-mode", default="mpc", choices=["mpc", "no_tes"])
    parser.add_argument("--tariff-multiplier", type=float, default=1.0)
    parser.add_argument("--outdoor-offset-C", type=float, default=0.0)
    args = parser.parse_args()
    run_dir = run_closed_loop(
        config_path=args.config,
        case_id=args.case_id,
        steps=args.steps,
        output_root=args.output_root,
        pv_perturbation=args.pv_perturbation,
        seed=args.seed,
        controller_mode=args.controller_mode,
        tariff_multiplier=args.tariff_multiplier,
        outdoor_offset_C=args.outdoor_offset_C,
    )
    print(run_dir)


if __name__ == "__main__":
    main()

