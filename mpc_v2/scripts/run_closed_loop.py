"""Run a deterministic synthetic/replay closed loop for chiller+TES MPC v1."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yaml

from mpc_v2.core.controller import EconomicTESMPCController
from mpc_v2.core.dr_service import summarize_dr_events
from mpc_v2.core.facility_model import (
    ChillerPlantModel,
    ChillerPlantParams,
    EconomicsParams,
    FacilityModel,
    FacilityParams,
    ValveParams,
    grid_and_spill_from_load_kw,
    grid_and_spill_from_plant_kw,
)
from mpc_v2.core.forecast import ForecastBuilder
from mpc_v2.core.io_schemas import MPCAction, MPCState, SchemaValidationError, load_yaml, parse_timestamp
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
) -> Path:
    """Run closed-loop validation and write monitor/solver/summary outputs."""

    cfg = load_yaml(config_path)
    cfg.setdefault("economics", {})
    if "demand_charge_rate" not in cfg["economics"] and "demand_charge_currency_per_kw_day" in cfg["economics"]:
        cfg["economics"]["demand_charge_rate"] = cfg["economics"].pop("demand_charge_currency_per_kw_day")
    cfg["economics"].setdefault("demand_charge_basis", "per_day_proxy")
    if demand_charge_rate is None:
        cfg["economics"]["demand_charge_rate"] = (
            float(cfg["economics"].get("demand_charge_rate", 0.0)) * float(demand_charge_multiplier)
        )
    else:
        cfg["economics"]["demand_charge_rate"] = float(demand_charge_rate)
    if demand_charge_basis is not None:
        cfg["economics"]["demand_charge_basis"] = str(demand_charge_basis)
    if pv_scale is not None:
        cfg["economics"]["pv_scale"] = float(pv_scale)
    if peak_cap_kw is not None:
        cfg["economics"]["peak_cap_kw"] = float(peak_cap_kw)
    if peak_cap_ratio is not None and peak_cap_reference_kw is not None:
        cfg["economics"]["peak_cap_kw"] = float(peak_cap_ratio) * float(peak_cap_reference_kw)
    if horizon_steps_override is not None:
        cfg["time"]["horizon_steps"] = int(horizon_steps_override)
    if w_terminal is not None:
        cfg["objective"]["w_terminal"] = float(w_terminal)
    if w_spill is not None:
        cfg["objective"]["w_spill"] = float(w_spill)
    if w_cycle is not None:
        cfg["objective"]["w_cycle"] = float(w_cycle)
    if w_peak_slack is not None:
        cfg["objective"]["w_peak_slack"] = float(w_peak_slack)
    if soc_target is not None:
        cfg["tes"]["soc_target"] = float(soc_target)
    if initial_soc is not None:
        cfg["tes"]["initial_soc"] = float(initial_soc)
    cfg.setdefault("tariff", {})
    if tariff_template is not None:
        cfg["tariff"]["template"] = str(tariff_template)
    if tariff_gamma is not None:
        cfg["tariff"]["gamma"] = float(tariff_gamma)
    if cp_uplift is not None:
        cfg["tariff"]["cp_uplift"] = float(cp_uplift)
    if float_share is not None:
        cfg["tariff"]["float_share"] = float(float_share)
    cfg.setdefault("dr", {})
    if dr_enabled is not None:
        cfg["dr"]["enabled"] = bool(dr_enabled)
    if dr_event_type is not None:
        cfg["dr"]["event_type"] = str(dr_event_type)
    if dr_reduction_frac is not None:
        cfg["dr"]["reduction_frac"] = float(dr_reduction_frac)
    if dr_start_hour is not None:
        cfg["dr"]["start_hour"] = float(dr_start_hour)
    if dr_duration_hours is not None:
        cfg["dr"]["duration_hours"] = float(dr_duration_hours)
    if dr_event_day_index is not None:
        cfg["dr"]["event_day_index"] = int(dr_event_day_index)
    if dr_event_start_timestamp is not None:
        cfg["dr"]["event_start_timestamp"] = str(dr_event_start_timestamp)
    if dr_baseline_kw is not None:
        cfg["dr"]["baseline_kw"] = float(dr_baseline_kw)
    if dr_compensation_cny_per_kwh is not None:
        cfg["dr"]["compensation_cny_per_kwh"] = float(dr_compensation_cny_per_kwh)

    dt_hours = float(cfg["time"]["dt_hours"])
    horizon_steps = int(cfg["time"]["horizon_steps"])
    n_steps = int(steps if steps is not None else cfg["time"]["default_closed_loop_steps"])
    synthetic = cfg.get("synthetic", {})
    start_ts = parse_timestamp(synthetic.get("start_timestamp", "2025-07-01 00:00:00"))
    cfg.setdefault("dr", {})
    cfg["dr"].setdefault("episode_start_timestamp", start_ts.isoformat(sep=" "))
    root = Path(output_root or cfg["paths"]["output_root"])
    run_dir = root / case_id
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{case_id}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_effective_config(
        run_dir=run_dir,
        cfg=cfg,
        config_path=config_path,
        case_id=case_id,
        controller_mode=controller_mode,
        closed_loop_steps=n_steps,
        pv_error_sigma=pv_error_sigma,
        seed=seed,
        tariff_multiplier=tariff_multiplier,
        outdoor_offset_c=outdoor_offset_c,
    )

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
        tariff_config=cfg.get("tariff", {}),
        dr_config=cfg.get("dr", {}),
    )
    controller = EconomicTESMPCController.from_config(cfg)

    it_load_kw = float(synthetic.get("it_load_kw", 18000.0))
    outdoor_base_c = float(synthetic.get("outdoor_base_c", 29.0))
    outdoor_amplitude_c = float(synthetic.get("outdoor_amplitude_c", 6.0))
    wet_bulb_depression_c = float(synthetic.get("wet_bulb_depression_c", 4.0))
    seed_value = int(seed if seed is not None else synthetic.get("seed", 7))

    soc = tes_params.initial_soc
    initial_soc = soc
    room_temp_c = room_params.initial_room_temp_c
    prev_q_ch = 0.0
    prev_q_dis = 0.0
    prev_u_ch = 0.0
    prev_u_dis = 0.0
    prev_mode_index = -1
    episode_peak_grid_so_far = 0.0
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
        solver_error = None
        action: MPCAction
        solution = None

        is_mpc_mode = controller_mode in {"mpc", "mpc_no_tes"}
        if is_mpc_mode:
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
                    valve_params=valve_params,
                    prev_u_ch=prev_u_ch,
                    prev_u_dis=prev_u_dis,
                    tes_params=tes_params,
                )
                solve_status = "fallback"
                fallback_used = True
                objective_value = 0.0
                solver_error = str(exc)
        elif controller_mode == "no_tes":
            action = _no_tes_action(
                room_model=room_model,
                chiller_model=chiller_model,
                room_temp_c=room_temp_c,
                outdoor_temp_c=float(actual.outdoor_temp_forecast_c[0]),
                wet_bulb_c=float(actual.wet_bulb_or_default()[0]),
                it_load_kw=float(actual.it_load_forecast_kw[0]),
                temp_target_c=float(cfg["temperature"]["max_c"]) - 0.5,
                tes_params=tes_params,
            )
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

        try:
            action.validate()
        except SchemaValidationError as exc:
            if not is_mpc_mode:
                raise
            action = _fallback_action(
                room_model=room_model,
                chiller_model=chiller_model,
                room_temp_c=room_temp_c,
                outdoor_temp_c=float(actual.outdoor_temp_forecast_c[0]),
                wet_bulb_c=float(actual.wet_bulb_or_default()[0]),
                it_load_kw=float(actual.it_load_forecast_kw[0]),
                temp_target_c=float(cfg["temperature"]["max_c"]) - 0.5,
                valve_params=valve_params,
                prev_u_ch=prev_u_ch,
                prev_u_dis=prev_u_dis,
                tes_params=tes_params,
            )
            action.validate()
            solve_status = "fallback"
            fallback_used = True
            objective_value = 0.0
            solver_error = f"action validation failed: {exc}"

        actual_pv = float(actual.pv_forecast_kw[0])
        actual_it = float(actual.it_load_forecast_kw[0])
        facility_power_kw = actual_it + action.plant_power_kw
        grid_import_kw, pv_spill_kw = grid_and_spill_from_load_kw(facility_power_kw, actual_pv)
        cold_station_proxy_grid_kw, cold_station_proxy_spill_kw = grid_and_spill_from_plant_kw(
            action.plant_power_kw,
            actual_pv,
        )
        episode_peak_grid_so_far = max(episode_peak_grid_so_far, grid_import_kw)
        pue = facility_power_kw / max(1e-9, actual_it)
        mode_flags = _mode_flags(action.mode_index, len(chiller_params.modes))
        mode_min, mode_max = _mode_bounds(action.mode_index, chiller_params)
        mode_specific_plr = action.q_chiller_kw_th / mode_max if mode_max > 1e-9 else 0.0
        instant_chiller_cop = action.q_chiller_kw_th / action.plant_power_kw if action.plant_power_kw > 1e-9 else 0.0
        u_signed = action.u_signed
        prev_u_signed = prev_u_ch - prev_u_dis
        signed_du = abs(u_signed - prev_u_signed)
        dynamic_cap = (
            float(actual.dynamic_peak_cap_kw[0])
            if actual.dynamic_peak_cap_kw is not None and float(actual.dynamic_peak_cap_kw[0]) >= 0.0
            else None
        )
        peak_cap = dynamic_cap if dynamic_cap is not None else economics_params.peak_cap_kw
        peak_slack_kw = max(0.0, grid_import_kw - peak_cap) if peak_cap is not None else 0.0
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
            "price_total_cny_mwh": float(actual.price_forecast[0]),
            "price_float_cny_mwh": (
                float(actual.price_float_forecast[0]) if actual.price_float_forecast else float(actual.price_forecast[0])
            ),
            "price_nonfloat_cny_mwh": (
                float(actual.price_nonfloat_forecast[0]) if actual.price_nonfloat_forecast else 0.0
            ),
            "tou_stage": str(actual.tou_stage[0]) if actual.tou_stage else "",
            "cp_flag": int(actual.cp_flag[0]) if actual.cp_flag else 0,
            "demand_charge_rate": economics_params.demand_charge_rate,
            "demand_charge_basis": economics_params.demand_charge_basis,
            "peak_cap_kw": peak_cap,
            "base_facility_kw": float(actual.base_facility_kw[0]),
            "base_cooling_kw_th": float(actual.base_cooling_kw_th[0]),
            "q_chiller_kw_th": action.q_chiller_kw_th,
            "q_load_kw_th": action.q_load_kw_th,
            "q_ch_tes_kw_th": action.q_ch_tes_kw_th,
            "q_dis_tes_kw_th": action.q_dis_tes_kw_th,
            "u_ch": action.u_ch,
            "u_dis": action.u_dis,
            "u_signed": u_signed,
            "du_ch": abs(action.u_ch - prev_u_ch),
            "du_dis": abs(action.u_dis - prev_u_dis),
            "signed_du": signed_du,
            "du_signed_max": valve_params.du_signed_max_per_step,
            "mode_index": action.mode_index,
            "selected_mode_q_min_kw_th": mode_min,
            "selected_mode_q_max_kw_th": mode_max,
            "mode_specific_plr": mode_specific_plr,
            "instant_chiller_cop": instant_chiller_cop,
            "plant_power_kw": action.plant_power_kw,
            "cold_station_power_kw": action.plant_power_kw,
            "grid_import_kw": grid_import_kw,
            "pv_spill_kw": pv_spill_kw,
            "cold_station_proxy_grid_import_kw": cold_station_proxy_grid_kw,
            "cold_station_proxy_pv_spill_kw": cold_station_proxy_spill_kw,
            "episode_peak_grid_so_far_kw": episode_peak_grid_so_far,
            "predicted_peak_grid_kw": predicted_peak_grid,
            "peak_slack_kw": peak_slack_kw,
            "dr_flag": int(actual.dr_flag[0]) if actual.dr_flag else 0,
            "dr_notice_type": str(actual.dr_notice_type[0]) if actual.dr_notice_type else "",
            "dr_req_kw": float(actual.dr_req_kw[0]) if actual.dr_req_kw else 0.0,
            "dr_baseline_kw": float(actual.dr_baseline_kw[0]) if actual.dr_baseline_kw else 0.0,
            "dr_event_id": str(actual.dr_event_id[0]) if actual.dr_event_id else "",
            "dr_compensation_cny_per_kwh": (
                float(actual.dr_compensation_cny_per_kwh[0]) if actual.dr_compensation_cny_per_kwh else 0.0
            ),
            "dr_response_threshold": float(cfg.get("dr", {}).get("response_threshold", 0.50)),
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
            "predicted_peak_grid_kw": predicted_peak_grid,
            "episode_peak_grid_so_far_kw": episode_peak_grid_so_far,
        }
        if fallback_used and solver_error is not None:
            solver_row["solver_error"] = solver_error
        solver_rows.append(solver_row)

        if controller_mode in {"no_tes", "mpc_no_tes"}:
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
    monitor.to_csv(run_dir / "timeseries.csv", index=False)
    solver_log.to_csv(run_dir / "solver_log.csv", index=False)
    events = summarize_dr_events(monitor, dt_hours=dt_hours, temp_max_c=float(cfg["temperature"]["max_c"]))
    events.to_csv(run_dir / "events.csv", index=False)
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
        soc_planning_max=tes_params.soc_planning_max,
        tes_capacity_kwh_th=tes_params.capacity_kwh_th,
        initial_soc=initial_soc,
        final_soc_after_last_update=soc,
    )
    summary_dict = asdict(summary)
    (run_dir / "episode_summary.json").write_text(json.dumps(summary_dict, indent=2), encoding="utf-8")
    pd.DataFrame([summary_dict]).to_csv(run_dir / "summary.csv", index=False)
    return run_dir


def _fallback_action(
    room_model: RoomModel,
    chiller_model: ChillerPlantModel,
    room_temp_c: float,
    outdoor_temp_c: float,
    wet_bulb_c: float,
    it_load_kw: float,
    temp_target_c: float,
    valve_params: ValveParams,
    prev_u_ch: float,
    prev_u_dis: float,
    tes_params: TESParams,
) -> MPCAction:
    q_load = room_model.required_cooling_kw_th(room_temp_c, outdoor_temp_c, it_load_kw, temp_target_c)
    u_signed = _ramp_signed(prev_u_ch - prev_u_dis, 0.0, valve_params.du_signed_max_per_step)
    return _dispatch_chiller_supply(
        chiller_model=chiller_model,
        wet_bulb_c=wet_bulb_c,
        q_required_load_kw_th=q_load,
        q_ch_target_kw_th=0.0,
        q_dis_kw_th=0.0,
        u_ch=max(0.0, u_signed),
        u_dis=max(0.0, -u_signed),
        tes_params=tes_params,
    )


def _no_tes_action(
    room_model: RoomModel,
    chiller_model: ChillerPlantModel,
    room_temp_c: float,
    outdoor_temp_c: float,
    wet_bulb_c: float,
    it_load_kw: float,
    temp_target_c: float,
    tes_params: TESParams,
) -> MPCAction:
    q_load = room_model.required_cooling_kw_th(room_temp_c, outdoor_temp_c, it_load_kw, temp_target_c)
    return _dispatch_chiller_supply(
        chiller_model=chiller_model,
        wet_bulb_c=wet_bulb_c,
        q_required_load_kw_th=q_load,
        q_ch_target_kw_th=0.0,
        q_dis_kw_th=0.0,
        u_ch=0.0,
        u_dis=0.0,
        tes_params=tes_params,
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

    ch_margin = tes_params.eta_ch * tes_params.q_ch_max_kw_th * valve_params.du_signed_max_per_step * dt_hours / tes_params.capacity_kwh_th
    dis_margin = (
        tes_params.q_dis_max_kw_th
        * valve_params.du_signed_max_per_step
        * dt_hours
        / (tes_params.eta_dis * tes_params.capacity_kwh_th)
    )
    target_signed = 0.0
    if low_price and soc < tes_params.soc_planning_max - ch_margin:
        target_signed = valve_params.du_signed_max_per_step
    elif high_price and soc > tes_params.soc_planning_min + dis_margin and q_required > 1e-9:
        target_signed = -valve_params.du_signed_max_per_step
    prev_signed = prev_u_ch - prev_u_dis
    u_signed = _ramp_signed(prev_signed, target_signed, valve_params.du_signed_max_per_step)
    u_ch = max(0.0, u_signed)
    u_dis = max(0.0, -u_signed)
    soc_available_kw = (soc - tes_params.soc_physical_min) * tes_params.eta_dis * tes_params.capacity_kwh_th / dt_hours
    soc_headroom_kw = (tes_params.soc_physical_max - soc) * tes_params.capacity_kwh_th / (
        tes_params.eta_ch * dt_hours
    )
    q_ch = min(u_ch * tes_params.q_ch_max_kw_th, max(0.0, soc_headroom_kw))
    q_dis = min(u_dis * tes_params.q_dis_max_kw_th, max(0.0, soc_available_kw))
    q_load = max(0.0, q_required - q_dis)
    return _dispatch_chiller_supply(
        chiller_model=chiller_model,
        wet_bulb_c=wet_bulb,
        q_required_load_kw_th=q_load,
        q_ch_target_kw_th=q_ch,
        q_dis_kw_th=q_dis,
        u_ch=u_ch,
        u_dis=u_dis,
        tes_params=tes_params,
    )


def _ramp(previous: float, target: float, step_limit: float) -> float:
    target = min(1.0, max(0.0, float(target)))
    previous = min(1.0, max(0.0, float(previous)))
    return min(previous + step_limit, max(previous - step_limit, target))


def _ramp_signed(previous: float, target: float, step_limit: float) -> float:
    target = min(1.0, max(-1.0, float(target)))
    previous = min(1.0, max(-1.0, float(previous)))
    return min(previous + step_limit, max(previous - step_limit, target))


def _dispatch_chiller_supply(
    chiller_model: ChillerPlantModel,
    wet_bulb_c: float,
    q_required_load_kw_th: float,
    q_ch_target_kw_th: float,
    q_dis_kw_th: float,
    u_ch: float,
    u_dis: float,
    tes_params: TESParams,
) -> MPCAction:
    q_required_load = max(0.0, float(q_required_load_kw_th))
    q_ch_target = max(0.0, float(q_ch_target_kw_th))
    q_chiller_req = q_required_load + q_ch_target
    q_chiller_actual, mode_index, plant_power = chiller_model.dispatch(q_chiller_req, wet_bulb_c)

    if q_chiller_actual < q_chiller_req - 1e-6:
        q_load_actual = min(q_required_load, q_chiller_actual)
        remaining = max(0.0, q_chiller_actual - q_load_actual)
        q_ch_actual = min(q_ch_target, remaining)
    else:
        q_load_actual = q_required_load
        q_ch_actual = q_ch_target

    q_dis_actual = max(0.0, float(q_dis_kw_th))
    u_ch = q_ch_actual / max(1e-9, tes_params.q_ch_max_kw_th)
    u_dis = q_dis_actual / max(1e-9, tes_params.q_dis_max_kw_th)

    action = MPCAction(
        q_ch_tes_kw_th=q_ch_actual,
        q_dis_tes_kw_th=q_dis_actual,
        q_chiller_kw_th=q_chiller_actual,
        q_load_kw_th=q_load_actual,
        plant_power_kw=plant_power,
        u_ch=max(0.0, min(1.0, float(u_ch))),
        u_dis=max(0.0, min(1.0, float(u_dis))),
        mode_index=mode_index,
        q_ch_max_kw_th=tes_params.q_ch_max_kw_th,
        q_dis_max_kw_th=tes_params.q_dis_max_kw_th,
    )
    action.validate()
    return action


def _mode_flags(mode_index: int, n_modes: int) -> dict[str, int]:
    return {f"z_mode_{i}": 1 if i == mode_index else 0 for i in range(n_modes)}


def _mode_bounds(mode_index: int, chiller_params: ChillerPlantParams) -> tuple[float, float]:
    if mode_index < 0:
        return 0.0, 0.0
    mode = chiller_params.modes[mode_index]
    return mode.q_min_kw_th, mode.q_max_kw_th


def _write_effective_config(
    run_dir: Path,
    cfg: dict[str, Any],
    config_path: str | Path,
    case_id: str,
    controller_mode: str,
    closed_loop_steps: int,
    pv_error_sigma: float,
    seed: int | None,
    tariff_multiplier: float,
    outdoor_offset_c: float,
) -> None:
    snapshot = dict(cfg)
    snapshot["effective_run"] = {
        "config_path": str(config_path),
        "case_id": case_id,
        "controller_mode": controller_mode,
        "closed_loop_steps": int(closed_loop_steps),
        "horizon_steps": int(cfg["time"]["horizon_steps"]),
        "pv_error_sigma": float(pv_error_sigma),
        "seed": seed,
        "tariff_multiplier": float(tariff_multiplier),
        "outdoor_offset_c": float(outdoor_offset_c),
        "pv_scale": float(cfg.get("economics", {}).get("pv_scale", 1.0)),
        "demand_charge_rate": float(cfg.get("economics", {}).get("demand_charge_rate", 0.0)),
        "demand_charge_basis": str(cfg.get("economics", {}).get("demand_charge_basis", "per_day_proxy")),
        "peak_cap_kw": cfg.get("economics", {}).get("peak_cap_kw"),
        "w_terminal": float(cfg.get("objective", {}).get("w_terminal", 0.0)),
        "w_spill": float(cfg.get("objective", {}).get("w_spill", 0.0)),
        "w_cycle": float(cfg.get("objective", {}).get("w_cycle", 0.0)),
    }
    (run_dir / "config_effective.yaml").write_text(yaml.safe_dump(snapshot, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--case-id", default="tes_mpc_smoke")
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--pv-error-sigma", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--controller-mode", default="mpc", choices=["mpc", "mpc_no_tes", "no_tes", "rbc"])
    parser.add_argument("--tariff-multiplier", type=float, default=1.0)
    parser.add_argument("--outdoor-offset-c", type=float, default=0.0)
    parser.add_argument("--pv-scale", type=float, default=None)
    parser.add_argument("--demand-charge-rate", type=float, default=None)
    parser.add_argument("--demand-charge-basis", default=None, choices=["per_day_proxy", "per_episode"])
    parser.add_argument("--demand-charge-multiplier", type=float, default=1.0)
    parser.add_argument("--horizon-steps", type=int, default=None)
    parser.add_argument("--w-terminal", type=float, default=None)
    parser.add_argument("--w-spill", type=float, default=None)
    parser.add_argument("--w-cycle", type=float, default=None)
    parser.add_argument("--w-peak-slack", type=float, default=None)
    parser.add_argument("--soc-target", type=float, default=None)
    parser.add_argument("--initial-soc", type=float, default=None)
    parser.add_argument("--peak-cap-kw", type=float, default=None)
    parser.add_argument("--peak-cap-ratio", type=float, default=None)
    parser.add_argument("--peak-cap-reference-kw", type=float, default=None)
    parser.add_argument("--tariff-template", default=None, choices=["none", "jiangsu_csv", "beijing", "guangdong_cold_storage"])
    parser.add_argument("--tariff-gamma", type=float, default=None)
    parser.add_argument("--cp-uplift", type=float, default=None)
    parser.add_argument("--float-share", type=float, default=None)
    parser.add_argument("--dr-enabled", action="store_true")
    parser.add_argument("--dr-event-type", default=None, choices=["day_ahead", "fast", "realtime", "peak_cap"])
    parser.add_argument("--dr-reduction-frac", type=float, default=None)
    parser.add_argument("--dr-start-hour", type=float, default=None)
    parser.add_argument("--dr-duration-hours", type=float, default=None)
    parser.add_argument("--dr-event-day-index", type=int, default=None)
    parser.add_argument("--dr-event-start-timestamp", default=None)
    parser.add_argument("--dr-baseline-kw", type=float, default=None)
    parser.add_argument("--dr-compensation-cny-per-kwh", type=float, default=None)
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
        demand_charge_basis=args.demand_charge_basis,
        demand_charge_multiplier=args.demand_charge_multiplier,
        horizon_steps_override=args.horizon_steps,
        w_terminal=args.w_terminal,
        w_spill=args.w_spill,
        w_cycle=args.w_cycle,
        w_peak_slack=args.w_peak_slack,
        soc_target=args.soc_target,
        initial_soc=args.initial_soc,
        peak_cap_kw=args.peak_cap_kw,
        peak_cap_ratio=args.peak_cap_ratio,
        peak_cap_reference_kw=args.peak_cap_reference_kw,
        tariff_template=args.tariff_template,
        tariff_gamma=args.tariff_gamma,
        cp_uplift=args.cp_uplift,
        float_share=args.float_share,
        dr_enabled=True if args.dr_enabled else None,
        dr_event_type=args.dr_event_type,
        dr_reduction_frac=args.dr_reduction_frac,
        dr_start_hour=args.dr_start_hour,
        dr_duration_hours=args.dr_duration_hours,
        dr_event_day_index=args.dr_event_day_index,
        dr_event_start_timestamp=args.dr_event_start_timestamp,
        dr_baseline_kw=args.dr_baseline_kw,
        dr_compensation_cny_per_kwh=args.dr_compensation_cny_per_kwh,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
