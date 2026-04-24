"""Probe #3: 测试 EMS actuator 写 schedule 值是否能影响 tank 初始化温度。

思路：
  - 保留 TES_Charge_Setpoint = Schedule:Constant, 初值 6.0
  - 新增 EMS actuator 指向 TES_Charge_Setpoint
  - 新增 EMS program 在 BeginNewEnvironment 把 setpoint 改成 11.0
  - 新增 EMS program 在 BeginTimestepBeforePredictor 把 setpoint 改回 6.0
  - 看 tank 节点温度起始值 = 11.0 (BeginNewEnvironment 生效) 还是 6.0 (初始化在 BeginNewEnvironment 之前)

用法：
    python tools/m1/probe_ems_setpoint_init.py
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


def _patch(src: Path, dst: Path) -> None:
    """Keep TES_Charge_Setpoint as Schedule:Constant=6.0, add EMS to overwrite at BeginNewEnvironment."""
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    # 1 day runperiod
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

    # TES_Set=0 (static)
    data["Schedule:Constant"]["TES_Set"]["hourly_value"] = 0.0

    # Actuator on TES_Charge_Setpoint (Schedule:Constant)
    data.setdefault("EnergyManagementSystem:Actuator", {})
    data["EnergyManagementSystem:Actuator"]["TES_Charge_SP_Act"] = {
        "actuated_component_unique_name": "TES_Charge_Setpoint",
        "actuated_component_type": "Schedule:Constant",
        "actuated_component_control_type": "Schedule Value",
    }

    # EMS Program to set to 11.0 at BeginNewEnvironment
    data["EnergyManagementSystem:Program"]["P_8_Init_SP"] = {
        "lines": [
            {"program_line": "SET TES_Charge_SP_Act = 11.0"},
        ]
    }

    # EMS Program to restore to 6.0 at BeginTimestepBeforePredictor
    data["EnergyManagementSystem:Program"]["P_9_Restore_SP"] = {
        "lines": [
            {"program_line": "SET TES_Charge_SP_Act = 6.0"},
        ]
    }

    # ProgramCallingManager: BeginNewEnvironment
    data["EnergyManagementSystem:ProgramCallingManager"]["P_Init"] = {
        "energyplus_model_calling_point": "BeginNewEnvironment",
        "programs": [{"program_name": "P_8_Init_SP"}],
    }
    # Restore at BeginTimestepBeforePredictor (before P_1/P_2/P_5)
    # 复用 existing P1 calling manager: insert P_9 BEFORE other programs
    # Actually insert as separate manager so it runs independently
    data["EnergyManagementSystem:ProgramCallingManager"]["P_Restore"] = {
        "energyplus_model_calling_point": "BeginTimestepBeforePredictor",
        "programs": [{"program_name": "P_9_Restore_SP"}],
    }

    # Output Tank Node T + setpoint
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

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _run(workdir: Path, epjson: Path) -> tuple[int, Path]:
    cmd = [str(EPLUS), "-w", str(WEATHER), "-d", str(workdir), "-r", str(epjson)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, workdir / "eplusout.csv"


def _extract(csv_path: Path, n_steps: int = 5) -> dict:
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
    base = ROOT / "tools" / "m1" / "smoke_tes_init_probe" / f"ems_init_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[probe] base: {base}")

    wd = base / "ems_init_11C"
    wd.mkdir(parents=True, exist_ok=True)
    epjson = wd / "input.epJSON"
    _patch(SRC, epjson)

    print(f"\n=== Scenario: EMS writes setpoint=11.0 at BeginNewEnvironment, 6.0 at each timestep ===")
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
        return 2

    res = _extract(csv_path, n_steps=5)
    print(f"  columns found: {list(res['header_cols'].keys())}")
    print(f"  First 5 steps:")
    for step in res["steps"]:
        n1 = step.get("node_1")
        n5 = step.get("node_5")
        n10 = step.get("node_10")
        print(f"    {step.get('date')} | setpoint={step.get('setpoint')}, "
              f"final_T={step.get('final_T')}, "
              f"n1={n1}, n5={n5}, n10={n10}")

    out = base / "probe_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"\n[probe] result: {out}")

    # Interpretation
    print("\n=== Interpretation ===")
    first_step = res["steps"][0] if res["steps"] else {}
    n1 = first_step.get("node_1")
    if n1 is not None:
        if abs(n1 - 11.0) < 0.1:
            print("  EMS BeginNewEnvironment DOES affect tank initialization (node T ≈ 11.0)")
            print("  -> Feasible: use EMS to write random T at BeginNewEnvironment, restore 6.0 at timestep")
        elif abs(n1 - 6.0) < 0.1:
            print("  EMS BeginNewEnvironment does NOT affect tank initialization (node T ≈ 6.0)")
            print("  -> Tank initialized with the Schedule:Constant's static value 6.0")
            print("  -> Feasible path: use Schedule:Compact with Until 00:15 = T_init, Until 24:00 = 6.0")
        else:
            print(f"  Unexpected value: n1={n1}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
