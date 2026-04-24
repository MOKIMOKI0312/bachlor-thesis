"""Probe #2: 验证 setpoint schedule 切换不会影响初始 tank temperature。

假设: E+ 在仿真第 1 个 timestep 初始化 tank 节点温度 = setpoint schedule 的 Period 1 值。
如果我用 Schedule:Compact:
  Until: 00:15 → 9.0  (目标 T_init)
  Until: 24:00 → 6.0  (正常 setpoint)

期望:
  - Step 1 (00:15): tank node T ≈ 9.0 (被初始化成 9.0)
  - Step 2+ (00:30 onwards): setpoint=6.0, chiller 启动, tank 开始冷却, T 逐步降回 6.0

用法：
    python tools/m1/probe_schedule_compact.py
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


def _patch(src: Path, dst: Path, t_init: float, t_normal: float = 6.0) -> None:
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    # 1 天 runperiod
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

    # 把 TES_Charge_Setpoint 从 Schedule:Constant 换成 Schedule:Compact
    # 注意：原本是 Schedule:Constant，需要先删除
    sc = data.get("Schedule:Constant", {})
    if "TES_Charge_Setpoint" in sc:
        del sc["TES_Charge_Setpoint"]

    # 添加 Schedule:Compact
    data.setdefault("Schedule:Compact", {})
    data["Schedule:Compact"]["TES_Charge_Setpoint"] = {
        "schedule_type_limits_name": "Temperature",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: AllDays"},
            {"field": "Until: 00:15"},
            {"field": str(t_init)},
            {"field": "Until: 24:00"},
            {"field": str(t_normal)},
        ],
    }

    data["Schedule:Constant"]["TES_Set"]["hourly_value"] = 0.0  # 静置（不放电，不充电）

    # 输出 Tank Node 1..10 温度和 setpoint schedule
    outvars = data.setdefault("Output:Variable", {})
    for i in range(1, 11):
        key = f"Output Tank Node {i} Probe"
        outvars[key] = {
            "key_value": "Chilled Water Tank",
            "variable_name": f"Chilled Water Thermal Storage Temperature Node {i}",
            "reporting_frequency": "Timestep",
        }
    outvars["Output Tank Final T"] = {
        "key_value": "Chilled Water Tank",
        "variable_name": "Chilled Water Thermal Storage Final Tank Temperature",
        "reporting_frequency": "Timestep",
    }
    outvars["Output Setpoint Schedule"] = {
        "key_value": "TES_Charge_Setpoint",
        "variable_name": "Schedule Value",
        "reporting_frequency": "Timestep",
    }
    # 输出 chiller 电耗看是否启动
    outvars["Output Chiller Elec"] = {
        "key_value": "90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton",
        "variable_name": "Chiller Electricity Rate",
        "reporting_frequency": "Timestep",
    }

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _run(workdir: Path, epjson: Path) -> tuple[int, Path]:
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(workdir), "-r", str(epjson)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, workdir / "eplusout.csv"


def _extract(csv_path: Path, n_steps: int = 10) -> dict:
    """Find columns for Tank Node, setpoint, chiller elec; return first n_steps rows."""
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        rows = []
        for i, row in enumerate(rdr):
            if i >= n_steps:
                break
            rows.append(row)

    result = {"header_cols": {}, "steps": []}
    import re
    for i, col in enumerate(header):
        col_l = col.lower()
        if "chilled water tank" in col_l and "node" in col_l and "temperature" in col_l:
            m = re.search(r"node\s+(\d+)", col_l)
            if m:
                result["header_cols"][f"node_{int(m.group(1))}"] = i
        elif "chilled water tank" in col_l and "final tank" in col_l:
            result["header_cols"]["final_T"] = i
        elif "tes_charge_setpoint" in col_l and "schedule value" in col_l:
            result["header_cols"]["setpoint"] = i
        elif "chiller" in col_l and "electricity rate" in col_l:
            result["header_cols"]["chiller_elec"] = i

    for row in rows:
        step = {"date": row[0] if row else None}
        for k, idx in result["header_cols"].items():
            try:
                step[k] = float(row[idx])
            except (ValueError, IndexError):
                step[k] = None
        result["steps"].append(step)

    return result


def main() -> int:
    tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "tools" / "m1" / "smoke_tes_init_probe" / f"compact_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[probe] base: {base}")

    scenarios = [
        ("t_init_9C", 9.0),
        ("t_init_11C", 11.0),
        ("t_init_6C_baseline", 6.0),
    ]

    results = {}
    for name, t_init in scenarios:
        wd = base / name
        wd.mkdir(parents=True, exist_ok=True)
        epjson = wd / "input.epJSON"
        _patch(SRC, epjson, t_init=t_init, t_normal=6.0)
        print(f"\n=== Scenario {name} (T_init={t_init}°C, T_normal=6.0°C) ===")
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
            results[name] = {"returncode": rc, "error": "failed"}
            continue

        res = _extract(csv_path, n_steps=20)
        results[name] = res
        print(f"  columns found: {list(res['header_cols'].keys())}")
        print(f"  First 10 steps:")
        for step in res["steps"][:10]:
            nodes_str = ", ".join([f"n{i}={step.get(f'node_{i}', 'NA')}" for i in [1, 5, 10]])
            print(f"    {step.get('date')} | setpoint={step.get('setpoint')}, "
                  f"final_T={step.get('final_T')}, chiller_W={step.get('chiller_elec')}, "
                  f"{nodes_str}")

    out = base / "probe_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[probe] result saved to: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
