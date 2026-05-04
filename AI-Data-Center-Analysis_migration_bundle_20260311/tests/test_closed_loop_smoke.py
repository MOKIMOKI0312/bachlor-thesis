import json

import pandas as pd
import pytest

from mpc_v2.core.metrics import compute_episode_metrics
from mpc_v2.scripts.run_closed_loop import run_closed_loop


def test_96_step_synthetic_closed_loop_smoke(tmp_path):
    run_dir = run_closed_loop(
        config_path="mpc_v2/config/base.yaml",
        case_id="pytest_96_step_smoke",
        steps=96,
        output_root=tmp_path,
        pv_perturbation="g05",
        seed=123,
    )
    monitor = pd.read_csv(run_dir / "monitor.csv")
    solver = pd.read_csv(run_dir / "solver_log.csv")
    summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
    assert len(monitor) == 96
    assert len(solver) == 96
    assert not monitor.isna().any().any()
    assert summary["has_nan"] is False
    assert summary["infeasible_count"] == 0
    assert summary["optimal_rate"] >= 0.95
    assert (monitor["tes_charge_kwth"] >= -1e-7).all()
    assert (monitor["tes_discharge_kwth"] >= -1e-7).all()


def test_metrics_rejects_solver_log_missing_required_columns():
    monitor = pd.DataFrame(
        {
            "price_usd_per_mwh": [29.0],
            "P_grid_kw": [1000.0],
            "P_spill_kw": [0.0],
            "pv_kw": [100.0],
            "facility_power_kw": [1100.0],
            "air_temperature_C": [24.0],
            "tes_soc": [0.5],
            "tes_charge_kwth": [0.0],
            "tes_discharge_kwth": [0.0],
            "pue_actual": [1.2],
        }
    )
    with pytest.raises(ValueError, match="solver_log is missing columns: \\['status'\\]"):
        compute_episode_metrics(monitor, pd.DataFrame({"solve_time_s": [0.1]}), case_id="missing_status")
    with pytest.raises(ValueError, match="solver_log is missing columns: \\['solve_time_s'\\]"):
        compute_episode_metrics(monitor, pd.DataFrame({"status": ["optimal"]}), case_id="missing_time")
