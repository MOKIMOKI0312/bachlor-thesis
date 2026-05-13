"""Run EnergyPlus with TES actions from no-control, RBC, or MPC controllers."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import sys
import time
from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd

from .common import (
    DEFAULT_BASELINE_TIMESERIES,
    DEFAULT_EPLUS_INSTALL,
    DEFAULT_MODEL,
    DEFAULT_PARAM_YAML,
    DEFAULT_PRICE,
    DEFAULT_PV,
    DEFAULT_SELECTED_ROOT,
    DEFAULT_WEATHER,
    EPLUS_ROOT,
    cyclic_lookup,
    ensure_path,
    load_external_series,
    read_yaml,
)
from .forecast import ForecastProvider
from .mpc_adapter import rbc_action, solve_energyplus_mpc_action


TEMP_CHARGE_BLOCK_C = 26.0
TEMP_ASSIST_C = 26.5
TEMP_HARD_C = 26.8
TEMP_FAN_ASSIST_C = 25.2
TEMP_FAN_PREP_C = 24.8
TEMP_SOC_MIN_FOR_DISCHARGE = 0.18
TEMP_SOC_ASSIST_RESERVE = 0.25
TEMP_VIOLATION_THRESHOLD_C = 27.0


class EnergyPlusMpcRunner:
    def __init__(
        self,
        controller: str,
        max_steps: int,
        eplus_root: str | Path,
        model: str | Path,
        weather: str | Path,
        params_path: str | Path,
        baseline_timeseries: str | Path,
        price_csv: str | Path,
        pv_csv: str | Path,
        raw_output_dir: str | Path,
        selected_output_root: str | Path,
        horizon_steps: int = 8,
        mode_integrality: str = "relaxed",
        load_forecast: str = "baseline",
        record_start_step: str | int = "auto",
        max_signed_du: float = 1.0,
        tes_capacity_mwh_th: float | None = None,
        tes_q_abs_max_kw_th: float | None = None,
        scenario_id: str = "",
        case_metadata: dict[str, Any] | None = None,
    ):
        self.controller = controller
        self.max_steps = int(max_steps)
        self.eplus_root = ensure_path(eplus_root, "EnergyPlus install", file=False)
        self.model = ensure_path(model, "EnergyPlus model")
        self.weather = ensure_path(weather, "EnergyPlus weather")
        self.params = self._apply_runtime_overrides(
            read_yaml(params_path),
            tes_capacity_mwh_th=tes_capacity_mwh_th,
            tes_q_abs_max_kw_th=tes_q_abs_max_kw_th,
        )
        self.baseline_timeseries = ensure_path(baseline_timeseries, "baseline timeseries")
        self.price_csv = ensure_path(price_csv, "price CSV")
        self.pv_csv = ensure_path(pv_csv, "PV CSV")
        self.raw_output_dir = Path(raw_output_dir)
        self.selected_output_root = Path(selected_output_root)
        self.horizon_steps = int(horizon_steps)
        self.mode_integrality = mode_integrality
        self.load_forecast = load_forecast
        self.max_signed_du = float(max_signed_du)
        self.scenario_id = scenario_id
        self.case_metadata = dict(case_metadata or {})
        self.critical_peak_windows = self.case_metadata.get("critical_peak_windows", [])
        self.critical_peak_uplift = float(self.case_metadata.get("critical_peak_uplift", 0.0) or 0.0)
        self.reserve_tes_for_critical_peak = bool(self.case_metadata.get("reserve_tes_for_critical_peak", False))
        self.tes_enabled = (
            float(self.params.get("tes", {}).get("capacity_kwh_th_proxy", 0.0)) > 0.0
            and float(self.params.get("tes", {}).get("q_abs_max_kw_th_proxy", 0.0)) > 0.0
        )
        self.forecast = ForecastProvider(
            str(self.baseline_timeseries),
            str(self.price_csv),
            str(self.pv_csv),
            horizon_steps=self.horizon_steps,
        )
        self.record_start_step = self._resolve_record_start_step(record_start_step)
        self.external = load_external_series(self.price_csv, self.pv_csv)
        self.action_rows: list[dict[str, Any]] = []
        self.observation_rows: list[dict[str, Any]] = []
        self.solver_rows: list[dict[str, Any]] = []
        self.handle_map: dict[str, Any] = {}
        self.fatal_error = ""
        self._handles_ready = False
        self._var_handles: dict[str, int] = {}
        self._meter_handles: dict[str, int] = {}
        self._actuator_handles: dict[str, int] = {}
        self._last_tes_set = 0.0
        self._simulation_step = 0

    def _apply_runtime_overrides(
        self,
        params: dict[str, Any],
        tes_capacity_mwh_th: float | None,
        tes_q_abs_max_kw_th: float | None,
    ) -> dict[str, Any]:
        out = deepcopy(params)
        tes = out.setdefault("tes", {})
        if tes_capacity_mwh_th is not None:
            capacity = float(tes_capacity_mwh_th)
            if capacity < 0:
                raise ValueError("tes_capacity_mwh_th must be non-negative")
            tes["capacity_kwh_th_proxy"] = capacity * 1000.0
            tes["runtime_capacity_mwh_th"] = capacity
            if capacity == 0:
                tes["q_abs_max_kw_th_proxy"] = 0.0
        if tes_q_abs_max_kw_th is not None and float(tes.get("capacity_kwh_th_proxy", 0.0)) > 0.0:
            q_abs = float(tes_q_abs_max_kw_th)
            if q_abs < 0:
                raise ValueError("tes_q_abs_max_kw_th must be non-negative")
            tes["q_abs_max_kw_th_proxy"] = q_abs
        return out

    def run(self) -> Path:
        api = self._load_api()
        state = api.state_manager.new_state()
        exchange = api.exchange
        runtime = api.runtime
        self.raw_output_dir.mkdir(parents=True, exist_ok=True)
        self.selected_output_root.mkdir(parents=True, exist_ok=True)

        for spec in self.params["variables"].values():
            exchange.request_variable(state, spec["variable_name"], spec["key"])

        def on_begin_timestep(current_state):
            if not exchange.api_data_fully_ready(current_state):
                return
            if not self._resolve_handles(exchange, current_state):
                self._stop(runtime, current_state)
                return
            if exchange.warmup_flag(current_state):
                self._set_tes(exchange, current_state, 0.0)
                return
            simulation_step = self._simulation_step
            if simulation_step < self.record_start_step:
                self._set_tes(exchange, current_state, 0.0)
                return
            step = simulation_step - self.record_start_step
            if step >= self.max_steps:
                self._set_tes(exchange, current_state, 0.0)
                self._stop(runtime, current_state)
                return
            timestamp = self._timestamp_for_step(simulation_step)
            observation = self._read_observation(exchange, current_state, step, simulation_step, timestamp)
            action = self._choose_action(observation, step, simulation_step, timestamp)
            self._apply_rate_limit(action)
            self._set_tes(exchange, current_state, float(action["tes_set"]))
            self._set_hvac_controls(exchange, current_state, action)
            action["tes_set_written"] = float(action["tes_set"])
            self.action_rows.append(action)

        def on_end_timestep(current_state):
            if not exchange.api_data_fully_ready(current_state) or exchange.warmup_flag(current_state):
                return
            if not self._handles_ready:
                return
            simulation_step = self._simulation_step
            if simulation_step < self.record_start_step:
                self._simulation_step += 1
                return
            step = simulation_step - self.record_start_step
            if step >= self.max_steps:
                self._stop(runtime, current_state)
                return
            timestamp = self._timestamp_for_step(simulation_step)
            row = self._read_observation(exchange, current_state, step, simulation_step, timestamp)
            row["tes_set_command"] = self.action_rows[step]["tes_set_written"] if step < len(self.action_rows) else 0.0
            self.observation_rows.append(row)
            self._simulation_step += 1
            if len(self.observation_rows) >= self.max_steps:
                self._stop(runtime, current_state)

        runtime.callback_begin_system_timestep_before_predictor(state, on_begin_timestep)
        runtime.callback_end_zone_timestep_after_zone_reporting(state, on_end_timestep)
        start = time.perf_counter()
        exit_code = runtime.run_energyplus(
            state,
            ["-w", str(self.weather), "-d", str(self.raw_output_dir), str(self.model)],
        )
        elapsed = time.perf_counter() - start
        api.state_manager.delete_state(state)
        if self.fatal_error:
            raise RuntimeError(self.fatal_error)
        case_dir = self._write_selected_outputs(exit_code, elapsed)
        return case_dir

    def _load_api(self):
        root = str(self.eplus_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(root)
        from pyenergyplus.api import EnergyPlusAPI

        return EnergyPlusAPI()

    def _resolve_handles(self, exchange, state) -> bool:
        if self._handles_ready:
            return True
        self._var_handles = {
            name: exchange.get_variable_handle(state, spec["variable_name"], spec["key"])
            for name, spec in self.params["variables"].items()
        }
        self._meter_handles = {name: exchange.get_meter_handle(state, meter) for name, meter in self.params["meters"].items()}
        self._actuator_handles = {
            name: exchange.get_actuator_handle(state, spec["component_type"], spec["control_type"], spec["key"])
            for name, spec in self.params["actuators"].items()
        }
        missing = [
            f"variable:{name}" for name, handle in self._var_handles.items() if handle < 0
        ] + [
            f"meter:{name}" for name, handle in self._meter_handles.items() if handle < 0
        ] + [
            f"actuator:{name}" for name, handle in self._actuator_handles.items() if handle < 0
        ]
        self.handle_map = {
            "variables": self._var_handles,
            "meters": self._meter_handles,
            "actuators": self._actuator_handles,
            "missing": missing,
        }
        if missing:
            self.fatal_error = "EnergyPlus API handle resolution failed: " + ", ".join(missing)
            return False
        self._handles_ready = True
        return True

    def _set_tes(self, exchange, state, value: float) -> None:
        value = float(np.clip(value, -1.0, 1.0))
        exchange.set_actuator_value(state, self._actuator_handles["tes_set"], value)
        self._last_tes_set = value

    def _resolve_record_start_step(self, value: str | int) -> int:
        if isinstance(value, int):
            return max(0, value)
        text = str(value).strip().lower()
        if text != "auto":
            return max(0, int(text))
        baseline = self.forecast.baseline
        if "chiller_cooling_kw" not in baseline:
            return 0
        window_len = min(max(self.max_steps, 1), 96)
        threshold_kw = 1000.0
        min_active = max(4, int(window_len * 0.25))
        for idx in range(0, max(1, len(baseline) - window_len)):
            window = baseline.iloc[idx : idx + window_len]
            if int((window["chiller_cooling_kw"] > threshold_kw).sum()) >= min_active:
                return int(idx)
        return 0

    def _choose_action(self, observation: dict[str, Any], step: int, simulation_step: int, timestamp: datetime) -> dict[str, Any]:
        price = float(self._external_value(self.external.price_per_kwh, timestamp))
        pv = float(self._external_value(self.external.pv_kw, timestamp))
        base = {
            "step": step,
            "simulation_step": simulation_step,
            "timestamp": timestamp.isoformat(sep=" "),
            "controller": self.controller,
            "price_per_kwh": price,
            "pv_kw": pv,
            "soc": observation["soc"],
            "tes_set": 0.0,
            "q_tes_net_kw_th_pred": 0.0,
            "q_chiller_kw_th_pred": 0.0,
            "solver_status": "not_used",
            "solver_time_s": 0.0,
            "fallback": False,
            "fallback_reason": "",
            "tes_set_before_safety": 0.0,
            "safety_override": False,
            "safety_reason": "",
            "tes_set_before_peak_reserve": 0.0,
            "peak_reserve_override": False,
            "tes_set_before_rate_limit": 0.0,
            "rate_limit_override": False,
            "crah_fan_set": 0.0,
            "crah_t_set": 0.0,
            "chiller_t_set": 0.0,
        }
        if self.controller == "no_control":
            return base
        if self.controller == "perturbation":
            profile = [-1.0, -0.5, 0.0, 0.5, 1.0, 0.0, 0.5, -0.5]
            base["tes_set"] = profile[step % len(profile)]
            return base
        if self.controller == "rbc":
            price_values = self.external.price_per_kwh.to_numpy(dtype=float)
            base["tes_set"] = rbc_action(price, float(np.quantile(price_values, 0.30)), float(np.quantile(price_values, 0.70)), observation["soc"])
            return base
        if self.controller == "mpc":
            forecast = self.forecast.horizon(simulation_step, timestamp, self.load_forecast)
            try:
                result = solve_energyplus_mpc_action(self.params, forecast, observation["soc"], self.mode_integrality)
                base.update(result)
            except Exception as exc:  # noqa: BLE001 - controller diagnostics must capture solver errors
                base["fallback"] = True
                base["fallback_reason"] = str(exc)
                self.solver_rows.append(dict(base))
                raise
            self._apply_temperature_guard(base, observation)
            self._apply_peak_reserve_guard(base, timestamp)
            self.solver_rows.append(dict(base))
            return base
        raise ValueError(f"unsupported controller: {self.controller}")

    def _apply_temperature_guard(self, action: dict[str, Any], observation: dict[str, Any]) -> None:
        action["tes_set_before_safety"] = float(action["tes_set"])
        action["safety_override"] = False
        action["safety_reason"] = ""
        zone_temp = float(observation.get("zone_temp_c", np.nan))
        soc = float(observation.get("soc", np.nan))
        if not np.isfinite(zone_temp):
            return

        guarded_tes_set = float(action["tes_set"])
        reason = ""
        if zone_temp >= TEMP_FAN_ASSIST_C:
            action["crah_fan_set"] = 1.0
            action["crah_t_set"] = 0.0
            action["chiller_t_set"] = 0.0
        elif zone_temp >= TEMP_FAN_PREP_C:
            action["crah_fan_set"] = 0.75
            action["crah_t_set"] = 0.0
            action["chiller_t_set"] = 0.0

        if not self.tes_enabled:
            if guarded_tes_set != 0.0:
                guarded_tes_set = 0.0
                reason = "tes_disabled"
        elif zone_temp >= TEMP_HARD_C:
            if np.isfinite(soc) and soc > TEMP_SOC_MIN_FOR_DISCHARGE:
                guarded_tes_set = max(guarded_tes_set, 1.0)
                reason = "hard_temperature_discharge"
            else:
                guarded_tes_set = max(guarded_tes_set, 0.0)
                reason = "hard_temperature_charge_block"
        elif zone_temp >= TEMP_ASSIST_C:
            if np.isfinite(soc) and soc > TEMP_SOC_ASSIST_RESERVE:
                guarded_tes_set = max(guarded_tes_set, 0.75)
                reason = "warm_temperature_assist"
            elif guarded_tes_set < 0.0:
                guarded_tes_set = 0.0
                reason = "warm_temperature_charge_block"
        elif zone_temp >= TEMP_CHARGE_BLOCK_C and guarded_tes_set < 0.0:
            guarded_tes_set = 0.0
            reason = "charge_block_near_temperature_limit"

        guarded_tes_set = float(np.clip(guarded_tes_set, -1.0, 1.0))
        if abs(guarded_tes_set - float(action["tes_set"])) > 1e-9:
            action["tes_set"] = guarded_tes_set
            action["safety_override"] = True
            action["safety_reason"] = reason

    def _apply_peak_reserve_guard(self, action: dict[str, Any], timestamp: datetime) -> None:
        action["tes_set_before_peak_reserve"] = float(action["tes_set"])
        action["peak_reserve_override"] = False
        if not self.reserve_tes_for_critical_peak or self.critical_peak_uplift <= 0.0:
            return
        if self._in_critical_peak(timestamp) or float(action["tes_set"]) <= 0.0:
            return
        if action.get("safety_override") and "temperature" in str(action.get("safety_reason", "")):
            return
        action["tes_set"] = 0.0
        action["peak_reserve_override"] = True

    def _in_critical_peak(self, timestamp: datetime) -> bool:
        hour = timestamp.hour + timestamp.minute / 60.0 + timestamp.second / 3600.0
        for window in self.critical_peak_windows or []:
            if len(window) != 2:
                continue
            start, end = float(window[0]), float(window[1])
            if start <= hour < end:
                return True
        return False

    def _apply_rate_limit(self, action: dict[str, Any]) -> None:
        action["tes_set_before_rate_limit"] = float(action["tes_set"])
        action["rate_limit_override"] = False
        limit = max(0.0, float(self.max_signed_du))
        if limit >= 1.0:
            return
        previous = float(self._last_tes_set)
        requested = float(action["tes_set"])
        delta = requested - previous
        if abs(delta) <= limit + 1e-12:
            return
        action["tes_set"] = float(previous + np.sign(delta) * limit)
        action["rate_limit_override"] = True

    def _set_hvac_controls(self, exchange, state, action: dict[str, Any]) -> None:
        for name in ("crah_fan_set", "crah_t_set", "chiller_t_set"):
            handle = self._actuator_handles.get(name)
            if handle is None or handle < 0:
                continue
            exchange.set_actuator_value(state, handle, float(np.clip(action.get(name, 0.0), 0.0, 1.0)))

    def _read_observation(self, exchange, state, step: int, simulation_step: int, timestamp: datetime) -> dict[str, Any]:
        values = {name: exchange.get_variable_value(state, handle) for name, handle in self._var_handles.items()}
        meters = {name: exchange.get_meter_value(state, handle) for name, handle in self._meter_handles.items()}
        dt_hours = float(self.params["energyplus"].get("dt_hours", 0.25))
        facility_kw = float(meters["facility_electricity_j"]) / (dt_hours * 3600.0 * 1000.0)
        purchased_kw = float(meters["purchased_electricity_j"]) / (dt_hours * 3600.0 * 1000.0)
        pv = float(self._external_value(self.external.pv_kw, timestamp))
        price = float(self._external_value(self.external.price_per_kwh, timestamp))
        grid_import_kw = max(0.0, facility_kw - pv)
        return {
            "step": step,
            "simulation_step": simulation_step,
            "timestamp": timestamp.isoformat(sep=" "),
            "soc": float(values["tes_soc"]),
            "tes_avg_temp_c": float(values["tes_avg_temp"]),
            "tes_set_echo": float(values["tes_set_echo"]),
            "tes_use_avail_echo": float(values["tes_use_avail_echo"]) if "tes_use_avail_echo" in values else np.nan,
            "tes_source_avail_echo": float(values["tes_source_avail_echo"]) if "tes_source_avail_echo" in values else np.nan,
            "chiller_avail_echo": float(values["chiller_avail_echo"]) if "chiller_avail_echo" in values else np.nan,
            "tes_use_side_kw": float(values["tes_use_heat_transfer_w"]) / 1000.0,
            "tes_source_side_kw": float(values["tes_source_heat_transfer_w"]) / 1000.0,
            "tes_tank_temp_c": float(values["tes_tank_temp_c"]),
            "zone_temp_c": float(values["zone_temp_c"]),
            "outdoor_drybulb_c": float(values["outdoor_drybulb_c"]),
            "outdoor_wetbulb_c": float(values["outdoor_wetbulb_c"]),
            "chiller_electricity_kw": float(values["chiller_electricity_w"]) / 1000.0,
            "chiller_cooling_kw": float(values["chiller_cooling_w"]) / 1000.0,
            "facility_electricity_kw": facility_kw,
            "purchased_electricity_kw": purchased_kw,
            "pv_kw": pv,
            "grid_import_kw": grid_import_kw,
            "pv_adjusted_cost": grid_import_kw * price * dt_hours,
            "price_per_kwh": price,
        }

    def _timestamp_for_step(self, simulation_step: int) -> datetime:
        row = self.forecast.baseline.iloc[simulation_step % len(self.forecast.baseline)]
        return pd.Timestamp(row["interval_start"]).to_pydatetime()

    def _external_value(self, series: pd.Series, timestamp: datetime) -> float:
        return float(cyclic_lookup(series, [timestamp])[0])

    def _stop(self, runtime, state) -> None:
        try:
            runtime.api.stopSimulation(state)
        except Exception:
            pass

    def _write_selected_outputs(self, exit_code: int, elapsed_s: float) -> Path:
        case_dir = self.selected_output_root / self.controller
        case_dir.mkdir(parents=True, exist_ok=True)
        obs = pd.DataFrame(self.observation_rows)
        actions = pd.DataFrame(self.action_rows)
        solver = pd.DataFrame(self.solver_rows)
        monitor = obs.merge(actions, on=["step", "simulation_step", "timestamp"], how="left", suffixes=("", "_action"))
        obs.to_csv(case_dir / "observation.csv", index=False)
        actions.to_csv(case_dir / "mpc_action.csv", index=False)
        solver.to_csv(case_dir / "solver_log.csv", index=False)
        monitor.to_csv(case_dir / "monitor.csv", index=False)
        summary = _summarize_monitor(monitor, self.controller, exit_code, elapsed_s)
        pd.DataFrame([summary]).to_csv(case_dir / "summary.csv", index=False)
        (case_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (case_dir / "handle_map.json").write_text(json.dumps(self.handle_map, indent=2), encoding="utf-8")
        manifest = {
            "scenario_id": self.scenario_id,
            "controller": self.controller,
            "max_steps": self.max_steps,
            "record_start_step": self.record_start_step,
            "max_signed_du": self.max_signed_du,
            "raw_output_dir": str(self.raw_output_dir),
            "selected_output_dir": str(case_dir),
            "model": str(self.model),
            "weather": str(self.weather),
            "params": self.params.get("source", {}),
            "mode_integrality": self.mode_integrality,
            "load_forecast": self.load_forecast,
            "exit_code": exit_code,
            "case_metadata": self.case_metadata,
        }
        (case_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        err = self.raw_output_dir / "eplusout.err"
        if err.exists():
            shutil.copy2(err, case_dir / "eplusout.err")
            warning_summary = _parse_err(err)
            (case_dir / "warning_summary.json").write_text(json.dumps(warning_summary, indent=2), encoding="utf-8")
        return case_dir


def _summarize_monitor(monitor: pd.DataFrame, controller: str, exit_code: int, elapsed_s: float) -> dict[str, Any]:
    if monitor.empty:
        return {"controller": controller, "steps": 0, "exit_code": exit_code, "elapsed_s": elapsed_s}
    fallback_count = int(monitor.get("fallback", pd.Series(dtype=bool)).fillna(False).sum())
    temp_above_27 = monitor["zone_temp_c"].sub(TEMP_VIOLATION_THRESHOLD_C).clip(lower=0.0)
    temp_above_30 = monitor["zone_temp_c"].sub(30.0).clip(lower=0.0)
    safety_override_count = int(monitor.get("safety_override", pd.Series(dtype=bool)).fillna(False).sum())
    crah_fan_assist_count = int((monitor.get("crah_fan_set", pd.Series(dtype=float)).fillna(0.0) > 0.5).sum())
    return {
        "controller": controller,
        "steps": int(len(monitor)),
        "record_start_step": int(monitor["simulation_step"].iloc[0]) if "simulation_step" in monitor else 0,
        "first_timestamp": str(monitor["timestamp"].iloc[0]),
        "last_timestamp": str(monitor["timestamp"].iloc[-1]),
        "exit_code": int(exit_code),
        "elapsed_s": float(elapsed_s),
        "fallback_count": fallback_count,
        "safety_override_count": safety_override_count,
        "crah_fan_assist_count": crah_fan_assist_count,
        "facility_energy_kwh": float((monitor["facility_electricity_kw"] * 0.25).sum()),
        "pv_adjusted_grid_kwh": float((monitor["grid_import_kw"] * 0.25).sum()),
        "pv_adjusted_cost": float(monitor["pv_adjusted_cost"].sum()),
        "peak_facility_kw": float(monitor["facility_electricity_kw"].max()),
        "peak_grid_kw": float(monitor["grid_import_kw"].max()),
        "soc_min": float(monitor["soc"].min()),
        "soc_max": float(monitor["soc"].max()),
        "soc_final": float(monitor["soc"].iloc[-1]),
        "zone_temp_min_c": float(monitor["zone_temp_c"].min()),
        "zone_temp_max_c": float(monitor["zone_temp_c"].max()),
        "temp_violation_threshold_c": TEMP_VIOLATION_THRESHOLD_C,
        "temp_violation_count_gt27c": int((monitor["zone_temp_c"] > TEMP_VIOLATION_THRESHOLD_C).sum()),
        "temp_violation_hours_gt27c": float((monitor["zone_temp_c"] > TEMP_VIOLATION_THRESHOLD_C).sum() * 0.25),
        "temp_violation_ratio_gt27c": float((monitor["zone_temp_c"] > TEMP_VIOLATION_THRESHOLD_C).mean()),
        "temp_violation_degree_hours_gt27c": float((temp_above_27 * 0.25).sum()),
        "temp_violation_count_gt30c": int((monitor["zone_temp_c"] > 30.0).sum()),
        "temp_violation_hours_gt30c": float((monitor["zone_temp_c"] > 30.0).sum() * 0.25),
        "temp_violation_ratio_gt30c": float((monitor["zone_temp_c"] > 30.0).mean()),
        "temp_violation_degree_hours_gt30c": float((temp_above_30 * 0.25).sum()),
        "tes_set_mismatch_count": int((monitor["tes_set_echo"].sub(monitor["tes_set_written"]).abs() > 1e-6).sum())
        if "tes_set_written" in monitor
        else -1,
        "tes_use_response_count": int(((monitor.get("tes_set_written", 0.0) > 0.01) & (monitor["tes_use_side_kw"].abs() > 1e-4)).sum()),
        "tes_source_response_count": int(((monitor.get("tes_set_written", 0.0) < -0.01) & (monitor["tes_source_side_kw"].abs() > 1e-4)).sum()),
    }


def _parse_err(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "severe_errors": text.count("** Severe  **"),
        "total_warning": text.count("** Warning **"),
        "cooling_tower_air_flow_ratio_failed": text.count("CoolingTower:VariableSpeed"),
        "tower_approach_out_of_range": text.count("Tower approach"),
        "tower_range_out_of_range": text.count("Tower range"),
        "wetbulb_out_of_range": text.count("wet-bulb"),
    }


def default_raw_output(controller: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return EPLUS_ROOT / "out" / f"energyplus_mpc_{controller}_{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller", choices=["no_control", "rbc", "mpc", "perturbation"], required=True)
    parser.add_argument("--max-steps", type=int, default=96)
    parser.add_argument("--energyplus-root", default=str(DEFAULT_EPLUS_INSTALL))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--weather", default=str(DEFAULT_WEATHER))
    parser.add_argument("--params", default=str(DEFAULT_PARAM_YAML))
    parser.add_argument("--baseline-timeseries", default=str(DEFAULT_BASELINE_TIMESERIES))
    parser.add_argument("--price-csv", default=str(DEFAULT_PRICE))
    parser.add_argument("--pv-csv", default=str(DEFAULT_PV))
    parser.add_argument("--raw-output-dir")
    parser.add_argument("--selected-output-root", default=str(DEFAULT_SELECTED_ROOT))
    parser.add_argument("--horizon-steps", type=int, default=8)
    parser.add_argument("--mode-integrality", choices=["strict", "relaxed"], default="relaxed")
    parser.add_argument("--load-forecast", choices=["baseline", "persistence"], default="baseline")
    parser.add_argument("--max-signed-du", type=float, default=1.0)
    parser.add_argument("--tes-capacity-mwh-th", type=float, default=None)
    parser.add_argument("--tes-q-abs-max-kw-th", type=float, default=None)
    parser.add_argument("--scenario-id", default="")
    parser.add_argument(
        "--case-metadata-json",
        default="{}",
        help="JSON object copied into run_manifest.json for scenario-level provenance.",
    )
    parser.add_argument(
        "--record-start-step",
        default="auto",
        help="EnergyPlus non-warmup timestep to start recording/control from, or 'auto' for the first active chiller window.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    raw = Path(args.raw_output_dir) if args.raw_output_dir else default_raw_output(args.controller)
    metadata = json.loads(args.case_metadata_json)
    if not isinstance(metadata, dict):
        raise ValueError("--case-metadata-json must decode to a JSON object")
    runner = EnergyPlusMpcRunner(
        controller=args.controller,
        max_steps=args.max_steps,
        eplus_root=args.energyplus_root,
        model=args.model,
        weather=args.weather,
        params_path=args.params,
        baseline_timeseries=args.baseline_timeseries,
        price_csv=args.price_csv,
        pv_csv=args.pv_csv,
        raw_output_dir=raw,
        selected_output_root=args.selected_output_root,
        horizon_steps=args.horizon_steps,
        mode_integrality=args.mode_integrality,
        load_forecast=args.load_forecast,
        record_start_step=args.record_start_step,
        max_signed_du=args.max_signed_du,
        tes_capacity_mwh_th=args.tes_capacity_mwh_th,
        tes_q_abs_max_kw_th=args.tes_q_abs_max_kw_th,
        scenario_id=args.scenario_id,
        case_metadata=metadata,
    )
    case_dir = runner.run()
    print(case_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
