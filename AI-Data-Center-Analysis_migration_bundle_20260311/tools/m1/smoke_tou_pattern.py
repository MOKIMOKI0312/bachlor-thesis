"""
TOU-Pattern Rule-Based TES Smoke Test (2026-04-24).

目的：验证 EnergyPlus 物理模型是否能在规则控制器驱动下完成 TOU 套利。
如果物理模型正常，规则控制器应让 SOC 产生日循环：
  - 谷段 00-07: TES_Set = -0.5 (charge)
  - 峰段 08-11: TES_Set = +0.5 (discharge)
  - 平段 12-14: TES_Set =  0.0 (idle)
  - 峰段 15-20: TES_Set = +0.5 (discharge)
  - 平段 21-23: TES_Set =  0.0 (idle)

期望：14 天内看到 14 个清晰的日循环 (SOC 上下波动 0.3+ 每天)，
      峰段 chiller_avail=0 (靠 tank 供冷)，谷段 chiller 满载充冷。

如果物理模型坏了，SOC 不会形成日循环，electricity 不会跟随 TOU 模式。

不依赖 RL / sinergym，直接用 E+ exe。
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EPLUS = Path(
    os.environ.get(
        "EPLUS_EXE",
        str(ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"),
    )
)
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _patch_epjson_with_tou(dst: Path, days: int = 14) -> None:
    """Replace TES_Set Schedule:Constant with a TOU-pattern Schedule:Compact."""
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    # Short runperiod
    end_month, end_day = 1, min(31, max(1, days))
    if days > 31:
        end_month, end_day = 1 + (days // 31), (days % 31) if days % 31 else 31
    data["RunPeriod"] = {"RP TOU Smoke": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": end_month, "end_day_of_month": end_day, "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}

    # Remove existing TES_Set from Schedule:Constant
    if "Schedule:Constant" in data and "TES_Set" in data["Schedule:Constant"]:
        del data["Schedule:Constant"]["TES_Set"]

    # Add Schedule:Compact with TOU pattern
    # Jiangsu TOU: trough 0-7, peak1 8-11, shoulder 12-14, peak2 15-20, shoulder 21-23
    if "Schedule:Compact" not in data:
        data["Schedule:Compact"] = {}
    data["Schedule:Compact"]["TES_Set"] = {
        "schedule_type_limits_name": "Any Number",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: AllDays"},
            {"field": "Until: 07:00"},
            {"field": -0.5},  # trough → charge
            {"field": "Until: 11:00"},
            {"field": +0.5},  # peak1 → discharge
            {"field": "Until: 14:00"},
            {"field": 0.0},   # shoulder → idle
            {"field": "Until: 20:00"},
            {"field": +0.5},  # peak2 → discharge
            {"field": "Until: 24:00"},
            {"field": 0.0},   # shoulder/trough → idle
        ],
    }

    # Ensure "Any Number" schedule type limits exists
    if "ScheduleTypeLimits" not in data:
        data["ScheduleTypeLimits"] = {}
    if "Any Number" not in data["ScheduleTypeLimits"]:
        data["ScheduleTypeLimits"]["Any Number"] = {
            "numeric_type": "Continuous"
        }

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _run_eplus(epjson: Path, outdir: Path, eplus_exe: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [str(eplus_exe), "-w", str(WEATHER), "-d", str(outdir), str(epjson)]
    print(f"[run] {cmd[0]} ...")
    return subprocess.run(cmd, capture_output=False).returncode


def _analyze(outdir: Path) -> dict:
    """Read the eplusout.csv, extract key variables, check daily cycling."""
    csv_path = outdir / "eplusout.csv"
    if not csv_path.exists():
        return {"error": "no eplusout.csv"}
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if not rows:
        return {"error": "empty csv"}

    # Find columns (E+ uses verbose names)
    cols = list(rows[0].keys())
    def find_col(*keywords):
        for c in cols:
            if all(k.lower() in c.lower() for k in keywords):
                return c
        return None

    col_soc   = find_col("tes_soc_actuator", "schedule value")
    col_tes   = find_col("tes_set", "schedule value")
    col_avail = find_col("chiller_avail_obs", "schedule value")
    col_air   = find_col("zone mean air temperature")
    col_elec  = find_col("electricity:facility")
    col_chill = find_col("chiller electric")

    print(f"  col_soc   = {col_soc}")
    print(f"  col_tes   = {col_tes}")
    print(f"  col_avail = {col_avail}")
    print(f"  col_air   = {col_air}")
    print(f"  col_elec  = {col_elec}")
    print(f"  col_chill = {col_chill}")

    def vals(col):
        if col is None: return []
        out = []
        for r in rows:
            v = r.get(col, "")
            try:
                out.append(float(v))
            except:
                pass
        return out

    soc = vals(col_soc)
    tes = vals(col_tes)
    avail = vals(col_avail)
    air = vals(col_air)
    elec = vals(col_elec)
    chill = vals(col_chill)

    # Daily cycle count (SOC crosses 0.5 upward)
    import numpy as np
    soc_arr = np.array(soc) if soc else np.array([])
    cycles = int(((soc_arr[:-1] < 0.5) & (soc_arr[1:] >= 0.5)).sum()) if len(soc_arr) > 1 else 0

    # Per-hour-of-day stats
    # Assume each row is one timestep; steps_per_hour could be 1 or 4
    n_steps = len(rows)
    # Date/Time column
    col_dt = find_col("date/time") or cols[0]
    dt_vals = [r.get(col_dt, "") for r in rows]
    # Parse hour from "01/01  01:00:00" style
    def parse_hour(s):
        try:
            # s like " 01/01  01:00:00"
            timepart = s.strip().split()[-1]  # "01:00:00"
            return int(timepart.split(":")[0])
        except:
            return -1
    hours = [parse_hour(s) for s in dt_vals]

    result = {
        "n_steps": n_steps,
        "soc_cycles": cycles,
        "soc": {
            "min": min(soc) if soc else 0, "max": max(soc) if soc else 0,
            "mean": sum(soc) / len(soc) if soc else 0,
            "std": float(np.std(soc_arr)) if len(soc_arr) else 0,
        },
        "air_temp": {
            "min": min(air) if air else 0, "max": max(air) if air else 0,
            "mean": sum(air) / len(air) if air else 0,
        },
        "facility_elec_GJ": {
            "sum_GJ": sum(elec) / 1e9 if elec else 0,
            "mean_per_step_GJ": sum(elec) / len(elec) / 1e9 if elec else 0,
        },
    }
    if chill:
        result["chiller_elec_GJ"] = {
            "sum_GJ": sum(chill) / 1e9,
            "nonzero_pct": (sum(1 for x in chill if x > 1) / len(chill)) * 100,
        }

    # Per-hour-of-day analysis for TOU compliance
    hour_soc = {h: [] for h in range(24)}
    hour_tes = {h: [] for h in range(24)}
    hour_elec = {h: [] for h in range(24)}
    hour_avail = {h: [] for h in range(24)}
    for i, h in enumerate(hours):
        if 0 <= h <= 23 and i < len(soc):
            hour_soc[h].append(soc[i])
            hour_tes[h].append(tes[i] if i < len(tes) else 0)
            hour_elec[h].append(elec[i] if i < len(elec) else 0)
            if i < len(avail):
                hour_avail[h].append(avail[i])

    hourly_table = []
    for h in range(24):
        if hour_soc[h]:
            hourly_table.append({
                "hour": h,
                "soc_mean": sum(hour_soc[h]) / len(hour_soc[h]),
                "tes_mean": sum(hour_tes[h]) / len(hour_tes[h]),
                "elec_GJ_mean": sum(hour_elec[h]) / len(hour_elec[h]) / 1e9,
                "chiller_on_pct": (sum(1 for x in hour_avail[h] if x > 0.5) / len(hour_avail[h]) * 100) if hour_avail[h] else -1,
            })
    result["hourly"] = hourly_table

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--eplus-exe", type=Path, default=DEFAULT_EPLUS)
    parser.add_argument("--outdir", type=Path, default=ROOT / "tools" / "m1" / "smoke_tou")
    args = parser.parse_args()

    if not args.eplus_exe.exists():
        raise FileNotFoundError(f"EnergyPlus exe not found: {args.eplus_exe}")

    out_root = args.outdir / _now_tag()
    out_root.mkdir(parents=True, exist_ok=True)

    # Patch epJSON
    patched = out_root / "DRL_DC_training_TOU.epJSON"
    _patch_epjson_with_tou(patched, days=args.days)
    print(f"[patch] wrote {patched}")

    # Run E+
    eout = out_root / "output"
    rc = _run_eplus(patched, eout, args.eplus_exe)
    print(f"[eplus] returncode = {rc}")

    # Analyze
    ana = _analyze(eout)
    print(f"[analyze] {json.dumps({k: v for k, v in ana.items() if k != 'hourly'}, indent=2, default=str)}")
    print(f"[hourly] expected TOU pattern: charge 0-6 (SOC↑), peak discharge 8-10/15-19 (SOC↓)")
    print(f"  {'hr':>4} {'soc_mean':>10} {'tes_mean':>10} {'elec_GJ':>10} {'chill_on%':>10}")
    for row in ana.get("hourly", []):
        print(f"  {row['hour']:>4} {row['soc_mean']:>10.4f} {row['tes_mean']:>10.3f} {row['elec_GJ_mean']:>10.4f} {row['chiller_on_pct']:>10.1f}")

    # Save JSON
    with open(out_root / "summary.json", "w", encoding="utf-8") as f:
        json.dump(ana, f, indent=2, default=str)
    print(f"[done] summary saved to {out_root}/summary.json")


if __name__ == "__main__":
    main()
