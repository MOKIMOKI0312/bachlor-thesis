"""
M1-A3b: EMS 动态关闭 Chiller, 迫使放电时 CRAH 负载走 TES Use 侧.

背景
  在 M1-A3 的 C_discharge 场景 (TES_Set=-0.5) 中, 即便 TES_Use_Avail_Sch=1,
  TES Use 侧 Heat Transfer Rate 全程为 0. 原因: Chilled Water Loop Cooling
  Equipment List 中 Chiller 优先级高于 TES, 只要 Chiller 能出力, CRAH 负载
  就走 Chiller, TES Use 分支无流量驱动.

方案 (Plan B, 直接 actuator)
  通过 EDD 文件确认 Chiller:Electric:EIR 支持直接 actuator:
    EnergyManagementSystem:Actuator Available,
    90.1-2019 WATERCOOLED  CENTRIFUGAL CHILLER 0 1230TONS 0.6KW/TON,
    Plant Component Chiller:Electric:EIR,On/Off Supervisory,[fraction]
  比 Schedule 路径更直接, 不需改 Chiller 对象字段.

  但为了保持可观测性 (sinergym 能看到 Chiller_Avail 状态用于 debug),
  我们同时:
    1. 新增 Schedule:Constant `Chiller_Avail_Sch` (默认 1, 供 Output:Variable 观测)
    2. 新增 EMS:Actuator `Chiller_Avail_Direct` 对 Plant Component Chiller:Electric:EIR
       (真正起作用的 actuator)
    3. 新增 EMS:Actuator `Chiller_Avail_Obs` 对 Chiller_Avail_Sch
       (仅为了记录 debug, sinergym 可观测)
    4. 扩展 P_5 Program:
         IF TES_Action < -0.05 AND SOC > 0.02   ! 放电模式 且 SOC 够
           SET Chiller_Avail_Direct = 0
           SET Chiller_Avail_Obs = 0
         ELSE
           SET Chiller_Avail_Direct = 1
           SET Chiller_Avail_Obs = 1
         ENDIF

用法:
    python tools/m1/4_chiller_avail_control.py --dry-run
    python tools/m1/4_chiller_avail_control.py -y
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

# 精确匹配 epJSON 里 Chiller:Electric:EIR 的 unique name
CHILLER_NAME = "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton"
# Chiller Supply Inlet Water Node — 通过 Mass Flow Rate Maximum Available Setpoint 置 0 可阻断
CHILLER_SUPPLY_INLET_NODE = (
    "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton Supply Inlet Water Node"
)
# Chiller Supply Outlet Node — 用 Temperature Setpoint 强制抬升到 30°C 让 Chiller 不需出力
CHILLER_SUPPLY_OUTLET_NODE = (
    "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton Supply Outlet Water Node"
)

SCHED_CHILLER_AVAIL_OBS = "Chiller_Avail_Sch"
# 多管齐下 (四种 actuator 同时生效, 因 BeginTimestepBeforePredictor 时某些可能被重置):
#   1. Plant Component Chiller:Electric:EIR / On/Off Supervisory (fraction)
#   2. Supply Side Branch / On/Off Supervisory (on/off)
#   3. Chiller Supply Outlet Node / Temperature Setpoint (C) — 抬高到 30°C
#   4. Chiller Supply Inlet Node / Mass Flow Rate Maximum Available Setpoint (kg/s) → 0
ACTUATOR_CHILLER_COMPONENT = "Chiller_Component_Avail"
ACTUATOR_CHILLER_BRANCH = "Chiller_Branch_Avail"
ACTUATOR_CHILLER_T_SP = "Chiller_Out_T_SP"
ACTUATOR_CHILLER_MFLOW_MAX = "Chiller_In_MFlow_Max"
ACTUATOR_CHILLER_OBS = "Chiller_Avail_Obs"


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _backup(src: Path, tag: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"A3b_before_{tag}__{src.name}"
    shutil.copy2(src, dst)
    return dst


def _ensure_schedule_constant(data: dict, name: str, val: float, limits: str) -> str:
    sc = data.setdefault("Schedule:Constant", {})
    if name in sc:
        return f"exists: {name}"
    sc[name] = {"hourly_value": val, "schedule_type_limits_name": limits}
    return f"added: {name}"


def _ensure_actuator(data: dict, key: str, component_name: str,
                     component_type: str, control_type: str) -> str:
    ema = data.setdefault("EnergyManagementSystem:Actuator", {})
    if key in ema:
        cur = ema[key]
        # 已存在则校验
        if (cur.get("actuated_component_unique_name") == component_name
            and cur.get("actuated_component_type") == component_type
            and cur.get("actuated_component_control_type") == control_type):
            return f"exists: {key}"
        else:
            ema[key] = {
                "actuated_component_unique_name": component_name,
                "actuated_component_type": component_type,
                "actuated_component_control_type": control_type,
            }
            return f"updated: {key}"
    ema[key] = {
        "actuated_component_unique_name": component_name,
        "actuated_component_type": component_type,
        "actuated_component_control_type": control_type,
    }
    return f"added: {key}"


def _ensure_output_variable(data: dict, key_value: str, variable_name: str,
                             freq: str = "Timestep") -> str:
    ov = data.setdefault("Output:Variable", {})
    # 查已有
    for k, obj in ov.items():
        if (obj.get("key_value") == key_value
                and obj.get("variable_name") == variable_name):
            return f"exists: Output:Variable {key_value}/{variable_name}"
    # 找新 key
    i = 1
    while f"Output:Variable {i}" in ov:
        i += 1
    ov[f"Output:Variable {i}"] = {
        "key_value": key_value,
        "variable_name": variable_name,
        "reporting_frequency": freq,
    }
    return f"added: Output:Variable {i} ({key_value}/{variable_name})"


# 新 P_5 扩展行 (在原 P_5 末尾追加)
# 注: EMS Runtime Language 在 epJSON 里不允许 '!' 开头的注释行,
# 用无害 SET 作为幂等 marker.
#
# 正常状态: Chiller 正常 (avail=1), 出口温度 setpoint 保持 6.67°C, flow max available 不变
# 放电状态: Chiller 关停, 出口温度 setpoint 抬到 30°C, flow max=0
# 流量阻断需要多 call-point, 单独新建 P_7 在 InsideHVACSystemIterationLoop 调用
CHILLER_CTRL_BLOCK = [
    "SET Chiller_Branch_Avail = 1",
    "SET Chiller_Component_Avail = 1",
    "SET Chiller_Out_T_SP = 6.67",
    "SET Chiller_In_MFlow_Max = 9999.0",
    "SET Chiller_Avail_Obs = 1",
    "IF TES_Action < 0.0 - 0.05",
    "IF SOC > 0.02",
    "SET Chiller_Branch_Avail = 0",
    "SET Chiller_Component_Avail = 0",
    "SET Chiller_Out_T_SP = 30.0",
    "SET Chiller_In_MFlow_Max = 0.0",
    "SET Chiller_Avail_Obs = 0",
    "ENDIF",
    "ENDIF",
]

# P_7: 在 InsideHVACSystemIterationLoop 再次强制 flow=0 & avail=0
# (因为 predictor/plant iteration 期间前面的 actuator 可能被重置)
# 需同时判断 TES_Set<-0.05 AND SOC>0.02, 否则 SOC=0 时还会把 Chiller 压住
P7_LINES = [
    "IF TES_Set_Sensor < 0.0 - 0.05",
    "IF SOC > 0.02",
    "SET Chiller_Branch_Avail = 0",
    "SET Chiller_Component_Avail = 0",
    "SET Chiller_In_MFlow_Max = 0.0",
    "SET Chiller_Out_T_SP = 30.0",
    "ENDIF",
    "ENDIF",
]

# 幂等 marker: 初始化 Chiller_Branch_Avail 那一行只在 A3b 添加.
MARKER = "SET Chiller_Branch_Avail = 1"


def _extend_p5(data: dict) -> str:
    progs = data.setdefault("EnergyManagementSystem:Program", {})
    if "P_5" not in progs:
        return "ERROR: P_5 not found"
    p5 = progs["P_5"]
    lines = p5.get("lines", [])
    # 检查 marker 是否已存在 (幂等)
    for ln in lines:
        if ln.get("program_line", "").strip() == MARKER:
            return "P_5 already extended (marker found)"
    # 追加
    for stmt in CHILLER_CTRL_BLOCK:
        lines.append({"program_line": stmt})
    p5["lines"] = lines
    return f"P_5 extended with {len(CHILLER_CTRL_BLOCK)} lines"


def apply_one(path: Path, tag: str, dry_run: bool) -> dict:
    report = {"file": str(path.name), "steps": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # 1. 备份
    if not dry_run:
        bp = _backup(path, tag)
        report["steps"].append(f"backup -> {bp}")

    # 2. Schedule:Constant Chiller_Avail_Sch (obs)
    r = _ensure_schedule_constant(data, SCHED_CHILLER_AVAIL_OBS, 1.0, "Always On Discrete Limits")
    report["steps"].append(r)

    # 3a. Actuator 对 Chiller 所在 Supply Branch On/Off Supervisory
    r = _ensure_actuator(
        data,
        ACTUATOR_CHILLER_BRANCH,
        "Chilled Water Loop Supply Branch 1",
        "Supply Side Branch",
        "On/Off Supervisory",
    )
    report["steps"].append(r)

    # 3b. Actuator 对 Plant Component Chiller:Electric:EIR On/Off Supervisory
    r = _ensure_actuator(
        data,
        ACTUATOR_CHILLER_COMPONENT,
        CHILLER_NAME,
        "Plant Component Chiller:Electric:EIR",
        "On/Off Supervisory",
    )
    report["steps"].append(r)

    # 3c. Actuator 对 Chiller Supply Outlet Node Temperature Setpoint
    r = _ensure_actuator(
        data,
        ACTUATOR_CHILLER_T_SP,
        CHILLER_SUPPLY_OUTLET_NODE,
        "System Node Setpoint",
        "Temperature Setpoint",
    )
    report["steps"].append(r)

    # 3d. Actuator 对 Chiller Supply Inlet Node Mass Flow Rate Maximum Available
    r = _ensure_actuator(
        data,
        ACTUATOR_CHILLER_MFLOW_MAX,
        CHILLER_SUPPLY_INLET_NODE,
        "System Node Setpoint",
        "Mass Flow Rate Maximum Available Setpoint",
    )
    report["steps"].append(r)

    # 4. Actuator 对 Chiller_Avail_Sch (观测用)
    r = _ensure_actuator(
        data,
        ACTUATOR_CHILLER_OBS,
        SCHED_CHILLER_AVAIL_OBS,
        "Schedule:Constant",
        "Schedule Value",
    )
    report["steps"].append(r)

    # 5. 扩展 P_5
    r = _extend_p5(data)
    report["steps"].append(r)

    # 5b. 新增 P_7 (放电时反复强制 Chiller off) + 在 InsideHVACSystemIterationLoop 调用
    progs = data.setdefault("EnergyManagementSystem:Program", {})
    if "P_7" not in progs:
        progs["P_7"] = {"lines": [{"program_line": s} for s in P7_LINES]}
        report["steps"].append(f"P_7 added ({len(P7_LINES)} lines)")
    else:
        report["steps"].append("P_7 already exists (skip)")

    pcm = data.setdefault("EnergyManagementSystem:ProgramCallingManager", {})
    if "P3" not in pcm:
        pcm["P3"] = {
            "energyplus_model_calling_point": "InsideHVACSystemIterationLoop",
            "programs": [{"program_name": "P_7"}],
        }
        report["steps"].append("ProgramCallingManager P3 added (InsideHVACSystemIterationLoop -> P_7)")
    else:
        report["steps"].append("ProgramCallingManager P3 exists (skip)")

    # 6. 添加 Output:Variable
    r = _ensure_output_variable(data, SCHED_CHILLER_AVAIL_OBS, "Schedule Value")
    report["steps"].append(r)
    r = _ensure_output_variable(data, CHILLER_NAME, "Chiller Electricity Rate")
    report["steps"].append(r)
    r = _ensure_output_variable(data, CHILLER_NAME, "Chiller Evaporator Cooling Rate")
    report["steps"].append(r)

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        report["steps"].append("file saved")
    else:
        report["steps"].append("[dry-run] file NOT saved")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-y", "--yes", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.yes:
        print("Use --dry-run or -y", file=sys.stderr)
        sys.exit(2)

    tag = _now_tag()
    print(f"=== M1-A3b Chiller Availability EMS Control ===  tag={tag}")
    for path in TARGETS:
        if not path.exists():
            print(f"  SKIP missing: {path}")
            continue
        print(f"\n--- {path.name} ---")
        rep = apply_one(path, tag, args.dry_run)
        for step in rep["steps"]:
            print(f"  {step}")

    print("\nDone.")


if __name__ == "__main__":
    main()
