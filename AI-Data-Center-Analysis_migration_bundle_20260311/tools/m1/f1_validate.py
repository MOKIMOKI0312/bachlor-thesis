"""F1 validation: run 1-day sim on both training and evaluation epJSON.

Check severe/fatal error count.
Also verify tank initial temperature = Schedule:Compact first value.

Usage:
    python tools/m1/f1_validate.py
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"


def _patch_short(src: Path, dst: Path, t_init: float = 6.0) -> None:
    """Copy epJSON with 1-day runperiod + optionally tweak T_init in Schedule:Compact."""
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    # 1-day runperiod
    data["RunPeriod"] = {"RP Validate": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": 1, "end_day_of_month": 1, "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 4}}
    data["Schedule:Constant"]["TES_Set"]["hourly_value"] = 0.0  # static

    # Modify Schedule:Compact first value (Until 00:15 = t_init)
    sc = data.get("Schedule:Compact", {}).get("TES_Charge_Setpoint")
    if sc is not None:
        # data[3] is the value after "Until: 00:15"
        sc["data"][3]["field"] = str(t_init)

    # Output Tank Node temps
    outvars = data.setdefault("Output:Variable", {})
    for i in range(1, 11):
        key = f"Output Tank Node {i} F1"
        outvars[key] = {
            "key_value": "Chilled Water Tank",
            "variable_name": f"Chilled Water Thermal Storage Temperature Node {i}",
            "reporting_frequency": "Timestep",
        }
    outvars["Output Tank Final T F1"] = {
        "key_value": "Chilled Water Tank",
        "variable_name": "Chilled Water Thermal Storage Final Tank Temperature",
        "reporting_frequency": "Timestep",
    }
    outvars["Output Setpoint Schedule F1"] = {
        "key_value": "TES_Charge_Setpoint",
        "variable_name": "Schedule Value",
        "reporting_frequency": "Timestep",
    }

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _run(workdir: Path, epjson: Path) -> tuple[int, Path]:
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(workdir), "-r", str(epjson)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, workdir / "eplusout.csv"


def _count_err(err_path: Path) -> dict:
    import re
    if not err_path.exists():
        return {"severe": -1, "fatal": -1, "severe_lines": [], "fatal_lines": [], "warnings": -1}
    sev, fat, warn = 0, 0, 0
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
            elif re.match(r"\s*\*\*\s*Warning\s*\*\*", line):
                warn += 1
    return {"severe": sev, "fatal": fat, "warnings": warn,
            "severe_lines": sev_lines, "fatal_lines": fat_lines}


def _extract_first(csv_path: Path) -> dict:
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        first = next(rdr)
        second = next(rdr)
        third = next(rdr)

    cols = {}
    import re
    for i, col in enumerate(header):
        col_l = col.lower()
        if "chilled water tank" in col_l and "node" in col_l and "temperature" in col_l:
            m = re.search(r"node\s+(\d+)", col_l)
            if m:
                cols[f"node_{int(m.group(1))}"] = i
        elif "chilled water tank" in col_l and "final tank" in col_l:
            cols["final_T"] = i
        elif "tes_charge_setpoint" in col_l and "schedule value" in col_l:
            cols["setpoint"] = i

    out = {"cols": cols, "steps": []}
    for row, label in zip([first, second, third], ["step1", "step2", "step3"]):
        step = {"date": row[0]}
        for k, idx in cols.items():
            try:
                step[k] = float(row[idx])
            except (ValueError, IndexError):
                step[k] = None
        out["steps"].append({"label": label, **step})
    return out


def main() -> int:
    tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "tools" / "m1" / "smoke_tes_init_probe" / f"f1_validate_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[f1-validate] base: {base}")

    # Test matrix:
    # (epjson, T_init)
    matrix = [
        ("DRL_DC_training.epJSON", 6.0),   # baseline
        ("DRL_DC_training.epJSON", 9.0),   # mid
        ("DRL_DC_training.epJSON", 12.0),  # extreme
        ("DRL_DC_evaluation.epJSON", 8.0),
    ]

    all_results = []
    overall_pass = True
    for ep_name, t_init in matrix:
        src = BUILDINGS / ep_name
        wd_name = f"{ep_name.replace('.epJSON', '')}_T{t_init:g}"
        wd = base / wd_name
        wd.mkdir(parents=True, exist_ok=True)
        epjson = wd / "input.epJSON"
        _patch_short(src, epjson, t_init=t_init)

        print(f"\n=== {ep_name} with T_init={t_init}°C ===")
        rc, csv_path = _run(wd, epjson)
        print(f"  returncode: {rc}")

        err = _count_err(wd / "eplusout.err")
        print(f"  err severe/fatal/warnings: {err['severe']}/{err['fatal']}/{err['warnings']}")
        if err["severe"] > 0:
            for ln in err["severe_lines"]:
                print(f"    SEV: {ln}")
        if err["fatal"] > 0:
            for ln in err["fatal_lines"]:
                print(f"    FAT: {ln}")

        case_result = {
            "ep_name": ep_name,
            "t_init": t_init,
            "returncode": rc,
            "err": err,
        }
        if rc != 0 or err["fatal"] > 0:
            case_result["verdict"] = "FAIL"
            overall_pass = False
        elif not csv_path.exists():
            case_result["verdict"] = "NO CSV"
            overall_pass = False
        else:
            extract = _extract_first(csv_path)
            case_result["tank_initial"] = extract
            # Key check: node 1 temp at step 1 should be close to t_init
            step1 = extract["steps"][0]
            n1 = step1.get("node_1")
            final_T = step1.get("final_T")
            sp = step1.get("setpoint")
            deviation = abs(n1 - t_init) if n1 is not None else None
            passed = (deviation is not None and deviation < 0.1)
            case_result["verdict"] = "PASS" if passed else "FAIL (init T mismatch)"
            if not passed:
                overall_pass = False
            print(f"  step1: date={step1.get('date')}, setpoint={sp}, final_T={final_T}, n1={n1}")
            print(f"  step2: date={extract['steps'][1].get('date')}, setpoint={extract['steps'][1].get('setpoint')}, final_T={extract['steps'][1].get('final_T')}")
            print(f"  verdict: {case_result['verdict']}  (|n1 - T_init|={deviation})")

        all_results.append(case_result)

    # Save
    result_path = base / "f1_validation_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"all_pass": overall_pass, "cases": all_results}, f, indent=2, ensure_ascii=False)
    print(f"\n[f1-validate] result: {result_path}")
    print(f"\n[f1-validate] OVERALL: {'PASS' if overall_pass else 'FAIL'}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
