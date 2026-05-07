"""Extract static EnergyPlus model parameters for MPC coupling."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .common import DEFAULT_MODEL, DEFAULT_PARAM_YAML, EPLUS_ROOT, write_yaml


def extract_static_params(model_path: str | Path = DEFAULT_MODEL) -> dict[str, Any]:
    model = Path(model_path)
    with model.open("r", encoding="utf-8") as fh:
        epjson = json.load(fh)
    timestep = epjson.get("Timestep", {})
    tank_name, tank = next(iter(epjson["ThermalStorage:ChilledWater:Mixed"].items()))
    schedules = epjson.get("Schedule:Constant", {})
    outputs = epjson.get("Output:Variable", {})
    actuators = epjson.get("EnergyManagementSystem:Actuator", {})
    programs = epjson.get("EnergyManagementSystem:Program", {})
    p5_lines = _program_lines(programs, "P_5")
    p6_lines = _program_lines(programs, "P_6")
    max_flow = _find_assignment_float(p5_lines, "Max_Flow")
    soc_hot = _find_assignment_float(p6_lines, "TES_SOC_HOT_TEMP")
    soc_cold = _find_assignment_float(p6_lines, "TES_SOC_COLD_TEMP")
    chiller_name = _find_output_key(outputs, "Chiller Electricity Rate")
    params = {
        "schema_version": 1,
        "source": {
            "model_path": str(model),
            "model_unmodified": True,
        },
        "energyplus": {
            "timestep_per_hour": int(next(iter(timestep.values())).get("number_of_timesteps_per_hour", 4)),
            "dt_hours": 0.25,
        },
        "tes": {
            "object_name": tank_name,
            "tank_volume_m3": float(tank["tank_volume"]),
            "nominal_cooling_capacity_w": float(tank["nominal_cooling_capacity"]),
            "capacity_kwh_th_proxy": float(tank["nominal_cooling_capacity"]) * 4.0 / 1000.0,
            "source_side_design_flow_rate": tank["source_side_design_flow_rate"],
            "use_side_design_flow_rate": tank["use_side_design_flow_rate"],
            "max_flow_kg_s_from_ems": max_flow,
            "soc_cold_temp_c": soc_cold,
            "soc_hot_temp_c": soc_hot,
            "soc_formula": "SOC = (soc_hot_temp_c - tank_avg_temp_c) / (soc_hot_temp_c - soc_cold_temp_c)",
            "soc_min": 0.15,
            "soc_max": 0.85,
            "soc_target": 0.50,
        },
        "actuators": {
            "tes_set": {"component_type": "Schedule:Constant", "control_type": "Schedule Value", "key": "TES_Set"},
            "ite_set": {"component_type": "Schedule:Constant", "control_type": "Schedule Value", "key": "ITE_Set"},
            "chiller_t_set": {"component_type": "Schedule:Constant", "control_type": "Schedule Value", "key": "Chiller_T_Set"},
        },
        "variables": {
            "tes_set_echo": {"variable_name": "Schedule Value", "key": "TES_Set"},
            "ite_set_echo": {"variable_name": "Schedule Value", "key": "ITE_Set"},
            "chiller_t_set_echo": {"variable_name": "Schedule Value", "key": "Chiller_T_Set"},
            "tes_soc": {"variable_name": "Schedule Value", "key": "TES_SOC_Obs"},
            "tes_avg_temp": {"variable_name": "Schedule Value", "key": "TES_Avg_Temp_Obs"},
            "tes_use_avail_echo": {"variable_name": "Schedule Value", "key": "TES_Use_Avail_Sch"},
            "tes_source_avail_echo": {"variable_name": "Schedule Value", "key": "TES_Source_Avail_Sch"},
            "chiller_avail_echo": {"variable_name": "Schedule Value", "key": "Chiller_Avail_Sch"},
            "tes_use_heat_transfer_w": {
                "variable_name": "Chilled Water Thermal Storage Use Side Heat Transfer Rate",
                "key": tank_name,
            },
            "tes_source_heat_transfer_w": {
                "variable_name": "Chilled Water Thermal Storage Source Side Heat Transfer Rate",
                "key": tank_name,
            },
            "tes_tank_temp_c": {
                "variable_name": "Chilled Water Thermal Storage Final Tank Temperature",
                "key": tank_name,
            },
            "zone_temp_c": {"variable_name": "Zone Air Temperature", "key": "DataCenter ZN"},
            "outdoor_drybulb_c": {"variable_name": "Site Outdoor Air DryBulb Temperature", "key": "Environment"},
            "outdoor_wetbulb_c": {"variable_name": "Site Outdoor Air WetBulb Temperature", "key": "Environment"},
            "chiller_electricity_w": {"variable_name": "Chiller Electricity Rate", "key": chiller_name},
            "chiller_cooling_w": {"variable_name": "Chiller Evaporator Cooling Rate", "key": chiller_name},
        },
        "meters": {
            "facility_electricity_j": "Electricity:Facility",
            "purchased_electricity_j": "ElectricityPurchased:Facility",
        },
        "schedules": {
            name: schedules[name]["hourly_value"]
            for name in [
                "TES_Set",
                "ITE_Set",
                "Chiller_T_Set",
                "TES_SOC_Obs",
                "TES_Avg_Temp_Obs",
                "TES_Use_Avail_Sch",
                "TES_Source_Avail_Sch",
            ]
            if name in schedules
        },
        "identified": {},
    }
    return params


def write_physical_model_doc(params: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path or EPLUS_ROOT / "docs" / "physical_model_parameters.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    tes = params["tes"]
    lines = [
        "# Physical Model Parameters",
        "",
        "This file records EnergyPlus parameters used by the MPC coupling layer.",
        "",
        "## EnergyPlus Timing",
        "",
        f"- Timesteps per hour: `{params['energyplus']['timestep_per_hour']}`",
        f"- MPC timestep: `{params['energyplus']['dt_hours']} h`",
        "",
        "## TES Object",
        "",
        f"- Object: `{tes['object_name']}`",
        f"- Tank volume: `{tes['tank_volume_m3']} m3`",
        f"- Nominal cooling capacity: `{tes['nominal_cooling_capacity_w']} W`",
        f"- Proxy thermal capacity: `{tes['capacity_kwh_th_proxy']} kWh_th`",
        f"- EMS maximum TES flow: `{tes['max_flow_kg_s_from_ems']} kg/s`",
        f"- SOC cold temperature: `{tes['soc_cold_temp_c']} C`",
        f"- SOC hot temperature: `{tes['soc_hot_temp_c']} C`",
        f"- SOC formula: `{tes['soc_formula']}`",
        "",
        "## Control Interface",
        "",
        "- Primary actuator: `TES_Set` as `Schedule:Constant / Schedule Value`.",
        "- Identification actuators: `ITE_Set` and `Chiller_T_Set` as `Schedule:Constant / Schedule Value`.",
        "- `TES_Set > 0` enables TES use side discharge.",
        "- `TES_Set < 0` enables TES source side charge.",
        "- MPC signed action mapping: `TES_Set = -clip(q_tes_net / q_tes_abs_max_kw_th, -1, 1)`.",
        "",
        "## Required Runtime Variables",
        "",
    ]
    for name, spec in params["variables"].items():
        lines.append(f"- `{name}`: `{spec['key']}` / `{spec['variable_name']}`")
    lines += ["", "## Required Meters", ""]
    for name, meter in params["meters"].items():
        lines.append(f"- `{name}`: `{meter}`")
    lines += ["", "## Modification History", "", "- 2026-05-07: initial parameter extraction for EnergyPlus-MPC coupling. No epJSON file was modified."]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _program_lines(programs: dict[str, Any], name: str) -> list[str]:
    return [item["program_line"] for item in programs.get(name, {}).get("lines", [])]


def _find_assignment_float(lines: list[str], name: str) -> float:
    pattern = re.compile(rf"SET\s+{re.escape(name)}\s*=\s*([-+0-9.]+)", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if match:
            return float(match.group(1))
    raise ValueError(f"could not find EMS assignment for {name}")


def _find_output_key(outputs: dict[str, Any], variable_name: str) -> str:
    for spec in outputs.values():
        if spec.get("variable_name") == variable_name:
            return str(spec["key_value"])
    raise ValueError(f"missing Output:Variable for {variable_name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--output", default=str(DEFAULT_PARAM_YAML))
    parser.add_argument("--doc", default=str(EPLUS_ROOT / "docs" / "physical_model_parameters.md"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    params = extract_static_params(args.model)
    write_yaml(args.output, params)
    doc = write_physical_model_doc(params, args.doc)
    print(args.output)
    print(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
