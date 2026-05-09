from datetime import datetime, timedelta
import importlib

import numpy as np
import pandas as pd
import pytest

from mpc_v2.kim_lite.model import _apply_tou_transform, _critical_peak_flags, _take_cyclic


def test_hourly_series_forward_fills_to_15min_for_kim_lite_and_energyplus():
    series = pd.Series(
        [10.0, 20.0],
        index=pd.to_datetime(["2025-01-01 00:00:00", "2025-01-01 01:00:00"]),
    )
    timestamps = [datetime(2024, 1, 1, 0, 0) + timedelta(minutes=15 * i) for i in range(8)]
    expected = np.asarray([10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0])

    common = importlib.import_module("Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.common")

    assert _take_cyclic(series, timestamps) == pytest.approx(expected)
    assert common.cyclic_lookup(series, timestamps) == pytest.approx(expected)


def test_tou_gamma_zero_flattens_floating_and_nonfloating_components():
    base_price = np.asarray([1.0, 3.0, 5.0], dtype=float)
    cp_flag = np.zeros(3, dtype=int)

    transformed, flags = _apply_tou_transform(base_price, alpha_float=0.8, gamma=0.0, cp_uplift=0.0, cp_flag=cp_flag)
    fully_nonfloating, _ = _apply_tou_transform(base_price, alpha_float=0.0, gamma=2.0, cp_uplift=0.0, cp_flag=cp_flag)

    assert flags.tolist() == [0, 0, 0]
    assert transformed == pytest.approx(np.full(3, base_price.mean()))
    assert fully_nonfloating == pytest.approx(np.full(3, base_price.mean()))


def test_critical_peak_flags_use_explicit_windows_not_price_quantiles():
    timestamps = [
        datetime(2025, 7, 1, 10, 45),
        datetime(2025, 7, 1, 11, 0),
        datetime(2025, 7, 1, 12, 45),
        datetime(2025, 7, 1, 13, 0),
        datetime(2025, 7, 1, 16, 30),
        datetime(2025, 9, 1, 16, 30),
    ]

    flags = _critical_peak_flags(timestamps, months=(7, 8), windows=((11.0, 13.0), (16.0, 17.0)))

    assert flags.tolist() == [0, 1, 1, 0, 1, 0]
