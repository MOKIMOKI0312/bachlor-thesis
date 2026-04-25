"""组件隔离验证：针对每个物理组件设置固定输入条件，跑 1 天 E+ 仿真，
验证关键输出变量符合物理预期。

矩阵驱动，每条测试包含:
  - schedules: 要覆盖的 Schedule:Constant 值
  - asserts: 对输出列的断言（min/max/mean 范围 / 比值检查）
  - description: 测试目的

输出:
  tools/m1/component_iso_<timestamp>/
    test_<id>/<eplus output>
    summary.json
"""
import csv
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS_PATH = Path(os.environ.get("EPLUS_PATH",
    "C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"))
EPLUS_EXE = EPLUS_PATH / "energyplus.exe"
SRC = ROOT / "Data" / "buildings" / "DRL_DC_training.epJSON"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"

assert EPLUS_EXE.exists(), f"EnergyPlus not found: {EPLUS_EXE}"
assert SRC.exists() and WEATHER.exists()


# --- 测试矩阵 ---
TESTS = [
    {
        "id": "T1_TES_charge",
        "subsys": "TES",
        "desc": "TES 强制满充 (TES_Set=-1.0)",
        "schedules": {"TES_Set": -1.0, "ITE_Set": 0.45},
        "asserts": [
            ("source_HT_max", "Chilled Water Tank.*Source Side Heat Transfer", "max", ">", 50_000),  # >50 kW
            ("use_HT_max",    "Chilled Water Tank.*Use Side Heat Transfer",    "max", "<", 100_000), # <100 kW (基本不放)
            ("source_HT_mean","Chilled Water Tank.*Source Side Heat Transfer", "mean", ">", 1_000),   # mean>1kW
        ],
    },
    {
        "id": "T2_TES_idle_chiller_only",
        "subsys": "TES_Topology",
        "desc": "TES 静止 (TES_Set=0)，仅 Chiller 供冷",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45},
        "asserts": [
            ("source_HT_mean", "Chilled Water Tank.*Source Side Heat Transfer", "abs_mean", "<", 50_000),
            ("use_HT_mean",    "Chilled Water Tank.*Use Side Heat Transfer",    "abs_mean", "<", 50_000),
            ("chiller_cool",   "Chiller Evaporator Cooling Rate",                "mean", ">", 100_000), # chiller 提供主要冷量
        ],
    },
    {
        "id": "T3_TES_discharge",
        "subsys": "TES",
        "desc": "TES 强制满放 (TES_Set=+1.0)",
        "schedules": {"TES_Set": +1.0, "ITE_Set": 0.45},
        "asserts": [
            ("use_HT_max",    "Chilled Water Tank.*Use Side Heat Transfer",    "max",  ">", 500_000),  # >500 kW
            ("use_HT_pct1kW", "Chilled Water Tank.*Use Side Heat Transfer",    "pct_above_1kW", ">", 0.5),
            ("source_HT_max", "Chilled Water Tank.*Source Side Heat Transfer", "max",  "<", 200_000),  # 不充电
        ],
    },
    {
        "id": "T4_Chiller_low_IT",
        "subsys": "Chiller",
        "desc": "Chiller 低 IT 负载 (ITE_Set=0.2)",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.20},
        "asserts": [
            ("chiller_elec_max", "Chiller Electricity Rate", "max", "<", 800_000),   # <800 kW elec
            ("chiller_cool_max", "Chiller Evaporator Cooling Rate", "max", "<", 3_000_000), # <3 MW
        ],
    },
    {
        "id": "T5_Chiller_high_IT",
        "subsys": "Chiller",
        "desc": "Chiller 满 IT 负载 (ITE_Set=1.0)",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 1.0},
        "asserts": [
            ("chiller_elec_max", "Chiller Electricity Rate", "max", ">", 200_000),  # >200 kW
            ("chiller_cool_max", "Chiller Evaporator Cooling Rate", "max", ">", 1_000_000), # >1 MW
        ],
    },
    {
        "id": "T6_Chiller_T_warm",
        "subsys": "Chiller",
        "desc": "Chiller 温度 setpoint 增量 +0.5（暖向）",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "Chiller_T_Set": +0.5},
        "asserts": [],  # 仅记录 baseline，不强断言（受 EMS 累积影响）
    },
    {
        "id": "T7_Chiller_T_cool",
        "subsys": "Chiller",
        "desc": "Chiller 温度 setpoint 增量 -0.5（冷向）",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "Chiller_T_Set": -0.5},
        "asserts": [],
    },
    {
        "id": "T8_CRAH_fan_high",
        "subsys": "CRAH",
        "desc": "CRAH 风机增量 +1.0（最大）",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CRAH_Fan_Set": +1.0},
        "asserts": [
            ("fan_mflow_max", "Fan Air Mass Flow Rate", "max", ">", 5),  # >5 kg/s 风机有响应
        ],
    },
    {
        "id": "T9_CRAH_fan_low",
        "subsys": "CRAH",
        "desc": "CRAH 风机增量 -1.0（最小）",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CRAH_Fan_Set": -1.0},
        "asserts": [
            ("fan_mflow_min", "Fan Air Mass Flow Rate", "min", ">=", 0),  # 不为负
        ],
    },
    {
        "id": "T10_CT_pump_high",
        "subsys": "CT_Pump",
        "desc": "CT 泵增量 +1.0",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CT_Pump_Set": +1.0},
        "asserts": [],  # 记录 baseline
    },
    {
        "id": "T11_CT_pump_low",
        "subsys": "CT_Pump",
        "desc": "CT 泵增量 -1.0",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CT_Pump_Set": -1.0},
        "asserts": [],
    },
    {
        "id": "T12_Topology_parallel_charge",
        "subsys": "Topology",
        "desc": "并行：Chiller 同时供 IT 和 充 TES (TES=-0.3, ITE=0.6)",
        "schedules": {"TES_Set": -0.3, "ITE_Set": 0.6},
        "asserts": [
            ("source_HT_mean", "Chilled Water Tank.*Source Side Heat Transfer", "mean", ">", 0),  # TES 在充
            ("chiller_cool_mean", "Chiller Evaporator Cooling Rate", "mean", ">", 100_000), # Chiller 在供冷
        ],
    },
]


