"""V1 验证 helper：跑 7 天 E+ 仿真，检查 .err 无 severe/fatal。

不依赖 vendor/，从 EPLUS_PATH 环境变量读取 EnergyPlus 安装路径。
"""
import json, os, re, shutil, subprocess, sys, datetime as _dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS_DIR = Path(os.environ.get("EPLUS_PATH", ""))
if not EPLUS_DIR or not (EPLUS_DIR / "energyplus.exe").exists():
    print(f"ERROR: set EPLUS_PATH to EnergyPlus 23.1 dir, got: {EPLUS_DIR}", file=sys.stderr)
    sys.exit(2)

building = sys.argv[1] if len(sys.argv) > 1 else "DRL_DC_training.epJSON"
days = int(sys.argv[2]) if len(sys.argv) > 2 else 7

src = ROOT / "Data" / "buildings" / building
wthr = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
assert src.exists(), src
assert wthr.exists(), wthr

tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
workdir = ROOT / "tools" / "m1" / f"v1_{tag}_{days}d"
workdir.mkdir(parents=True, exist_ok=True)

with open(src, encoding="utf-8") as f:
    data = json.load(f)
end_day = min(31, max(1, days))
data["RunPeriod"] = {"RP_V1": {
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
short = workdir / "input.epJSON"
with open(short, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

cmd = [str(EPLUS_DIR / "energyplus.exe"), "-w", str(wthr), "-d", str(workdir), "-r", str(short)]
print(f"[V1] cmd: {' '.join(cmd)}")
t0 = _dt.datetime.now()
res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
elapsed = (_dt.datetime.now() - t0).total_seconds()
print(f"[V1] returncode={res.returncode} elapsed={elapsed:.1f}s")

err = workdir / "eplusout.err"
severe, fatal, warn = 0, 0, 0
sev_lines, fat_lines = [], []
if err.exists():
    with open(err, encoding="utf-8", errors="replace") as f:
        for line in f:
            if re.match(r"\s*\*\*\s*Severe\s*\*\*", line):
                severe += 1
                if len(sev_lines) < 20: sev_lines.append(line.rstrip())
            elif re.match(r"\s*\*\*\s*Fatal\s*\*\*", line):
                fatal += 1
                if len(fat_lines) < 20: fat_lines.append(line.rstrip())
            elif re.match(r"\s*\*\*\s*Warning\s*\*\*", line):
                warn += 1
result = {
    "returncode": res.returncode, "elapsed_sec": elapsed,
    "workdir": str(workdir), "err_severe": severe, "err_fatal": fatal,
    "err_warnings": warn, "severe_first_20": sev_lines, "fatal_first_20": fat_lines,
}
print("=== V1 RESULT ===")
print(json.dumps(result, indent=2, ensure_ascii=False))
passed = (res.returncode == 0 and severe == 0 and fatal == 0)
print(f"V1 PASS: {passed}")
sys.exit(0 if passed else 1)
