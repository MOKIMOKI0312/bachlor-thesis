"""Small statistical helpers for paired MPC scenario comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PairedComparison:
    """Summary of paired metric differences."""

    metric: str
    baseline: str
    candidate: str
    n_pairs: int
    mean_difference: float
    median_difference: float
    ci_low: float
    ci_high: float


def paired_metric_summary(
    frame: pd.DataFrame,
    pair_columns: Iterable[str],
    controller_column: str,
    metric: str,
    baseline: str,
    candidate: str,
    n_boot: int = 2000,
    seed: int = 7,
) -> PairedComparison:
    """Compute baseline-minus-candidate paired differences and bootstrap CI."""

    pair_columns = list(pair_columns)
    required = set(pair_columns + [controller_column, metric])
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"summary frame is missing columns: {sorted(missing)}")
    pivot = frame.pivot_table(index=pair_columns, columns=controller_column, values=metric, aggfunc="first")
    if baseline not in pivot.columns or candidate not in pivot.columns:
        raise ValueError(f"controllers {baseline!r} and {candidate!r} must both be present")
    diffs = (pivot[baseline] - pivot[candidate]).dropna().to_numpy(dtype=float)
    if len(diffs) == 0:
        raise ValueError("no paired observations available")
    ci_low, ci_high = bootstrap_ci(diffs, n_boot=n_boot, seed=seed)
    return PairedComparison(
        metric=metric,
        baseline=baseline,
        candidate=candidate,
        n_pairs=int(len(diffs)),
        mean_difference=float(np.mean(diffs)),
        median_difference=float(np.median(diffs)),
        ci_low=ci_low,
        ci_high=ci_high,
    )


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, seed: int = 7, alpha: float = 0.05) -> tuple[float, float]:
    """Return a percentile bootstrap confidence interval for the mean."""

    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        raise ValueError("bootstrap_ci needs at least one finite value")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive")
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(int(n_boot), len(values)), replace=True).mean(axis=1)
    return (float(np.quantile(draws, alpha / 2.0)), float(np.quantile(draws, 1.0 - alpha / 2.0)))


def holm_bonferroni(p_values: Iterable[float], alpha: float = 0.05) -> list[bool]:
    """Return reject decisions using Holm-Bonferroni family-wise correction."""

    p_values = [float(p) for p in p_values]
    if any(p < 0.0 or p > 1.0 or not np.isfinite(p) for p in p_values):
        raise ValueError("p-values must be finite and in [0, 1]")
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    reject = [False] * m
    for rank, idx in enumerate(order):
        threshold = alpha / (m - rank)
        if p_values[idx] <= threshold:
            reject[idx] = True
        else:
            break
    return reject