def patch_epjson(test_schedules: dict, dst: Path, days: int = 1):
    """生成 patched epJSON，覆盖指定 schedule 值并设置短 RunPeriod。"""
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    schs = data.setdefault("Schedule:Constant", {})
    for sch_name, value in test_schedules.items():
        if sch_name in schs:
            schs[sch_name]["hourly_value"] = value
        else:
            print(f"  [warn] schedule '{sch_name}' not found", file=sys.stderr)

    end_day = min(31, max(1, days))
    data["RunPeriod"] = {"RP_iso": {
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

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_col(header: list, pattern: str) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    for i, h in enumerate(header):
        if rx.search(h):
            return i
    return -1


def col_stats(rows: list, idx: int) -> dict:
    if idx < 0:
        return {"missing": True}
    vals = []
    for r in rows:
        if idx < len(r):
            try: vals.append(float(r[idx]))
            except (ValueError, IndexError): pass
    if not vals:
        return {"missing": True, "n_rows": len(rows)}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": sum(vals) / len(vals),
        "abs_mean": sum(abs(v) for v in vals) / len(vals),
        "pct_above_1kW": sum(1 for v in vals if abs(v) > 1000) / len(vals),
        "last": vals[-1],
    }


def evaluate_assert(stats: dict, op: str, threshold) -> bool:
    if "missing" in stats and stats["missing"]:
        return False
    val = stats.get(op.split("_")[0] if op in ("abs_mean", "pct_above_1kW") else op)
    if op == "abs_mean":
        val = stats["abs_mean"]
    elif op == "pct_above_1kW":
        val = stats["pct_above_1kW"]
    elif op in ("max", "min", "mean"):
        val = stats[op]
    return val is not None and {
        ">": val > threshold, "<": val < threshold,
        ">=": val >= threshold, "<=": val <= threshold,
    }["compare"] if False else None


def cmp_op(stats: dict, stat_kind: str, op: str, threshold) -> tuple:
    """Returns (passed, actual_value)."""
    val = stats.get(stat_kind, None)
    if val is None or stats.get("missing"):
        return False, None
    cmp_table = {
        ">":  val >  threshold,
        "<":  val <  threshold,
        ">=": val >= threshold,
        "<=": val <= threshold,
    }
    return cmp_table[op], val


def run_test(t: dict, base_dir: Path, days: int = 1) -> dict:
    wd = base_dir / t["id"]
    wd.mkdir(parents=True, exist_ok=True)
    ep = wd / "input.epJSON"
    patch_epjson(t["schedules"], ep, days=days)

    cmd = [str(EPLUS_EXE), "-w", str(WEATHER), "-d", str(wd), "-r", str(ep)]
    t0 = _dt.datetime.now()
    res = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    elapsed = (_dt.datetime.now() - t0).total_seconds()

    err = wd / "eplusout.err"
    severe, fatal = 0, 0
    sev_lines = []
    if err.exists():
        with open(err, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if re.match(r"\s*\*\*\s*Severe\s*\*\*", ln):
                    severe += 1
                    if len(sev_lines) < 5: sev_lines.append(ln.rstrip())
                elif re.match(r"\s*\*\*\s*Fatal\s*\*\*", ln):
                    fatal += 1

    csv_path = wd / "eplusout.csv"
    if not csv_path.exists() or res.returncode != 0:
        return {"id": t["id"], "subsys": t["subsys"], "desc": t["desc"],
                "schedules": t["schedules"], "elapsed_sec": elapsed,
                "returncode": res.returncode, "severe": severe, "fatal": fatal,
                "severe_lines": sev_lines, "stats_failed": True,
                "asserts_pass": False, "stats": {},
                "stderr_tail": res.stderr.splitlines()[-5:] if res.stderr else []}

    with open(csv_path, encoding="utf-8") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = list(rdr)

    # 收集所有关键变量统计（不仅是断言中提到的）
    key_patterns = {
        "tes_use_HT":    r"Chilled Water Tank.*Use Side Heat Transfer",
        "tes_source_HT": r"Chilled Water Tank.*Source Side Heat Transfer",
        "tes_loss_HT":   r"Chilled Water Tank.*Heat Loss Rate",
        "tes_tank_T":    r"Chilled Water Tank.*Final Tank Temperature",
        "chiller_elec":  r"Chiller Electricity Rate",
        "chiller_cool":  r"Chiller Evaporator Cooling Rate",
        "fan_mflow":     r"Fan Air Mass Flow Rate",
        "zone_air_T":    r"DataCenter ZN.*Zone Air Temperature",
        "facility_elec": r"Electricity:Facility",
    }
    stats = {}
    for tag, pat in key_patterns.items():
        idx = find_col(header, pat)
        stats[tag] = {"col_idx": idx} | col_stats(rows, idx)

    # 评估断言
    assert_results = []
    all_pass = True
    for assert_def in t["asserts"]:
        name, var_pat, stat_kind, op, threshold = assert_def
        idx = find_col(header, var_pat)
        if idx < 0:
            assert_results.append({"name": name, "pass": False,
                                   "reason": "column not found", "pattern": var_pat})
            all_pass = False
            continue
        col_st = col_stats(rows, idx)
        passed, actual = cmp_op(col_st, stat_kind, op, threshold)
        assert_results.append({
            "name": name, "pass": passed,
            "expected": f"{stat_kind} {op} {threshold:g}" if isinstance(threshold, (int, float)) else f"{stat_kind} {op} {threshold}",
            "actual": actual,
        })
        if not passed:
            all_pass = False

    return {
        "id": t["id"], "subsys": t["subsys"], "desc": t["desc"],
        "schedules": t["schedules"], "elapsed_sec": elapsed,
        "returncode": res.returncode, "severe": severe, "fatal": fatal,
        "severe_lines": sev_lines,
        "stats": stats, "asserts": assert_results, "asserts_pass": all_pass,
    }


def main():
    tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "tools" / "m1" / f"component_iso_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[iso] output dir: {base}")
    print(f"[iso] {len(TESTS)} tests, 1 day each\n")

    results = []
    for i, t in enumerate(TESTS, 1):
        print(f"--- [{i}/{len(TESTS)}] {t['id']} ({t['subsys']}) ---")
        print(f"    {t['desc']}")
        print(f"    schedules: {t['schedules']}")
        r = run_test(t, base)
        verdict = "PASS" if r.get("asserts_pass") and r["severe"] == 0 and r["fatal"] == 0 else (
            "FAIL" if r.get("asserts_pass") is False else "WARN")
        print(f"    [{verdict}] severe={r['severe']} fatal={r['fatal']} elapsed={r.get('elapsed_sec',0):.1f}s")
        # Print key stats
        for tag_, st in r.get("stats", {}).items():
            if "missing" not in st or not st["missing"]:
                print(f"      {tag_:14s}: min={st.get('min'):.0f} max={st.get('max'):.0f} mean={st.get('mean'):.0f}".replace(":.0f", "")
                      if isinstance(st.get('min'), (int, float)) else f"      {tag_}: {st}")
        # Print assert results
        for a in r.get("asserts", []):
            mark = "✓" if a["pass"] else "✗"
            print(f"      {mark} {a['name']}: expect {a.get('expected','?')} | actual={a.get('actual')}")
        results.append(r)
        print()

    summary_path = base / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"=== SUMMARY: {summary_path}")

    n_pass = sum(1 for r in results if r.get("asserts_pass") and r["severe"] == 0)
    n_fail = sum(1 for r in results if r.get("asserts_pass") is False)
    n_warn = len(results) - n_pass - n_fail
    print(f"=== TOTAL: {n_pass} PASS / {n_fail} FAIL / {n_warn} WARN (no asserts) / {len(results)} tests")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
