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
        sampling_profile: dict[str, Any] | None = None,
    ):
        self.controller = controller
        self.max_steps = int(max_steps)
        self.eplus_root = ensure_path(eplus_root, "EnergyPlus install", file=False)
        self.model = ensure_path(model, "EnergyPlus model")
        self.weather = ensure_path(weather, "EnergyPlus weather")
        self.params = read_yaml(params_path)
        self.baseline_timeseries = ensure_path(baseline_timeseries, "baseline timeseries")
        self.price_csv = ensure_path(price_csv, "price CSV")
        self.pv_csv = ensure_path(pv_csv, "PV CSV")
        self.raw_output_dir = Path(raw_output_dir)
        self.selected_output_root = Path(selected_output_root)
        self.horizon_steps = int(horizon_steps)
        self.mode_integrality = mode_integrality
        self.load_forecast = load_forecast
        self.sampling_profile = sampling_profile or {}
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
            self._apply_sampling_actuators(exchange, current_state, action)
            self._set_tes(exchange, current_state, float(action["tes_set"]))
            action["tes_set_written"] = float(action["tes_set"])
            if "ite_set" in action:
                action["ite_set_written"] = float(action["ite_set"])
            if "chiller_t_set" in action:
                action["chiller_t_set_written"] = float(action["chiller_t_set"])
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
        self._set_actuator(exchange, state, "tes_set", value)

    def _set_actuator(self, exchange, state, name: str, value: float) -> None:
        value = float(np.clip(value, -1.0, 1.0))
        exchange.set_actuator_value(state, self._actuator_handles[name], value)
        if name == "tes_set":
            self._last_tes_set = value

    def _apply_sampling_actuators(self, exchange, state, action: dict[str, Any]) -> None:
        if "ite_set" in action and "ite_set" in self._actuator_handles:
            self._set_actuator(exchange, state, "ite_set", float(action["ite_set"]))
        if "chiller_t_set" in action and "chiller_t_set" in self._actuator_handles:
            self._set_actuator(exchange, state, "chiller_t_set", float(action["chiller_t_set"]))

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
        }
        if self.controller == "no_control":
            return base
        if self.controller == "perturbation":
            profile = [-1.0, -0.5, 0.0, 0.5, 1.0, 0.0, 0.5, -0.5]
            base["tes_set"] = profile[step % len(profile)]
            return base
        if self.controller == "sampling":
            base.update(self._sampling_values(timestamp, simulation_step))
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
            self.solver_rows.append(dict(base))
            return base
        raise ValueError(f"unsupported controller: {self.controller}")

    def _sampling_values(self, timestamp: datetime, simulation_step: int) -> dict[str, Any]:
        family = str(self.sampling_profile.get("family", "sampling"))
        values = {
            "case_id": self.sampling_profile.get("case_id", "sampling"),
            "sampling_family": family,
            "identification_only": bool(self.sampling_profile.get("identification_only", True)),
            "ite_set": float(self.sampling_profile.get("ite_set", 0.45)),
            "chiller_t_set": float(self.sampling_profile.get("chiller_t_set", 0.0)),
            "tes_set": 0.0,
        }
        if family == "tes_pulse":
            pulse = float(self.sampling_profile["tes_set"])
            hour = timestamp.hour + timestamp.minute / 60.0
            if hour < 4.0:
                values["tes_set"] = -0.5 if pulse > 0.0 else 0.5
            elif hour < 10.0:
                values["tes_set"] = 0.0
            elif hour < 14.0:
                values["tes_set"] = pulse
            else:
                values["tes_set"] = 0.0
        elif family == "combined":
            seed = int(self.sampling_profile.get("seed", 0))
            day_index = int(simulation_step // 96)
            rng = np.random.default_rng(seed * 1000003 + day_index)
            ite_levels = np.asarray([0.35, 0.45, 0.55], dtype=float)
            chiller_levels = np.asarray([0.0, 0.5, 1.0], dtype=float)
            amp_levels = np.asarray([0.25, 0.5, 0.75, 1.0], dtype=float)
            values["ite_set"] = float(ite_levels[(day_index + seed) % len(ite_levels)])
            values["chiller_t_set"] = float(chiller_levels[(day_index + 2 * seed) % len(chiller_levels)])
            amplitude = float(rng.choice(amp_levels))
            block = int((timestamp.hour * 4 + timestamp.minute // 15) // 16)
            sign = 1.0 if ((block + day_index + seed) % 2 == 0) else -1.0
            values["tes_set"] = float(sign * amplitude)
        else:
            values["tes_set"] = float(self.sampling_profile.get("tes_set", 0.0))
        values["tes_set"] = float(np.clip(values["tes_set"], -1.0, 1.0))
        values["ite_set"] = float(np.clip(values["ite_set"], 0.0, 1.0))
        values["chiller_t_set"] = float(np.clip(values["chiller_t_set"], 0.0, 1.0))
        return values

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
            "ite_set_echo": float(values["ite_set_echo"]) if "ite_set_echo" in values else np.nan,
            "chiller_t_set_echo": float(values["chiller_t_set_echo"]) if "chiller_t_set_echo" in values else np.nan,
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
        case_name = str(self.sampling_profile.get("case_id", self.controller)) if self.controller == "sampling" else self.controller
        case_dir = self.selected_output_root / case_name
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
            "controller": self.controller,
            "max_steps": self.max_steps,
            "record_start_step": self.record_start_step,
            "raw_output_dir": str(self.raw_output_dir),
            "selected_output_dir": str(case_dir),
            "model": str(self.model),
            "weather": str(self.weather),
            "params": self.params.get("source", {}),
            "mode_integrality": self.mode_integrality,
            "load_forecast": self.load_forecast,
            "sampling_profile": self.sampling_profile,
            "exit_code": exit_code,
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
    return {
        "controller": controller,
        "steps": int(len(monitor)),
        "record_start_step": int(monitor["simulation_step"].iloc[0]) if "simulation_step" in monitor else 0,
        "first_timestamp": str(monitor["timestamp"].iloc[0]),
        "last_timestamp": str(monitor["timestamp"].iloc[-1]),
        "exit_code": int(exit_code),
        "elapsed_s": float(elapsed_s),
        "fallback_count": fallback_count,
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
        "tes_set_mismatch_count": int((monitor["tes_set_echo"].sub(monitor["tes_set_written"]).abs() > 1e-6).sum())
        if "tes_set_written" in monitor
        else -1,
        "ite_set_mismatch_count": int((monitor["ite_set_echo"].sub(monitor["ite_set_written"]).abs() > 1e-6).sum())
        if "ite_set_written" in monitor and "ite_set_echo" in monitor
        else 0,
        "chiller_t_set_mismatch_count": int((monitor["chiller_t_set_echo"].sub(monitor["chiller_t_set_written"]).abs() > 1e-6).sum())
        if "chiller_t_set_written" in monitor and "chiller_t_set_echo" in monitor
        else 0,
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
    parser.add_argument("--controller", choices=["no_control", "rbc", "mpc", "perturbation", "sampling"], required=True)
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
    parser.add_argument(
        "--record-start-step",
        default="auto",
        help="EnergyPlus non-warmup timestep to start recording/control from, or 'auto' for the first active chiller window.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    raw = Path(args.raw_output_dir) if args.raw_output_dir else default_raw_output(args.controller)
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
    )
    case_dir = runner.run()
    print(case_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
