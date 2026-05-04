import numpy as np
import pandas as pd

from mpc_v2.core.forecast import apply_pv_perturbation, resample_hourly_to_15min


def test_hourly_resampling_repeats_to_15min():
    idx = pd.to_datetime(["2025-01-01 00:00:00", "2025-01-01 01:00:00"])
    series = pd.Series([10.0, 20.0], index=idx)
    out = resample_hourly_to_15min(series, mode="average_power")
    assert list(out.iloc[:4]) == [10.0, 10.0, 10.0, 10.0]
    assert out.iloc[4] == 20.0


def test_price_stepwise_resampling_repeats_to_15min():
    idx = pd.to_datetime(["2025-01-01 00:00:00", "2025-01-01 01:00:00"])
    series = pd.Series([29.0, 158.0], index=idx)
    out = resample_hourly_to_15min(series, mode="step")
    assert list(out.iloc[:4]) == [29.0, 29.0, 29.0, 29.0]
    assert out.iloc[4] == 158.0


def test_pv_perturbation_is_seeded_and_non_negative():
    pv = np.full(8, 100.0)
    a = apply_pv_perturbation(pv, "g10", seed=42)
    b = apply_pv_perturbation(pv, "g10", seed=42)
    assert np.allclose(a, b)
    assert np.all(a >= 0)
    assert not np.allclose(a, pv)


def test_all_pv_perturbation_modes_are_supported():
    pv = np.full(8, 100.0)
    for mode in ["nominal", "g05", "g10", "g20"]:
        out = apply_pv_perturbation(pv, mode, seed=42)
        assert out.shape == pv.shape
        assert np.all(out >= 0)
    assert np.allclose(apply_pv_perturbation(pv, "nominal", seed=42), pv)
