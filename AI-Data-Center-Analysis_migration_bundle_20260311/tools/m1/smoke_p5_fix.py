"""
Smoke test for the P_5/P_7 chiller-kill deadlock fix (2026-04-23).

不依赖 sinergym 的 RL 管线，直接用 E+ exe 跑一天仿真：
  - A (charge):    TES_Set = -0.5  → 期望 chiller 始终 ON，SOC 上升
  - B (discharge): TES_Set = +0.5  → 放电早期 chiller OFF，SOC 降到 <0.15 时 chiller 恢复

每天 24 小时 * 4 timestep = 96 步；各取首/中/末 3 个采样点汇报。

用法：
    python tools/m1/smoke_p5_fix.py
    python tools/m1/smoke_p5_fix.py --only A   # 只跑充电
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
# NOTE: fix-p5-chiller-b068 worktree 的 vendor/ 不包含 E+。直接用 great-hugle 的
# 安装（同一台机器上另一个 worktree 的副本，位置固定）。
# 如果该路径不在，脚本会报错，用户需自行指定 --eplus-exe。
DEFAULT_EPLUS = Path(
    "C:/Users/18430/Desktop/毕业设计代码/.claude/worktrees/great-hugle-fb3530"
    "/AI-Data-Center-Analysis_migration_bundle_20260311"
    "/vendor/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64/energyplus.exe"
)
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"

# 只在 2025-01-01 跑 1 天，timestep 15 分钟 → 96 steps
# 固定 RunPeriod 用 weekday = Wednesday（与 Jan 1 2025 匹配）
SCENARIOS = [
    ("A_charge",    -0.5),  # 强制充电：v<0
    ("B_discharge", +0.5),  # 强制放电：v>0
]


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _patch_epjson(tes_set_val: float, dst: Path, days: int = 1) -> None:
    """写一份短 runperiod 的 epJSON，TES_Set 固定为 tes_set_val。"""
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    end_day = min(31, max(1, days))
    data["RunPeriod"] = {"RP Short": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": 1, "end_day_of_month": end_day, "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 4}}
    data["Schedule:Constant"]["TES_Set"]["hourly_value"] = tes_set_val

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _pick_col(header: list[str], substrs: list[str]) -> int:
    low = [h.lower() for h in header]
    for i, h in enumerate(low):
        if all(s.lower() in h for s in substrs):
            return i
    return -1


def _parse_csv(csv_path: Path) -> dict:
    """Return dict with columns needed for smoke analysis."""
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = list(rdr)

    cols = {
        "date":           0,  # eplus always writes Date/Time as first col
        "tes_set":        _pick_col(header, ["TES_Set", "Schedule Value"]),
        "chiller_avail":  _pick_col(header, ["Chiller_Avail_Sch", "Schedule Value"]),
        "chiller_T":      _pick_col(header, ["Chilled Water Loop Supply Outlet Node", "Temperature"]),
        "chiller_elec":   _pick_col(header, ["1230TON WATERCOOLED CHILLER", "Electricity Rate"]),
        "air_temp":       _pick_col(header, ["DataCenter ZN", "Zone Air Temperature"]),
        "soc":            _pick_col(header, ["TES_SOC_Obs", "Schedule Value"]),
        "facility_elec":  _pick_col(header, ["Electricity:Facility"]),
        "tank_T":         _pick_col(header, ["Chilled Water Tank", "Final Tank Temperature"]),
        "use_ht":         _pick_col(header, ["Chilled Water Tank", "Use Side Heat Transfer Rate"]),
        "source_ht":      _pick_col(header, ["Chilled Water Tank", "Source Side Heat Transfer Rate"]),
    }

    out = {"header_indices": cols, "header": header, "n_rows": len(rows)}
    series = {k: [] for k in cols}
    for r in rows:
        for k, idx in cols.items():
            if idx < 0:
                series[k].append(None)
                continue
            try:
                if k == "date":
                    series[k].append(r[idx])
                else:
                    series[k].append(float(r[idx]))
            except (ValueError, IndexError):
                series[k].append(None)
    out["series"] = series
    return out


def _safe_stat(vals: list) -> dict:
    clean = [v for v in vals if isinstance(v, (int, float))]
    if not clean:
        return {"missing": True}
    return {
        "n": len(clean),
        "min": min(clean),
        "max": max(clean),
        "mean": sum(clean) / len(clean),
        "last": clean[-1],
    }


def _count_err(err_path: Path) -> dict:
    import re
    if not err_path.exists():
        return {"severe": -1, "fatal": -1}
    sev, fat = 0, 0
    sev_lines, fat_lines = [], []
    with open(err_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if re.match(r"\s*\*\*\s*Severe\s*\*\*", line):
                sev += 1
                if len(sev_lines) < 10:
                    sev_lines.append(line.rstrip())
            elif re.match(r"\s*\*\*\s*Fatal\s*\*\*", line):
                fat += 1
                if len(fat_lines) < 10:
                    fat_lines.append(line.rstrip())
    return {"severe": sev, "fatal": fat, "severe_lines": sev_lines, "fatal_lines": fat_lines}


def _analyze_scenario(name: str, tes_set_val: float, parsed: dict) -> dict:
    s = parsed["series"]
    cols = parsed["header_indices"]

    # 判定: 把 Chiller_Avail_Obs 作为首要指标（E+ 内 EMS 写入）
    ca = [v for v in s["chiller_avail"] if isinstance(v, (int, float))]
    soc = [v for v in s["soc"] if isinstance(v, (int, float))]
    air = [v for v in s["air_temp"] if isinstance(v, (int, float))]

    # 采样点：首 / 中 / 末
    idxs = []
    if ca:
        idxs = [0, len(ca) // 2, len(ca) - 1]

    samples = []
    for i in idxs:
        row = {"step_idx": i, "date": s["date"][i] if s["date"] else None}
        for k in ("tes_set", "chiller_avail", "chiller_T", "chiller_elec",
                  "air_temp", "soc", "facility_elec", "tank_T",
                  "use_ht", "source_ht"):
            vals = s.get(k, [])
            if i < len(vals):
                row[k] = vals[i]
            else:
                row[k] = None
        samples.append(row)

    # 汇总统计
    summary = {
        "scenario": name,
        "tes_set_constant": tes_set_val,
        "n_steps": parsed["n_rows"],
        "missing_cols": [k for k, v in cols.items() if v < 0],
        "stats": {
            "chiller_avail": _safe_stat(s["chiller_avail"]),
            "soc":           _safe_stat(s["soc"]),
            "air_temp":      _safe_stat(s["air_temp"]),
            "tank_T":        _safe_stat(s["tank_T"]),
            "chiller_elec":  _safe_stat(s["chiller_elec"]),
            "facility_elec": _safe_stat(s["facility_elec"]),
        },
        "samples": samples,
    }

    # 根据 scenario 做判定
    if name == "A_charge":
        # 期望（核心修复目标）：
        #   1) chiller_avail 始终 = 1（死锁已解除，充电时 chiller 不会被误关）
        #   2) SOC 没有灾难性下降（>0.3 的 drop 算不正常）
        #   3) air_temp 峰值 < 40°C（30-40°C 允许，但 >40°C 就是冷却失控）
        # 不要求 SOC 严格上升——§9.10 已知 chiller 无余量时 source 充冷有限
        first_soc = soc[0] if soc else None
        last_soc = soc[-1] if soc else None
        ca_min = min(ca) if ca else None
        air_max = max(air) if air else None
        soc_drop = (first_soc - last_soc) if (first_soc is not None and last_soc is not None) else None
        summary["verdict"] = {
            "chiller_always_ON (expect ca_min==1)": ca_min,
            "SOC_change (first→last, 允许±0.3)": (first_soc, last_soc, -soc_drop if soc_drop is not None else None),
            "air_temp_max (expect <40)": air_max,
            "pass": (ca_min == 1) and (soc_drop is not None and soc_drop < 0.3) and (air_max is not None and air_max < 40),
        }
    elif name == "B_discharge":
        # 期望：早期 chiller=0；SOC 下降；当 SOC<0.15 时 chiller 应恢复=1
        # 分两段检查
        # - 前 20% 步：soc>0.15 且 ca=0 的 step 占比（放电 working）
        # - soc 首次 <0.15 之后的 step：ca 应恢复 1
        n = len(soc)
        idx_soc_low = next((i for i, v in enumerate(soc) if v < 0.15), None)
        first_soc = soc[0] if soc else None
        last_soc = soc[-1] if soc else None

        # 前段: soc>0.15 时 chiller 多数应该关
        off_count_hi = sum(1 for i in range(n) if soc[i] > 0.15 and ca[i] == 0) if n > 0 else 0
        hi_count = sum(1 for v in soc if v > 0.15)
        off_ratio_hi = off_count_hi / hi_count if hi_count else None

        # 低段: soc<0.15 之后 chiller 应重新开
        on_after_low = None
        if idx_soc_low is not None and idx_soc_low < n - 1:
            # 看 idx_soc_low 之后（第一个 SOC<0.15 的下一步起）chiller 是否恢复
            # 允许 1 step 延迟
            tail_ca = ca[idx_soc_low + 1:]
            on_after_low = {
                "tail_n": len(tail_ca),
                "on_count": sum(1 for v in tail_ca if v == 1),
                "on_ratio": sum(1 for v in tail_ca if v == 1) / len(tail_ca) if tail_ca else None,
            }

        summary["verdict"] = {
            "SOC_fell (expect last < first)": (first_soc, last_soc),
            "chiller_OFF_ratio_when_SOC_high (expect >0.5)": off_ratio_hi,
            "first_step_with_SOC<0.15": idx_soc_low,
            "chiller_recovers_after_SOC_low": on_after_low,
            "air_temp_max": max(air) if air else None,
            "pass": (
                first_soc is not None
                and last_soc is not None
                and last_soc < first_soc
                and off_ratio_hi is not None
                and off_ratio_hi > 0.5
                and (on_after_low is None or (on_after_low.get("on_ratio") or 0) > 0.5)
            ),
        }

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eplus-exe", default=str(DEFAULT_EPLUS),
                        help="Path to energyplus.exe (defaults to great-hugle worktree's copy)")
    parser.add_argument("--only", choices=["A", "B"], default=None,
                        help="Only run scenario A (charge) or B (discharge)")
    parser.add_argument("--days", type=int, default=1,
                        help="Simulation length in days (default 1)")
    parser.add_argument("--keep", action="store_true",
                        help="Keep output dir (default: keep)")
    args = parser.parse_args()

    eplus_exe = Path(args.eplus_exe)
    if not eplus_exe.exists():
        print(f"ERROR: energyplus.exe not found at {eplus_exe}", file=sys.stderr)
        return 2
    if not SRC.exists():
        print(f"ERROR: epJSON not found: {SRC}", file=sys.stderr)
        return 2
    if not WEATHER.exists():
        print(f"ERROR: weather not found: {WEATHER}", file=sys.stderr)
        return 2

    tag = _now_tag()
    base = ROOT / "tools" / "m1" / f"smoke_p5fix_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[smoke] output dir: {base}")
    print(f"[smoke] E+ exe:     {eplus_exe}")
    print(f"[smoke] epJSON src: {SRC}")

    scenarios = SCENARIOS
    if args.only == "A":
        scenarios = [SCENARIOS[0]]
    elif args.only == "B":
        scenarios = [SCENARIOS[1]]

    all_results = {}
    overall_pass = True
    for name, val in scenarios:
        wd = base / name
        wd.mkdir(parents=True, exist_ok=True)
        ep = wd / "input.epJSON"
        _patch_epjson(val, ep, days=args.days)

        print(f"\n=== Scenario {name} (TES_Set={val:+.2f}) ===")
        print(f"  workdir: {wd}")
        cmd = [str(eplus_exe), "-w", str(WEATHER), "-d", str(wd), "-r", str(ep)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        elapsed = None
        print(f"  returncode: {r.returncode}")

        err = _count_err(wd / "eplusout.err")
        print(f"  err severe/fatal: {err['severe']}/{err['fatal']}")
        if err["severe"] > 0:
            print(f"  severe lines:")
            for ln in err["severe_lines"]:
                print(f"    {ln}")
        if err["fatal"] > 0:
            print(f"  fatal lines:")
            for ln in err["fatal_lines"]:
                print(f"    {ln}")

        result = {"scenario": name, "tes_set": val, "returncode": r.returncode, "err": err}
        csv_path = wd / "eplusout.csv"
        if not csv_path.exists() or r.returncode != 0 or err["fatal"] > 0:
            result["error"] = "simulation failed or no eplusout.csv"
            overall_pass = False
            all_results[name] = result
            continue

        parsed = _parse_csv(csv_path)
        analysis = _analyze_scenario(name, val, parsed)
        result["analysis"] = analysis
        all_results[name] = result

        # Pretty-print summary
        print(f"  n_steps: {analysis['n_steps']}")
        if analysis["missing_cols"]:
            print(f"  [warn] missing columns: {analysis['missing_cols']}")
        stats = analysis["stats"]
        print(f"  chiller_avail: min={stats['chiller_avail'].get('min')}, "
              f"max={stats['chiller_avail'].get('max')}, "
              f"mean={stats['chiller_avail'].get('mean')}")
        print(f"  SOC:           min={stats['soc'].get('min')}, "
              f"max={stats['soc'].get('max')}, "
              f"last={stats['soc'].get('last')}")
        print(f"  air_temp (°C): min={stats['air_temp'].get('min')}, "
              f"max={stats['air_temp'].get('max')}, "
              f"mean={stats['air_temp'].get('mean')}")
        print(f"  tank_T (°C):   min={stats['tank_T'].get('min')}, "
              f"max={stats['tank_T'].get('max')}, "
              f"last={stats['tank_T'].get('last')}")
        print(f"  chiller_elec (W): mean={stats['chiller_elec'].get('mean')}, "
              f"max={stats['chiller_elec'].get('max')}")
        print(f"  facility_elec (J): mean={stats['facility_elec'].get('mean')}")
        print(f"  --- 3 samples (first/mid/last) ---")
        for row in analysis["samples"]:
            print(f"    step#{row['step_idx']:3d} [{row.get('date')}]: "
                  f"tes_set={row.get('tes_set')}, "
                  f"ca={row.get('chiller_avail')}, "
                  f"soc={row.get('soc')}, "
                  f"air={row.get('air_temp')}, "
                  f"tank={row.get('tank_T')}")
        print(f"  --- verdict ---")
        print(f"  {json.dumps(analysis['verdict'], indent=4, ensure_ascii=False)}")
        if not analysis["verdict"]["pass"]:
            overall_pass = False

    summary_path = base / "summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== smoke output: {summary_path}")
    print(f"=== OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
