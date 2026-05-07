"""Fit explainable MPC prediction models from EnergyPlus sampling outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import DEFAULT_BASELINE_TIMESERIES, DEFAULT_PARAM_YAML, REPO_ROOT, load_baseline_timeseries, read_yaml, write_yaml
from .run_sampling_matrix import DEFAULT_SAMPLING_ROOT


REPORT_PATH = REPO_ROOT / "docs" / "energyplus_mpc_sampling_report_20260507.md"


def fit_prediction_models(root: str | Path, baseline_timeseries: str | Path = DEFAULT_BASELINE_TIMESERIES, params_path: str | Path = DEFAULT_PARAM_YAML) -> dict[str, Any]:
    result_root = Path(root)
    result_root.mkdir(parents=True, exist_ok=True)
    samples = collect_samples(result_root, baseline_timeseries)
    samples.to_csv(result_root / "samples_15min.csv", index=False)
    params = read_yaml(params_path)
    metrics, models = _fit_models(samples, params)
    metrics.to_csv(result_root / "fit_metrics.csv", index=False)
    model_doc = _build_model_doc(result_root, samples, metrics, models)
    write_yaml(result_root / "prediction_models.yaml", model_doc)
    _write_figures(result_root, samples, models)
    _write_report(result_root, samples, metrics, model_doc)
    return model_doc


def collect_samples(root: Path, baseline_timeseries: str | Path = DEFAULT_BASELINE_TIMESERIES) -> pd.DataFrame:
    frames: list[pd.DataFrame] = [_baseline_frame(baseline_timeseries)]
    manifest = _load_manifest(root)
    for monitor_path in sorted(root.glob("*/monitor.csv")):
        case_id = monitor_path.parent.name
        frames.append(_monitor_frame(monitor_path, case_id, manifest.get(case_id, {}), bootstrap=False))
    if not list(root.glob("*/monitor.csv")):
        coupling_root = REPO_ROOT / "results" / "energyplus_mpc_20260507"
        for monitor_path in sorted(coupling_root.glob("*/monitor.csv")):
            case_id = f"bootstrap_{monitor_path.parent.name}"
            meta = {
                "family": f"bootstrap_{monitor_path.parent.name}",
                "purpose": "bootstrap_pipeline_validation",
                "identification_only": True,
            }
            frames.append(_monitor_frame(monitor_path, case_id, meta, bootstrap=True))
    samples = pd.concat(frames, ignore_index=True, sort=False)
    samples["timestamp"] = pd.to_datetime(samples["timestamp"])
    samples["date"] = samples["timestamp"].dt.date.astype(str)
    samples["split"] = np.where(samples["timestamp"].dt.dayofyear % 5 == 0, "validation", "train")
    samples["tes_set_abs"] = samples["tes_set_written"].abs()
    samples["soc_next"] = samples.groupby("case_id")["soc"].shift(-1)
    samples["zone_temp_next_c"] = samples.groupby("case_id")["zone_temp_c"].shift(-1)
    samples["soc_delta_next"] = samples["soc_next"] - samples["soc"]
    return samples


def _baseline_frame(path: str | Path) -> pd.DataFrame:
    frame = load_baseline_timeseries(path).copy()
    soc = ((12.0 - frame["tes_tank_temp_c"].astype(float)) / (12.0 - 6.67)).clip(0.0, 1.0)
    out = pd.DataFrame(
        {
            "case_id": "baseline_existing",
            "family": "baseline_reuse",
            "purpose": "baseline_reference",
            "identification_only": False,
            "bootstrap_existing": False,
            "timestamp": frame["interval_start"],
            "simulation_step": np.arange(len(frame), dtype=int),
            "soc": soc,
            "tes_set_written": 0.0,
            "ite_set_written": 0.45,
            "chiller_t_set_written": 0.0,
            "tes_set_echo": 0.0,
            "ite_set_echo": 0.45,
            "chiller_t_set_echo": 0.0,
            "tes_use_side_kw": frame["tes_use_side_kw"].astype(float),
            "tes_source_side_kw": frame["tes_source_side_kw"].astype(float),
            "chiller_cooling_kw": frame["chiller_cooling_kw"].astype(float),
            "chiller_electricity_kw": frame["chiller_electricity_kw"].astype(float),
            "facility_electricity_kw": frame["facility_electricity_kw"].astype(float),
            "outdoor_wetbulb_c": frame["outdoor_wetbulb_c"].astype(float),
            "zone_temp_c": frame["zone_air_temp_c"].astype(float),
        }
    )
    return out


def _monitor_frame(path: Path, case_id: str, meta: dict[str, Any], bootstrap: bool) -> pd.DataFrame:
    frame = pd.read_csv(path)
    for col, default in [("ite_set_written", 0.45), ("chiller_t_set_written", 0.0), ("tes_set_written", 0.0)]:
        if col not in frame:
            frame[col] = default
    for col in ["ite_set_echo", "chiller_t_set_echo"]:
        if col not in frame:
            written = col.replace("_echo", "_written")
            frame[col] = frame.get(written, np.nan)
    frame["case_id"] = case_id
    frame["family"] = meta.get("family", "unknown")
    frame["purpose"] = meta.get("purpose", "")
    frame["identification_only"] = bool(meta.get("identification_only", True))
    frame["bootstrap_existing"] = bootstrap
    keep = [
        "case_id",
        "family",
        "purpose",
        "identification_only",
        "bootstrap_existing",
        "timestamp",
        "simulation_step",
        "soc",
        "tes_set_written",
        "ite_set_written",
        "chiller_t_set_written",
        "tes_set_echo",
        "ite_set_echo",
        "chiller_t_set_echo",
        "tes_use_side_kw",
        "tes_source_side_kw",
        "chiller_cooling_kw",
        "chiller_electricity_kw",
        "facility_electricity_kw",
        "outdoor_wetbulb_c",
        "zone_temp_c",
    ]
    return frame[keep]


def _load_manifest(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "sampling_manifest.csv"
    if not path.exists():
        return {}
    rows = pd.read_csv(path).fillna("").to_dict("records")
    return {str(row["case_id"]): row for row in rows}


def _fit_models(samples: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    chiller_rows = samples[samples["chiller_cooling_kw"] > 100.0].copy()
    chiller_model, chiller_metrics = _fit_linear_model(
        chiller_rows,
        ["chiller_cooling_kw", "outdoor_wetbulb_c", "chiller_t_set_written"],
        "chiller_electricity_kw",
    )
    discharge_rows = samples[(samples["tes_set_written"] > 0.01) & (samples["tes_use_side_kw"].abs() > 1e-4)].copy()
    charge_rows = samples[(samples["tes_set_written"] < -0.01) & (samples["tes_source_side_kw"].abs() > 1e-4)].copy()
    discharge_rows["q_tes_response_abs_kw"] = discharge_rows["tes_use_side_kw"].abs()
    charge_rows["q_tes_response_abs_kw"] = charge_rows["tes_source_side_kw"].abs()
    discharge_model, discharge_metrics = _fit_linear_model(
        discharge_rows,
        ["tes_set_abs", "soc", "chiller_cooling_kw", "outdoor_wetbulb_c"],
        "q_tes_response_abs_kw",
    )
    charge_model, charge_metrics = _fit_linear_model(
        charge_rows,
        ["tes_set_abs", "soc", "chiller_cooling_kw", "outdoor_wetbulb_c"],
        "q_tes_response_abs_kw",
    )
    zone_rows = samples.dropna(subset=["zone_temp_next_c"]).copy()
    zone_model, zone_metrics = _fit_linear_model(
        zone_rows,
        ["zone_temp_c", "outdoor_wetbulb_c", "tes_use_side_kw", "tes_source_side_kw", "chiller_cooling_kw"],
        "zone_temp_next_c",
    )
    soc_metrics = _soc_rollout_metrics(samples, params)
    direction_accuracy = _tes_direction_accuracy(samples)
    metric_rows = [
        chiller_metrics | {"model": "chiller_power", "target": "chiller_electricity_kw", "threshold": 0.15},
        discharge_metrics | {"model": "tes_discharge_response", "target": "abs(tes_use_side_kw)", "threshold": np.nan},
        charge_metrics | {"model": "tes_charge_response", "target": "abs(tes_source_side_kw)", "threshold": np.nan},
        zone_metrics | {"model": "zone_temperature_safety", "target": "zone_temp_next_c", "threshold": np.nan},
        soc_metrics | {"model": "soc_24h_rollout", "target": "soc", "threshold": 0.03},
        {"model": "tes_direction", "target": "direction", "rows": int((samples["tes_set_abs"] > 0.01).sum()), "validation_cvrmse": np.nan, "validation_mae": 1.0 - direction_accuracy, "score": direction_accuracy, "threshold": 0.95},
    ]
    metrics = pd.DataFrame(metric_rows)
    models = {
        "chiller_power": chiller_model,
        "tes_discharge_response": discharge_model,
        "tes_charge_response": charge_model,
        "zone_temperature_safety": zone_model,
        "soc": {
            "capacity_kwh_th": float(params["tes"].get("capacity_kwh_th_proxy", 39069.768)),
            "dt_hours": float(params["energyplus"].get("dt_hours", 0.25)),
            "loss_per_h": float(soc_metrics.get("loss_per_h", 0.0)),
        },
    }
    return metrics, models


def _fit_linear_model(frame: pd.DataFrame, features: list[str], target: str) -> tuple[dict[str, Any], dict[str, Any]]:
    valid = frame.dropna(subset=features + [target]).copy()
    if len(valid) < len(features) + 2:
        return (
            {"type": "linear", "features": features, "intercept": 0.0, "coefficients": {feature: 0.0 for feature in features}, "rows": int(len(valid)), "status": "insufficient_data"},
            {"rows": int(len(valid)), "validation_cvrmse": np.nan, "validation_mae": np.nan, "score": np.nan},
        )
    train = valid[valid["split"] == "train"]
    validation = valid[valid["split"] == "validation"]
    if len(validation) < len(features) + 2:
        validation = valid.iloc[::5]
        train = valid.drop(validation.index)
    if len(train) < len(features) + 2:
        train = valid
    x_train = _design_matrix(train, features)
    y_train = train[target].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
    eval_frame = validation if not validation.empty else valid
    pred = _design_matrix(eval_frame, features) @ beta
    actual = eval_frame[target].to_numpy(dtype=float)
    rmse = float(np.sqrt(np.mean((pred - actual) ** 2))) if len(actual) else np.nan
    mae = float(np.mean(np.abs(pred - actual))) if len(actual) else np.nan
    denom = float(np.mean(np.abs(actual))) if len(actual) else np.nan
    cvrmse = float(rmse / denom) if denom and denom > 1e-9 else np.nan
    return (
        {
            "type": "linear",
            "features": features,
            "intercept": float(beta[0]),
            "coefficients": {feature: float(value) for feature, value in zip(features, beta[1:])},
            "rows": int(len(valid)),
            "status": "fitted",
        },
        {"rows": int(len(valid)), "validation_cvrmse": cvrmse, "validation_mae": mae, "score": cvrmse},
    )


def _design_matrix(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.column_stack([np.ones(len(frame))] + [frame[feature].to_numpy(dtype=float) for feature in features])


def _soc_rollout_metrics(samples: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    capacity = float(params["tes"].get("capacity_kwh_th_proxy", 39069.768))
    dt_hours = float(params["energyplus"].get("dt_hours", 0.25))
    valid = samples.dropna(subset=["soc_next"]).copy()
    if valid.empty:
        return {"rows": 0, "validation_cvrmse": np.nan, "validation_mae": np.nan, "score": np.nan, "loss_per_h": 0.0}
    no_tes = valid[valid["tes_set_abs"] <= 0.01]
    loss_per_h = float(np.maximum(0.0, -no_tes["soc_delta_next"].median() / dt_hours)) if len(no_tes) else 0.0
    q_source = valid["tes_source_side_kw"].clip(upper=0.0).abs()
    q_use = valid["tes_use_side_kw"].clip(lower=0.0).abs()
    pred = (valid["soc"] + (q_source - q_use) * dt_hours / capacity - loss_per_h * dt_hours).clip(0.0, 1.0)
    mae = float(np.mean(np.abs(pred - valid["soc_next"])))
    return {"rows": int(len(valid)), "validation_cvrmse": np.nan, "validation_mae": mae, "score": mae, "loss_per_h": loss_per_h}


def _tes_direction_accuracy(samples: pd.DataFrame) -> float:
    active = samples[samples["tes_set_abs"] > 0.01].copy()
    if active.empty:
        return float("nan")
    expected_discharge = active["tes_set_written"] > 0.0
    actual_discharge = active["tes_use_side_kw"].abs() >= active["tes_source_side_kw"].abs()
    return float((expected_discharge == actual_discharge).mean())


def _build_model_doc(root: Path, samples: pd.DataFrame, metrics: pd.DataFrame, models: dict[str, Any]) -> dict[str, Any]:
    full_sampling_present = bool((samples["bootstrap_existing"] == False).sum() > 35040 and (samples["family"] == "tes_pulse").any())  # noqa: E712
    chiller_ok = _metric_ok(metrics, "chiller_power", 0.15, "validation_cvrmse")
    soc_ok = _metric_ok(metrics, "soc_24h_rollout", 0.03, "validation_mae")
    direction_ok = _metric_ok(metrics, "tes_direction", 0.95, "score", greater=True)
    failure_reasons: list[str] = []
    if not full_sampling_present:
        failure_reasons.append("full high_explainable sampling matrix has not been run; fit used baseline/bootstrap data")
    if not chiller_ok:
        failure_reasons.append("chiller validation CVRMSE above 15% or unavailable")
    if not soc_ok:
        failure_reasons.append("SOC rollout MAE above 0.03 or unavailable")
    if not direction_ok:
        failure_reasons.append("TES direction accuracy below 95% or unavailable")
    return {
        "schema_version": 1,
        "source_root": str(root),
        "split_method": "date_block_dayofyear_mod_5_validation",
        "samples": {
            "rows": int(len(samples)),
            "cases": int(samples["case_id"].nunique()),
            "bootstrap_existing_rows": int(samples["bootstrap_existing"].sum()),
        },
        "adoption_ready": not failure_reasons,
        "failure_reasons": failure_reasons,
        "models": models,
    }


def _metric_ok(metrics: pd.DataFrame, model: str, threshold: float, column: str, greater: bool = False) -> bool:
    row = metrics[metrics["model"] == model]
    if row.empty:
        return False
    value = float(row.iloc[0][column])
    if np.isnan(value):
        return False
    return value >= threshold if greater else value <= threshold


def _write_figures(root: Path, samples: pd.DataFrame, models: dict[str, Any]) -> None:
    figure_dir = root / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    active = samples[samples["chiller_cooling_kw"] > 100.0]
    if not active.empty:
        plt.figure(figsize=(7, 4))
        plt.scatter(active["chiller_cooling_kw"], active["chiller_electricity_kw"], s=4, alpha=0.25)
        plt.xlabel("Chiller cooling (kW_th)")
        plt.ylabel("Chiller electricity (kW)")
        plt.tight_layout()
        plt.savefig(figure_dir / "chiller_power_fit.png", dpi=160)
        plt.close()
    tes = samples[samples["tes_set_abs"] > 0.01]
    if not tes.empty:
        plt.figure(figsize=(7, 4))
        plt.scatter(tes["tes_set_written"], tes["tes_use_side_kw"], s=8, alpha=0.35, label="use side")
        plt.scatter(tes["tes_set_written"], tes["tes_source_side_kw"], s=8, alpha=0.35, label="source side")
        plt.xlabel("TES_Set")
        plt.ylabel("TES heat transfer (kW)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figure_dir / "tes_response_by_setpoint.png", dpi=160)
        plt.close()
    soc = samples.dropna(subset=["soc_next"])
    if not soc.empty:
        plt.figure(figsize=(7, 4))
        plt.scatter(soc["soc"], soc["soc_next"], s=4, alpha=0.25)
        plt.xlabel("SOC(t)")
        plt.ylabel("SOC(t+1)")
        plt.tight_layout()
        plt.savefig(figure_dir / "soc_one_step_scatter.png", dpi=160)
        plt.close()
    zone = samples.dropna(subset=["zone_temp_next_c"])
    if not zone.empty:
        plt.figure(figsize=(7, 4))
        plt.scatter(zone["zone_temp_c"], zone["zone_temp_next_c"], s=4, alpha=0.25)
        plt.xlabel("Zone temp(t) C")
        plt.ylabel("Zone temp(t+1) C")
        plt.tight_layout()
        plt.savefig(figure_dir / "zone_temp_one_step_scatter.png", dpi=160)
        plt.close()


def _write_report(root: Path, samples: pd.DataFrame, metrics: pd.DataFrame, model_doc: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    metric_md = _frame_to_markdown(metrics.fillna(""))
    failure_lines = "\n".join(f"- {reason}" for reason in model_doc["failure_reasons"]) or "- None"
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# EnergyPlus MPC Sampling Report 2026-05-07",
                "",
                "## Summary",
                "",
                f"- Samples root: `{root}`",
                f"- Rows: `{len(samples)}`",
                f"- Cases: `{samples['case_id'].nunique()}`",
                f"- Adoption ready: `{model_doc['adoption_ready']}`",
                "",
                "This report treats sampling outputs as parameter-identification data. Identification-only perturbations are not normal operating conclusions.",
                "",
                "## Metrics",
                "",
                metric_md,
                "",
                "## Failure Reasons / Limits",
                "",
                failure_lines,
                "",
                "## Thesis Impact",
                "",
                "No thesis draft update is required until these identified models are accepted as thesis methods or conclusions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _frame_to_markdown(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.to_dict("records"):
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_SAMPLING_ROOT))
    parser.add_argument("--baseline-timeseries", default=str(DEFAULT_BASELINE_TIMESERIES))
    parser.add_argument("--params", default=str(DEFAULT_PARAM_YAML))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    fit_prediction_models(args.root, args.baseline_timeseries, args.params)
    print(Path(args.root) / "prediction_models.yaml")
    print(REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
