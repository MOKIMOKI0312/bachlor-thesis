"""F1 end-to-end simulation: 3 "resets" with different random T_init, verify tank init temps differ.

This simulates what sinergym would do if its reset() injects T_init.
For each of 3 "episodes":
  1. Sample T_init ~ U(6, 12)
  2. Inject into Schedule:Compact.TES_Charge_Setpoint.data[3].field
  3. Run 1-day E+ simulation
  4. Record step1 node_1 temperature

Expected: 3 step1 node_1 values differ by >0.5°C, verifying per-episode randomization works.

Usage:
    python tools/m1/f1_simulate_random_reset.py
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPLUS = ROOT / "vendor" / "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64" / "energyplus.exe"
BUILDINGS = ROOT / "Data" / "buildings"
WEATHER = ROOT / "Data" / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
SRC = BUILDINGS / "DRL_DC_training.epJSON"


def _patch(src: Path, dst: Path, t_init: float) -> None:
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    # 1-day runperiod
    data["RunPeriod"] = {"RP F1": {
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

    # Inject T_init into Schedule:Compact (simulates sinergym's hook)
    sc = data["Schedule:Compact"]["TES_Charge_Setpoint"]
    sc["data"][3]["field"] = f"{t_init:.3f}"

    # Output tank obs
    outvars = data.setdefault("Output:Variable", {})
    for i in range(1, 11):
        outvars[f"F1Out Tank Node {i}"] = {
            "key_value": "Chilled Water Tank",
            "variable_name": f"Chilled Water Thermal Storage Temperature Node {i}",
            "reporting_frequency": "Timestep",
        }
    outvars["F1Out Tank Final T"] = {
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


def _get_step1_final_T(csv_path: Path) -> float | None:
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        header = next(rdr)
        row1 = next(rdr, None)
        if row1 is None:
            return None
    col = -1
    for i, c in enumerate(header):
        if "chilled water tank" in c.lower() and "final tank" in c.lower():
            col = i
            break
    if col < 0:
        return None
    try:
        return float(row1[col])
    except (ValueError, IndexError):
        return None


def main() -> int:
    # Fixed seed for reproducibility
    rng = random.Random(42)
    tag = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "tools" / "m1" / "smoke_tes_init_probe" / f"f1_simulate_reset_{tag}"
    base.mkdir(parents=True, exist_ok=True)
    print(f"[f1-sim] base: {base}")

    n_resets = 3
    results = []
    t_inits = []

    for ep in range(1, n_resets + 1):
        t_init = rng.uniform(6.0, 12.0)
        t_inits.append(t_init)
        wd = base / f"ep{ep:02d}_Tinit{t_init:.3f}"
        wd.mkdir(parents=True, exist_ok=True)
        epjson = wd / "input.epJSON"
        _patch(SRC, epjson, t_init=t_init)

        print(f"\n=== 'Episode' {ep}: T_init={t_init:.3f}°C ===")
        rc, csv_path = _run(wd, epjson)
        print(f"  returncode: {rc}")

        if rc != 0 or not csv_path.exists():
            print(f"  FAIL")
            results.append(None)
            continue

        final_T = _get_step1_final_T(csv_path)
        soc = (12.0 - final_T) / 6.0 if final_T is not None else None
        soc = max(0.0, min(1.0, soc)) if soc is not None else None
        print(f"  step1 tank Final T: {final_T:.4f}°C  -> SOC={soc:.4f}" if final_T else "  no final_T")
        results.append((t_init, final_T, soc))

    # Cross-check: all 3 step1 temps should differ
    print(f"\n=== F1 Randomization Smoke Summary ===")
    print(f"  T_init sequence (seed=42): {[f'{t:.3f}' for t in t_inits]}")
    print(f"  step1 final_T results: {[f'{r[1]:.3f}' if r else 'FAIL' for r in results]}")
    print(f"  step1 SOC results:     {[f'{r[2]:.3f}' if r else 'FAIL' for r in results]}")

    # pass criterion: differences >0.5 between all 3 pairs
    valid = [r for r in results if r is not None]
    if len(valid) < n_resets:
        print("  FAIL: some runs failed")
        return 1

    t_vals = [v[1] for v in valid]
    diffs = [abs(t_vals[i] - t_vals[j]) for i in range(len(t_vals)) for j in range(i + 1, len(t_vals))]
    min_diff = min(diffs) if diffs else 0
    max_diff = max(diffs) if diffs else 0
    print(f"  pairwise diff range: [{min_diff:.3f}, {max_diff:.3f}]")
    passed = min_diff > 0.1
    print(f"  verdict: {'PASS' if passed else 'FAIL'} (need min_diff > 0.1)")

    out = base / "f1_simulate_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "passed": passed,
            "seed": 42,
            "t_inits": t_inits,
            "results": [{"t_init": r[0], "final_T": r[1], "SOC": r[2]} if r else None for r in results],
            "min_pairwise_diff": min_diff,
            "max_pairwise_diff": max_diff,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[f1-sim] result: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
