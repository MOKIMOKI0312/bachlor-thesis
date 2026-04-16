"""
M1-A2: 将 Chilled Water Tank 接入 Chilled Water Loop（单 loop 并联方案 A）。

拓扑：
  Supply 侧（冷源，并联在 Chiller 旁）：
      Branch 3 "Chilled Water Loop Supply Branch 3":
        ThermalStorage:ChilledWater:Stratified (Use Side — 放冷给 CRAH 回路)
          use_inlet  = CW Tank Use Inlet Node   (热水回流口)
          use_outlet = CW Tank Use Outlet Node  (冷水出水口)
      Splitter/Mixer/BranchList 都加 Branch 3

  Demand 侧（冷汇，并联在 CRAH Coil 旁）：
      Branch 3 "Chilled Water Loop Demand Branch 3":
        ThermalStorage:ChilledWater:Stratified (Source Side — 从 chiller 充冷)
          source_inlet  = CW Tank Source Inlet Node
          source_outlet = CW Tank Source Outlet Node
      Splitter/Mixer/BranchList 都加 Branch 3

同时：
  - 更新 Chilled Water Loop Cooling Equipment List，加入 TES 作为 Equipment 3
  - 不添加额外泵：已有 Primary Pump (constant) + Secondary Pump (variable) 驱动
  - TES 对象已由 M1-A1 写入，node 名称已匹配此脚本期望

用法：
    python tools/m1/2_wire_loop.py --dry-run
    python tools/m1/2_wire_loop.py -y
"""

import argparse
import copy
import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDINGS = ROOT / "Data" / "buildings"
BACKUP_DIR = BUILDINGS / "backups"
TARGETS = [BUILDINGS / "DRL_DC_training.epJSON",
           BUILDINGS / "DRL_DC_evaluation.epJSON"]

TES_NAME = "Chilled Water Tank"

# Node names — must exactly match M1-A1 placeholders
USE_INLET = "CW Tank Use Inlet Node"
USE_OUTLET = "CW Tank Use Outlet Node"
SRC_INLET = "CW Tank Source Inlet Node"
SRC_OUTLET = "CW Tank Source Outlet Node"

# Branch names
SUPPLY_BR3 = "Chilled Water Loop Supply Branch 3"
DEMAND_BR3 = "Chilled Water Loop Demand Branch 3"


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path: Path, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"A2_before_{tag}_{path.name}"
    shutil.copy2(path, dst)
    return dst


def _ensure_tes_exists(data: dict) -> None:
    tes_map = data.get("ThermalStorage:ChilledWater:Stratified", {})
    if TES_NAME not in tes_map:
        raise RuntimeError(
            f"Chilled Water Tank not found in ThermalStorage:ChilledWater:Stratified. "
            f"Did you run M1-A1 first?"
        )
    # Double-check node names match our wiring
    tes = tes_map[TES_NAME]
    expected = {
        "use_side_inlet_node_name": USE_INLET,
        "use_side_outlet_node_name": USE_OUTLET,
        "source_side_inlet_node_name": SRC_INLET,
        "source_side_outlet_node_name": SRC_OUTLET,
    }
    for field, want in expected.items():
        got = tes.get(field)
        if got != want:
            raise RuntimeError(
                f"TES {field}={got!r} but wiring expects {want!r}. "
                f"M1-A1 node placeholders mismatch — inspect tools/m1/1_add_tes_obj.py"
            )


def _add_supply_branch3(data: dict, report: dict) -> None:
    branches = data.setdefault("Branch", {})
    if SUPPLY_BR3 in branches:
        report["skipped"].append(f"Branch/{SUPPLY_BR3}")
        return
    branches[SUPPLY_BR3] = {
        "components": [
            {
                "component_object_type": "ThermalStorage:ChilledWater:Stratified",
                "component_name": TES_NAME,
                "component_inlet_node_name": USE_INLET,
                "component_outlet_node_name": USE_OUTLET,
            }
        ]
    }
    report["added"].append(f"Branch/{SUPPLY_BR3} (TES Use Side)")


def _add_demand_branch3(data: dict, report: dict) -> None:
    branches = data.setdefault("Branch", {})
    if DEMAND_BR3 in branches:
        report["skipped"].append(f"Branch/{DEMAND_BR3}")
        return
    branches[DEMAND_BR3] = {
        "components": [
            {
                "component_object_type": "ThermalStorage:ChilledWater:Stratified",
                "component_name": TES_NAME,
                "component_inlet_node_name": SRC_INLET,
                "component_outlet_node_name": SRC_OUTLET,
            }
        ]
    }
    report["added"].append(f"Branch/{DEMAND_BR3} (TES Source Side)")


