"""R2-1 + R2-2: Resize TES tank 4300→1400 m³, rewrite EMS P_5 for continuous flow control.

Instead of adding physical pumps (conflicts with loop pump), we use EMS actuators
to directly set TES Use/Source Side mass flow rates via node setpoints.

Usage:
    python tools/m1/r2_resize_and_rewire.py --dry-run   # preview changes
    python tools/m1/r2_resize_and_rewire.py -y           # apply changes
"""
import argparse
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILDINGS = REPO / "Data" / "buildings"
SINERGYM_BUILDINGS = REPO / "sinergym" / "data" / "buildings"
BACKUP_DIR = BUILDINGS / "backups"

EPJSON_FILES = [
    BUILDINGS / "DRL_DC_training.epJSON",
    BUILDINGS / "DRL_DC_evaluation.epJSON",
]

# --- Design parameters (from tech route §1.0) ---
NEW_VOLUME = 1400.0        # m³ (Zhu paper)
HD_RATIO = 1.5             # height / diameter
_D = (4 * NEW_VOLUME / (math.pi * HD_RATIO)) ** (1.0 / 3.0)
NEW_DIAMETER = round(_D, 2)
NEW_HEIGHT = round(HD_RATIO * _D, 2)

# Flow sizing: 4h full charge/discharge cycle
DISCHARGE_HOURS = 4.0
MAX_VOL_FLOW = NEW_VOLUME / (DISCHARGE_HOURS * 3600)  # m³/s
MAX_MASS_FLOW = round(MAX_VOL_FLOW * 1000, 1)         # kg/s

# Nominal cooling capacity scales with volume
OLD_VOLUME = 4300.0
OLD_NOMINAL_COOLING = 30_000_000.0
NEW_NOMINAL_COOLING = round(OLD_NOMINAL_COOLING * NEW_VOLUME / OLD_VOLUME)


