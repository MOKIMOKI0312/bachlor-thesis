"""PV profile scaling for Phase 3 capacity sensitivity."""

from __future__ import annotations

import pandas as pd


def scale_pv_profile(base_pv_kw: pd.Series, base_capacity_mwp: float, target_capacity_mwp: float) -> pd.Series:
    """Scale a non-negative PV power profile linearly between MWp capacities.

    Negative PV inputs are rejected rather than clipped, because clipping would
    hide data-quality problems in the source profile.
    """

    if float(base_capacity_mwp) <= 0:
        raise ValueError("base_capacity_mwp must be positive")
    if float(target_capacity_mwp) < 0:
        raise ValueError("target_capacity_mwp must be non-negative")
    values = pd.to_numeric(base_pv_kw, errors="raise").astype(float)
    if (values < -1e-9).any():
        raise ValueError("base_pv_kw must be non-negative")
    if float(target_capacity_mwp) == 0:
        return pd.Series(0.0, index=base_pv_kw.index, name=base_pv_kw.name)
    scaled = values.clip(lower=0.0) * (float(target_capacity_mwp) / float(base_capacity_mwp))
    return pd.Series(scaled.to_numpy(), index=base_pv_kw.index, name=base_pv_kw.name)
