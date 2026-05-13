"""Helpers for Phase 3 online MPC+EnergyPlus scenario runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SOC_COLD_TEMP_C = 6.67
SOC_HOT_TEMP_C = 12.0
WATER_KWH_PER_M3K = 1.163
WATER_CP_KJ_PER_KGK = 4.186


def tes_capacity_to_tank_volume_m3(
    capacity_mwh_th: float,
    cold_temp_c: float = SOC_COLD_TEMP_C,
    hot_temp_c: float = SOC_HOT_TEMP_C,
) -> float:
    """Convert chilled-water TES capacity to EnergyPlus tank volume."""

    capacity = float(capacity_mwh_th)
    if capacity < 0:
        raise ValueError("capacity_mwh_th must be non-negative")
    delta_t = float(hot_temp_c) - float(cold_temp_c)
    if delta_t <= 0:
        raise ValueError("hot_temp_c must be greater than cold_temp_c")
    if capacity == 0:
        return 0.0
    return capacity * 1000.0 / (WATER_KWH_PER_M3K * delta_t)


def tes_power_to_flow_kg_s(
    q_abs_max_kw_th: float,
    cold_temp_c: float = SOC_COLD_TEMP_C,
    hot_temp_c: float = SOC_HOT_TEMP_C,
) -> float:
    """Return water mass flow for a requested thermal power and DeltaT."""

    q_abs = float(q_abs_max_kw_th)
    if q_abs < 0:
        raise ValueError("q_abs_max_kw_th must be non-negative")
    delta_t = float(hot_temp_c) - float(cold_temp_c)
    if delta_t <= 0:
        raise ValueError("hot_temp_c must be greater than cold_temp_c")
    return q_abs / (WATER_CP_KJ_PER_KGK * delta_t) if q_abs else 0.0


def write_scenario_model(
    base_model_path: str | Path,
    output_path: str | Path,
    tes_capacity_mwh_th: float,
    q_abs_max_kw_th: float,
) -> Path:
    """Write an epJSON copy with scenario TES volume and fixed TES power."""

    base_model_path = Path(base_model_path)
    output_path = Path(output_path)
    model = json.loads(base_model_path.read_text(encoding="utf-8"))
    capacity = float(tes_capacity_mwh_th)
    q_abs = float(q_abs_max_kw_th) if capacity > 0 else 0.0
    flow = tes_power_to_flow_kg_s(q_abs)
    if capacity > 0:
        tank = model["ThermalStorage:ChilledWater:Mixed"]["Chilled Water Tank"]
        tank["tank_volume"] = round(tes_capacity_to_tank_volume_m3(capacity), 6)
        tank["nominal_cooling_capacity"] = round(q_abs * 1000.0, 6)
        tank["tank_recovery_time"] = max(1.0, round(capacity * 1000.0 / max(q_abs, 1e-9), 6))
    _replace_ems_flow(model, flow)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return output_path


def _replace_ems_flow(model: dict[str, Any], flow_kg_s: float) -> None:
    flow_text = f"{float(flow_kg_s):.6f}".rstrip("0").rstrip(".")
    programs = model.get("EnergyManagementSystem:Program", {})
    for program in programs.values():
        for line in program.get("lines", []):
            text = str(line.get("program_line", ""))
            if text.strip().startswith("SET Max_Flow ="):
                line["program_line"] = f"SET Max_Flow = {flow_text}"
            elif "SET Flow_Now = @Abs TES_Signal_Now *" in text:
                prefix = text.split("*", 1)[0].rstrip()
                line["program_line"] = f"{prefix} * {flow_text}"
