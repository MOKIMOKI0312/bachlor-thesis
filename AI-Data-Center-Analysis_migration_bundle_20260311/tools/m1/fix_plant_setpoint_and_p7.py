"""Fix: TES Use 分支不放冷的真正 root cause.

修复 1: PlantEquipmentOperation:ComponentSetpoint 追加 equipment_3 = ChilledWaterTank
        Plant solver 现在知道在 Chiller kill 后用 TES 维持 supply outlet setpoint.
修复 2: P_7 (HVAC iteration guard) 追加 TES Use/Source 流量重置, 防止 plant solver
        在 HVAC 内迭代中覆盖 EMS 在 BeginTimestepBeforePredictor 写的 setpoint.

P_5 / P_6 / Wrapper / Reward 完全不动.

Usage:
    python tools/m1/fix_plant_setpoint_and_p7.py --dry-run
    python tools/m1/fix_plant_setpoint_and_p7.py -y
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    ("Data/buildings/DRL_DC_training.epJSON", "DRL_DC_training.epJSON"),
    ("Data/buildings/DRL_DC_evaluation.epJSON", "DRL_DC_evaluation.epJSON"),
    ("sinergym/data/buildings/DRL_DC_training.epJSON", "sinergym_DRL_DC_training.epJSON"),
    ("sinergym/data/buildings/DRL_DC_evaluation.epJSON", "sinergym_DRL_DC_evaluation.epJSON"),
]

PO_SCHEME_NAME = "Chilled Water Loop Setpoint Operation Scheme"

NEW_EQUIPMENT_3 = {
    "equipment_3_object_type": "ThermalStorage:ChilledWater:Stratified",
    "equipment_3_name": "Chilled Water Tank",
    "demand_calculation_3_node_name": "CW Tank Use Inlet Node",
    "setpoint_3_node_name": "CW Tank Use Outlet Node",
    "component_3_flow_rate": "Autosize",
    "operation_3_type": "Cooling",
}

NEW_P7_LINES = [
    "SET TES_Signal_Now = TES_Set_Sensor",
    "SET Flow_Now = @Abs TES_Signal_Now * 389.0",
    "IF TES_Signal_Now > 0.01",
    "  SET TES_Use_Avail = 1",
    "  SET TES_Use_MFlow_Max = Flow_Now",
    "  SET TES_Use_MFlow_Min = Flow_Now",
    "  IF SOC > 0.15",
    "    SET Chiller_Branch_Avail = 0",
    "    SET Chiller_Component_Avail = 0",
    "    SET Chiller_Out_T_SP = 30.0",
    "    SET Chiller_In_MFlow_Max = 0.0",
    "    SET Chiller_Avail_Obs = 0",
    "  ENDIF",
    "ELSEIF TES_Signal_Now < 0.0 - 0.01",
    "  SET TES_Source_Avail = 1",
    "  SET TES_Source_MFlow_Max = Flow_Now",
    "  SET TES_Source_MFlow_Min = Flow_Now",
    "ENDIF",
]


def patch_epjson(ep: dict) -> dict:
    """Apply both fixes; raise if structure unexpected."""
    # Fix 1: PlantEquipmentOperation:ComponentSetpoint
    po_root = ep.get("PlantEquipmentOperation:ComponentSetpoint")
    if po_root is None:
        raise RuntimeError("Missing PlantEquipmentOperation:ComponentSetpoint")
    if PO_SCHEME_NAME not in po_root:
        raise RuntimeError(
            f"Expected scheme name '{PO_SCHEME_NAME}', got {list(po_root.keys())}"
        )
    scheme = po_root[PO_SCHEME_NAME]
    # idempotency: only add if not present
    for k, v in NEW_EQUIPMENT_3.items():
        scheme[k] = v

    # Fix 2: P_7 lines
    progs = ep.get("EnergyManagementSystem:Program")
    if progs is None or "P_7" not in progs:
        raise RuntimeError("Missing EMS Program P_7")
    p7 = progs["P_7"]
    p7["lines"] = [{"program_line": ln} for ln in NEW_P7_LINES]
    return ep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="预览不写盘")
    ap.add_argument("-y", action="store_true", help="确认写盘")
    args = ap.parse_args()

    if not args.dry_run and not args.y:
        print("必须指定 --dry-run 或 -y")
        return 2

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = REPO_ROOT / "Data" / "buildings" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for rel, tag in TARGETS:
        src = REPO_ROOT / rel
        if not src.exists():
            raise FileNotFoundError(src)
        backup = backup_dir / f"PlantSetpointFix_before_{timestamp}_{tag}"
        with src.open("r", encoding="utf-8") as f:
            ep = json.load(f)
        patched = patch_epjson(ep)

        # Diff summary
        po_keys = list(patched["PlantEquipmentOperation:ComponentSetpoint"][PO_SCHEME_NAME].keys())
        p7_lines = [ln["program_line"] for ln in patched["EnergyManagementSystem:Program"]["P_7"]["lines"]]
        print(f"--- {rel} ---")
        print(f"  ComponentSetpoint keys ({len(po_keys)}): equipment_3 added = "
              f"{patched['PlantEquipmentOperation:ComponentSetpoint'][PO_SCHEME_NAME]['equipment_3_name']}")
        print(f"  P_7 lines: {len(p7_lines)} (was 9)")

        if args.dry_run:
            continue

        # backup then write (preserve original CRLF, indent=2, no sort, no trailing newline)
        shutil.copy2(src, backup)
        body = json.dumps(patched, indent=2, ensure_ascii=False, sort_keys=False)
        body_crlf = body.replace("\n", "\r\n")
        with src.open("w", encoding="utf-8", newline="") as f:
            f.write(body_crlf)
        print(f"  backup: {backup}")
        print(f"  wrote: {src}")

        # validate JSON loadable
        with src.open("r", encoding="utf-8") as f:
            json.load(f)

    if args.dry_run:
        print("DRY-RUN done; no files written.")
    else:
        print(f"All 4 epJSON patched. timestamp={timestamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
