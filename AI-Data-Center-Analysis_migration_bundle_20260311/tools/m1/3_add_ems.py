"""
M1-A3: 给 Chilled Water Tank 添加 EMS 控制 + SOC 观测。

核心目标
  1. RL agent 通过 action[5] ∈ [-1,+1] 写入 Schedule:Constant `TES_Set`（EMS actuator `TES_DRL`）。
  2. EMS P_5 根据 TES_Set 决定 Use 侧/Source 侧 availability：
       TES_Set > +0.05 → 充电 (Source=1, Use=0)
       TES_Set < -0.05 → 放电 (Source=0, Use=1)
       |TES_Set| ≤ 0.05 → 静置 (Source=0, Use=0)
     并叠加 SOC 物理约束：
       SOC < 0.02 → 禁放电（Use=0）
       SOC > 0.98 → 禁充电（Source=0）
  3. EMS P_6 通过 10 节点温度算 SOC，写入 Schedule:Constant `TES_SOC_Obs`（供 sinergym 观测）。

Tank 之前的 use/source availability 都挂在 "Always On Discrete"（全局共享），
需改挂到专用 `TES_Use_Avail_Sch` 和 `TES_Source_Avail_Sch`，由 EMS 写入。

用法：
    python tools/m1/3_add_ems.py --dry-run
    python tools/m1/3_add_ems.py -y
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

# 新 schedule 名
SCHED_TES_SET = "TES_Set"
SCHED_USE_AVAIL = "TES_Use_Avail_Sch"
SCHED_SRC_AVAIL = "TES_Source_Avail_Sch"
SCHED_SOC_OBS = "TES_SOC_Obs"

NEW_SCHEDULES = {
    SCHED_TES_SET: {
        "hourly_value": 0.0,
        # 不设 schedule_type_limits：RL agent 写入 [-1,+1] 会超出 Fractional [0,1] 导致 FATAL
        # 跟其它 _Set schedule（CRAH_Fan_Set 等）保持一致，不做 EnergyPlus 级别校验
    },
    SCHED_USE_AVAIL: {
        "hourly_value": 0.0,
        "schedule_type_limits_name": "Always On Discrete Limits",
    },
    SCHED_SRC_AVAIL: {
        "hourly_value": 0.0,
        "schedule_type_limits_name": "Always On Discrete Limits",
    },
    SCHED_SOC_OBS: {
        "hourly_value": 0.5,
        "schedule_type_limits_name": "Fractional",
    },
}

# 新 actuator
NEW_ACTUATORS = {
    "TES_DRL": {
        "actuated_component_unique_name": SCHED_TES_SET,
        "actuated_component_type": "Schedule:Constant",
        "actuated_component_control_type": "Schedule Value",
    },
    "TES_Use_Avail": {
        "actuated_component_unique_name": SCHED_USE_AVAIL,
        "actuated_component_type": "Schedule:Constant",
        "actuated_component_control_type": "Schedule Value",
    },
    "TES_Source_Avail": {
        "actuated_component_unique_name": SCHED_SRC_AVAIL,
        "actuated_component_type": "Schedule:Constant",
        "actuated_component_control_type": "Schedule Value",
    },
    "TES_SOC_Actuator": {
        "actuated_component_unique_name": SCHED_SOC_OBS,
        "actuated_component_type": "Schedule:Constant",
        "actuated_component_control_type": "Schedule Value",
    },
}

# 10 节点温度 sensor + TES_Set 读取 sensor
# (sensor_name) -> (key, variable_name)
NEW_SENSORS = {}
for i in range(1, 11):
    NEW_SENSORS[f"T_node_{i}"] = (
        TES_NAME,
        f"Chilled Water Thermal Storage Temperature Node {i}",
    )
NEW_SENSORS["TES_Set_Sensor"] = (SCHED_TES_SET, "Schedule Value")

# 新 global variables
NEW_GLOBALS = ["SOC", "T_tank_avg", "TES_Action"]

# Program P_5: mode selection (before timestep)
P5_LINES = [
    "SET TES_Action = TES_Set_Sensor",
    "IF SOC < 0.02",
    "SET TES_Use_Avail = 0",
    "IF TES_Action > 0.05",
    "SET TES_Source_Avail = 1",
    "ELSE",
    "SET TES_Source_Avail = 0",
    "ENDIF",
    "ELSEIF SOC > 0.98",
    "SET TES_Source_Avail = 0",
    "IF TES_Action < 0.0 - 0.05",
    "SET TES_Use_Avail = 1",
    "ELSE",
    "SET TES_Use_Avail = 0",
    "ENDIF",
    "ELSE",
    "IF TES_Action > 0.05",
    "SET TES_Source_Avail = 1",
    "SET TES_Use_Avail = 0",
    "ELSEIF TES_Action < 0.0 - 0.05",
    "SET TES_Source_Avail = 0",
    "SET TES_Use_Avail = 1",
    "ELSE",
    "SET TES_Source_Avail = 0",
    "SET TES_Use_Avail = 0",
    "ENDIF",
    "ENDIF",
]

# Program P_6: SOC calculation (after timestep report)
P6_LINES = [
    "SET T_tank_avg = (T_node_1 + T_node_2 + T_node_3 + T_node_4 + T_node_5 + T_node_6 + T_node_7 + T_node_8 + T_node_9 + T_node_10) / 10.0",
    "SET SOC = (12.0 - T_tank_avg) / 6.0",
    "IF SOC < 0.0",
    "SET SOC = 0.0",
    "ENDIF",
    "IF SOC > 1.0",
    "SET SOC = 1.0",
    "ENDIF",
    "SET TES_SOC_Actuator = SOC",
]


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path: Path, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"A3_before_{tag}_{path.name}"
    shutil.copy2(path, dst)
    return dst


def _add_schedules(data: dict, report: dict) -> None:
    data.setdefault("Schedule:Constant", {})
    for name, body in NEW_SCHEDULES.items():
        if name in data["Schedule:Constant"]:
            report["skipped"].append(f"Schedule:Constant/{name}")
        else:
            data["Schedule:Constant"][name] = copy.deepcopy(body)
            report["added"].append(f"Schedule:Constant/{name}")


def _retarget_tes_availability(data: dict, report: dict) -> None:
    tes = data["ThermalStorage:ChilledWater:Stratified"][TES_NAME]
    cur_use = tes.get("use_side_availability_schedule_name")
    cur_src = tes.get("source_side_availability_schedule_name")
    if cur_use != SCHED_USE_AVAIL:
        tes["use_side_availability_schedule_name"] = SCHED_USE_AVAIL
        report["added"].append(
            f"TES.use_side_availability: {cur_use!r} -> {SCHED_USE_AVAIL!r}"
        )
    else:
        report["skipped"].append("TES.use_side_availability (already set)")
    if cur_src != SCHED_SRC_AVAIL:
        tes["source_side_availability_schedule_name"] = SCHED_SRC_AVAIL
        report["added"].append(
            f"TES.source_side_availability: {cur_src!r} -> {SCHED_SRC_AVAIL!r}"
        )
    else:
        report["skipped"].append("TES.source_side_availability (already set)")


def _add_actuators(data: dict, report: dict) -> None:
    data.setdefault("EnergyManagementSystem:Actuator", {})
    for name, body in NEW_ACTUATORS.items():
        if name in data["EnergyManagementSystem:Actuator"]:
            report["skipped"].append(f"EMS:Actuator/{name}")
        else:
            data["EnergyManagementSystem:Actuator"][name] = copy.deepcopy(body)
            report["added"].append(f"EMS:Actuator/{name}")


def _add_sensors(data: dict, report: dict) -> None:
    data.setdefault("EnergyManagementSystem:Sensor", {})
    for name, (key, var) in NEW_SENSORS.items():
        if name in data["EnergyManagementSystem:Sensor"]:
            report["skipped"].append(f"EMS:Sensor/{name}")
        else:
            data["EnergyManagementSystem:Sensor"][name] = {
                "output_variable_or_output_meter_index_key_name": key,
                "output_variable_or_output_meter_name": var,
            }
            report["added"].append(f"EMS:Sensor/{name} = ({key} / {var})")


def _add_globals(data: dict, report: dict) -> None:
    gv = data.setdefault("EnergyManagementSystem:GlobalVariable", {})
    # 既有结构：{"EnergyManagementSystem:GlobalVariable 1": {"variables": [{"erl_variable_name": ...}, ...]}}
    if not gv:
        gv["EnergyManagementSystem:GlobalVariable 1"] = {"variables": []}
    first_key = next(iter(gv))
    existing = {v["erl_variable_name"] for v in gv[first_key].get("variables", [])}
    for gname in NEW_GLOBALS:
        if gname in existing:
            report["skipped"].append(f"EMS:GlobalVariable/{gname}")
        else:
            gv[first_key]["variables"].append({"erl_variable_name": gname})
            report["added"].append(f"EMS:GlobalVariable/{gname}")


def _add_programs(data: dict, report: dict) -> None:
    progs = data.setdefault("EnergyManagementSystem:Program", {})
    for pname, lines in [("P_5", P5_LINES), ("P_6", P6_LINES)]:
        if pname in progs:
            report["skipped"].append(f"EMS:Program/{pname}")
            continue
        progs[pname] = {"lines": [{"program_line": ln} for ln in lines]}
        report["added"].append(f"EMS:Program/{pname} ({len(lines)} lines)")


def _update_calling_manager(data: dict, report: dict) -> None:
    pcm = data.setdefault("EnergyManagementSystem:ProgramCallingManager", {})
    # 现有 P1（BeginTimestepBeforePredictor）执行 P_1、P_2
    # P_5 与它们一样在 timestep 之前决策 → 加入 P1
    # P_6 读 10 节点温度 → 最稳妥在 timestep 末尾报告阶段算，新建 P2 calling manager
    if "P1" in pcm:
        progs_p1 = pcm["P1"]["programs"]
        existing_names = {p["program_name"] for p in progs_p1}
        if "P_5" not in existing_names:
            progs_p1.append({"program_name": "P_5"})
            report["added"].append("EMS:ProgramCallingManager/P1 += P_5")
        else:
            report["skipped"].append("EMS:ProgramCallingManager/P1/P_5")
    else:
        raise RuntimeError("expected existing calling manager P1 missing")

    # 新建 P2 calling manager for P_6
    if "P2" in pcm:
        existing_names = {p["program_name"] for p in pcm["P2"]["programs"]}
        if "P_6" not in existing_names:
            pcm["P2"]["programs"].append({"program_name": "P_6"})
            report["added"].append("EMS:ProgramCallingManager/P2 += P_6")
        else:
            report["skipped"].append("EMS:ProgramCallingManager/P2/P_6")
    else:
        pcm["P2"] = {
            "energyplus_model_calling_point": "EndOfZoneTimestepAfterZoneReporting",
            "programs": [{"program_name": "P_6"}],
        }
        report["added"].append("EMS:ProgramCallingManager/P2 (EndOfZoneTimestepAfterZoneReporting) += P_6")


def _add_soc_output(data: dict, report: dict) -> None:
    """Add Output:Variable for TES_SOC_Obs (Schedule Value) and 10 node temps for debugging."""
    outs = data.setdefault("Output:Variable", {})
    existing = {(v.get("variable_name"), v.get("key_value")) for v in outs.values()}

    def _next_n() -> int:
        used = set()
        for k in outs:
            parts = k.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                used.add(int(parts[-1]))
        n = 1
        while n in used:
            n += 1
        return n

    wanted = [
        ("Schedule Value", SCHED_SOC_OBS),
        ("Schedule Value", SCHED_TES_SET),
        ("Schedule Value", SCHED_USE_AVAIL),
        ("Schedule Value", SCHED_SRC_AVAIL),
    ]
    for var, key in wanted:
        if (var, key) in existing:
            report["skipped"].append(f"Output:Variable {var}/{key}")
            continue
        n = _next_n()
        slot = f"Output:Variable {n}"
        outs[slot] = {
            "key_value": key,
            "variable_name": var,
            "reporting_frequency": "Timestep",
        }
        report["added"].append(f"{slot}: {var}/{key}")


def apply(data: dict) -> dict:
    report = {"added": [], "skipped": []}

    # sanity
    if TES_NAME not in data.get("ThermalStorage:ChilledWater:Stratified", {}):
        raise RuntimeError("TES not found; run M1-A1/A2 first")

    _add_schedules(data, report)
    _retarget_tes_availability(data, report)
    _add_actuators(data, report)
    _add_sensors(data, report)
    _add_globals(data, report)
    _add_programs(data, report)
    _update_calling_manager(data, report)
    _add_soc_output(data, report)

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
    print(f"[M1-A3] timestamp tag: {tag}")
    print(f"[M1-A3] mode: {'DRY-RUN' if args.dry_run else 'APPLY'}")

    for epjson in TARGETS:
        if not epjson.exists():
            print(f"  MISSING: {epjson}", file=sys.stderr)
            sys.exit(1)

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

    print("\n[M1-A3] done.")


if __name__ == "__main__":
    main()
