"""
M1 辅助：用 energyplus.exe 直接跑 N 天仿真，读 eplusout.err 报告 Severe/Fatal 数量。

用法：
    python tools/m1/run_sim_for_days.py --days 1 --building DRL_DC_training.epJSON
    python tools/m1/run_sim_for_days.py --days 7 --building DRL_DC_training.epJSON

会在 tools/m1/sim_<YYYYMMDD-HHMMSS>_<days>d/ 下输出结果（复制 eplusout.err + eplusout.eso）。
"""

import argparse
import copy
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS_DIR = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
EPLUS_EXE = EPLUS_DIR / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER_DIR = ROOT / "Data" / "weather"


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _make_short_epjson(src: Path, dst: Path, days: int) -> None:
    """Copy src to dst but replace RunPeriod to cover only first `days` days of Jan."""
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    # Find or create a RunPeriod. Keep simulation small: Jan 1 -> Jan (1+days-1)
    end_day = min(31, max(1, days))
    run_periods = data.setdefault("RunPeriod", {})
    # Replace all existing RunPeriods with a single short one
    rp_body = {
        "begin_month": 1,
        "begin_day_of_month": 1,
        "begin_year": 2025,
        "end_month": 1,
        "end_day_of_month": end_day,
        "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }
    if days > 31:
        # extend to cover more — but clamp via month/day
        # simple clamp: end of January for days >= 31, or set end_month based on day count
        total = days
        m = 1
        d = 1
        remaining = total
        # Rough: step through months
        mlen = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        day_index = 0  # 0-based counter of day # within year
        day_index += (total - 1)
        # resolve into month/day
        cum = 0
        for i, ml in enumerate(mlen, start=1):
            if day_index < cum + ml:
                m = i
                d = day_index - cum + 1
                break
            cum += ml
        rp_body["end_month"] = m
        rp_body["end_day_of_month"] = d

    # Clear any existing RunPeriods and replace
    data["RunPeriod"] = {"RP Short": rp_body}

    # Also force timesteps_per_hour to 4 via Timestep
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 4}}

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _count_err(err_path: Path) -> dict:
    severe = 0
    fatal = 0
    warnings = 0
    severe_lines = []
    fatal_lines = []
    if not err_path.exists():
        return {"severe": -1, "fatal": -1, "warnings": -1, "missing": True,
                "severe_lines": [], "fatal_lines": []}
    with open(err_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            # "   ** Severe  ** ..."
            if re.match(r"\s*\*\*\s*Severe\s*\*\*", line):
                severe += 1
                if len(severe_lines) < 20:
                    severe_lines.append(line.rstrip())
            elif re.match(r"\s*\*\*\s*Fatal\s*\*\*", line):
                fatal += 1
                if len(fatal_lines) < 20:
                    fatal_lines.append(line.rstrip())
            elif re.match(r"\s*\*\*\s*Warning\s*\*\*", line):
                warnings += 1
    return {"severe": severe, "fatal": fatal, "warnings": warnings,
            "missing": False, "severe_lines": severe_lines, "fatal_lines": fatal_lines}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--building", type=str, default="DRL_DC_training.epJSON")
    parser.add_argument("--weather", type=str,
                        default="CHN_JS_Nanjing.582380_TMYx.2009-2023.epw")
    parser.add_argument("--keep-dir", action="store_true",
                        help="don't delete output dir on success")
    args = parser.parse_args()

    src = BUILDINGS / args.building
    wthr = WEATHER_DIR / args.weather
    if not src.exists():
        print(f"ERROR missing building: {src}", file=sys.stderr)
        sys.exit(2)
    if not wthr.exists():
        print(f"ERROR missing weather: {wthr}", file=sys.stderr)
        sys.exit(2)
    if not EPLUS_EXE.exists():
        print(f"ERROR missing energyplus.exe: {EPLUS_EXE}", file=sys.stderr)
        sys.exit(2)

    tag = _now_tag()
    workdir = ROOT / "tools" / "m1" / f"sim_{tag}_{args.days}d"
    workdir.mkdir(parents=True, exist_ok=True)

    short_epjson = workdir / "input.epJSON"
    _make_short_epjson(src, short_epjson, args.days)
    print(f"[runsim] workdir: {workdir}")
    print(f"[runsim] short epJSON: {short_epjson}")
    print(f"[runsim] days: {args.days}, building: {args.building}")

    cmd = [str(EPLUS_EXE),
           "-w", str(wthr),
           "-d", str(workdir),
           "-r",
           str(short_epjson)]
    print(f"[runsim] cmd: {' '.join(cmd)}")
    started = _dt.datetime.now()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = (_dt.datetime.now() - started).total_seconds()
    print(f"[runsim] returncode: {res.returncode}, elapsed: {elapsed:.1f}s")

    err_path = workdir / "eplusout.err"
    err_info = _count_err(err_path)

    result = {
        "returncode": res.returncode,
        "elapsed_sec": elapsed,
        "workdir": str(workdir),
        "err_severe": err_info["severe"],
        "err_fatal": err_info["fatal"],
        "err_warnings": err_info["warnings"],
        "err_missing": err_info["missing"],
        "severe_first_20": err_info["severe_lines"],
        "fatal_first_20": err_info["fatal_lines"],
    }

    # stdout tail
    if res.stdout:
        print("--- stdout tail ---")
        print("\n".join(res.stdout.splitlines()[-20:]))
    if res.stderr:
        print("--- stderr tail ---")
        print("\n".join(res.stderr.splitlines()[-20:]))

    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    passed = (res.returncode == 0 and err_info["severe"] == 0 and err_info["fatal"] == 0)
    print(f"\nPASS: {passed}")

    (workdir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
