"""W2 scenario summary: TES energy + PV self-consumption.

Reads 3 cells (MILP / Heuristic / Baseline-neutral) and aggregates:
- Section 4.1 energy: cost_usd_total, total_load_mwh, pue_avg, comfort_violation_pct
- Section 4.2 PV   : self_consumption_rate, pv_load_coverage, grid_import/export
- MPC-only         : sign_rate, dsoc_prepeak/peak, mode_switches, gate_pass

Baseline cell columns are filled with N/A for MPC-only metrics.
PV and energy columns are auto-detected via aliases and unit fallbacks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PV_ALIASES = ["current_pv_kw", "pv_current_kw", "pv_kw", "pv_power_kw"]
FACILITY_ALIASES = ["Electricity:Facility", "Facility:Electricity", "Electricity_Facility"]
IT_ALIASES = ["ITE-CPU:InteriorEquipment:Electricity", "ITE_CPU_InteriorEquipment_Electricity"]
SOC_ALIASES = ["TES_SOC", "tes_soc"]
MODE_ALIASES = ["tes_mpc_mode_label"]

COST_KEYS = ["cost_usd", "cost_usd_total", "total_cost_usd", "cost_total"]
PUE_KEYS = ["pue", "pue_avg", "PUE"]
COMFORT_KEYS = ["comfort_violation_pct", "comfort_pct", "comfort"]
SIGN_RATE_KEYS = ["charge_window_sign_rate"]
DSOC_PREPEAK_KEYS = ["delta_soc_prepeak", "dsoc_prepeak"]
DSOC_PEAK_KEYS = ["delta_soc_peak", "dsoc_peak"]
GATE_KEYS = ["mechanism_gate_pass", "gate_pass"]


def first_match(d: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def first_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    for c in aliases:
        if c in df.columns:
            return c
    return None


def _read_result(result_path: Path) -> dict[str, Any]:
    if not result_path.exists():
        return {}
    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)
    if isinstance(result, list) and result:
        result = result[0]
    if not isinstance(result, dict):
        return {}
    return result


def _candidate_result_paths(tag: str, runs_dir: Path) -> list[Path]:
    paths = [
        runs_dir / tag / "result.json",
        Path("runs/eval_m2") / f"{tag}_neutral" / "result.json",
        Path("runs/eval_m2") / tag / "result.json",
    ]
    paths.extend(Path("runs").rglob(f"*{tag}*/result.json"))
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in paths:
        if p not in seen:
            unique.append(p)
            seen.add(p)
    return unique


def resolve_cell_paths(tag: str, runs_dir: Path, override_dir: str | None = None) -> tuple[Path, Path | None]:
    if override_dir:
        run_dir = Path(override_dir) / tag
        result_path = run_dir / "result.json"
        if (run_dir / "monitor.csv").exists():
            return run_dir, result_path if result_path.exists() else None

    direct_dir = runs_dir / tag
    direct_result = direct_dir / "result.json"
    if (direct_dir / "monitor.csv").exists():
        return direct_dir, direct_result if direct_result.exists() else None

    for result_path in _candidate_result_paths(tag, runs_dir):
        result = _read_result(result_path)
        monitor_csv = result.get("monitor_csv")
        if monitor_csv:
            monitor_path = Path(str(monitor_csv))
            if monitor_path.exists():
                return monitor_path.parent, result_path

    monitor_candidates = list(Path("runs").rglob(f"*{tag}*/monitor.csv"))
    monitor_candidates += list(Path("runs").rglob(f"*{tag}*/episode-001/monitor.csv"))
    if monitor_candidates:
        monitor_path = monitor_candidates[0]
        result_candidates = [p for p in _candidate_result_paths(tag, runs_dir) if p.exists()]
        result_path = result_candidates[0] if result_candidates else None
        return monitor_path.parent, result_path

    raise FileNotFoundError(f"cannot locate monitor.csv for tag={tag}")


def load_cell(run_dir: Path, result_path: Path | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    monitor_path = run_dir / "monitor.csv"
    if not monitor_path.exists():
        raise FileNotFoundError(f"missing monitor.csv: {monitor_path}")
    df = pd.read_csv(monitor_path)
    result = _read_result(result_path) if result_path else _read_result(run_dir / "result.json")
    return df, result


def reconstruct_pv_kw(df: pd.DataFrame, pv_csv: Path, peak_kw: float = 6000.0) -> np.ndarray:
    """Fallback: rebuild PV series from CSV + step index.

    Assumes step starts at Jan 1, 0:00 and timesteps_per_hour=4.
    """
    pv = pd.read_csv(pv_csv)
    if "power_kw" in pv.columns:
        hourly_kw = pv["power_kw"].to_numpy(dtype=np.float64)
    elif "power_ratio" in pv.columns:
        hourly_kw = pv["power_ratio"].to_numpy(dtype=np.float64) * peak_kw
    else:
        raise RuntimeError(f"PV CSV {pv_csv} missing power_kw / power_ratio column")
    n_rows = len(df)
    upsampled = np.repeat(hourly_kw, 4)
    if len(upsampled) < n_rows:
        upsampled = np.tile(upsampled, int(np.ceil(n_rows / len(upsampled))))
    return upsampled[:n_rows]


def facility_to_mwh_step(
    df: pd.DataFrame,
    fac_col: str,
    result: dict[str, Any],
    timesteps_per_hour: int,
) -> tuple[np.ndarray, str]:
    raw = df[fac_col].astype(float).to_numpy()
    median = float(np.nanmedian(np.abs(raw)))
    if median > 1.0e5:
        return raw / 3.6e9, "J_per_step"
    if result.get("energy_unit_detected") == "MWh" or "mwh_step" in df.columns or median < 100.0:
        return raw, "MWh_per_step"
    dt_h = 1.0 / timesteps_per_hour
    return raw * dt_h / 1000.0, "W"


def derive_pv_metrics(
    df: pd.DataFrame,
    result: dict[str, Any],
    pv_csv: Path,
    timesteps_per_hour: int = 4,
) -> tuple[dict[str, float], dict[str, Any]]:
    pv_col = first_col(df, PV_ALIASES)
    fac_col = first_col(df, FACILITY_ALIASES)
    if fac_col is None:
        raise RuntimeError(f"facility column not found. monitor cols={list(df.columns)[:30]}...")

    diagnostics: dict[str, Any] = {
        "pv_reconstructed": False,
        "pv_col": pv_col,
        "facility_col": fac_col,
    }
    if pv_col is not None:
        pv_kw = df[pv_col].astype(float).to_numpy()
    else:
        print(f"  [info] PV column missing in monitor; reconstructing from {pv_csv}")
        pv_kw = reconstruct_pv_kw(df, pv_csv)
        diagnostics["pv_reconstructed"] = True

    facility_mwh_step, facility_unit = facility_to_mwh_step(df, fac_col, result, timesteps_per_hour)
    diagnostics["facility_unit"] = facility_unit

    dt_h = 1.0 / timesteps_per_hour
    load_kw = facility_mwh_step / dt_h * 1000.0
    pv_consumed_kw = np.minimum(pv_kw, load_kw)

    pv_total_gen_mwh = float(np.nansum(pv_kw) * dt_h / 1000.0)
    pv_consumed_mwh = float(np.nansum(pv_consumed_kw) * dt_h / 1000.0)
    load_total_mwh = float(np.nansum(facility_mwh_step))

    scr_pct = pv_consumed_mwh / pv_total_gen_mwh * 100.0 if pv_total_gen_mwh > 0 else 0.0
    coverage_pct = pv_consumed_mwh / load_total_mwh * 100.0 if load_total_mwh > 0 else 0.0
    grid_import_mwh = float(np.nansum(np.maximum(0.0, load_kw - pv_kw)) * dt_h / 1000.0)
    grid_export_mwh = float(np.nansum(np.maximum(0.0, pv_kw - load_kw)) * dt_h / 1000.0)

    diagnostic = {
        "pv_col_used": pv_col if pv_col is not None else "RECONSTRUCTED_FROM_CSV",
        "pv_kw_mean": float(np.mean(pv_kw)),
        "pv_kw_max": float(np.max(pv_kw)),
        "pv_kw_nonzero_steps": int(np.sum(pv_kw > 1.0)),
        "load_kw_mean": float(np.mean(load_kw)),
        "load_kw_max": float(np.max(load_kw)),
        "load_kw_min": float(np.min(load_kw)),
        "pv_exceeds_load_steps": int(np.sum(pv_kw > load_kw)),
        "pv_exceeds_load_pct": float(np.sum(pv_kw > load_kw) / len(pv_kw) * 100.0),
    }
    print(f"  [pv-diag] {diagnostic}")

    return (
        {
            "pv_total_gen_mwh": pv_total_gen_mwh,
            "pv_consumed_mwh": pv_consumed_mwh,
            "self_consumption_rate_pct": scr_pct,
            "pv_load_coverage_pct": coverage_pct,
            "grid_import_mwh": grid_import_mwh,
            "grid_export_mwh": grid_export_mwh,
            "total_load_mwh": load_total_mwh,
            "_pv_diagnostic": diagnostic,
        },
        diagnostics,
    )


def derive_mpc_metrics(df: pd.DataFrame, result: dict[str, Any]) -> dict[str, Any]:
    out = {
        "sign_rate": first_match(result, SIGN_RATE_KEYS, "N/A"),
        "dsoc_prepeak": first_match(result, DSOC_PREPEAK_KEYS, "N/A"),
        "dsoc_peak": first_match(result, DSOC_PEAK_KEYS, "N/A"),
        "mechanism_gate_pass": first_match(result, GATE_KEYS, "N/A"),
    }
    mode_col = first_col(df, MODE_ALIASES)
    if mode_col:
        labels = df[mode_col].fillna("").astype(str).to_numpy()
        out["mode_switches"] = int(np.sum(labels[1:] != labels[:-1]))
    else:
        out["mode_switches"] = "N/A"
    return out


def fallback_count(result: dict[str, Any]) -> int:
    counts = result.get("solver_status_counts")
    if isinstance(counts, dict):
        return int(counts.get("milp_to_heuristic_fallback", 0))
    return 0


def validate(df_out: pd.DataFrame) -> dict[str, Any]:
    if len(df_out) != 3:
        raise RuntimeError(f"expected 3 rows, got {len(df_out)}")
    algorithms = set(df_out["algorithm"].astype(str))
    expected = {"baseline_neutral", "heuristic", "mpc_milp"}
    if algorithms != expected:
        raise RuntimeError(f"expected algorithms {sorted(expected)}, got {sorted(algorithms)}")

    by_algo = df_out.set_index("algorithm")
    base_cost = float(by_algo.loc["baseline_neutral", "cost_usd_total"])
    heur_cost = float(by_algo.loc["heuristic", "cost_usd_total"])
    milp_cost = float(by_algo.loc["mpc_milp", "cost_usd_total"])
    if not (base_cost >= heur_cost >= milp_cost):
        raise RuntimeError(
            "cost monotonicity failed: "
            f"baseline={base_cost}, heuristic={heur_cost}, milp={milp_cost}"
        )

    base_scr = float(by_algo.loc["baseline_neutral", "self_consumption_rate_pct"])
    heur_scr = float(by_algo.loc["heuristic", "self_consumption_rate_pct"])
    milp_scr = float(by_algo.loc["mpc_milp", "self_consumption_rate_pct"])
    scr_span = max(base_scr, heur_scr, milp_scr) - min(base_scr, heur_scr, milp_scr)
    scr_monotonic = base_scr <= heur_scr <= milp_scr
    if not (scr_monotonic or scr_span < 2.0):
        raise RuntimeError(
            "SCR monotonicity failed: "
            f"baseline={base_scr}, heuristic={heur_scr}, milp={milp_scr}, span={scr_span}"
        )

    comfort_max = float(df_out["comfort_violation_pct"].astype(float).max())
    if comfort_max >= 5.0:
        raise RuntimeError(f"comfort check failed: max={comfort_max}")

    return {
        "cost_monotonic": True,
        "scr_monotonic": bool(scr_monotonic),
        "scr_close_within_2pp": bool(scr_span < 2.0),
        "comfort_lt_5pct": True,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", required=True)
    ap.add_argument("--runs-dir", default="runs/m2_tes_mpc_oracle")
    ap.add_argument("--baseline-dir", default=None, help="If baseline output not in runs-dir, override here.")
    ap.add_argument("--pv-csv", default="Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv")
    ap.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip cost/SCR/comfort monotonicity checks; emit csv/md anyway.",
    )
    args = ap.parse_args()

    runs_dir = Path(args.runs_dir)
    cells_spec = [
        ("baseline_neutral", f"w2_baseline_neutral_year_{args.ts}", args.baseline_dir),
        ("heuristic", f"w2_mpc_heuristic_year_{args.ts}", None),
        ("mpc_milp", f"w2_mpc_milp_year_{args.ts}", None),
    ]

    rows: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for algo, tag, override_dir in cells_spec:
        run_dir, result_path = resolve_cell_paths(tag, runs_dir, override_dir)
        print(f"==> {algo} ({tag})")
        print(f"    run_dir={run_dir}")
        if result_path:
            print(f"    result={result_path}")
        df, result = load_cell(run_dir, result_path)
        print(f"    rows={len(df)} cols={len(df.columns)} result_keys={len(result)}")

        cost_total = first_match(result, COST_KEYS)
        if cost_total is None:
            if "cost_usd_step" in df.columns:
                cost_total = float(df["cost_usd_step"].astype(float).sum())
            else:
                cost_total = float("nan")
        pue = first_match(result, PUE_KEYS, float("nan"))
        comfort = first_match(result, COMFORT_KEYS, float("nan"))

        pv, pv_diag = derive_pv_metrics(df, result, Path(args.pv_csv))
        mpc = derive_mpc_metrics(df, result)
        diagnostics[algo] = {
            "tag": tag,
            "run_dir": str(run_dir),
            "result_path": str(result_path) if result_path else None,
            "fallback_count": fallback_count(result),
            **pv_diag,
        }

        rows.append(
            {
                "algorithm": algo,
                "tag": tag,
                "total_steps": len(df),
                "cost_usd_total": cost_total,
                "total_load_mwh": pv["total_load_mwh"],
                "pue_avg": pue,
                "comfort_violation_pct": comfort,
                "pv_total_gen_mwh": pv["pv_total_gen_mwh"],
                "pv_consumed_mwh": pv["pv_consumed_mwh"],
                "self_consumption_rate_pct": pv["self_consumption_rate_pct"],
                "pv_load_coverage_pct": pv["pv_load_coverage_pct"],
                "grid_import_mwh": pv["grid_import_mwh"],
                "grid_export_mwh": pv["grid_export_mwh"],
                "_pv_diagnostic": pv.get("_pv_diagnostic"),
                **mpc,
            }
        )

    pv_diag = {}
    for row in rows:
        diag = row.pop("_pv_diagnostic", None)
        if diag:
            pv_diag[row["algorithm"]] = diag

    df_out = pd.DataFrame(rows)

    base = df_out[df_out["algorithm"] == "baseline_neutral"].iloc[0]
    base_cost = float(base["cost_usd_total"])
    base_pue = float(base["pue_avg"])
    base_scr = float(base["self_consumption_rate_pct"])

    df_out["cost_saving_vs_baseline_usd"] = base_cost - df_out["cost_usd_total"].astype(float)
    df_out["cost_saving_vs_baseline_pct"] = df_out["cost_saving_vs_baseline_usd"] / base_cost * 100.0
    df_out["pue_improvement_vs_baseline"] = base_pue - df_out["pue_avg"].astype(float)
    df_out["self_consumption_uplift_vs_baseline_pp"] = df_out["self_consumption_rate_pct"].astype(float) - base_scr

    if args.skip_validation:
        try:
            validation = validate(df_out)
            print(f"Validation: {validation}")
        except RuntimeError as e:
            print(f"[WARN] validation failed but --skip-validation given: {e}")
            validation = {"status": "skipped_due_to_failure", "error": str(e)}
    else:
        validation = validate(df_out)

    out_csv = Path(f"analysis/m2f1_w2_scenario_compare_{args.ts}.csv")
    out_md = Path(f"analysis/m2f1_w2_scenario_compare_{args.ts}.md")
    diag_path = Path(f"analysis/m2f1_w2_pv_diagnostic_{args.ts}.json")
    val_path = Path(f"analysis/m2f1_w2_scenario_validation_{args.ts}.json")
    df_out.to_csv(out_csv, index=False)

    energy_cols = [
        "algorithm",
        "total_steps",
        "cost_usd_total",
        "total_load_mwh",
        "pue_avg",
        "comfort_violation_pct",
        "cost_saving_vs_baseline_usd",
        "cost_saving_vs_baseline_pct",
        "pue_improvement_vs_baseline",
    ]
    pv_cols = [
        "algorithm",
        "pv_total_gen_mwh",
        "pv_consumed_mwh",
        "self_consumption_rate_pct",
        "pv_load_coverage_pct",
        "grid_import_mwh",
        "grid_export_mwh",
        "self_consumption_uplift_vs_baseline_pp",
    ]
    mpc_cols = ["algorithm", "sign_rate", "dsoc_prepeak", "dsoc_peak", "mode_switches", "mechanism_gate_pass"]

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# W2 Scenario Comparison ({args.ts})\n\n")
        f.write("## Section 4.1 TES energy contribution\n\n")
        f.write(df_out[energy_cols].to_markdown(index=False, floatfmt=".4f"))
        f.write("\n\n## Section 4.2 PV self-consumption comparison\n\n")
        f.write(df_out[pv_cols].to_markdown(index=False, floatfmt=".4f"))
        f.write("\n\n## MPC mechanism diagnostics (MPC cells only)\n\n")
        f.write(df_out[mpc_cols].to_markdown(index=False))
        f.write("\n")

    with open(diag_path, "w", encoding="utf-8") as f:
        json.dump(pv_diag, f, indent=2, ensure_ascii=False)
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {out_csv}")
    print(f"Wrote {out_md}")
    print(f"Wrote {diag_path}")
    print(f"Wrote {val_path}")
    print("\n=== ENERGY TABLE ===")
    print(df_out[energy_cols].to_string(index=False))
    print("\n=== PV TABLE ===")
    print(df_out[pv_cols].to_string(index=False))
    print("\n=== DIAGNOSTICS ===")
    print(json.dumps({"diagnostics": diagnostics, "pv_diagnostic": pv_diag, "validation": validation}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