def backup(path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"{path.stem}_R2_before_{ts}{path.suffix}"
    shutil.copy2(path, dst)
    return dst


def resize_tank(bld: dict) -> list[str]:
    """R2-1: Resize ThermalStorage:ChilledWater:Stratified."""
    changes = []
    tank = bld["ThermalStorage:ChilledWater:Stratified"]["Chilled Water Tank"]

    old_v = tank["tank_volume"]
    old_h = tank["tank_height"]

    tank["tank_volume"] = NEW_VOLUME
    tank["tank_height"] = NEW_HEIGHT
    tank["temperature_sensor_height"] = round(NEW_HEIGHT / 2, 1)
    tank["nominal_cooling_capacity"] = NEW_NOMINAL_COOLING

    tank["use_side_inlet_height"] = round(NEW_HEIGHT - 0.5, 1)
    tank["use_side_outlet_height"] = 0.5
    tank["source_side_inlet_height"] = 0.5
    tank["source_side_outlet_height"] = round(NEW_HEIGHT - 0.5, 1)

    changes.append(f"  tank_volume: {old_v} → {NEW_VOLUME}")
    changes.append(f"  tank_height: {old_h} → {NEW_HEIGHT}")
    changes.append(f"  diameter (doc only): {NEW_DIAMETER} m")
    changes.append(f"  nominal_cooling_capacity: {OLD_NOMINAL_COOLING} → {NEW_NOMINAL_COOLING}")
    changes.append(f"  sensor_height: {round(NEW_HEIGHT/2, 1)}")
    return changes


def add_flow_actuators(bld: dict) -> list[str]:
    """Add EMS actuators for TES node mass flow rate setpoints.

    Uses 'System Node Setpoint' → 'Mass Flow Rate Maximum Available Setpoint'
    on TES inlet nodes to control flow through TES branches.
    """
    changes = []
    actuators = bld["EnergyManagementSystem:Actuator"]

    # Use side (discharge path) — control flow at Use Inlet Node
    actuators["TES_Use_MFlow_Max"] = {
        "actuated_component_unique_name": "CW Tank Use Inlet Node",
        "actuated_component_type": "System Node Setpoint",
        "actuated_component_control_type": "Mass Flow Rate Maximum Available Setpoint",
    }
    actuators["TES_Use_MFlow_Min"] = {
        "actuated_component_unique_name": "CW Tank Use Inlet Node",
        "actuated_component_type": "System Node Setpoint",
        "actuated_component_control_type": "Mass Flow Rate Minimum Available Setpoint",
    }

    # Source side (charge path) — control flow at Source Inlet Node
    actuators["TES_Source_MFlow_Max"] = {
        "actuated_component_unique_name": "CW Tank Source Inlet Node",
        "actuated_component_type": "System Node Setpoint",
        "actuated_component_control_type": "Mass Flow Rate Maximum Available Setpoint",
    }
    actuators["TES_Source_MFlow_Min"] = {
        "actuated_component_unique_name": "CW Tank Source Inlet Node",
        "actuated_component_type": "System Node Setpoint",
        "actuated_component_control_type": "Mass Flow Rate Minimum Available Setpoint",
    }

    changes.append("  Added TES_Use_MFlow_Max/Min (node setpoint on Use Inlet)")
    changes.append("  Added TES_Source_MFlow_Max/Min (node setpoint on Source Inlet)")
    return changes


def rewrite_p5(bld: dict) -> list[str]:
    """R2-2: Rewrite EMS Program P_5 for continuous flow control via node setpoints.

    TES_Set_Sensor carries signed valve position v ∈ [-1, +1]:
      v > 0  → discharge (Use side), flow = v * MAX_MASS_FLOW
      v < 0  → charge (Source side), flow = |v| * MAX_MASS_FLOW + chiller off
      v ≈ 0  → idle
    """
    changes = []
    programs = bld["EnergyManagementSystem:Program"]

    programs["P_5"] = {
        "lines": [{"program_line": line} for line in [
            "SET TES_Signal = TES_Set_Sensor",
            f"SET Max_Flow = {MAX_MASS_FLOW}",
            "SET Flow = @Abs TES_Signal * Max_Flow",
            # Default: no forced flow, avail off
            "SET TES_Use_MFlow_Max = 0.0",
            "SET TES_Use_MFlow_Min = 0.0",
            "SET TES_Source_MFlow_Max = 0.0",
            "SET TES_Source_MFlow_Min = 0.0",
            "SET TES_Use_Avail = 0",
            "SET TES_Source_Avail = 0",
            # Discharge (v > 0): Use side on, request flow
            "IF TES_Signal > 0.01",
            "  SET TES_Use_Avail = 1",
            "  SET TES_Use_MFlow_Max = Flow",
            "  SET TES_Use_MFlow_Min = Flow",
            "  SET TES_Source_Avail = 0",
            # Charge (v < 0): Source side on, request flow
            "ELSEIF TES_Signal < 0.0 - 0.01",
            "  SET TES_Source_Avail = 1",
            "  SET TES_Source_MFlow_Max = Flow",
            "  SET TES_Source_MFlow_Min = Flow",
            "  SET TES_Use_Avail = 0",
            "ENDIF",
            # --- Chiller shutdown during discharge ---
            "SET Chiller_Branch_Avail = 1",
            "SET Chiller_Component_Avail = 1",
            "SET Chiller_Out_T_SP = 6.67",
            "SET Chiller_In_MFlow_Max = 9999.0",
            "SET Chiller_Avail_Obs = 1",
            "IF TES_Signal < 0.0 - 0.01",
            "  IF SOC > 0.02",
            "    SET Chiller_Branch_Avail = 0",
            "    SET Chiller_Component_Avail = 0",
            "    SET Chiller_Out_T_SP = 30.0",
            "    SET Chiller_In_MFlow_Max = 0.0",
            "    SET Chiller_Avail_Obs = 0",
            "  ENDIF",
            "ENDIF",
        ]]
    }

    changes.append(f"  Rewrote P_5: node mass flow setpoints (max={MAX_MASS_FLOW} kg/s)")
    changes.append("  v>0 → discharge (Use), v<0 → charge (Source) + chiller off")
    return changes


def rewrite_p7(bld: dict) -> list[str]:
    """Update P_7 threshold to match."""
    changes = []
    programs = bld["EnergyManagementSystem:Program"]

    programs["P_7"] = {
        "lines": [{"program_line": line} for line in [
            "IF TES_Set_Sensor < 0.0 - 0.01",
            "  IF SOC > 0.02",
            "    SET Chiller_Branch_Avail = 0",
            "    SET Chiller_Component_Avail = 0",
            "    SET Chiller_Out_T_SP = 30.0",
            "    SET Chiller_In_MFlow_Max = 0.0",
            "    SET Chiller_Avail_Obs = 0",
            "  ENDIF",
            "ENDIF",
        ]]
    }

    changes.append("  Updated P_7 threshold to 0.01")
    return changes


def remove_stale_pump_actuators(bld: dict) -> list[str]:
    """Remove any pump actuators added by previous failed attempt."""
    changes = []
    actuators = bld.get("EnergyManagementSystem:Actuator", {})
    for name in ["TES_Use_Pump_MFlow", "TES_Source_Pump_MFlow"]:
        if name in actuators:
            del actuators[name]
            changes.append(f"  Removed stale actuator: {name}")

    # Remove any TES pumps from Pump:VariableSpeed
    pumps = bld.get("Pump:VariableSpeed", {})
    for name in ["TES Use Pump", "TES Source Pump"]:
        if name in pumps:
            del pumps[name]
            changes.append(f"  Removed stale pump: {name}")

    # Revert branches if they contain pump references
    branches = bld.get("Branch", {})
    sb3 = branches.get("Chilled Water Loop Supply Branch 3", {})
    if len(sb3.get("components", [])) > 1:
        sb3["components"] = [{
            "component_object_type": "ThermalStorage:ChilledWater:Stratified",
            "component_name": "Chilled Water Tank",
            "component_inlet_node_name": "CW Tank Use Inlet Node",
            "component_outlet_node_name": "CW Tank Use Outlet Node",
        }]
        changes.append("  Reverted Supply Branch 3 to TES-only")

    db3 = branches.get("Chilled Water Loop Demand Branch 3", {})
    if len(db3.get("components", [])) > 1:
        db3["components"] = [{
            "component_object_type": "ThermalStorage:ChilledWater:Stratified",
            "component_name": "Chilled Water Tank",
            "component_inlet_node_name": "CW Tank Source Inlet Node",
            "component_outlet_node_name": "CW Tank Source Outlet Node",
        }]
        changes.append("  Reverted Demand Branch 3 to TES-only")

    return changes


def process_file(path: Path, dry_run: bool) -> list[str]:
    all_changes = [f"\n=== {path.name} ==="]

    with open(path, encoding="utf-8") as f:
        bld = json.load(f)

    # Clean up any stale objects from previous attempt
    cleanup = remove_stale_pump_actuators(bld)
    if cleanup:
        all_changes.append("\n[Cleanup] Removing stale objects from failed pump attempt:")
        all_changes.extend(cleanup)

    all_changes.append("\n[R2-1] Tank resize:")
    all_changes.extend(resize_tank(bld))

    all_changes.append("\n[R2-2a] Add flow control actuators (node setpoints):")
    all_changes.extend(add_flow_actuators(bld))

    all_changes.append("\n[R2-2b] Rewrite EMS P_5:")
    all_changes.extend(rewrite_p5(bld))

    all_changes.append("\n[R2-2c] Update EMS P_7:")
    all_changes.extend(rewrite_p7(bld))

    if dry_run:
        all_changes.append("\n  [DRY RUN] No file written.")
    else:
        bak = backup(path)
        all_changes.append(f"\n  Backup: {bak.name}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bld, f, indent=2)
        all_changes.append(f"  Written: {path}")

    return all_changes


def sync_to_sinergym(dry_run: bool) -> list[str]:
    changes = ["\n=== Sync to sinergym/data/buildings/ ==="]
    for src in EPJSON_FILES:
        dst = SINERGYM_BUILDINGS / src.name
        if dry_run:
            changes.append(f"  [DRY RUN] Would copy {src.name} → {dst}")
        else:
            shutil.copy2(src, dst)
            changes.append(f"  Copied {src.name} → {dst}")
    return changes


def main():
    parser = argparse.ArgumentParser(description="R2: Resize tank + continuous flow via EMS")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("-y", "--yes", action="store_true")
    args = parser.parse_args()

    dry_run = args.dry_run

    print(f"Design parameters:")
    print(f"  Volume: {NEW_VOLUME} m³")
    print(f"  Height: {NEW_HEIGHT} m, Diameter: {NEW_DIAMETER} m (H/D={HD_RATIO})")
    print(f"  Max flow: {MAX_VOL_FLOW:.4f} m³/s = {MAX_MASS_FLOW} kg/s")
    print(f"  Nominal cooling: {NEW_NOMINAL_COOLING} W")

    all_changes = []
    for path in EPJSON_FILES:
        all_changes.extend(process_file(path, dry_run))

    all_changes.extend(sync_to_sinergym(dry_run))

    for line in all_changes:
        print(line)

    if not dry_run:
        print("\n=== JSON validation ===")
        for path in EPJSON_FILES:
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
                print(f"  OK {path.name}")
            except json.JSONDecodeError as e:
                print(f"  FAIL {path.name}: {e}")
                sys.exit(1)
        for path in EPJSON_FILES:
            dst = SINERGYM_BUILDINGS / path.name
            try:
                with open(dst, encoding="utf-8") as f:
                    json.load(f)
                print(f"  OK sinergym/{path.name}")
            except json.JSONDecodeError as e:
                print(f"  FAIL sinergym/{path.name}: {e}")
                sys.exit(1)


if __name__ == "__main__":
    main()