def _update_branchlist(data: dict, report: dict, list_name: str,
                       new_branch: str, insert_before_outlet: bool = True) -> None:
    blists = data.get("BranchList", {})
    if list_name not in blists:
        raise RuntimeError(f"BranchList {list_name!r} not found")
    entries = blists[list_name]["branches"]
    names = [e["branch_name"] for e in entries]
    if new_branch in names:
        report["skipped"].append(f"BranchList/{list_name}/{new_branch}")
        return
    # insert just before the *outlet* entry (the last one that has 'Outlet' in name)
    insert_idx = len(entries)
    if insert_before_outlet:
        for i, n in enumerate(names):
            if "Outlet" in n:
                insert_idx = i
                break
    entries.insert(insert_idx, {"branch_name": new_branch})
    report["added"].append(f"BranchList/{list_name} += {new_branch} (at idx {insert_idx})")


def _update_splitter(data: dict, report: dict, splitter_name: str, new_branch: str) -> None:
    splitters = data.get("Connector:Splitter", {})
    if splitter_name not in splitters:
        raise RuntimeError(f"Splitter {splitter_name!r} not found")
    entries = splitters[splitter_name]["branches"]
    existing = [e["outlet_branch_name"] for e in entries]
    if new_branch in existing:
        report["skipped"].append(f"Connector:Splitter/{splitter_name}/{new_branch}")
        return
    entries.append({"outlet_branch_name": new_branch})
    report["added"].append(f"Connector:Splitter/{splitter_name} += {new_branch}")


def _update_mixer(data: dict, report: dict, mixer_name: str, new_branch: str) -> None:
    mixers = data.get("Connector:Mixer", {})
    if mixer_name not in mixers:
        raise RuntimeError(f"Mixer {mixer_name!r} not found")
    entries = mixers[mixer_name]["branches"]
    existing = [e["inlet_branch_name"] for e in entries]
    if new_branch in existing:
        report["skipped"].append(f"Connector:Mixer/{mixer_name}/{new_branch}")
        return
    entries.append({"inlet_branch_name": new_branch})
    report["added"].append(f"Connector:Mixer/{mixer_name} += {new_branch}")


def _update_plant_equipment_list(data: dict, report: dict) -> None:
    lst_name = "Chilled Water Loop Cooling Equipment List"
    pel = data.get("PlantEquipmentList", {})
    if lst_name not in pel:
        raise RuntimeError(f"PlantEquipmentList {lst_name!r} not found")
    items = pel[lst_name].get("equipment", [])
    # check if TES already
    for it in items:
        if (it.get("equipment_object_type") == "ThermalStorage:ChilledWater:Stratified"
                and it.get("equipment_name") == TES_NAME):
            report["skipped"].append(f"PlantEquipmentList/{lst_name}/{TES_NAME}")
            return
    items.append({
        "equipment_object_type": "ThermalStorage:ChilledWater:Stratified",
        "equipment_name": TES_NAME,
    })
    pel[lst_name]["equipment"] = items
    report["added"].append(f"PlantEquipmentList/{lst_name} += {TES_NAME}")


def apply(data: dict) -> dict:
    report = {"added": [], "skipped": []}

    _ensure_tes_exists(data)

    # Supply side Branch 3 (TES Use Side)
    _add_supply_branch3(data, report)
    _update_branchlist(data, report,
                       "Chilled Water Loop Supply Branches", SUPPLY_BR3)
    _update_splitter(data, report,
                     "Chilled Water Loop Supply Splitter", SUPPLY_BR3)
    _update_mixer(data, report,
                  "Chilled Water Loop Supply Mixer", SUPPLY_BR3)

    # Demand side Branch 3 (TES Source Side)
    _add_demand_branch3(data, report)
    _update_branchlist(data, report,
                       "Chilled Water Loop Demand Branches", DEMAND_BR3)
    _update_splitter(data, report,
                     "Chilled Water Loop Demand Splitter", DEMAND_BR3)
    _update_mixer(data, report,
                  "Chilled Water Loop Demand Mixer", DEMAND_BR3)

    # Plant equipment list — TES as cooling supplier on Supply side
    _update_plant_equipment_list(data, report)

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    args = parser.parse_args()

    if not (args.dry_run or args.yes):
        print("ERROR: pass --dry-run or -y", file=sys.stderr)
        sys.exit(2)

    tag = _now_tag()
    print(f"[M1-A2] timestamp tag: {tag}")
    print(f"[M1-A2] mode: {'DRY-RUN' if args.dry_run else 'APPLY'}")

    for epjson in TARGETS:
        print(f"\n--- Processing {epjson.name} ---")
        with open(epjson, encoding="utf-8") as f:
            data = json.load(f)

        try:
            report = apply(data)
        except RuntimeError as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        for line in report["added"]:
            print(f"  ADD:  {line}")
        for line in report["skipped"]:
            print(f"  SKIP: {line}")

        if args.dry_run:
            continue

        bpath = backup(epjson, tag)
        print(f"  BACKUP -> {bpath}")
        with open(epjson, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  WROTE  -> {epjson}")
        with open(epjson, encoding="utf-8") as f:
            _ = json.load(f)
        print("  JSON re-parse: OK")

    print("\n[M1-A2] done.")


if __name__ == "__main__":
    main()
