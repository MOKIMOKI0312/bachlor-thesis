"""Add TES_Avg_Temp_Obs schedule + EMS actuator + P_6 output line to epJSON files.

Usage:
    python tools/m1/r2_add_avg_temp_obs.py -y
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILDINGS = REPO / "Data" / "buildings"
SINERGYM_BUILDINGS = REPO / "sinergym" / "data" / "buildings"
import shutil

EPJSON_FILES = [
    BUILDINGS / "DRL_DC_training.epJSON",
    BUILDINGS / "DRL_DC_evaluation.epJSON",
]


def patch(bld: dict) -> list[str]:
    changes = []

    # 1. Add Schedule:Constant for avg temp observation
    schedules = bld.setdefault("Schedule:Constant", {})
    if "TES_Avg_Temp_Obs" not in schedules:
        schedules["TES_Avg_Temp_Obs"] = {"hourly_value": 10.0}
        changes.append("Added Schedule:Constant TES_Avg_Temp_Obs")

    # 2. Add EMS:Actuator to write T_tank_avg to the schedule
    actuators = bld["EnergyManagementSystem:Actuator"]
    if "TES_Avg_Temp_Actuator" not in actuators:
        actuators["TES_Avg_Temp_Actuator"] = {
            "actuated_component_unique_name": "TES_Avg_Temp_Obs",
            "actuated_component_type": "Schedule:Constant",
            "actuated_component_control_type": "Schedule Value",
        }
        changes.append("Added EMS:Actuator TES_Avg_Temp_Actuator")

    # 3. Add global variable if not present
    gvars = bld["EnergyManagementSystem:GlobalVariable"]["EnergyManagementSystem:GlobalVariable 1"]["variables"]
    has_avg_temp = any(v.get("erl_variable_name") == "T_tank_avg" for v in gvars)
    if not has_avg_temp:
        changes.append("T_tank_avg already exists as global var (from P_6)")

    # 4. Append output line to P_6
    p6_lines = bld["EnergyManagementSystem:Program"]["P_6"]["lines"]
    last_line = p6_lines[-1]["program_line"]
    if "TES_Avg_Temp_Actuator" not in last_line:
        p6_lines.append({"program_line": "SET TES_Avg_Temp_Actuator = T_tank_avg"})
        changes.append("Added P_6 line: SET TES_Avg_Temp_Actuator = T_tank_avg")

    # 5. Add Output:Variable for observation
    output_vars = bld.get("Output:Variable", {})
    if "TES_Avg_Temp_Output" not in output_vars:
        output_vars["TES_Avg_Temp_Output"] = {
            "key_value": "TES_Avg_Temp_Obs",
            "reporting_frequency": "Timestep",
            "variable_name": "Schedule Value",
        }
        bld["Output:Variable"] = output_vars
        changes.append("Added Output:Variable for TES_Avg_Temp_Obs")

    return changes


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("-y", action="store_true")
    args = parser.parse_args()

    for path in EPJSON_FILES:
        print(f"\n=== {path.name} ===")
        with open(path, encoding="utf-8") as f:
            bld = json.load(f)

        changes = patch(bld)
        for c in changes:
            print(f"  {c}")

        if args.y:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bld, f, indent=2)
            print(f"  Written: {path.name}")
            # Sync
            dst = SINERGYM_BUILDINGS / path.name
            shutil.copy2(path, dst)
            print(f"  Synced to sinergym")
        else:
            print("  [DRY RUN]")


if __name__ == "__main__":
    main()
