"""
Audit baseline probe — 2026-04-24

固定 "中性 action"（fan/chiller/pumps 50%，ITE 中档默认 0.45，TES 静置 0）
跑冬/夏各 7 天，收集物理变量并筛选 err 文件 warnings / severes。

不挂 RL policy，纯物理 sanity check。

用法：
    python tools/m1/audit_baseline_probe.py --season winter
    python tools/m1/audit_baseline_probe.py --season summer
    python tools/m1/audit_baseline_probe.py --season both  # default
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
EPLUS = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"

SEASONS = {
    # name: (begin_mon, begin_day, end_mon, end_day, start_weekday)
    "winter": (1, 1, 1, 7, "Wednesday"),  # 2025-01-01 .. 2025-01-07
    "summer": (6, 1, 6, 7, "Sunday"),     # 2025-06-01 .. 2025-06-07
}

# center action — P_1 会把 [0,1] action 映射到窗口 [now-step, now+step] 内
# CRAH_T_S = 0.5  → (max-min)*0.5 + min = mid of window
# CRAH_Fan_S = 0.5, Chiller_T_S = 0.5, CT_Pump_S = 0.5 — 所有 HVAC 50%
# ITE_Set = 0.45 (默认值不改)
# TES_Set = 0.0 (静置)
NEUTRAL_ACTION = {
    "CRAH_T_Set": 0.5,
    "CRAH_Fan_Set": 0.5,
    "Chiller_T_Set": 0.5,
    "CT_Pump_Set": 0.5,
    "ITE_Set": 0.45,
    "TES_Set": 0.0,
}


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _patch_epjson(dst: Path, season: str, timesteps_per_hour: int = 4) -> None:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    bm, bd, em, ed, wkd = SEASONS[season]
    data["RunPeriod"] = {"RP Audit": {
        "begin_month": bm, "begin_day_of_month": bd, "begin_year": 2025,
        "end_month": em, "end_day_of_month": ed, "end_year": 2025,
        "day_of_week_for_start_day": wkd,
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}
    # Use 4/hr so we can see sub-hourly SimHVAC errors
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": timesteps_per_hour}}

    # Set all neutral action schedules
    for sched_name, value in NEUTRAL_ACTION.items():
        if sched_name in data["Schedule:Constant"]:
            data["Schedule:Constant"][sched_name]["hourly_value"] = value

    # Add extra Output:Variable we need for audit
    extra_vars = [
        ("Chiller Part Load Ratio", "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton"),
        ("Cooling Tower Fan Electricity Rate", "Centrifugal Fan Cycling Open Cooling Tower 40.2 gpm/hp"),
        ("Cooling Tower Heat Transfer Rate", "Centrifugal Fan Cycling Open Cooling Tower 40.2 gpm/hp"),
        ("Cooling Tower Outside Air Wet Bulb Temperature", "Centrifugal Fan Cycling Open Cooling Tower 40.2 gpm/hp"),
        ("Fluid Heat Exchanger Heat Transfer Rate", "Integrated Waterside Economizer Heat Exchanger"),
        ("Fluid Heat Exchanger Operation Status", "Integrated Waterside Economizer Heat Exchanger"),
        ("Cooling Coil Total Cooling Rate", "CRAH Water Clg Coil"),
        ("ITE Total Heat Gain to Zone Rate", "LargeDataCenterHighITE StandaloneDataCenter IT equipment 1"),
        ("ITE CPU Electric Power", "LargeDataCenterHighITE StandaloneDataCenter IT equipment 1"),
        ("Pump Electricity Rate", "Chilled Water Loop Secondary Pump"),
        ("Pump Electricity Rate", "Chilled Water Loop Primary Pump"),
        ("Pump Electricity Rate", "Condenser Water Loop Constant Pump"),
        ("Chiller COP", "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton"),
        ("Facility Total HVAC Electricity Demand Rate", "Whole Building"),
    ]
    ov = data.setdefault("Output:Variable", {})
    for i, (var, key) in enumerate(extra_vars):
        name = f"Audit OV {i}"
        ov[name] = {
            "variable_name": var,
            "key_value": key,
            "reporting_frequency": "Timestep",
        }

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _pick_col(header: list[str], substrs: list[str]) -> int:
    low = [h.lower() for h in header]
    for i, h in enumerate(low):
        if all(s.lower() in h for s in substrs):
            return i
    return -1


def _safe_stat(vals: list, tag: str = "") -> dict:
    clean = [v for v in vals if isinstance(v, (int, float))]
    if not clean:
        return {"missing": True, "tag": tag}
    return {
        "n": len(clean),
        "min": min(clean),
        "max": max(clean),
        "mean": sum(clean) / len(clean),
    }


def _analyze_err(err_path: Path) -> dict:
    if not err_path.exists():
        return {"missing": True}
    sev = 0
    fat = 0
    warnings = 0
    sev_lines: list[str] = []
    fat_lines: list[str] = []
    warn_samples: dict[str, int] = {}  # unique signature -> count
    simhvac_max_iter = 0
    warmup_not_converged = 0
    ct_freeze = 0
    checkwarmup_details: list[str] = []
    with open(err_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if re.search(r"\*\*\s*Severe\s*\*\*", line):
                sev += 1
                if len(sev_lines) < 40:
                    sev_lines.append(line.rstrip())
            elif re.search(r"\*\*\s*Fatal\s*\*\*", line):
                fat += 1
                if len(fat_lines) < 20:
                    fat_lines.append(line.rstrip())
            elif re.search(r"\*\*\s*Warning\s*\*\*", line):
                warnings += 1
                # Canonicalize: drop numbers and specific times to aggregate
                sig = re.sub(r"\d+(\.\d+)?", "<N>", line.strip())[:160]
                warn_samples[sig] = warn_samples.get(sig, 0) + 1
            if "SimHVAC: Maximum iterations" in line:
                simhvac_max_iter += 1
            if "CheckWarmupConvergence" in line or "did not converge" in line.lower():
                warmup_not_converged += 1
                if len(checkwarmup_details) < 10:
                    checkwarmup_details.append(line.rstrip())
            if "Cooling tower water outlet temperature is below the specified minimum" in line:
                ct_freeze += 1
    # Top-10 most common warnings
    top = sorted(warn_samples.items(), key=lambda kv: -kv[1])[:10]
    return {
        "severe": sev,
        "fatal": fat,
        "warnings_total": warnings,
        "simhvac_max_iter": simhvac_max_iter,
        "warmup_not_converged": warmup_not_converged,
        "ct_freeze_warns": ct_freeze,
        "sev_lines": sev_lines,
        "fat_lines": fat_lines,
        "warmup_details": checkwarmup_details,
        "top_warnings": top,
    }


def _analyze_csv(csv_path: Path) -> dict:
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = list(rdr)
    cols = {
        "air":       _pick_col(header, ["DataCenter ZN", "Zone Air Temperature"]),
        "rh":        _pick_col(header, ["DataCenter ZN", "Zone Air Relative Humidity"]),
        "oat":       _pick_col(header, ["Outdoor Air DryBulb"]),
        "oawb":      _pick_col(header, ["Outdoor Air WetBulb"]),
        "ct_out":    _pick_col(header, ["Condenser Water Loop Supply Outlet Node", "System Node Temperature"]),
        "chiller_out": _pick_col(header, ["1230tons 0.6kW/ton Supply Outlet Water Node", "Temperature"]),
        "crah_in":   _pick_col(header, ["CRAH Supply Inlet Node", "Temperature"]),
        "crah_out":  _pick_col(header, ["CRAH Supply Outlet Node", "Temperature"]),
        "fan_mflow": _pick_col(header, ["CRAH FAN", "Fan Air Mass Flow Rate"]),
        "chw_sp":    _pick_col(header, ["Chilled Water Loop Temp - 44F", "Schedule Value"]),
        "sec_mflow": _pick_col(header, ["Chilled Water Loop Secondary Pump", "Pump Mass Flow Rate"]),
        "ct_mflow":  _pick_col(header, ["CONDENSER WATER LOOP CONSTANT PUMP", "Pump Mass Flow Rate"]),
        "tank_T":    _pick_col(header, ["Chilled Water Tank", "Final Tank Temperature"]),
        "tank_use":  _pick_col(header, ["Chilled Water Tank", "Use Side Heat Transfer Rate"]),
        "tank_src":  _pick_col(header, ["Chilled Water Tank", "Source Side Heat Transfer Rate"]),
        "tank_loss": _pick_col(header, ["Chilled Water Tank", "Tank Heat Loss Rate"]),
        "soc":       _pick_col(header, ["TES_SOC_Obs", "Schedule Value"]),
        "tes_set":   _pick_col(header, ["TES_Set", "Schedule Value"]),
        "chiller_avail": _pick_col(header, ["Chiller_Avail_Sch", "Schedule Value"]),
        "chiller_plr": _pick_col(header, ["1230tons 0.6kW/ton", "Part Load Ratio"]),
        "chiller_cop": _pick_col(header, ["1230tons 0.6kW/ton", "Chiller COP"]),
        "chiller_el":  _pick_col(header, ["1230tons 0.6kW/ton", "Chiller Electricity Rate"]),
        "chiller_cool": _pick_col(header, ["1230tons 0.6kW/ton", "Chiller Evaporator Cooling Rate"]),
        "ct_fan_el":   _pick_col(header, ["Cooling Tower", "Cooling Tower Fan Electricity Rate"]),
        "ct_ht":       _pick_col(header, ["Cooling Tower", "Cooling Tower Heat Transfer Rate"]),
        "hx_ht":       _pick_col(header, ["Integrated Waterside Economizer", "Fluid Heat Exchanger Heat Transfer Rate"]),
        "hx_op":       _pick_col(header, ["Integrated Waterside Economizer", "Fluid Heat Exchanger Operation Status"]),
        "coil_cool":   _pick_col(header, ["CRAH Water Clg Coil", "Cooling Coil Total Cooling Rate"]),
        "ite_heat":    _pick_col(header, ["LargeDataCenterHighITE", "ITE Total Heat Gain to Zone Rate"]),
        "ite_cpu_el":  _pick_col(header, ["LargeDataCenterHighITE", "ITE CPU Electric Power"]),
        "pump_sec_el": _pick_col(header, ["Chilled Water Loop Secondary Pump", "Pump Electricity Rate"]),
        "pump_pri_el": _pick_col(header, ["Chilled Water Loop Primary Pump", "Pump Electricity Rate"]),
        "pump_ct_el":  _pick_col(header, ["Condenser Water Loop Constant Pump", "Pump Electricity Rate"]),
        "facility_el": _pick_col(header, ["Electricity:Facility"]),
        "hvac_el":     _pick_col(header, ["Whole Building", "Facility Total HVAC Electricity"]),
        "ite_meter":   _pick_col(header, ["ITE-CPU:InteriorEquipment:Electricity"]),
    }
    series = {k: [] for k in cols}
    for r in rows:
        for k, idx in cols.items():
            if idx < 0 or idx >= len(r):
                series[k].append(None)
                continue
            try:
                series[k].append(float(r[idx]))
            except (ValueError, TypeError):
                series[k].append(None)
    stats = {k: _safe_stat(series[k], tag=k) for k in cols}
    missing = [k for k, v in cols.items() if v < 0]

    # Compute PUE
    pue = None
    fac = [v for v in series["facility_el"] if isinstance(v, (int, float))]
    ite = [v for v in series["ite_meter"] if isinstance(v, (int, float))]
    if fac and ite and len(fac) == len(ite):
        total_fac = sum(fac)
        total_ite = sum(ite)
        if total_ite > 0:
            pue = total_fac / total_ite

    # Compute average Chiller COP (actual)
    chel = [v for v in series["chiller_el"] if isinstance(v, (int, float)) and v > 0]
    chc = [v for v in series["chiller_cool"] if isinstance(v, (int, float))]
    actual_cop = None
    if chel and chc:
        # Pair by non-null
        pairs = [(e, c) for e, c in zip(series["chiller_el"], series["chiller_cool"])
                 if isinstance(e, (int, float)) and isinstance(c, (int, float)) and e > 100]
        if pairs:
            sum_q = sum(c for e, c in pairs)
            sum_p = sum(e for e, c in pairs)
            if sum_p > 0:
                actual_cop = sum_q / sum_p

    return {
        "header_len": len(header),
        "n_rows": len(rows),
        "missing_cols": missing,
        "stats": stats,
        "pue": pue,
        "actual_cop": actual_cop,
    }


def run_season(season: str, out_base: Path) -> dict:
    wd = out_base / season
    wd.mkdir(parents=True, exist_ok=True)
    ep = wd / "input.epJSON"
    _patch_epjson(ep, season, timesteps_per_hour=4)

    print(f"\n=== Season {season} ===")
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(wd), "-r", str(ep)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"  returncode: {r.returncode}")

    err = _analyze_err(wd / "eplusout.err")
    print(f"  err severe={err.get('severe')}, fatal={err.get('fatal')}, warnings={err.get('warnings_total')}")
    print(f"  simhvac_max_iter={err.get('simhvac_max_iter')}, warmup_not_converged={err.get('warmup_not_converged')}, ct_freeze_warns={err.get('ct_freeze_warns')}")
    if err.get("sev_lines"):
        print("  -- top severe --")
        for ln in err["sev_lines"][:6]:
            print(f"    {ln}")
    if err.get("fat_lines"):
        print("  -- top fatal --")
        for ln in err["fat_lines"][:6]:
            print(f"    {ln}")
    if err.get("top_warnings"):
        print("  -- top warnings --")
        for sig, c in err["top_warnings"][:6]:
            print(f"    x{c:4d}: {sig}")

    result = {"season": season, "rc": r.returncode, "err": err}
    csv_path = wd / "eplusout.csv"
    if csv_path.exists() and r.returncode == 0 and err["fatal"] == 0:
        analysis = _analyze_csv(csv_path)
        result["analysis"] = analysis
        print(f"  n_steps: {analysis['n_rows']}, missing_cols: {analysis['missing_cols']}")
        print(f"  PUE (whole-period energy ratio): {analysis['pue']}")
        print(f"  Actual Chiller COP: {analysis['actual_cop']}")
        s = analysis["stats"]
        for key in ["oat", "air", "rh", "ct_out", "chiller_out", "crah_out", "fan_mflow",
                    "sec_mflow", "ct_mflow", "tank_T", "chiller_plr", "chiller_el",
                    "chiller_cool", "ct_fan_el", "ct_ht", "hx_ht", "hx_op", "coil_cool",
                    "ite_heat", "ite_cpu_el", "pump_sec_el", "pump_pri_el", "pump_ct_el",
                    "facility_el", "hvac_el", "ite_meter"]:
            v = s.get(key, {})
            if v.get("missing"):
                continue
            print(f"  {key:14s}: min={v['min']:.2f} mean={v['mean']:.2f} max={v['max']:.2f}")
    else:
        print("  [skip CSV] simulation failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=["winter", "summer", "both"], default="both")
    args = parser.parse_args()

    if not EPLUS.exists():
        print(f"E+ not found: {EPLUS}", file=sys.stderr)
        return 2
    if not WEATHER.exists():
        print(f"Weather not found: {WEATHER}", file=sys.stderr)
        return 2

    tag = _now_tag()
    base = ROOT / "tools" / "m1" / "audit_baseline" / tag
    base.mkdir(parents=True, exist_ok=True)
    print(f"[audit] output dir: {base}")

    seasons = ["winter", "summer"] if args.season == "both" else [args.season]
    results = {}
    for s in seasons:
        results[s] = run_season(s, base)

    summary_path = base / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
