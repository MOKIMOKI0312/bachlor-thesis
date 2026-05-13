import pandas as pd
import pytest

from mpc_v2.phase3_sizing.pv_scaling import scale_pv_profile


def test_pv_20_to_40_doubles_and_preserves_index():
    index = pd.date_range("2025-07-01", periods=3, freq="h")
    base = pd.Series([0.0, 1000.0, 2000.0], index=index)
    scaled = scale_pv_profile(base, base_capacity_mwp=20, target_capacity_mwp=40)
    assert list(scaled) == [0.0, 2000.0, 4000.0]
    assert scaled.index.equals(index)


def test_pv_20_to_zero_returns_zero_profile():
    base = pd.Series([0.0, 1000.0, 2000.0], index=pd.date_range("2025-07-01", periods=3, freq="h"))
    scaled = scale_pv_profile(base, base_capacity_mwp=20, target_capacity_mwp=0)
    assert scaled.eq(0.0).all()


def test_negative_pv_is_rejected():
    base = pd.Series([0.0, -1.0, 2.0])
    with pytest.raises(ValueError, match="non-negative"):
        scale_pv_profile(base, base_capacity_mwp=20, target_capacity_mwp=40)
