"""
M1 修复：P_5 + P_7 的 chiller-kill 死锁 bug。

Bug 根因（见任务说明）
======================
技术路线 §3.1 约定 `v>0 = 放电`，`v<0 = 充电`。原 P_5 把 "关 chiller" 块放在
`IF TES_Signal < -0.01`（充电分支）里，等于"充电时把唯一的冷源关掉"，造成物理
死锁：充电永远不会发生，chiller 还被强行关停，机房温度爆表。

运行期观察（run-074/episode-060 及以后）确认 agent 学会了 reward exploit：发
TES_Set=负（本应是"充电"） → chiller 被关 → Electricity 下降 → reward 上升；
代价是 Zone 温度 58°C，但 comfort λ=1.0 不够罚。

P_7 是 HVAC 迭代内的"守护"，复制了和 P_5 一模一样的 kill 块，方向同样是反的。
它的**结构是必要的**：BeginTimestepBeforePredictor 的 actuator 设置在 HVAC
solver 迭代内会被覆盖，必须在 InsideHVACSystemIterationLoop 反复强制——建筑
模型说明 §9.11 明确说明"P_7 守护说明：非冗余"。所以修 P_7 方向而不是删除它。

修复策略
========
1. P_5：把 "关 chiller" 块从 `IF TES_Signal < -0.01` 搬到 `IF TES_Signal > 0.01`
   （放电分支）。放电期 tank 给 coil 供冷，chiller 可以关掉省电。
2. P_5：SOC 安全阈值 `> 0.02` 提升到 `> 0.15`，跟 reward 的 `soc_low=0.15`
   对齐，避免 tank 快耗尽时 chiller 还被关。
3. P_7：同步修方向 —— 条件从 `TES_Set_Sensor < -0.01`（充电）改为
   `TES_Set_Sensor > 0.01`（放电），SOC 阈值同步 0.02→0.15。逻辑体不变。

用法
====
  python tools/m1/fix_p5_chiller_deadlock.py --dry-run         # 仅预览
  python tools/m1/fix_p5_chiller_deadlock.py -y                # 同时写回 training+evaluation
  python tools/m1/fix_p5_chiller_deadlock.py -y --only training
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDINGS = ROOT / "Data" / "buildings"


# -----------------------------------------------------------------------------
# 期望的 P_5 新内容：放电分支里叠加关 chiller，SOC 安全阈值 0.15
# -----------------------------------------------------------------------------
NEW_P5_LINES: list[str] = [
    # 读取 RL 动作并计算流量
    "SET TES_Signal = TES_Set_Sensor",
    "SET Max_Flow = 97.2",
    "SET Flow = @Abs TES_Signal * Max_Flow",
    # 默认：两侧都关
    "SET TES_Use_MFlow_Max = 0.0",
    "SET TES_Use_MFlow_Min = 0.0",
    "SET TES_Source_MFlow_Max = 0.0",
    "SET TES_Source_MFlow_Min = 0.0",
    "SET TES_Use_Avail = 0",
    "SET TES_Source_Avail = 0",
    # 放电分支 (v > 0)：Use 侧开
    "IF TES_Signal > 0.01",
    "  SET TES_Use_Avail = 1",
    "  SET TES_Use_MFlow_Max = Flow",
    "  SET TES_Use_MFlow_Min = Flow",
    "  SET TES_Source_Avail = 0",
    # 充电分支 (v < 0)：Source 侧开
    "ELSEIF TES_Signal < 0.0 - 0.01",
    "  SET TES_Source_Avail = 1",
    "  SET TES_Source_MFlow_Max = Flow",
    "  SET TES_Source_MFlow_Min = Flow",
    "  SET TES_Use_Avail = 0",
    "ENDIF",
    # Chiller 默认全开
    "SET Chiller_Branch_Avail = 1",
    "SET Chiller_Component_Avail = 1",
    "SET Chiller_Out_T_SP = 6.67",
    "SET Chiller_In_MFlow_Max = 9999.0",
    "SET Chiller_Avail_Obs = 1",
    # 放电期省电：tank 供冷充足时才关 chiller
    # SOC 阈值从 0.02 提到 0.15，与 reward.soc_low 对齐
    "IF TES_Signal > 0.01",
    "  IF SOC > 0.15",
    "    SET Chiller_Branch_Avail = 0",
    "    SET Chiller_Component_Avail = 0",
    "    SET Chiller_Out_T_SP = 30.0",
    "    SET Chiller_In_MFlow_Max = 0.0",
    "    SET Chiller_Avail_Obs = 0",
    "  ENDIF",
    "ENDIF",
]


# -----------------------------------------------------------------------------
# 期望的 P_7 新内容（HVAC 迭代循环内守护，保持 P_5 决策在迭代中不被 solver 覆盖）
# 条件：放电分支 v>0.01 且 SOC>0.15 时，反复把 chiller 4 个 actuator 强制设为关停。
# -----------------------------------------------------------------------------
NEW_P7_LINES: list[str] = [
    "IF TES_Set_Sensor > 0.01",
    "  IF SOC > 0.15",
    "    SET Chiller_Branch_Avail = 0",
    "    SET Chiller_Component_Avail = 0",
    "    SET Chiller_Out_T_SP = 30.0",
    "    SET Chiller_In_MFlow_Max = 0.0",
    "    SET Chiller_Avail_Obs = 0",
    "  ENDIF",
    "ENDIF",
]


def _replace_p5(data: dict) -> None:
    """Rewrite EnergyManagementSystem:Program.P_5 with NEW_P5_LINES."""
    programs = data.get("EnergyManagementSystem:Program", {})
    if "P_5" not in programs:
        raise RuntimeError("Program P_5 not found in epJSON")
    programs["P_5"] = {"lines": [{"program_line": ln} for ln in NEW_P5_LINES]}


def _replace_p7(data: dict) -> None:
    """Rewrite EnergyManagementSystem:Program.P_7 with NEW_P7_LINES.

    保留 P_7 整个对象和 ProgramCallingManager.P3（InsideHVACSystemIterationLoop），
    只更正它的条件方向（充电→放电）和 SOC 阈值（0.02→0.15）。
    """
    programs = data.get("EnergyManagementSystem:Program", {})
    if "P_7" not in programs:
        raise RuntimeError("Program P_7 not found in epJSON")
    programs["P_7"] = {"lines": [{"program_line": ln} for ln in NEW_P7_LINES]}

    # 确认 P3 manager 还在调用 P_7
    managers = data.get("EnergyManagementSystem:ProgramCallingManager", {})
    p3 = managers.get("P3")
    if p3 is None:
        raise RuntimeError("ProgramCallingManager P3 not found (P_7 guard removed?)")
    prog_names = [p.get("program_name") for p in p3.get("programs", [])]
    if "P_7" not in prog_names:
        raise RuntimeError(f"P_7 not in P3 manager programs list: {prog_names}")


def _validate(data: dict) -> dict:
    """Sanity check after modification: return summary dict."""
    programs = data.get("EnergyManagementSystem:Program", {})
    p5 = programs["P_5"]["lines"]
    p5_text = "\n".join(ln["program_line"] for ln in p5)
    p7 = programs["P_7"]["lines"]
    p7_text = "\n".join(ln["program_line"] for ln in p7)

    # P_5: new kill block must be under "IF TES_Signal > 0.01" (second occurrence)
    # and SOC threshold must be 0.15
    p5_positive_kill = "IF TES_Signal > 0.01\n  IF SOC > 0.15\n    SET Chiller_Branch_Avail = 0" in p5_text
    p5_negative_kill_bug = "IF TES_Signal < 0.0 - 0.01\n  IF SOC > 0" in p5_text

    # P_7: condition must now be `TES_Set_Sensor > 0.01` (discharge) + SOC > 0.15
    p7_positive = "IF TES_Set_Sensor > 0.01\n  IF SOC > 0.15" in p7_text
    p7_negative_bug = "IF TES_Set_Sensor < 0.0 - 0.01" in p7_text

    managers = data.get("EnergyManagementSystem:ProgramCallingManager", {})
    return {
        "P_5_line_count": len(p5),
        "P_5_has_positive_kill_block": p5_positive_kill,
        "P_5_has_negative_kill_block_bug": p5_negative_kill_bug,
        "P_7_line_count": len(p7),
        "P_7_condition_positive": p7_positive,
        "P_7_condition_negative_bug": p7_negative_bug,
        "manager_count": len(managers),
        "manager_names": sorted(managers.keys()),
        "P3_calls_P7": "P_7" in [p.get("program_name") for p in managers.get("P3", {}).get("programs", [])],
    }


def _plan_diff(src: Path) -> tuple[dict, dict, dict]:
    """Load, apply mods in memory, return (original_summary, modified_data, new_summary)."""
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    before = {
        "P_5_line_count": len(data["EnergyManagementSystem:Program"]["P_5"]["lines"]),
        "P_7_line_count": len(data["EnergyManagementSystem:Program"]["P_7"]["lines"])
            if "P_7" in data["EnergyManagementSystem:Program"] else 0,
        "managers": sorted(data.get("EnergyManagementSystem:ProgramCallingManager", {}).keys()),
    }

    _replace_p5(data)
    _replace_p7(data)

    after = _validate(data)
    return before, data, after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Only print what would change, don't write")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Actually write modified files back")
    parser.add_argument("--only", choices=["training", "evaluation"],
                        default=None, help="Only modify this file")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("ERROR: must specify either --dry-run or -y", file=sys.stderr)
        return 2

    targets = []
    if args.only in (None, "training"):
        targets.append(BUILDINGS / "DRL_DC_training.epJSON")
    if args.only in (None, "evaluation"):
        targets.append(BUILDINGS / "DRL_DC_evaluation.epJSON")

    for target in targets:
        if not target.exists():
            print(f"ERROR: missing {target}", file=sys.stderr)
            return 2

        print(f"\n=== {target.name} ===")
        before, data, after = _plan_diff(target)

        print(f"  BEFORE: P_5 lines={before['P_5_line_count']}, "
              f"P_7 lines={before['P_7_line_count']}, "
              f"managers={before['managers']}")
        print(f"  AFTER:  P_5 lines={after['P_5_line_count']}, "
              f"P_5 has positive-branch kill={after['P_5_has_positive_kill_block']}, "
              f"P_5 still has buggy negative kill={after['P_5_has_negative_kill_block_bug']}")
        print(f"          P_7 lines={after['P_7_line_count']}, "
              f"P_7 condition positive={after['P_7_condition_positive']}, "
              f"P_7 still has buggy negative={after['P_7_condition_negative_bug']}, "
              f"managers={after['manager_names']}, P3 calls P_7={after['P3_calls_P7']}")

        # Assertions
        assert after["P_5_has_positive_kill_block"], \
            "Post-fix P_5 missing IF TES_Signal > 0.01 / IF SOC > 0.15 / KILL CHILLER block"
        assert not after["P_5_has_negative_kill_block_bug"], \
            "Post-fix P_5 still has buggy 'IF TES_Signal < -0.01 / IF SOC > 0' block"
        assert after["P_7_condition_positive"], \
            "Post-fix P_7 missing IF TES_Set_Sensor > 0.01 / IF SOC > 0.15 guard"
        assert not after["P_7_condition_negative_bug"], \
            "Post-fix P_7 still has buggy 'TES_Set_Sensor < -0.01' condition"
        assert after["P3_calls_P7"], \
            "ProgramCallingManager.P3 should still call P_7 (HVAC iteration guard)"

        if args.yes:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  [WROTE] {target}")
        else:
            print(f"  [DRY-RUN] would write {target}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
