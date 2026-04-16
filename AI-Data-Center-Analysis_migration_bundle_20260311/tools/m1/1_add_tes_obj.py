"""
M1-A1: 向两个 DRL_DC epJSON 中添加 ThermalStorage:ChilledWater:Stratified 对象 + 配套 Schedule:Constant
       和 Output:Variable 观测变量。此步骤尚不接 PlantLoop：node 字段预填占位名，由 M1-A2 脚本接线。

设计参数（见 代码开发进度管理.md 第 6 节）：
  - 对象名           Chilled Water Tank
  - Tank Volume      4300 m3
  - Tank Height      22 m
  - Tank Shape       VerticalCylinder
  - Nominal Cap      30 MW
  - Number of Nodes  10
  - Deadband         0.5 degC
  - U (skin loss)    0.4 W/m2-K
  - Ambient Zone     DataCenter ZN
  - Setpoint Temp    6 degC (通过 Schedule:Constant `TES_Charge_Setpoint`)
  - Use/Source eff   1.0
  - Use/Source flow  Autosize

用法：
    python tools/m1/1_add_tes_obj.py --dry-run
    python tools/m1/1_add_tes_obj.py -y      # 确认执行
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

# Node name placeholders (M1-A2 会实际接入 loop)
USE_INLET = "CW Tank Use Inlet Node"
USE_OUTLET = "CW Tank Use Outlet Node"
SRC_INLET = "CW Tank Source Inlet Node"
SRC_OUTLET = "CW Tank Source Outlet Node"

TES_OBJECT = {
    "tank_volume": 4300.0,
    "tank_height": 22.0,
    "tank_shape": "VerticalCylinder",
    "setpoint_temperature_schedule_name": "TES_Charge_Setpoint",
    "deadband_temperature_difference": 0.5,
    "temperature_sensor_height": 11.0,
    "minimum_temperature_limit": 1.0,
    "nominal_cooling_capacity": 30_000_000.0,  # 30 MW
    "ambient_temperature_indicator": "Zone",
    "ambient_temperature_zone_name": "DataCenter ZN",
    "uniform_skin_loss_coefficient_per_unit_area_to_ambient_temperature": 0.4,
    "use_side_inlet_node_name": USE_INLET,
    "use_side_outlet_node_name": USE_OUTLET,
    "use_side_heat_transfer_effectiveness": 1.0,
    "use_side_availability_schedule_name": "Always On Discrete",
    "use_side_inlet_height": 21.5,           # 顶部：热水回流口
    "use_side_outlet_height": 0.5,           # 底部：冷水出水口
    "use_side_design_flow_rate": "Autosize",
    "source_side_inlet_node_name": SRC_INLET,
    "source_side_outlet_node_name": SRC_OUTLET,
    "source_side_heat_transfer_effectiveness": 1.0,
    "source_side_availability_schedule_name": "Always On Discrete",
    "source_side_inlet_height": 0.5,         # 底部：chiller 冷水进口
    "source_side_outlet_height": 21.5,       # 顶部：热水返回口（充冷时热水从底抽，冷水从顶返？实际相反）
    "source_side_design_flow_rate": "Autosize",
    "tank_recovery_time": 4.0,
    "inlet_mode": "Seeking",
    "number_of_nodes": 10,
    "additional_destratification_conductivity": 0.0,
}

TES_SETPOINT_SCHED = {
    "TES_Charge_Setpoint": {
        "hourly_value": 6.0,
        "schedule_type_limits_name": "Temperature",
    }
}

TES_OUTPUT_VARS = [
    "Chilled Water Thermal Storage Final Tank Temperature",
    "Chilled Water Thermal Storage Use Side Heat Transfer Rate",
    "Chilled Water Thermal Storage Source Side Heat Transfer Rate",
    "Chilled Water Thermal Storage Tank Heat Loss Rate",
]


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path: Path, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"A1_before_{tag}_{path.name}"
    shutil.copy2(path, dst)
    return dst


def _next_output_variable_key(data: dict) -> int:
    """Find smallest positive integer N such that 'Output:Variable N' is unused."""
    existing = data.get("Output:Variable", {})
    used = set()
    for k in existing:
        # patterns like "Output:Variable 3", "Output:Variable 19"
        parts = k.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            used.add(int(parts[-1]))
    n = 1
    while n in used:
        n += 1
    return n


def apply(data: dict) -> dict:
    """Mutate dict: add TES object, schedule, outputs."""
    report = {"added": [], "skipped": []}

    # 1) ThermalStorage:ChilledWater:Stratified
    data.setdefault("ThermalStorage:ChilledWater:Stratified", {})
    if TES_NAME in data["ThermalStorage:ChilledWater:Stratified"]:
        report["skipped"].append(f"ThermalStorage:ChilledWater:Stratified/{TES_NAME} (already exists)")
    else:
        data["ThermalStorage:ChilledWater:Stratified"][TES_NAME] = copy.deepcopy(TES_OBJECT)
        report["added"].append(f"ThermalStorage:ChilledWater:Stratified/{TES_NAME}")

    # 2) Schedule:Constant TES_Charge_Setpoint
    data.setdefault("Schedule:Constant", {})
    for sched_name, sched_body in TES_SETPOINT_SCHED.items():
        if sched_name in data["Schedule:Constant"]:
            report["skipped"].append(f"Schedule:Constant/{sched_name}")
        else:
            data["Schedule:Constant"][sched_name] = copy.deepcopy(sched_body)
            report["added"].append(f"Schedule:Constant/{sched_name}")

    # 3) Output:Variable entries
    data.setdefault("Output:Variable", {})
    existing_vars = {
        (v.get("variable_name"), v.get("key_value"))
        for v in data["Output:Variable"].values()
    }
    for var_name in TES_OUTPUT_VARS:
        key = (var_name, TES_NAME)
        if key in existing_vars:
            report["skipped"].append(f"Output:Variable {var_name} / {TES_NAME}")
            continue
        n = _next_output_variable_key(data)
        slot = f"Output:Variable {n}"
        data["Output:Variable"][slot] = {
            "key_value": TES_NAME,
            "variable_name": var_name,
            "reporting_frequency": "Timestep",
        }
        report["added"].append(f"{slot}: {var_name} / {TES_NAME}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without writing")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Confirm and write")
    args = parser.parse_args()

    if not (args.dry_run or args.yes):
        print("ERROR: pass --dry-run (preview) or -y (apply).", file=sys.stderr)
        sys.exit(2)

    tag = _now_tag()
    print(f"[M1-A1] timestamp tag: {tag}")
    print(f"[M1-A1] mode: {'DRY-RUN' if args.dry_run else 'APPLY'}")

    for epjson in TARGETS:
        if not epjson.exists():
            print(f"  MISSING: {epjson}", file=sys.stderr)
            sys.exit(1)

        print(f"\n--- Processing {epjson.name} ---")
        with open(epjson, encoding="utf-8") as f:
            data = json.load(f)

        report = apply(data)
        for line in report["added"]:
            print(f"  ADD:  {line}")
        for line in report["skipped"]:
            print(f"  SKIP: {line}")

        if args.dry_run:
            continue

        # Backup then write
        bpath = backup(epjson, tag)
        print(f"  BACKUP -> {bpath}")

        with open(epjson, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  WROTE  -> {epjson}")

        # Basic JSON legality re-read check
        with open(epjson, encoding="utf-8") as f:
            _ = json.load(f)
        print("  JSON re-parse: OK")

    print("\n[M1-A1] done.")


if __name__ == "__main__":
    main()
