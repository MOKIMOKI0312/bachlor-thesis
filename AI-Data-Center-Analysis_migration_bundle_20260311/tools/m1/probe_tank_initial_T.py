"""Probe: 看 E+ 对 stratified tank 在仿真开始时使用的默认 initial_temperature。

这是 F1 (TES SOC random init) 设计的前置 probe：
  1) 本地 E+ 跑 1 小时（4 timestep）的 runperiod 仿真
  2) TES_Set=0（静置）、TES_Charge_Setpoint 保持 6.0°C
  3) 检查 eso 第 1 步的 Tank Node 1..10 温度
  4) 如果是 `setpoint_temp = 6.0`，说明 E+ 默认用 setpoint 初始化
     如果是 `14.4` 或 `20`，说明 hardcoded

用法：
    python tools/m1/probe_tank_initial_T.py
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
SRC = BUILDINGS / "DRL_DC_training.epJSON"


def _patch(src: Path, dst: Path, setpoint_override: float | None = None) -> None:
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    # runperiod: 1 天（短）
    data["RunPeriod"] = {"RP Probe": {
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
    # 静置
    data["Schedule:Constant"]["TES_Set"]["hourly_value"] = 0.0
    if setpoint_override is not None:
        data["Schedule:Constant"]["TES_Charge_Setpoint"]["hourly_value"] = setpoint_override

    # 确保有 Output:Variable 输出 Tank Node 1..10 温度
    outvars = data.setdefault("Output:Variable", {})
    for i in range(1, 11):
        key = f"Output Tank Node {i} Probe"
        outvars[key] = {
            "key_value": "Chilled Water Tank",
            "variable_name": f"Chilled Water Thermal Storage Temperature Node {i}",
            "reporting_frequency": "Timestep",
        }
    # 也加总 tank 温度
    outvars["Output Tank Final T"] = {
        "key_value": "Chilled Water Tank",
        "variable_name": "Chilled Water Thermal Storage Final Tank Temperature",
        "reporting_frequency": "Timestep",
    }

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _run(workdir: Path, epjson: Path) -> tuple[int, Path]:
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(workdir), "-r", str(epjson)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, workdir / "eplusout.csv"


def _extract_first_step(csv_path: Path) -> dict:
    """Find columns for Tank Node 1..10 and return first row values."""
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        first = next(rdr, None)
        second = next(rdr, None)
        third = next(rdr, None)

    result = {"header_cols": {}, "step1": {}, "step2": {}, "step3": {}}

    # Find columns
    for i, col in enumerate(header):
        col_l = col.lower()
        if "chilled water tank" in col_l and "node" in col_l and "temperature" in col_l:
            # parse node number
            import re
            m = re.search(r"node\s+(\d+)", col_l)
            if m:
                node = int(m.group(1))
                result["header_cols"][f"node_{node}"] = i
        elif "chilled water tank" in col_l and "final tank temperature" in col_l:
            result["header_cols"]["final_T"] = i

    rows = [first, second, third]
    labels = ["step1", "step2", "step3"]
    for row, label in zip(rows, labels):
        if row is None:
            continue
        result[label]["date"] = row[0] if row else None
        for k, idx in result["header_cols"].items():
            try:
                result[label][k] = float(row[idx])
            except (ValueError, IndexError):
                result[label][k] = None
    return result


def main() -> int:
    tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "tools" / "m1" / "smoke_tes_init_probe" / tag
    base.mkdir(parents=True, exist_ok=True)
    print(f"[probe] base: {base}")

    scenarios = [
        ("setpoint_6C", 6.0),  # default
        ("setpoint_10C", 10.0),  # override setpoint high
    ]
    results = {}
    for name, sp in scenarios:
        wd = base / name
        wd.mkdir(parents=True, exist_ok=True)
        epjson = wd / "input.epJSON"
        _patch(SRC, epjson, setpoint_override=sp)
        print(f"\n=== Scenario {name} (TES_Charge_Setpoint={sp}°C) ===")
        rc, csv_path = _run(wd, epjson)
        print(f"  returncode: {rc}")
        if rc != 0 or not csv_path.exists():
            err = wd / "eplusout.err"
            if err.exists():
                with open(err, encoding="utf-8", errors="replace") as f:
                    lines = [l for l in f if "severe" in l.lower() or "fatal" in l.lower()]
                    print("  ERR SEVERE/FATAL lines:")
                    for l in lines[:20]:
                        print(f"    {l.rstrip()}")
            continue

        res = _extract_first_step(csv_path)
        results[name] = res
        print("  First 3 step tank node temperatures:")
        for step_label in ("step1", "step2", "step3"):
            if step_label not in res:
                continue
            step = res[step_label]
            print(f"    {step_label}: date={step.get('date')}")
            nodes = [f"n{i}={step.get(f'node_{i}')}" for i in range(1, 11)]
            print(f"      nodes: {', '.join(nodes)}")
            print(f"      final_T={step.get('final_T')}")

    # save
    out = base / "probe_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[probe] result saved to: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
