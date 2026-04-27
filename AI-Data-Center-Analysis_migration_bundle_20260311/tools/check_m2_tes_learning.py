"""Lightweight TES-learning diagnostics for running M2 jobs.

The checker reads completed training monitor.csv episodes. It is intentionally
observational: it does not run evaluation and does not touch the active jobs.
For M2, TES valve position > 0 means discharge and < 0 means charge.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STEPS_PER_HOUR = 4
STEPS_PER_DAY = 24 * STEPS_PER_HOUR


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def resolve_workspace(job_dir: Path) -> Path | None:
    status = load_json(job_dir / "status.json")
    if status and status.get("workspace_path"):
        return Path(status["workspace_path"])
    manifest = load_json(job_dir / "manifest.json")
    if manifest and manifest.get("status_file"):
        status = load_json(Path(manifest["status_file"]))
        if status and status.get("workspace_path"):
            return Path(status["workspace_path"])
    return None


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def corr(a: pd.Series, b: pd.Series) -> float | None:
    frame = pd.DataFrame({"a": numeric(a), "b": numeric(b)}).dropna()
    if len(frame) < 10 or frame["a"].std() == 0 or frame["b"].std() == 0:
        return None
    value = float(frame["a"].corr(frame["b"]))
    return None if math.isnan(value) else value


def is_complete_monitor(path: Path) -> bool:
    try:
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-1]
    except Exception:
        return False
    return tail.rstrip().endswith(",True") or ",True," in tail


def monitor_episode_number(path: Path) -> int:
    try:
        return int(path.parent.name.split("-")[-1])
    except Exception:
        return -1


def read_progress(workspace: Path) -> dict[str, Any]:
    path = workspace / "progress.csv"
    if not path.exists():
        return {"completed_rows": 0}
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {"completed_rows": 0, "error": str(exc)}
    if df.empty:
        return {"completed_rows": 0}
    learning = df.iloc[1:].copy() if len(df) > 1 else df.iloc[0:0].copy()
    latest = learning.iloc[-1].to_dict() if not learning.empty else {}
    return {
        "completed_rows": int(len(df)),
        "completed_learning_rows": int(len(learning)),
        "latest_learning_episode": latest,
    }


def analyze_workspace(job_name: str, workspace: Path | None, last_episodes: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "job": job_name,
        "workspace": str(workspace) if workspace else None,
        "completed_learning_episodes": 0,
        "status": "missing_workspace",
    }
    if workspace is None or not workspace.exists():
        return result

    monitors = sorted(
        workspace.glob("episode-*/monitor.csv"),
        key=monitor_episode_number,
    )
    completed = [
        path for path in monitors
        if monitor_episode_number(path) > 1 and is_complete_monitor(path)
    ]
    result["completed_learning_episodes"] = len(completed)
    result["progress"] = read_progress(workspace)
    if not completed:
        result["status"] = "no_completed_learning_episode"
        return result

    selected = completed[-last_episodes:] if last_episodes > 0 else completed
    frames: list[pd.DataFrame] = []
    for path in selected:
        try:
            df = pd.read_csv(path, index_col=False)
        except Exception as exc:
            result.setdefault("read_errors", []).append(f"{path}: {exc}")
            continue
        df["episode_file"] = path.parent.name
        frames.append(df)

    if not frames:
        result["status"] = "no_readable_monitor"
        return result

    df = pd.concat(frames, ignore_index=True)
    valve_column = "TES_valve_wrapper_position" if "TES_valve_wrapper_position" in df.columns else "TES_DRL"
    required = [valve_column, "TES_SOC", "price_current_norm", "pv_current_ratio"]
    missing = [name for name in required if name not in df.columns]
    if missing:
        result["status"] = "missing_columns"
        result["missing_columns"] = missing
        return result

    for col in [
        "TES_DRL", "TES_valve_wrapper_position", "TES_SOC", "TES_avg_temp", "price_current_norm",
        "pv_current_ratio", "hour_sin", "hour_cos", "reward",
        "air_temperature", "Electricity:Facility",
    ]:
        if col in df.columns:
            df[col] = numeric(df[col])
    df = df.dropna(subset=[valve_column, "TES_SOC", "price_current_norm"])
    if len(df) < 100:
        result["status"] = "insufficient_rows"
        result["rows"] = int(len(df))
        return result

    valve = df[valve_column].clip(-1, 1)
    soc = df["TES_SOC"].clip(0, 1)
    price = df["price_current_norm"]
    pv = df["pv_current_ratio"] if "pv_current_ratio" in df.columns else pd.Series(dtype=float)

    low_price = df[price <= price.quantile(0.25)]
    high_price = df[price >= price.quantile(0.75)]
    low_pv = df[pv <= pv.quantile(0.25)] if not pv.empty else pd.DataFrame()
    high_pv = df[pv >= pv.quantile(0.75)] if not pv.empty else pd.DataFrame()

    usable_days = len(soc) // STEPS_PER_DAY
    daily_amp: list[float] = []
    for day in range(usable_days):
        chunk = soc.iloc[day * STEPS_PER_DAY:(day + 1) * STEPS_PER_DAY]
        if len(chunk) == STEPS_PER_DAY:
            daily_amp.append(float(chunk.max() - chunk.min()))

    soc_equiv_cycles = float(soc.diff().abs().dropna().sum() / 2.0)
    active = valve.abs() > 0.05
    saturated = valve.abs() > 0.95

    high_price_mean = float(high_price[valve_column].mean()) if not high_price.empty else None
    low_price_mean = float(low_price[valve_column].mean()) if not low_price.empty else None
    price_response = (
        high_price_mean - low_price_mean
        if high_price_mean is not None and low_price_mean is not None
        else None
    )

    high_pv_mean = float(high_pv[valve_column].mean()) if not high_pv.empty else None
    low_pv_mean = float(low_pv[valve_column].mean()) if not low_pv.empty else None
    pv_response = (
        high_pv_mean - low_pv_mean
        if high_pv_mean is not None and low_pv_mean is not None
        else None
    )

    result.update(
        {
            "status": "ok",
            "valve_column": valve_column,
            "analyzed_episodes": [path.parent.name for path in selected],
            "rows": int(len(df)),
            "valve_mean": float(valve.mean()),
            "valve_abs_mean": float(valve.abs().mean()),
            "valve_active_fraction": float(active.mean()),
            "valve_saturation_fraction": float(saturated.mean()),
            "charge_fraction": float((valve < -0.05).mean()),
            "discharge_fraction": float((valve > 0.05).mean()),
            "soc_min": float(soc.min()),
            "soc_max": float(soc.max()),
            "soc_mean": float(soc.mean()),
            "soc_daily_amplitude_mean": float(np.mean(daily_amp)) if daily_amp else None,
            "soc_equivalent_cycles_in_sample": soc_equiv_cycles,
            "price_high_valve_mean": high_price_mean,
            "price_low_valve_mean": low_price_mean,
            "price_response_high_minus_low": price_response,
            "pv_high_valve_mean": high_pv_mean,
            "pv_low_valve_mean": low_pv_mean,
            "pv_response_high_minus_low": pv_response,
            "corr_valve_price": corr(valve, price),
            "corr_valve_pv": corr(valve, pv) if not pv.empty else None,
            "latest_reward_mean": float(df["reward"].mean()) if "reward" in df.columns else None,
        }
    )
    return result


def aggregate(results: list[dict[str, Any]], min_episodes: int, strong_episodes: int) -> dict[str, Any]:
    ok = [item for item in results if item.get("status") == "ok"]
    if not ok:
        return {"verdict": "no_data", "reason": "No readable completed learning episodes yet."}

    min_done = min(int(item.get("completed_learning_episodes", 0)) for item in ok)
    avg_price_response = float(np.nanmean([
        item.get("price_response_high_minus_low", np.nan) for item in ok
    ]))
    avg_amp = float(np.nanmean([
        item.get("soc_daily_amplitude_mean", np.nan) for item in ok
    ]))
    avg_active = float(np.nanmean([
        item.get("valve_active_fraction", np.nan) for item in ok
    ]))
    avg_saturation = float(np.nanmean([
        item.get("valve_saturation_fraction", np.nan) for item in ok
    ]))
    positive_price_seeds = sum(
        1 for item in ok
        if (item.get("price_response_high_minus_low") is not None
            and item["price_response_high_minus_low"] > 0.10)
    )

    if min_done < min_episodes:
        verdict = "too_early"
        reason = f"Need at least {min_episodes} completed learning episodes per seed; minimum is {min_done}."
    elif min_done < strong_episodes:
        if avg_price_response > 0.10 and avg_amp > 0.10 and positive_price_seeds >= max(1, len(ok) // 2):
            verdict = "early_positive_signal"
            reason = "TES behavior is beginning to align with price, but this is not yet a reliable convergence claim."
        else:
            verdict = "early_weak_or_unclear"
            reason = "Enough for a first look, but price-conditioned TES behavior is weak or inconsistent."
    else:
        if avg_price_response > 0.15 and avg_amp > 0.20 and avg_active > 0.20 and avg_saturation < 0.80:
            verdict = "credible_learning_candidate"
            reason = "TES action is price-conditioned, SOC cycles materially, and the policy is not just saturated."
        else:
            verdict = "not_learned_or_unclear"
            reason = "At the stronger checkpoint, TES behavior does not yet meet the learning heuristics."

    return {
        "verdict": verdict,
        "reason": reason,
        "min_completed_learning_episodes": min_done,
        "avg_price_response_high_minus_low": avg_price_response,
        "avg_soc_daily_amplitude_mean": avg_amp,
        "avg_valve_active_fraction": avg_active,
        "avg_valve_saturation_fraction": avg_saturation,
        "positive_price_response_seeds": positive_price_seeds,
        "seed_count": len(ok),
    }


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.{digits}f}"
    return str(value)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    lines = [
        "# M2 TES Learning Check",
        "",
        f"- Checked at: `{payload['checked_at']}`",
        f"- Verdict: `{agg.get('verdict')}`",
        f"- Reason: {agg.get('reason')}",
        "",
        "| Job | Done learn ep | Analyzed | Price response | SOC daily amp | Active frac | Saturated frac | Charge frac | Discharge frac | SOC range |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in payload["jobs"]:
        soc_range = ""
        if item.get("soc_min") is not None and item.get("soc_max") is not None:
            soc_range = f"{item['soc_min']:.3f}-{item['soc_max']:.3f}"
        lines.append(
            "| {job} | {done} | {episodes} | {price} | {amp} | {active} | {sat} | {charge} | {discharge} | {soc} |".format(
                job=item.get("job"),
                done=item.get("completed_learning_episodes", 0),
                episodes=",".join(item.get("analyzed_episodes", [])),
                price=fmt(item.get("price_response_high_minus_low")),
                amp=fmt(item.get("soc_daily_amplitude_mean")),
                active=fmt(item.get("valve_active_fraction")),
                sat=fmt(item.get("valve_saturation_fraction")),
                charge=fmt(item.get("charge_fraction")),
                discharge=fmt(item.get("discharge_fraction")),
                soc=soc_range,
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `Price response` = mean actual TES valve position during high-price quartile minus mean valve during low-price quartile.",
            "- M2 direction: valve > 0 discharges TES; valve < 0 charges TES.",
            "- A positive price response means the policy tends to discharge more in expensive hours than cheap hours.",
            "- This is a training-behavior diagnostic, not a deterministic evaluation result.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dirs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--last-episodes", type=int, default=3)
    parser.add_argument("--min-episodes", type=int, default=5)
    parser.add_argument("--strong-episodes", type=int, default=10)
    args = parser.parse_args()

    jobs = []
    for job_dir in args.job_dirs:
        workspace = resolve_workspace(job_dir)
        jobs.append(analyze_workspace(job_dir.name, workspace, args.last_episodes))

    payload = {
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "jobs": jobs,
        "aggregate": aggregate(jobs, args.min_episodes, args.strong_episodes),
    }

    write_markdown(args.output, payload)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
