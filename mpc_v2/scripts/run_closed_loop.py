"""Run a deterministic synthetic/replay closed loop for chiller+TES MPC v1."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.facility_model import (
    ChillerPlantModel,
    ChillerPlantParams,
    EconomicsParams,
    FacilityModel,
    FacilityParams,
    ValveParams,
    grid_and_spill_from_plant_kw,
)
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCAction, MPCState, load_yaml, parse_timestamp
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
    pv_scale: float | None = None,
    demand_charge_rate: float | None = None,
    demand_charge_multiplier: float = 1.0,
) -> Path:
    """Run closed-loop validation and write monitor/solver/summary outputs."""

    cfg = load_yaml(config_path)
    cfg.setdefault("economics", {})
    if demand_charge_rate is None:
        cfg["economics"]["demand_charge_currency_per_kw_day"] = (
            float(cfg["economics"].get("demand_charge_currency_per_kw_day", 0.0)) * float(demand_charge_multiplier)
        )
    else:
        cfg["economics"]["demand_charge_currency_per_kw_day"] = float(demand_charge_rate)
    if pv_scale is not None:
        cfg["economics"]["pv_scale"] = float(pv_scale)

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
    chiller_params = ChillerPlantParams.from_config(cfg["chiller"])
    valve_params = ValveParams.from_config(cfg.get("valve", {}))
    economics_params = EconomicsParams.from_config(cfg.get("economics", {}))
    tes_model = TESModel(tes_params, dt_hours=dt_hours)
    room_model = RoomModel(room_params, dt_hours=dt_hours)
    facility_model = FacilityModel(facility_params)
    chiller_model = ChillerPlantModel(chiller_params)
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
    wet_bulb_depression_c = float(synthetic.get("wet_bulb_depression_c", 4.0))
    seed_value = int(seed if seed is not None else synthetic.get("seed", 7))

    soc = tes_params.initial_soc
    room_temp_c = room_params.initial_room_temp_c
    prev_q_ch = 0.0
    prev_q_dis = 0.0
    prev_u_ch = 0.0
    prev_u_dis = 0.0
    prev_mode_index = -1
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
            pv_scale=economics_params.pv_scale,
            wet_bulb_depression_c=wet_bulb_depression_c,
        )
        actual = forecast_builder.actual_at(
            now_ts=now,
            it_load_kw=it_load_kw,
            outdoor_base_c=outdoor_base_c,
            outdoor_amplitude_c=outdoor_amplitude_c,
            outdoor_offset_c=outdoor_offset_c,
            tariff_multiplier=tariff_multiplier,
            pv_scale=economics_params.pv_scale,
            wet_bulb_depression_c=wet_bulb_depression_c,
        )
        fallback_used = False
        objective_value = 0.0
        solve_status = "baseline"
        solve_time_s = 0.0
        mip_gap = None
        predicted_room_temp = room_temp_c
        predicted_soc = soc
        predicted_peak_grid = 0.0
        action: MPCAction
        solution = None

        if controller_mode in {"mpc", "no_tes"}:
            try:
                state = MPCState(
                    soc=soc,
                    room_temp_c=room_temp_c,
                    prev_q_ch_tes_kw_th=prev_q_ch,
                    prev_q_dis_tes_kw_th=prev_q_dis,
                    prev_u_ch=prev_u_ch,
                    prev_u_dis=prev_u_dis,
                    prev_mode_index=prev_mode_index,
                )
                action, solution = controller.compute_action(state, forecast, tes_available=controller_mode == "mpc")
                if solution.status in {"infeasible", "unbounded", "solver_error"}:
                    raise RuntimeError(f"unusable MILP solution status: {solution.status}")
                solve_status = solution.status
                solve_time_s = solution.solve_time_s
                mip_gap = solution.mip_gap
                objective_value = solution.objective_value
                predicted_room_temp = float(solution.room_temp_c[1])
                predicted_soc = float(solution.soc[1])
                predicted_peak_grid = solution.peak_grid_kw
            except Exception as exc:
                action = _fallback_action(
                    room_model=room_model,
                    chiller_model=chiller_model,
                    room_temp_c=room_temp_c,
                    outdoor_temp_c=float(actual.outdoor_temp_forecast_c[0]),
                    wet_bulb_c=float(actual.wet_bulb_or_default()[0]),
                    it_load_kw=float(actual.it_load_forecast_kw[0]),
                    temp_target_c=float(cfg["temperature"]["max_c"]) - 0.5,
                )
                solve_status = "fallback"
                fallback_used = True
                objective_value = 0.0
                solver_error = str(exc)
        elif controller_mode == "rbc":
            action = _rbc_action(
                forecast=forecast,
                room_model=room_model,
                chiller_model=chiller_model,
                tes_params=tes_params,
                valve_params=valve_params,
                soc=soc,
                room_temp_c=room_temp_c,
                prev_u_ch=prev_u_ch,
                prev_u_dis=prev_u_dis,
                temp_target_c=float(cfg["temperature"]["max_c"]) - 0.5,
                dt_hours=dt_hours,
            )
        else:
            raise ValueError(f"unsupported controller_mode: {controller_mode}")

        actual_pv = float(actual.pv_forecast_kw[0])
        grid_import_kw, pv_spill_kw = grid_and_spill_from_plant_kw(action.plant_power_kw, actual_pv)
        actual_it = float(actual.it_load_forecast_kw[0])
        facility_power_kw = actual_it + action.plant_power_kw
        pue = facility_power_kw / max(1e-9, actual_it)
        mode_flags = _mode_flags(action.mode_index, len(chiller_params.modes))
        monitor_row = {
            "timestamp": now.isoformat(sep=" "),
            "step": step,
            "scenario_id": case_id,
            "controller_type": controller_mode,
            "outdoor_temp_c": float(actual.outdoor_temp_forecast_c[0]),
            "wet_bulb_c": float(actual.wet_bulb_or_default()[0]),
            "it_load_kw": actual_it,
            "pv_actual_kw": actual_pv,
            "pv_forecast_kw": float(forecast.pv_forecast_kw[0]),
            "price_currency_per_mwh": float(actual.price_forecast[0]),
            "demand_charge_rate": economics_params.demand_charge_currency_per_kw_day,
            "base_facility_kw": float(actual.base_facility_kw[0]),
            "base_cooling_kw_th": float(actual.base_cooling_kw_th[0]),
            "q_chiller_kw_th": action.q_chiller_kw_th,
            "q_load_kw_th": action.q_load_kw_th,
            "q_ch_tes_kw_th": action.q_ch_tes_kw_th,
            "q_dis_tes_kw_th": action.q_dis_tes_kw_th,
            "u_ch": action.u_ch,
            "u_dis": action.u_dis,
            "du_ch": abs(action.u_ch - prev_u_ch),
            "du_dis": abs(action.u_dis - prev_u_dis),
            "mode_index": action.mode_index,
            "plant_power_kw": action.plant_power_kw,
            "cold_station_power_kw": action.plant_power_kw,
            "grid_import_kw": grid_import_kw,
            "pv_spill_kw": pv_spill_kw,
            "peak_grid_kw": max(predicted_peak_grid, grid_import_kw),
            "room_temp_c": room_temp_c,
            "predicted_room_temp_c": predicted_room_temp,
            "soc": soc,
            "predicted_soc": predicted_soc,
            "facility_power_kw": facility_power_kw,
            "pue": pue,
            "fallback_used": fallback_used,
            **mode_flags,
        }
        monitor_rows.append(monitor_row)
        solver_row = {
            "timestamp": now.isoformat(sep=" "),
            "step": step,
            "solve_status": solve_status,
            "objective_value": objective_value,
            "solve_time_s": solve_time_s,
            "mip_gap": mip_gap,
            "mode_index": action.mode_index,
            "peak_grid_kw": monitor_row["peak_grid_kw"],
        }
        if fallback_used:
            solver_row["solver_error"] = solver_error
        solver_rows.append(solver_row)

        if controller_mode == "no_tes":
            next_soc = soc
        else:
            next_soc = tes_model.next_soc(soc, action.q_ch_tes_kw_th, action.q_dis_tes_kw_th)
        soc = min(1.0, max(0.0, next_soc))
        room_temp_c = room_model.next_temperature(
            room_temp_c=room_temp_c,
            outdoor_temp_c=float(actual.outdoor_temp_forecast_c[0]),
            it_load_kw=actual_it,
            q_cooling_total_kw_th=action.q_load_kw_th + action.q_dis_tes_kw_th,
        )
        prev_q_ch = action.q_ch_tes_kw_th
        prev_q_dis = action.q_dis_tes_kw_th
        prev_u_ch = action.u_ch
        prev_u_dis = action.u_dis
        prev_mode_index = action.mode_index

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


def _fallback_action(
    room_model: RoomModel,
    chiller_model: ChillerPlantModel,
    room_temp_c: float,
    outdoor_temp_c: float,
    wet_bulb_c: float,
    it_load_kw: float,
    temp_target_c: float,
) -> MPCAction:
    q_load = room_model.required_cooling_kw_th(room_temp_c, outdoor_temp_c, it_load_kw, temp_target_c)
    q_chiller, mode_index, plant_power = chiller_model.dispatch(q_load, wet_bulb_c)
    q_load = q_chiller
    return MPCAction(
        q_ch_tes_kw_th=0.0,
        q_dis_tes_kw_th=0.0,
        q_chiller_kw_th=q_chiller,
        q_load_kw_th=q_load,
        plant_power_kw=plant_power,
        u_ch=0.0,
        u_dis=0.0,
        mode_index=mode_index,
    )


def _rbc_action(
    forecast,
    room_model: RoomModel,
    chiller_model: ChillerPlantModel,
    tes_params: TESParams,
    valve_params: ValveParams,
    soc: float,
    room_temp_c: float,
    prev_u_ch: float,
    prev_u_dis: float,
    temp_target_c: float,
    dt_hours: float,
) -> MPCAction:
    price = pd.Series(forecast.price_forecast)
    low_price = float(forecast.price_forecast[0]) <= float(price.quantile(0.25))
    high_price = float(forecast.price_forecast[0]) >= float(price.quantile(0.75))
    outdoor = float(forecast.outdoor_temp_forecast_c[0])
    wet_bulb = float(forecast.wet_bulb_or_default()[0])
    it_load = float(forecast.it_load_forecast_kw[0])
    q_required = room_model.required_cooling_kw_th(room_temp_c, outdoor, it_load, temp_target_c)

    q_dis = 0.0
    if high_price and soc > tes_params.soc_planning_min + 1e-6:
        soc_available_kw = (soc - tes_params.soc_planning_min) * tes_params.eta_dis * tes_params.capacity_kwh_th / dt_hours
        q_dis = min(tes_params.q_dis_max_kw_th, soc_available_kw, q_required)

    q_load = max(0.0, q_required - q_dis)
    q_ch = 0.0
    if low_price and soc < tes_params.soc_planning_max - 1e-6:
        soc_headroom_kw = (tes_params.soc_planning_max - soc) * tes_params.capacity_kwh_th / (
            tes_params.eta_ch * dt_hours
        )
        q_ch = min(tes_params.q_ch_max_kw_th, soc_headroom_kw)

    target_u_ch = q_ch / max(1e-9, tes_params.q_ch_max_kw_th)
    target_u_dis = q_dis / max(1e-9, tes_params.q_dis_max_kw_th)
    u_ch = _ramp(prev_u_ch, target_u_ch, valve_params.du_max_per_step)
    u_dis = _ramp(prev_u_dis, target_u_dis, valve_params.du_max_per_step)
    if u_ch + u_dis > 1.0:
        if high_price:
            u_ch = 0.0
        else:
            u_dis = 0.0
    q_ch = min(q_ch, u_ch * tes_params.q_ch_max_kw_th)
    q_dis = min(q_dis, u_dis * tes_params.q_dis_max_kw_th)
    q_load = max(0.0, q_required - q_dis)
    q_chiller_req = q_load + q_ch
    q_chiller, mode_index, plant_power = chiller_model.dispatch(q_chiller_req, wet_bulb)
    if q_chiller > q_load + q_ch + 1e-6:
        q_load += q_chiller - q_load - q_ch
    return MPCAction(
        q_ch_tes_kw_th=q_ch,
        q_dis_tes_kw_th=q_dis,
        q_chiller_kw_th=q_chiller,
        q_load_kw_th=q_load,
        plant_power_kw=plant_power,
        u_ch=u_ch,
        u_dis=u_dis,
        mode_index=mode_index,
    )


def _ramp(previous: float, target: float, step_limit: float) -> float:
    target = min(1.0, max(0.0, float(target)))
    previous = min(1.0, max(0.0, float(previous)))
    return min(previous + step_limit, max(previous - step_limit, target))


def _mode_flags(mode_index: int, n_modes: int) -> dict[str, int]:
    return {f"z_mode_{i}": 1 if i == mode_index else 0 for i in range(n_modes)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--case-id", default="tes_mpc_smoke")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--pv-error-sigma", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--controller-mode", default="mpc", choices=["mpc", "no_tes", "rbc"])
    parser.add_argument("--tariff-multiplier", type=float, default=1.0)
    parser.add_argument("--outdoor-offset-c", type=float, default=0.0)
    parser.add_argument("--pv-scale", type=float, default=None)
    parser.add_argument("--demand-charge-rate", type=float, default=None)
    parser.add_argument("--demand-charge-multiplier", type=float, default=1.0)
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
        pv_scale=args.pv_scale,
        demand_charge_rate=args.demand_charge_rate,
        demand_charge_multiplier=args.demand_charge_multiplier,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
