from datetime import datetime, timedelta

import pandas as pd
import pytest

from mpc_v2.core.dr_service import DRService, summarize_dr_events
from mpc_v2.core.statistics import bootstrap_ci, holm_bonferroni, paired_metric_summary
from mpc_v2.core.tariff_service import TariffService
from mpc_v2.scripts.generate_china_matrix import generate_china_matrix


def test_beijing_tariff_splits_float_component_and_marks_critical_peak():
    timestamps = [datetime(2025, 7, 1, 10), datetime(2025, 7, 1, 11), datetime(2025, 7, 1, 23)]
    service = TariffService({"template": "beijing", "gamma": 0.0, "cp_uplift": 0.2, "float_share": 0.8})
    result = service.apply(timestamps, [100.0, 200.0, 50.0])
    assert result.tou_stage == ["peak", "peak", "valley"]
    assert result.cp_flag == [0, 1, 0]
    assert result.price_nonfloat == pytest.approx([20.0, 40.0, 10.0])
    assert result.price_float[1] > result.price_float[0]


def test_one_step_tariff_uses_reference_mean_for_actual_settlement():
    timestamp = [datetime(2025, 7, 1, 10)]
    base_price = [200.0]
    flat = TariffService(
        {"template": "beijing", "gamma": 0.0, "cp_uplift": 0.0, "float_share": 0.8},
        reference_price_mean=100.0,
    ).apply(timestamp, base_price)
    high_spread = TariffService(
        {"template": "beijing", "gamma": 2.0, "cp_uplift": 0.0, "float_share": 0.8},
        reference_price_mean=100.0,
    ).apply(timestamp, base_price)
    assert flat.price_total[0] == pytest.approx(120.0)
    assert high_spread.price_total[0] == pytest.approx(280.0)


def test_dr_service_builds_event_cap_and_summary():
    timestamps = [datetime(2025, 7, 1, 18) + timedelta(minutes=15 * i) for i in range(4)]
    service = DRService(
        {
            "enabled": True,
            "event_type": "realtime",
            "start_hour": 18.0,
            "duration_hours": 1.0,
            "reduction_frac": 0.10,
            "baseline_kw": 1000.0,
            "compensation_cny_per_kwh": 4.8,
        }
    )
    series = service.build(timestamps, [900.0, 900.0, 900.0, 900.0])
    assert series.dr_flag == [1, 1, 1, 1]
    assert series.dr_req_kw == pytest.approx([100.0, 100.0, 100.0, 100.0])
    assert series.dynamic_peak_cap_kw == pytest.approx([900.0, 900.0, 900.0, 900.0])

    monitor = pd.DataFrame(
        {
            "dr_flag": [1, 1, 1, 1],
            "dr_event_id": ["e", "e", "e", "e"],
            "scenario_id": ["case", "case", "case", "case"],
            "dr_notice_type": ["realtime", "realtime", "realtime", "realtime"],
            "timestamp": [str(ts) for ts in timestamps],
            "dr_baseline_kw": [1000.0, 1000.0, 1000.0, 1000.0],
            "dr_req_kw": [100.0, 100.0, 100.0, 100.0],
            "grid_import_kw": [900.0, 950.0, 1000.0, 900.0],
            "q_dis_tes_kw_th": [10.0, 20.0, 0.0, 30.0],
            "room_temp_c": [25.0, 26.0, 27.5, 25.0],
            "dr_response_threshold": [0.5, 0.5, 0.5, 0.5],
            "dr_compensation_cny_per_kwh": [4.8, 4.8, 4.8, 4.8],
        }
    )
    events = summarize_dr_events(monitor, dt_hours=0.25, temp_max_c=27.0)
    assert events["requested_reduction_kwh"].iloc[0] == pytest.approx(100.0)
    assert events["served_reduction_kwh"].iloc[0] == pytest.approx(62.5)
    assert events["dr_revenue_cny"].iloc[0] > 0.0


def test_dr_event_day_index_triggers_only_once_in_month():
    timestamps = [datetime(2025, 7, 1) + timedelta(minutes=15 * i) for i in range(30 * 96)]
    service = DRService(
        {
            "enabled": True,
            "event_type": "day_ahead",
            "start_hour": 18.0,
            "duration_hours": 2.0,
            "event_day_index": 19,
            "episode_start_timestamp": "2025-07-01 00:00:00",
            "reduction_frac": 0.10,
            "baseline_kw": 1000.0,
        }
    )
    series = service.build(timestamps, [900.0] * len(timestamps))
    assert sum(series.dr_flag) == 8
    assert series.dr_event_id.count("dr_event") == 8


def test_generate_china_matrix_counts_and_peak_reference_source():
    matrix = generate_china_matrix(profile="month")
    sets = matrix["scenario_sets"]
    assert len(sets["china_tou_screening_full"]) == 40
    assert len(sets["china_tou_full_compare_full"]) == 32
    assert len(sets["china_peakcap_full"]) == 24
    assert len(sets["china_dr_event_full"]) == 18
    assert len(sets["china_robustness_full"]) == 24
    assert len(sets["china_all_full"]) == 138
    peak_case = matrix["scenarios"][sets["china_peakcap_full"][0]]
    assert peak_case["peak_cap_reference_source"] == "peakcap_reference_hot_mpc_no_tes"
    assert matrix["metadata"]["closed_loop_steps"] == 2880


def test_generate_soc_neutral_matrix_sets_terminal_target():
    matrix = generate_china_matrix(profile="month_soc_neutral")
    assert matrix["metadata"]["soc_neutral_terminal"] is True
    scenario = matrix["scenarios"]["tou_screen_g1_cp0p2_hot_mpc_tes"]
    assert scenario["soc_target"] == pytest.approx(0.5)
    assert scenario["w_terminal"] == pytest.approx(50000.0)
    assert scenario["truncate_horizon_to_episode"] is True
    robust = matrix["scenarios"]["robust_base_cp20_soc0p8_mpc_tes"]
    assert robust["initial_soc"] == pytest.approx(0.8)
    assert robust["soc_target"] == pytest.approx(0.8)


def test_statistics_helpers_return_paired_summary_and_holm_decisions():
    frame = pd.DataFrame(
        {
            "weather": ["hot", "hot", "mild", "mild"],
            "controller": ["mpc_no_tes", "mpc_tes", "mpc_no_tes", "mpc_tes"],
            "total_cost": [100.0, 90.0, 80.0, 75.0],
        }
    )
    summary = paired_metric_summary(
        frame,
        pair_columns=["weather"],
        controller_column="controller",
        metric="total_cost",
        baseline="mpc_no_tes",
        candidate="mpc_tes",
        n_boot=50,
        seed=1,
    )
    assert summary.n_pairs == 2
    assert summary.mean_difference == pytest.approx(7.5)
    assert bootstrap_ci([1.0, 2.0, 3.0], n_boot=20, seed=1)[0] <= 2.0
    assert holm_bonferroni([0.01, 0.04, 0.20]) == [True, False, False]
