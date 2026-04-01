"""
clean_epjson.py - Remove PV/Wind/Battery/unused EMS objects from DRL_DC epJSON files.

Removes:
- ElectricLoadCenter, Generator:PVWatts, Generator:WindTurbine (all sub-objects)
- Battery-related EMS Actuators, Sensors, Programs, GlobalVariables
- Battery/wind/solar Schedule:Constant objects
- LiIonBattery Output:Variable objects
"""

import json
import sys
from pathlib import Path

BASE = Path(r"C:\Users\18430\Desktop\毕业设计代码\AI-Data-Center-Analysis_migration_bundle_20260311\Data\buildings")

FILES = [
    BASE / "DRL_DC_training.epJSON",
    BASE / "DRL_DC_evaluation.epJSON",
]

# A. Entire top-level categories to delete
TOP_LEVEL_DELETE = [
    "ElectricLoadCenter:Distribution",
    "ElectricLoadCenter:Generators",
    "ElectricLoadCenter:Inverter:PVWatts",
    "ElectricLoadCenter:Storage:LiIonNMCBattery",
    "Generator:PVWatts",
    "Generator:WindTurbine",
]

# B. EMS Actuators to delete
ACTUATORS_DELETE = ["Charge_rate", "Discharge_rate", "min_v", "max_v"]

# C. EMS Sensors to delete
SENSORS_DELETE = [
    "SoC", "B_V", "Charge_S", "Charge_Def", "Discharge_S",
    "Wind_Pro1", "Wind_Pro2", "Wind_Pro3", "Solar_Pro", "Pro", "Dem",
]

# D. EMS Programs to delete
PROGRAMS_DELETE = ["P_3", "P_4"]

# G. Schedule:Constant keys to delete
SCHEDULE_CONST_DELETE = ["Charge_Def_Set", "Charge_Set", "Discharge_Set", "min_v", "max_v"]

# F. GlobalVariable entries to remove
GLOBAL_VAR_REMOVE = ["min_value", "max_value"]


def clean(data: dict) -> dict:
    # A. Delete entire top-level categories
    for key in TOP_LEVEL_DELETE:
        if key in data:
            print(f"  Deleted top-level: {key} (had {len(data[key])} sub-objects)")
            del data[key]

    # B. Delete EMS Actuators
    cat = "EnergyManagementSystem:Actuator"
    if cat in data:
        for k in ACTUATORS_DELETE:
            if k in data[cat]:
                del data[cat][k]
                print(f"  Deleted {cat} -> {k}")

    # C. Delete EMS Sensors
    cat = "EnergyManagementSystem:Sensor"
    if cat in data:
        for k in SENSORS_DELETE:
            if k in data[cat]:
                del data[cat][k]
                print(f"  Deleted {cat} -> {k}")

    # D. Delete EMS Programs
    cat = "EnergyManagementSystem:Program"
    if cat in data:
        for k in PROGRAMS_DELETE:
            if k in data[cat]:
                del data[cat][k]
                print(f"  Deleted {cat} -> {k}")

    # E. ProgramCallingManager: remove P_3 from P1's programs list, delete P4
    cat = "EnergyManagementSystem:ProgramCallingManager"
    if cat in data:
        if "P1" in data[cat]:
            progs = data[cat]["P1"]["programs"]
            before = len(progs)
            data[cat]["P1"]["programs"] = [
                p for p in progs if p.get("program_name") != "P_3"
            ]
            after = len(data[cat]["P1"]["programs"])
            if before != after:
                print(f"  Removed P_3 from {cat} -> P1 programs ({before} -> {after})")
        if "P4" in data[cat]:
            del data[cat]["P4"]
            print(f"  Deleted {cat} -> P4")

    # F. GlobalVariable: remove min_value, max_value entries
    cat = "EnergyManagementSystem:GlobalVariable"
    if cat in data:
        for obj_name, obj in data[cat].items():
            if "variables" in obj:
                before = len(obj["variables"])
                obj["variables"] = [
                    v for v in obj["variables"]
                    if v.get("erl_variable_name") not in GLOBAL_VAR_REMOVE
                ]
                after = len(obj["variables"])
                if before != after:
                    print(f"  Removed {before - after} GlobalVariable entries ({before} -> {after})")

    # G. Schedule:Constant deletions
    cat = "Schedule:Constant"
    if cat in data:
        for k in SCHEDULE_CONST_DELETE:
            if k in data[cat]:
                del data[cat][k]
                print(f"  Deleted {cat} -> {k}")

    # H. Output:Variable - delete LiIonBattery / "Electric Storage" entries
    cat = "Output:Variable"
    if cat in data:
        to_delete = []
        for k, v in data[cat].items():
            if v.get("key_value") == "LiIonBattery":
                to_delete.append(k)
            elif "Electric Storage" in v.get("variable_name", ""):
                to_delete.append(k)
        for k in to_delete:
            del data[cat][k]
            print(f"  Deleted {cat} -> {k}")

    return data


def print_summary(data: dict):
    categories = [
        "EnergyManagementSystem:Actuator",
        "EnergyManagementSystem:Sensor",
        "EnergyManagementSystem:Program",
        "EnergyManagementSystem:ProgramCallingManager",
        "EnergyManagementSystem:GlobalVariable",
        "Schedule:Constant",
        "Output:Variable",
    ]
    for cat in categories:
        if cat in data:
            count = len(data[cat])
            print(f"  {cat}: {count} objects")
            if cat in (
                "EnergyManagementSystem:Actuator",
                "EnergyManagementSystem:Sensor",
                "EnergyManagementSystem:Program",
                "EnergyManagementSystem:ProgramCallingManager",
                "Schedule:Constant",
            ):
                print(f"    Keys: {list(data[cat].keys())}")
        else:
            print(f"  {cat}: REMOVED (0)")

    # Check removed top-level
    for key in TOP_LEVEL_DELETE:
        if key in data:
            print(f"  WARNING: {key} still exists!")
        else:
            print(f"  {key}: REMOVED (OK)")


def main():
    for fpath in FILES:
        print(f"\n{'='*60}")
        print(f"Processing: {fpath.name}")
        print(f"{'='*60}")

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        data = clean(data)

        # Validate JSON round-trip
        json_str = json.dumps(data, indent=4)
        json.loads(json_str)  # parse back to confirm validity
        print("  JSON validation: OK")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"  Saved: {fpath}")

        print(f"\n--- Summary for {fpath.name} ---")
        print_summary(data)

    print("\nDone. Both files cleaned successfully.")


if __name__ == "__main__":
    main()
