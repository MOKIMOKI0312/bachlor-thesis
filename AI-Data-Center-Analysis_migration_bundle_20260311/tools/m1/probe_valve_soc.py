"""Probe valve → SOC causality in BOTH directions.

The 2026-04-23 smoke test (smoke_p5_fix_final/) only verified:
  - discharge (v=+0.5) from SOC=0.80 → works (0.80 → 0.016)
  - charge (v=-0.5) from SOC=0.97 (already full) → inconclusive (0.97 → 0.93)

This probe uses a phased schedule:
  Phase 1 (Day 1-3): TES_Set = +0.5 → drain the tank to SOC ~0
  Phase 2 (Day 4-7): TES_Set = -0.5 → attempt to refill

If charge path works, SOC should RISE in phase 2.
If charge path is blocked (Chiller-starvation or EMS bug), SOC stays near 0.

Usage:
    python tools/m1/probe_valve_soc.py
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS_EXE = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"
OUT = Path(__file__).resolve().parent / "probe_valve_soc_out"


def make_epjson(dst: Path, days: int = 7) -> None:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    data["RunPeriod"] = {"Probe": {
        "begin_month": 1, "begin_day_of_month": 1, "begin_year": 2025,
        "end_month": 1, "end_day_of_month": days, "end_year": 2025,
        "day_of_week_for_start_day": "Wednesday",
        "apply_weekend_holiday_rule": "No",
        "use_weather_file_daylight_saving_period": "No",
        "use_weather_file_holidays_and_special_days": "No",
        "use_weather_file_rain_indicators": "Yes",
        "use_weather_file_snow_indicators": "Yes",
    }}
    data["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": 4}}
    # Remove Schedule:Constant "TES_Set" and replace with Schedule:Compact
    if "TES_Set" in data.get("Schedule:Constant", {}):
        del data["Schedule:Constant"]["TES_Set"]
    sc_compact = data.setdefault("Schedule:Compact", {})
    # Phase 1: days 1-3 discharge (+0.5), Phase 2: days 4+ charge (-0.5)
    sc_compact["TES_Set"] = {
        "data": [
            {"field": "Through: 1/3"},
            {"field": "For: AllDays"},
            {"field": "Until: 24:00"},
            {"field": "0.5"},
            {"field": "Through: 12/31"},
            {"field": "For: AllDays"},
            {"field": "Until: 24:00"},
            {"field": "-0.5"},
        ]
    }
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_eplus(epjson: Path, workdir: Path) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [str(EPLUS_EXE), "-w", str(WEATHER), "-d", str(workdir), "-x", "-r", str(epjson)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    (workdir / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (workdir / "stderr.log").write_text(result.stderr, encoding="utf-8")
    return result.returncode


def find_col(header, *substrs):
    for i, h in enumerate(header):
        if all(s.lower() in h.lower() for s in substrs):
            return i
    return -1


def analyze(workdir: Path):
    csv_path = workdir / "eplusout.csv"
    if not csv_path.exists():
        return None
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        cols = {
            "soc": find_col(header, "TES_SOC_Obs", "Schedule Value"),
            "tes_set": find_col(header, "TES_Set", "Schedule Value"),
            "tank_t": find_col(header, "Final Tank Temperature"),
            "use_ht": find_col(header, "Use Side Heat Transfer Rate"),
            "source_ht": find_col(header, "Source Side Heat Transfer Rate"),
            "chiller_avail": find_col(header, "Chiller_Avail_Sch", "Schedule Value"),
            "air_t": find_col(header, "Zone Mean Air Temperature"),
        }
        if cols["air_t"] < 0:
            cols["air_t"] = find_col(header, "Zone Air Temperature", "DataCenter")
        rows = []
        for row in rdr:
            try:
                rec = {"date": row[0].strip()}
                for name, idx in cols.items():
                    rec[name] = float(row[idx]) if idx >= 0 and row[idx].strip() else None
                rows.append(rec)
            except (ValueError, IndexError):
                continue
    return {"cols": cols, "rows": rows, "header_sample": header[:10]}


def summarize(rows, phase_boundary_idx):
    """phase_boundary_idx = step index at end of phase 1 (discharge), start of phase 2 (charge)"""
    phase1 = rows[:phase_boundary_idx]
    phase2 = rows[phase_boundary_idx:]

    def stats(rs, key):
        vals = [r[key] for r in rs if r.get(key) is not None]
        if not vals:
            return None
        return {"min": min(vals), "max": max(vals), "first": vals[0], "last": vals[-1], "mean": sum(vals) / len(vals)}

    return {
        "phase1_discharge": {
            "n_steps": len(phase1),
            "soc": stats(phase1, "soc"),
            "tank_t": stats(phase1, "tank_t"),
            "use_ht": stats(phase1, "use_ht"),
            "source_ht": stats(phase1, "source_ht"),
            "chiller_avail_mean": (sum(r.get("chiller_avail") or 0 for r in phase1) / len(phase1)) if phase1 else None,
            "air_t_max": max((r.get("air_t") or -1e9) for r in phase1) if phase1 else None,
        },
        "phase2_charge": {
            "n_steps": len(phase2),
            "soc": stats(phase2, "soc"),
            "tank_t": stats(phase2, "tank_t"),
            "use_ht": stats(phase2, "use_ht"),
            "source_ht": stats(phase2, "source_ht"),
            "chiller_avail_mean": (sum(r.get("chiller_avail") or 0 for r in phase2) / len(phase2)) if phase2 else None,
            "air_t_max": max((r.get("air_t") or -1e9) for r in phase2) if phase2 else None,
        },
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    epjson = OUT / "probe.epjson"
    make_epjson(epjson, days=7)
    workdir = OUT / "sim"
    print(f"Running E+ 7 days, 15-min timestep...")
    rc = run_eplus(epjson, workdir)
    print(f"E+ returncode: {rc}")

    result = analyze(workdir)
    if result is None:
        print("ERROR: no eplusout.csv")
        print("Check stderr.log in", workdir)
        sys.exit(1)
    rows = result["rows"]
    cols = result["cols"]
    print(f"Columns found: {cols}")
    print(f"Total rows: {len(rows)}")

    # Phase boundary: end of day 3 at 15-min = 3 * 96 = 288
    boundary = min(288, len(rows) // 2)
    summary = summarize(rows, boundary)

    # Sample points
    sample_idxs = [0, 95, 191, 287, 383, 479, 575, 671]  # end of each day roughly
    samples = []
    for i in sample_idxs:
        if i < len(rows):
            samples.append({"step": i, **rows[i]})

    report = {
        "scenario": "phased: days 1-3 discharge (+0.5), days 4+ charge (-0.5)",
        "n_steps": len(rows),
        "phase_boundary_step": boundary,
        "summary": summary,
        "samples": samples,
    }
    out_path = OUT / "probe_result.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nSamples at end of each day:")
    for s in samples:
        print(f"  step {s['step']:3d} | SOC={s.get('soc')} | tank_T={s.get('tank_t')} | "
              f"TES_Set={s.get('tes_set')} | src_HT={s.get('source_ht')} | "
              f"use_HT={s.get('use_ht')} | chill_avail={s.get('chiller_avail')} | "
              f"air_T={s.get('air_t')}")
    print(f"\nReport: {out_path}")


if __name__ == "__main__":
    main()
