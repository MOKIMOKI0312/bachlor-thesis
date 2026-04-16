"""
M1-A3 验证：跑 3 个 TES_Set 情境的 7-day 仿真，分别统计 Source/Use Heat Transfer Rate 和 SOC。

情境：
  A: TES_Set = +0.5  → 期望 Source 持续充电（SOC 升），Use 不工作
  B: TES_Set =  0    → 期望 Source 和 Use 都为 0，SOC 稳定
  C: TES_Set = -0.5  → 期望 Use 持续放电（SOC 降），Source 不工作

对每种情境：
  1. 复制 training epJSON → 临时文件
  2. 改 Schedule:Constant `TES_Set`.hourly_value = {+0.5 | 0 | -0.5}
  3. RunPeriod: Jan 1-7
  4. 调 energyplus.exe
  5. 读 eplusout.csv 统计 Source/Use HT 非零 timestep、SOC 最大/最小/末值

用法：
    python tools/m1/test_tes_scenarios.py
"""

import csv
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS_DIR = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
EPLUS_EXE = EPLUS_DIR / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"

SCENARIOS = [
    ("A_charge", +0.5),
    ("B_idle", 0.0),
    ("C_discharge", -0.5),
]


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _make_epjson(tes_set_val: float, dst: Path, days: int = 7) -> None:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    # RunPeriod: Jan 1 → Jan days
    data["RunPeriod"] = {"RP Short": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": 1, "end_day_of_month": days, "end_year": 2025,
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


def _pick_csv_col(header: list, name_substrs: list) -> int:
    """Return col index whose header matches ALL substrings (case-insensitive)."""
    low = [h.lower() for h in header]
    for i, h in enumerate(low):
        if all(s.lower() in h for s in name_substrs):
            return i
    return -1


def _analyze(workdir: Path) -> dict:
    csv_path = workdir / "eplusout.csv"
    if not csv_path.exists():
        return {"error": "no eplusout.csv"}
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = list(rdr)

    idx_src_ht = _pick_csv_col(header, ["Chilled Water Tank", "Source Side Heat Transfer Rate"])
    idx_use_ht = _pick_csv_col(header, ["Chilled Water Tank", "Use Side Heat Transfer Rate"])
    idx_tank_T = _pick_csv_col(header, ["Chilled Water Tank", "Final Tank Temperature"])
    idx_soc = _pick_csv_col(header, ["TES_SOC_Obs", "Schedule Value"])
    idx_tes_set = _pick_csv_col(header, ["TES_Set", "Schedule Value"])
    idx_use_avail = _pick_csv_col(header, ["TES_Use_Avail_Sch", "Schedule Value"])
    idx_src_avail = _pick_csv_col(header, ["TES_Source_Avail_Sch", "Schedule Value"])

    def stats(idx: int) -> dict:
        if idx < 0:
            return {"missing": True}
        vals = []
        nz = 0
        for r in rows:
            try:
                v = float(r[idx])
            except (ValueError, IndexError):
                continue
            vals.append(v)
            if abs(v) > 1e-3:
                nz += 1
        if not vals:
            return {"missing": True}
        return {
            "n": len(vals),
            "min": min(vals),
            "max": max(vals),
            "mean": sum(vals) / len(vals),
            "last": vals[-1],
            "nonzero_count": nz,
        }

    return {
        "header_indices": {
            "src_ht": idx_src_ht, "use_ht": idx_use_ht, "tank_T": idx_tank_T,
            "soc": idx_soc, "tes_set": idx_tes_set,
            "use_avail": idx_use_avail, "src_avail": idx_src_avail,
        },
        "src_ht": stats(idx_src_ht),
        "use_ht": stats(idx_use_ht),
        "tank_T": stats(idx_tank_T),
        "soc": stats(idx_soc),
        "tes_set": stats(idx_tes_set),
        "use_avail": stats(idx_use_avail),
        "src_avail": stats(idx_src_avail),
    }


def _count_err(err_path: Path) -> dict:
    import re
    if not err_path.exists():
        return {"severe": -1, "fatal": -1}
    sev, fat = 0, 0
    with open(err_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if re.match(r"\s*\*\*\s*Severe\s*\*\*", line): sev += 1
            elif re.match(r"\s*\*\*\s*Fatal\s*\*\*", line): fat += 1
    return {"severe": sev, "fatal": fat}


def main() -> None:
    tag = _now_tag()
    base = ROOT / "tools" / "m1" / f"scen_{tag}"
    base.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for name, val in SCENARIOS:
        wd = base / name
        wd.mkdir(parents=True, exist_ok=True)
        ep = wd / "input.epJSON"
        _make_epjson(val, ep, days=7)
        cmd = [str(EPLUS_EXE), "-w", str(WEATHER), "-d", str(wd), "-r", str(ep)]
        print(f"\n=== Scenario {name} (TES_Set={val}) ===")
        print(f"  workdir: {wd}")
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"  returncode: {r.returncode}")
        err = _count_err(wd / "eplusout.err")
        print(f"  err severe/fatal: {err['severe']}/{err['fatal']}")
        stats = _analyze(wd)
        all_results[name] = {"returncode": r.returncode, "err": err, "stats": stats}
        # Abbreviated print
        if err.get("fatal", 0) > 0 or "error" in stats:
            print(f"  (skipping stats print — sim failed)")
        else:
            def _g(d, k): return d.get(k) if isinstance(d, dict) else None
            print(f"  TES_Set schedule:   last={_g(stats.get('tes_set',{}),'last')}, mean={_g(stats.get('tes_set',{}),'mean')}")
            print(f"  TES_Use_Avail_Sch:  nonzero_count={_g(stats.get('use_avail',{}),'nonzero_count')}, max={_g(stats.get('use_avail',{}),'max')}")
            print(f"  TES_Source_Avail_Sch: nonzero_count={_g(stats.get('src_avail',{}),'nonzero_count')}, max={_g(stats.get('src_avail',{}),'max')}")
            print(f"  Source HT Rate (W): nz={_g(stats.get('src_ht',{}),'nonzero_count')}, min={_g(stats.get('src_ht',{}),'min')}, max={_g(stats.get('src_ht',{}),'max')}, mean={_g(stats.get('src_ht',{}),'mean')}")
            print(f"  Use HT Rate (W):    nz={_g(stats.get('use_ht',{}),'nonzero_count')}, min={_g(stats.get('use_ht',{}),'min')}, max={_g(stats.get('use_ht',{}),'max')}, mean={_g(stats.get('use_ht',{}),'mean')}")
            print(f"  Tank Temperature (C): min={_g(stats.get('tank_T',{}),'min')}, max={_g(stats.get('tank_T',{}),'max')}, last={_g(stats.get('tank_T',{}),'last')}")
            print(f"  SOC: min={_g(stats.get('soc',{}),'min')}, max={_g(stats.get('soc',{}),'max')}, mean={_g(stats.get('soc',{}),'mean')}, last={_g(stats.get('soc',{}),'last')}")

    (base / "summary.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsummary -> {base / 'summary.json'}")


if __name__ == "__main__":
    main()
