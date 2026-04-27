"""Reproducible EnergyPlus model audit for the M1/M2 datacenter model.

Outputs a fresh tools/m1/model_audit_<timestamp>/ directory containing:
  - repo/git/building MD5 metadata
  - static epJSON checks for topology, EMS, actuators, and schedules
  - one EnergyPlus run directory per component-isolation scenario
  - parsed severe/fatal/warning counts and scenario metrics
  - machine-readable audit.json and human-readable report.md

This script does not start RL training and does not reuse old
verify_components_out results.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_BUILDINGS = ROOT / "Data" / "buildings"
SINERGYM_BUILDINGS = ROOT / "sinergym" / "data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_EPLUS = Path(
    "C:/Users/18430/EnergyPlus-23.1.0/"
    "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
)
TES_OBJECT_TYPES = (
    "ThermalStorage:ChilledWater:Mixed",
    "ThermalStorage:ChilledWater:Stratified",
)

BUILDING_FILES = {
    "data_training": DATA_BUILDINGS / "DRL_DC_training.epJSON",
    "data_evaluation": DATA_BUILDINGS / "DRL_DC_evaluation.epJSON",
    "sinergym_training": SINERGYM_BUILDINGS / "DRL_DC_training.epJSON",
    "sinergym_evaluation": SINERGYM_BUILDINGS / "DRL_DC_evaluation.epJSON",
}

SCENARIOS = [
    {
        "id": "tes_idle",
        "desc": "TES idle, chiller serves IT load",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45},
    },
    {
        "id": "tes_discharge",
        "desc": "TES discharge via positive action",
        "schedules": {"TES_Set": 1.0, "ITE_Set": 0.45},
    },
    {
        "id": "tes_charge",
        "desc": "TES negative action opens source side from cold initial tank",
        "schedules": {"TES_Set": -1.0, "ITE_Set": 0.45},
    },
    {
        "id": "tes_cycle",
        "desc": "TES phased discharge then charge cycle",
        "schedules": {"ITE_Set": 0.45},
        "run_days": 7,
        "compact_schedules": {
            "TES_Set": [
                "Through: 1/3",
                "For: AllDays",
                "Until: 24:00",
                "0.5",
                "Through: 12/31",
                "For: AllDays",
                "Until: 24:00",
                "-0.5",
            ]
        },
    },
    {
        "id": "chiller_low_it",
        "desc": "Low IT load",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.20},
    },
    {
        "id": "chiller_high_it",
        "desc": "High IT load",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 1.0},
    },
    {
        "id": "pumps_high",
        "desc": "Condenser pump high command",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CT_Pump_Set": 1.0},
    },
    {
        "id": "pumps_low",
        "desc": "Condenser pump low command",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CT_Pump_Set": 0.0},
    },
    {
        "id": "crah_high",
        "desc": "CRAH fan high command",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CRAH_Fan_Set": 1.0},
    },
    {
        "id": "crah_low",
        "desc": "CRAH fan low command",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.45, "CRAH_Fan_Set": 0.0},
    },
    {
        "id": "tower_economizer",
        "desc": "Tower/economizer connected baseline",
        "schedules": {"TES_Set": 0.0, "ITE_Set": 0.60, "CT_Pump_Set": 1.0},
    },
]


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_hash() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def p2_lines(data: dict[str, Any]) -> list[str]:
    return [
        item.get("program_line", "")
        for item in data.get("EnergyManagementSystem:Program", {})
        .get("P_2", {})
        .get("lines", [])
    ]


def same_file(a: Path, b: Path) -> bool:
    return md5(a) == md5(b)


def check(condition: bool, label: str, detail: Any = None) -> dict[str, Any]:
    return {"label": label, "pass": bool(condition), "detail": detail}


def branch_has_component(data: dict[str, Any], branch: str, obj_type: str, name: str) -> bool:
    comps = data.get("Branch", {}).get(branch, {}).get("components", [])
    return any(
        c.get("component_object_type") == obj_type and c.get("component_name") == name
        for c in comps
    )


def branch_has_tes(data: dict[str, Any], branch: str, name: str) -> bool:
    return any(branch_has_component(data, branch, obj_type, name) for obj_type in TES_OBJECT_TYPES)


def tes_object_types_present(data: dict[str, Any]) -> list[str]:
    return [
        obj_type
        for obj_type in TES_OBJECT_TYPES
        if name_exists(data.get(obj_type, {}), "Chilled Water Tank")
    ]


def name_exists(objects: dict[str, Any], name: str) -> bool:
    return name in objects


def static_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    actuators = data.get("EnergyManagementSystem:Actuator", {})
    programs = data.get("EnergyManagementSystem:Program", {})
    schedules = data.get("Schedule:Constant", {})
    plant_loops = data.get("PlantLoop", {})
    checks = [
        check(len(plant_loops) == 2, "exactly 2 PlantLoop objects", list(plant_loops)),
        check("Chilled Water Loop" in plant_loops, "Chilled Water Loop exists"),
        check("Condenser Water Loop" in plant_loops, "Condenser Water Loop exists"),
        check(
            bool(tes_object_types_present(data)),
            "TES chilled-water tank exists",
            tes_object_types_present(data),
        ),
        check(bool(data.get("Chiller:Electric:EIR")), "Chiller exists", list(data.get("Chiller:Electric:EIR", {}))),
        check(bool(data.get("CoolingTower:VariableSpeed")), "Cooling tower exists"),
        check(bool(data.get("HeatExchanger:FluidToFluid")), "Waterside economizer exists"),
        check(bool(data.get("Fan:VariableVolume")), "CRAH fan exists"),
        check(bool(data.get("Coil:Cooling:Water")), "CRAH water coil exists"),
        check("Chilled Water Loop Primary Pump" in data.get("Pump:ConstantSpeed", {}), "primary pump exists"),
        check("Chilled Water Loop Secondary Pump" in data.get("Pump:VariableSpeed", {}), "secondary pump exists"),
        check("Condenser Water Loop Constant Pump" in data.get("Pump:VariableSpeed", {}), "condenser pump exists"),
        check(all(p in programs for p in ("P_1", "P_2", "P_5", "P_6", "P_7")), "EMS P_1/P_2/P_5/P_6/P_7 exist"),
        check(p2_lines(data) == ["SET ITE_rate = ITE_S"], "P_2 maps ITE_S to ITE_rate", p2_lines(data)),
        check("ITE_Set" in schedules, "ITE_Set schedule retained as wrapper/agent entry"),
        check("TES_Set" in schedules, "TES_Set schedule retained as TES entry"),
        check(
            branch_has_tes(data, "Chilled Water Loop Supply Branch 3", "Chilled Water Tank"),
            "TES Use side is on Chilled Water Loop Supply Branch 3",
        ),
        check(
            branch_has_tes(data, "Chilled Water Loop Demand Branch 3", "Chilled Water Tank"),
            "TES Source side is on Chilled Water Loop Demand Branch 3",
        ),
        check(
            "Chilled Water Loop Setpoint Operation Scheme"
            in data.get("PlantEquipmentOperation:ComponentSetpoint", {}),
            "ComponentSetpoint operation scheme exists",
        ),
        check("Chiller_Bypass_Avail" in actuators, "chiller bypass actuator exists"),
        check("TES_SOC_Actuator" in actuators, "TES SOC actuator exists"),
        check("TES_Avg_Temp_Actuator" in actuators, "TES average temperature actuator exists"),
        check(
            all(
                name in actuators
                for name in (
                    "TES_Use_MFlow_Max",
                    "TES_Use_MFlow_Min",
                    "TES_Source_MFlow_Max",
                    "TES_Source_MFlow_Min",
                )
            ),
            "TES use/source flow min/max actuators exist",
        ),
        check("TES_Use_Avail" in actuators and "TES_Source_Avail" in actuators, "TES availability actuators exist"),
    ]
    return checks


def ensure_output_variable(data: dict[str, Any], key: str, variable: str, tag: str) -> None:
    out = data.setdefault("Output:Variable", {})
    if any(v.get("key_value") == key and v.get("variable_name") == variable for v in out.values()):
        return
    out[tag] = {
        "key_value": key,
        "variable_name": variable,
        "reporting_frequency": "Timestep",
    }


def patched_model(
    base: dict[str, Any],
    schedules: dict[str, float],
    run_days: int = 1,
    compact_schedules: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    data = json.loads(json.dumps(base))
    sch = data.setdefault("Schedule:Constant", {})
    for name, value in schedules.items():
        if name not in sch:
            raise KeyError(f"Schedule:Constant {name!r} missing")
        sch[name]["hourly_value"] = value
    for name, fields in (compact_schedules or {}).items():
        data.get("Schedule:Constant", {}).pop(name, None)
        data.setdefault("Schedule:Compact", {})[name] = {
            "schedule_type_limits_name": "Any Number",
            "data": [{"field": field} for field in fields]
        }
    data["RunPeriod"] = {
        "RP_audit": {
            "begin_month": 1,
            "begin_day_of_month": 1,
            "begin_year": 2025,
            "end_month": 1,
            "end_day_of_month": run_days,
            "end_year": 2025,
            "day_of_week_for_start_day": "Wednesday",
            "apply_weekend_holiday_rule": "No",
            "use_weather_file_daylight_saving_period": "No",
            "use_weather_file_holidays_and_special_days": "No",
            "use_weather_file_rain_indicators": "Yes",
            "use_weather_file_snow_indicators": "Yes",
        }
    }
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 4}}
    ensure_output_variable(data, "TES_Set", "Schedule Value", "Audit TES_Set")
    ensure_output_variable(data, "TES_Use_Avail_Sch", "Schedule Value", "Audit TES_Use_Avail")
    ensure_output_variable(data, "TES_Source_Avail_Sch", "Schedule Value", "Audit TES_Source_Avail")
    ensure_output_variable(data, "ITE_Set", "Schedule Value", "Audit ITE_Set")
    ensure_output_variable(data, "DataCenter Equipment_SCH", "Schedule Value", "Audit ITE_rate")
    ensure_output_variable(data, "TES_SOC_Obs", "Schedule Value", "Audit TES_SOC")
    ensure_output_variable(data, "TES_Avg_Temp_Obs", "Schedule Value", "Audit TES_Avg_Temp")
    ensure_output_variable(data, "Centrifugal Fan Cycling Open Cooling Tower 40.2 gpm/hp", "Cooling Tower Heat Transfer Rate", "Audit Tower Heat")
    ensure_output_variable(data, "Integrated Waterside Economizer Heat Exchanger", "Fluid Heat Exchanger Heat Transfer Rate", "Audit Economizer Heat")
    return data


def parse_err(path: Path) -> dict[str, Any]:
    counts = {"warning": 0, "severe": 0, "fatal": 0}
    categories: dict[str, int] = {}
    samples: dict[str, list[str]] = {"warning": [], "severe": [], "fatal": []}
    if not path.exists():
        return {"counts": counts, "categories": categories, "samples": samples}

    rx = re.compile(r"\*\*\s*(Warning|Severe|Fatal)\s*\*\*\s*(.*)", re.IGNORECASE)
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            m = rx.search(line)
            if not m:
                continue
            level = m.group(1).lower()
            msg = m.group(2).strip()
            counts[level] += 1
            category = re.split(r"[:=]", msg, maxsplit=1)[0].strip()[:100] or "(empty)"
            categories[category] = categories.get(category, 0) + 1
            if len(samples[level]) < 10:
                samples[level].append(line.rstrip())
    return {"counts": counts, "categories": categories, "samples": samples}


def find_col(header: list[str], pattern: str) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    for i, name in enumerate(header):
        if rx.search(name):
            return i
    return -1


def stats_for(rows: list[list[str]], idx: int) -> dict[str, Any]:
    if idx < 0:
        return {"missing": True}
    vals = []
    for row in rows:
        if idx >= len(row):
            continue
        try:
            vals.append(float(row[idx]))
        except ValueError:
            pass
    if not vals:
        return {"missing": True, "n_rows": len(rows)}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": sum(vals) / len(vals),
        "abs_mean": sum(abs(v) for v in vals) / len(vals),
        "last": vals[-1],
        "pct_abs_gt_1kw": sum(1 for v in vals if abs(v) > 1000.0) / len(vals),
    }


METRICS = {
    "tes_set": r"TES_Set.*Schedule Value",
    "tes_use_avail": r"TES_Use_Avail_Sch.*Schedule Value",
    "tes_source_avail": r"TES_Source_Avail_Sch.*Schedule Value",
    "tes_soc": r"TES_SOC_Obs.*Schedule Value",
    "tes_avg_temp": r"TES_Avg_Temp_Obs.*Schedule Value",
    "tes_use_heat": r"Chilled Water Tank.*Use Side Heat Transfer",
    "tes_source_heat": r"Chilled Water Tank.*Source Side Heat Transfer",
    "chiller_elec": r"Chiller Electricity Rate",
    "chiller_cooling": r"Chiller Evaporator Cooling Rate",
    "secondary_pump_flow": r"Chilled Water Loop Secondary Pump.*Pump Mass Flow Rate",
    "condenser_pump_flow": r"Condenser Water Loop Constant Pump.*Pump Mass Flow Rate",
    "fan_flow": r"CRAH FAN.*Fan Air Mass Flow Rate",
    "zone_temp": r"DataCenter ZN.*Zone Air Temperature",
    "ite_set": r"ITE_Set.*Schedule Value",
    "ite_rate": r"DataCenter Equipment_SCH.*Schedule Value",
    "ite_electricity": r"ITE-CPU:InteriorEquipment:Electricity",
    "tower_heat": r"Cooling Tower Heat Transfer Rate",
    "economizer_heat": r"Fluid Heat Exchanger Heat Transfer Rate",
}


def run_scenario(eplus_exe: Path, base_model: dict[str, Any], out_dir: Path, scenario: dict[str, Any]) -> dict[str, Any]:
    work = out_dir / scenario["id"]
    work.mkdir(parents=True, exist_ok=True)
    input_path = work / "input.epJSON"
    model = patched_model(
        base_model,
        scenario["schedules"],
        run_days=int(scenario.get("run_days", 1)),
        compact_schedules=scenario.get("compact_schedules"),
    )
    with input_path.open("w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    cmd = [str(eplus_exe), "-w", str(WEATHER), "-d", str(work), "-r", str(input_path)]
    started = dt.datetime.now()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = (dt.datetime.now() - started).total_seconds()
    (work / "energyplus.stdout.txt").write_text(res.stdout, encoding="utf-8", errors="replace")
    (work / "energyplus.stderr.txt").write_text(res.stderr, encoding="utf-8", errors="replace")

    err_info = parse_err(work / "eplusout.err")
    csv_path = work / "eplusout.csv"
    metrics: dict[str, Any] = {}
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
        for key, pattern in METRICS.items():
            metrics[key] = stats_for(rows, find_col(header, pattern))

    return {
        "id": scenario["id"],
        "desc": scenario["desc"],
        "schedules": scenario["schedules"],
        "command": cmd,
        "returncode": res.returncode,
        "elapsed_sec": elapsed,
        "err": err_info,
        "metrics": metrics,
        "output_dir": str(work),
    }


def metric(results: dict[str, Any], scenario: str, name: str, stat: str) -> float | None:
    value = results.get(scenario, {}).get("metrics", {}).get(name, {}).get(stat)
    return None if value is None else float(value)


def gt(a: float | None, b: float | None, margin: float = 0.0) -> bool:
    return a is not None and b is not None and a > b + margin


def component_assertions(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {s["id"]: s for s in scenarios}
    assertions = []
    for s in scenarios:
        counts = s["err"]["counts"]
        assertions.append(check(s["returncode"] == 0, f"{s['id']} EnergyPlus returncode is 0", s["returncode"]))
        assertions.append(check(counts["severe"] == 0 and counts["fatal"] == 0, f"{s['id']} has no severe/fatal", counts))
        z_min = s["metrics"].get("zone_temp", {}).get("min")
        z_max = s["metrics"].get("zone_temp", {}).get("max")
        assertions.append(
            check(
                z_min is not None and z_max is not None and 5.0 <= z_min <= z_max <= 60.0,
                f"{s['id']} zone temperature uses non-contradictory sane bound [5, 60] C",
                {"min": z_min, "max": z_max},
            )
        )

    assertions.extend(
        [
            check(
                metric(by_id, "tes_idle", "tes_use_heat", "abs_mean") is not None
                and metric(by_id, "tes_idle", "tes_use_heat", "abs_mean") < 50_000
                and metric(by_id, "tes_idle", "tes_source_heat", "abs_mean") < 50_000,
                "TES idle keeps use/source heat near zero",
                {
                    "use_abs_mean": metric(by_id, "tes_idle", "tes_use_heat", "abs_mean"),
                    "source_abs_mean": metric(by_id, "tes_idle", "tes_source_heat", "abs_mean"),
                },
            ),
            check(
                gt(
                    metric(by_id, "tes_discharge", "tes_use_heat", "abs_mean"),
                    metric(by_id, "tes_idle", "tes_use_heat", "abs_mean"),
                    10_000,
                ),
                "TES positive command increases use-side heat vs idle",
                {
                    "idle": metric(by_id, "tes_idle", "tes_use_heat", "abs_mean"),
                    "discharge": metric(by_id, "tes_discharge", "tes_use_heat", "abs_mean"),
                },
            ),
            check(
                gt(
                    metric(by_id, "tes_charge", "tes_source_avail", "mean"),
                    metric(by_id, "tes_idle", "tes_source_avail", "mean"),
                    0.5,
                ),
                "TES negative command opens source side vs idle",
                {
                    "idle": metric(by_id, "tes_idle", "tes_source_avail", "mean"),
                    "charge": metric(by_id, "tes_charge", "tes_source_avail", "mean"),
                    "source_heat_abs_mean": metric(by_id, "tes_charge", "tes_source_heat", "abs_mean"),
                },
            ),
            check(
                gt(
                    metric(by_id, "tes_cycle", "tes_source_heat", "abs_mean"),
                    metric(by_id, "tes_idle", "tes_source_heat", "abs_mean"),
                    1_000,
                )
                and gt(
                    metric(by_id, "tes_cycle", "tes_soc", "max"),
                    metric(by_id, "tes_cycle", "tes_soc", "min"),
                    0.1,
                ),
                "TES phased cycle produces source-side charge heat after discharge",
                {
                    "idle_source_heat": metric(by_id, "tes_idle", "tes_source_heat", "abs_mean"),
                    "cycle_source_heat": metric(by_id, "tes_cycle", "tes_source_heat", "abs_mean"),
                    "cycle_soc_min": metric(by_id, "tes_cycle", "tes_soc", "min"),
                    "cycle_soc_max": metric(by_id, "tes_cycle", "tes_soc", "max"),
                },
            ),
            check(
                gt(
                    metric(by_id, "chiller_high_it", "chiller_cooling", "mean"),
                    metric(by_id, "chiller_low_it", "chiller_cooling", "mean"),
                    100_000,
                ),
                "Chiller cooling is higher at high IT load",
                {
                    "low": metric(by_id, "chiller_low_it", "chiller_cooling", "mean"),
                    "high": metric(by_id, "chiller_high_it", "chiller_cooling", "mean"),
                },
            ),
            check(
                gt(
                    metric(by_id, "chiller_high_it", "ite_electricity", "mean"),
                    metric(by_id, "chiller_low_it", "ite_electricity", "mean"),
                    100_000,
                ),
                "ITE electric load is higher when ITE_Set is high",
                {
                    "low": metric(by_id, "chiller_low_it", "ite_electricity", "mean"),
                    "high": metric(by_id, "chiller_high_it", "ite_electricity", "mean"),
                },
            ),
            check(
                gt(
                    metric(by_id, "pumps_high", "condenser_pump_flow", "mean"),
                    metric(by_id, "pumps_low", "condenser_pump_flow", "mean"),
                    10.0,
                ),
                "Condenser pump command changes pump flow",
                {
                    "low": metric(by_id, "pumps_low", "condenser_pump_flow", "mean"),
                    "high": metric(by_id, "pumps_high", "condenser_pump_flow", "mean"),
                },
            ),
            check(
                gt(metric(by_id, "crah_high", "fan_flow", "mean"), metric(by_id, "crah_low", "fan_flow", "mean"), 1.0),
                "CRAH fan command changes air flow",
                {
                    "low": metric(by_id, "crah_low", "fan_flow", "mean"),
                    "high": metric(by_id, "crah_high", "fan_flow", "mean"),
                },
            ),
            check(
                metric(by_id, "tower_economizer", "tower_heat", "abs_mean") is not None
                or metric(by_id, "tower_economizer", "economizer_heat", "abs_mean") is not None,
                "Tower/economizer metrics are present",
                {
                    "tower": metric(by_id, "tower_economizer", "tower_heat", "abs_mean"),
                    "economizer": metric(by_id, "tower_economizer", "economizer_heat", "abs_mean"),
                },
            ),
        ]
    )
    return assertions


def write_report(out_dir: Path, audit: dict[str, Any]) -> None:
    lines = [
        "# EnergyPlus Model Audit",
        "",
        f"- Repo: `{audit['repo_path']}`",
        f"- Git hash: `{audit['git_hash']}`",
        f"- EnergyPlus: `{audit['energyplus_exe']}`",
        f"- Weather: `{audit['weather']}`",
        "",
        "## Building MD5",
        "",
        "| Key | Path | MD5 |",
        "|---|---|---|",
    ]
    for key, item in audit["buildings"].items():
        lines.append(f"| {key} | `{item['path']}` | `{item['md5']}` |")
    lines.extend(
        [
            "",
            "## Mirror Comparison",
            "",
            f"- Training Data vs sinergym mirror: `{audit['mirror_compare']['training']}`",
            f"- Evaluation Data vs sinergym mirror: `{audit['mirror_compare']['evaluation']}`",
            "",
            "## Static Checks",
            "",
            "| Result | Check | Detail |",
            "|---|---|---|",
        ]
    )
    for c in audit["static_checks"]:
        lines.append(f"| {'PASS' if c['pass'] else 'FAIL'} | {c['label']} | `{c.get('detail')}` |")

    lines.extend(["", "## Component Scenarios", "", "| Scenario | RC | Severe | Fatal | Warnings | Output |", "|---|---:|---:|---:|---:|---|"])
    for s in audit["scenarios"]:
        counts = s["err"]["counts"]
        lines.append(
            f"| {s['id']} | {s['returncode']} | {counts['severe']} | {counts['fatal']} | "
            f"{counts['warning']} | `{s['output_dir']}` |"
        )

    lines.extend(["", "## Component Assertions", "", "| Result | Assertion | Detail |", "|---|---|---|"])
    for c in audit["component_assertions"]:
        lines.append(f"| {'PASS' if c['pass'] else 'FAIL'} | {c['label']} | `{c.get('detail')}` |")

    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--building", default=str(BUILDING_FILES["data_training"]))
    parser.add_argument("--scenarios", default="all", help="comma-separated ids or 'all'")
    parser.add_argument("--no-eplus", action="store_true", help="only run static audit")
    args = parser.parse_args()

    eplus_dir = Path(os.environ.get("EPLUS_PATH", str(DEFAULT_EPLUS)))
    eplus_exe = eplus_dir / "energyplus.exe"
    if not args.no_eplus and not eplus_exe.exists():
        raise FileNotFoundError(f"EnergyPlus executable not found: {eplus_exe}")
    if not WEATHER.exists():
        raise FileNotFoundError(f"Weather file not found: {WEATHER}")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "tools" / "m1" / f"model_audit_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    selected = SCENARIOS
    if args.scenarios != "all":
        wanted = {x.strip() for x in args.scenarios.split(",") if x.strip()}
        selected = [s for s in SCENARIOS if s["id"] in wanted]
        missing = wanted - {s["id"] for s in selected}
        if missing:
            raise ValueError(f"Unknown scenarios: {sorted(missing)}")

    buildings = {key: {"path": str(path), "md5": md5(path)} for key, path in BUILDING_FILES.items()}
    base_path = Path(args.building)
    base_model = load_json(base_path)
    audit: dict[str, Any] = {
        "repo_path": str(ROOT),
        "git_hash": git_hash(),
        "energyplus_exe": str(eplus_exe),
        "weather": str(WEATHER),
        "created_at": stamp,
        "buildings": buildings,
        "mirror_compare": {
            "training": "identical" if same_file(BUILDING_FILES["data_training"], BUILDING_FILES["sinergym_training"]) else "different; inspect MD5 above",
            "evaluation": "identical" if same_file(BUILDING_FILES["data_evaluation"], BUILDING_FILES["sinergym_evaluation"]) else "different; inspect MD5 above",
        },
        "static_checks": static_audit(base_model),
        "scenarios": [],
        "component_assertions": [],
    }

    shutil.copy2(base_path, out_dir / "source_building.epJSON")
    if not args.no_eplus:
        for i, scenario in enumerate(selected, 1):
            print(f"[{i}/{len(selected)}] {scenario['id']}: {scenario['desc']}")
            result = run_scenario(eplus_exe, base_model, out_dir, scenario)
            counts = result["err"]["counts"]
            print(
                f"  rc={result['returncode']} severe={counts['severe']} "
                f"fatal={counts['fatal']} warnings={counts['warning']} "
                f"out={result['output_dir']}"
            )
            audit["scenarios"].append(result)
        audit["component_assertions"] = component_assertions(audit["scenarios"])

    with (out_dir / "audit.json").open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    write_report(out_dir, audit)

    n_static_fail = sum(1 for c in audit["static_checks"] if not c["pass"])
    n_component_fail = sum(1 for c in audit["component_assertions"] if not c["pass"])
    print(f"[audit] output: {out_dir}")
    print(f"[audit] static_fail={n_static_fail} component_fail={n_component_fail}")
    return 0 if n_static_fail == 0 and n_component_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
