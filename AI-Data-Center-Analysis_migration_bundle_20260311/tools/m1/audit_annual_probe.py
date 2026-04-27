"""
Audit annual probe — runs full 1-year baseline simulation to detect
annual warning cumulative counts, warmup convergence, CT freeze events.
Uses center action (neutral).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EPLUS = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"


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


def _patch_epjson(dst: Path, tsph: int = 1) -> None:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    data["RunPeriod"] = {"RP Annual": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": 12, "end_day_of_month": 31, "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": tsph}}
    for sched_name, value in NEUTRAL_ACTION.items():
        if sched_name in data["Schedule:Constant"]:
            data["Schedule:Constant"][sched_name]["hourly_value"] = value
    # Reduce output frequency to Hourly to avoid huge CSV
    for k, ov in data["Output:Variable"].items():
        ov["reporting_frequency"] = "Hourly"
    for k, m in data["Output:Meter"].items():
        m["reporting_frequency"] = "Hourly"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> int:
    if not EPLUS.exists():
        print(f"E+ not found: {EPLUS}", file=sys.stderr)
        return 2

    tag = _now_tag()
    base = ROOT / "tools" / "m1" / "audit_baseline" / f"annual_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    ep = base / "input.epJSON"
    _patch_epjson(ep, tsph=1)

    print(f"[audit] output dir: {base}")
    print("[audit] running 1-year annual simulation with Timestep=1/hr (matches base epJSON)")
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(base), "-r", str(ep)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"  returncode: {r.returncode}")

    err_path = base / "eplusout.err"
    if err_path.exists():
        text = err_path.read_text(encoding="utf-8", errors="replace")
        # Summary counts
        sev = len(re.findall(r"\*\*\s*Severe\s*\*\*", text))
        fat = len(re.findall(r"\*\*\s*Fatal\s*\*\*", text))
        warn = len(re.findall(r"\*\*\s*Warning\s*\*\*", text))
        print(f"  sev={sev}, fat={fat}, warn={warn}")
        # CT freeze
        ct_freeze = len(re.findall(r"Cooling tower water outlet temperature.*below.*minimum", text, re.IGNORECASE))
        simhvac = len(re.findall(r"SimHVAC:\s*Maximum iterations", text))
        warmup_nc = len(re.findall(r"did not converge", text, re.IGNORECASE))
        ct_range = len(re.findall(r"Tower range temperature is out(side)?\s*(of)?\s*model\s*boundaries|Tower range temperature is out of range", text))
        print(f"  ct_freeze={ct_freeze}, simhvac_max_iter={simhvac}, warmup_not_converged={warmup_nc}, ct_range={ct_range}")
        # Print last 80 lines
        lines = text.splitlines()
        print("---- last 120 lines of err ----")
        for L in lines[-120:]:
            print(L)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
