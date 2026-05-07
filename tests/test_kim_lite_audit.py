import pandas as pd

from mpc_v2.scripts.audit_kim_lite_results import audit_root


def test_audit_flags_non_neutral_storage_priority(tmp_path):
    phase_b = tmp_path / "phase_b_attribution"
    phase_b.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "controller": "storage_priority_neutral_tes",
                "solver_status": "storage_priority_neutral",
                "soc_final": 0.55,
                "terminal_soc_abs_error": 0.05,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.55,
            }
        ]
    ).to_csv(phase_b / "summary.csv", index=False)
    pd.DataFrame(
        [
            {"metric": "RBC_gap_neutral", "value": 1.0},
            {"metric": "RBC_gap_non_neutral", "value": 2.0},
        ]
    ).to_csv(phase_b / "attribution_table.csv", index=False)
    issues = audit_root(tmp_path)
    assert any("terminal SOC error" in issue for issue in issues)


def test_audit_flags_fractional_strict_peak_cap(tmp_path):
    phase_b = tmp_path / "phase_b_attribution"
    phase_b.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "controller": "storage_priority_neutral_tes",
                "solver_status": "storage_priority_neutral",
                "soc_final": 0.5,
                "terminal_soc_abs_error": 0.0,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.5,
            }
        ]
    ).to_csv(phase_b / "summary.csv", index=False)
    pd.DataFrame(
        [
            {"metric": "RBC_gap_neutral", "value": 1.0},
            {"metric": "RBC_gap_non_neutral", "value": 2.0},
        ]
    ).to_csv(phase_b / "attribution_table.csv", index=False)
    phase_d = tmp_path / "phase_d_peakcap"
    phase_d.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "case_id": "strict_bad",
                "controller": "paper_like_mpc_tes",
                "solver_status": "optimal",
                "mode_integrality": "strict",
                "strict_success": True,
                "fallback_reason": "",
                "mode_fractionality_max": 0.25,
                "cap_ratio": 0.99,
                "peak_cap_kw": 100.0,
                "peak_grid_kw": 100.0,
                "peak_slack_max_kw": 0.0,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.5,
            }
        ]
    ).to_csv(phase_d / "summary.csv", index=False)
    issues = audit_root(tmp_path)
    assert any("strict mode fractionality" in issue for issue in issues)
