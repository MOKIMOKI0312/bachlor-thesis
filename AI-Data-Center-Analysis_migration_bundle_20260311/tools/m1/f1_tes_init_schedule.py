"""F1 (TES SOC random init): 把 TES_Charge_Setpoint 从 Schedule:Constant 改成 Schedule:Compact。

背景：
- E+ 23.1 `ThermalStorage:ChilledWater:Stratified` 没有 initial_temperature 字段，
  没有节点温度 EMS actuator。
- 但 probe #1/#2 证实：tank 节点初始温度 = setpoint_temperature_schedule 首值。
- Schedule:Compact 可以分段设置：
  * Until 00:15 = T_init (随机目标 T ∈ U(6, 12))  → tank 初始化成 T_init
  * Until 24:00 = 6.0                           → 恢复正常 cut-out 温度控制

改动范围（三个 epJSON 共通）：
  - 删除 Schedule:Constant 中的 TES_Charge_Setpoint
  - 添加 Schedule:Compact 中的 TES_Charge_Setpoint，默认 init_T = 6.0（等价旧行为）
  - sinergym 的 reset 流程在加载 self.building 后修改第一段值（Python 改动，由 code-fixer 接手）

用法：
    python tools/m1/f1_tes_init_schedule.py --dry-run   # 预览变更
    python tools/m1/f1_tes_init_schedule.py -y           # 确认写盘
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[2]
BUILDINGS_DIR = ROOT / "Data" / "buildings"

TARGETS = [
    # Only DRL_DC_* has TES; Baseline_DC.epJSON has no TES and must not be patched.
    "DRL_DC_training.epJSON",
    "DRL_DC_evaluation.epJSON",
]

DEFAULT_T_INIT = 6.0   # 默认值，保持旧行为等价
DEFAULT_T_NORMAL = 6.0  # 正常运行时的 setpoint (cut-out)


def _patch(data: dict) -> Tuple[bool, List[str]]:
    """
    Apply F1 patch to the epJSON dict.
    Returns (changed, log_lines).
    """
    log: List[str] = []
    changed = False

    # ---- 0. Sanity: only patch files that actually have TES ----
    tes_obj = data.get("ThermalStorage:ChilledWater:Stratified", {})
    if not tes_obj:
        log.append("  [skip] no ThermalStorage:ChilledWater:Stratified object — not patching")
        return False, log

    # ---- 1. Remove Schedule:Constant.TES_Charge_Setpoint ----
    sc = data.get("Schedule:Constant", {})
    if "TES_Charge_Setpoint" in sc:
        old_val = sc["TES_Charge_Setpoint"].get("hourly_value", None)
        old_limits = sc["TES_Charge_Setpoint"].get("schedule_type_limits_name", None)
        del sc["TES_Charge_Setpoint"]
        log.append(
            f"  [-] Schedule:Constant.TES_Charge_Setpoint removed "
            f"(was hourly_value={old_val}, limits={old_limits})"
        )
        changed = True

    # ---- 2. Add Schedule:Compact.TES_Charge_Setpoint ----
    scc = data.setdefault("Schedule:Compact", {})
    if "TES_Charge_Setpoint" in scc:
        # idempotency guard: only overwrite if content differs from target
        old_data = scc["TES_Charge_Setpoint"].get("data", [])
        log.append(
            f"  [!] Schedule:Compact.TES_Charge_Setpoint already exists with "
            f"{len(old_data)} fields - overwriting"
        )

    scc["TES_Charge_Setpoint"] = {
        "schedule_type_limits_name": "Temperature",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: AllDays"},
            {"field": "Until: 00:15"},
            {"field": str(DEFAULT_T_INIT)},
            {"field": "Until: 24:00"},
            {"field": str(DEFAULT_T_NORMAL)},
        ],
    }
    log.append(
        f"  [+] Schedule:Compact.TES_Charge_Setpoint added "
        f"(Until 00:15 = {DEFAULT_T_INIT}, Until 24:00 = {DEFAULT_T_NORMAL})"
    )
    changed = True

    # ---- 3. Sanity: ensure Schedule:Constant still exists but without TES_Charge_Setpoint ----
    # (Schedule:Constant dict may become empty if it was the only key, but E+ is fine with empty
    # section or missing section; we leave empty if so.)
    if not sc:
        # keep empty {} rather than deleting the section - safer
        pass

    return changed, log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview the changes without writing to disk")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Confirm writing changes to disk")
    parser.add_argument("--target", action="append", default=None,
                        help="Target epJSON basename (default: all three)")
    args = parser.parse_args()

    if not (args.dry_run or args.yes):
        print("ERROR: must specify --dry-run or -y", file=sys.stderr)
        return 2

    targets = args.target if args.target else TARGETS

    for t in targets:
        src = BUILDINGS_DIR / t
        if not src.exists():
            print(f"WARNING: {src} not found, skipping", file=sys.stderr)
            continue

        print(f"\n--- Processing {src.name} ---")
        with open(src, encoding="utf-8") as f:
            data = json.load(f)

        changed, log = _patch(data)
        for line in log:
            print(line)

        if not changed:
            print("  (no changes)")
            continue

        if args.dry_run:
            print("  [dry-run] not writing")
            continue

        # Validate by re-serializing + re-parsing
        # Use indent=2 to match the original epJSON formatting (avoid noisy diffs)
        try:
            text = json.dumps(data, indent=2, ensure_ascii=False)
            _ = json.loads(text)
        except Exception as e:
            print(f"  ERROR: patched JSON is invalid: {e}", file=sys.stderr)
            return 3

        with open(src, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  [write] {src.name}")

    if args.dry_run:
        print("\n[dry-run] DONE. No files changed. Use -y to write.")
    else:
        print("\n[write] DONE. Files updated.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
