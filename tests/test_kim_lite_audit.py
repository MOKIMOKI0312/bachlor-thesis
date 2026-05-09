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
                "signed_valve_violation_count": 0,
                "mode_integrality": "fixed",
                "mode_fractionality_max": 0.0,
                "mode_fractionality_mean": 0.0,
                "mode_fractionality_count": 0,
                "mode_fractionality_hours": 0.0,
                "TES_discharge_during_cp_kwh_th": 0.0,
                "TES_charge_during_valley_kwh_th": 0.0,
                "grid_reduction_during_cp_kwh": 0.0,
                "cp_hours": 0.0,
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
                "signed_valve_violation_count": 0,
                "mode_integrality": "fixed",
                "mode_fractionality_max": 0.0,
                "mode_fractionality_mean": 0.0,
                "mode_fractionality_count": 0,
                "mode_fractionality_hours": 0.0,
                "TES_discharge_during_cp_kwh_th": 0.0,
                "TES_charge_during_valley_kwh_th": 0.0,
                "grid_reduction_during_cp_kwh": 0.0,
                "cp_hours": 0.0,
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
                "controller": "paper_like_mpc_tes_relaxed",
                "solver_status": "optimal",
                "mode_integrality": "strict",
                "strict_success": True,
                "fallback_reason": "",
                "mode_fractionality_max": 0.25,
                "mode_fractionality_mean": 0.01,
                "mode_fractionality_count": 1,
                "mode_fractionality_hours": 0.25,
                "cap_ratio": 0.99,
                "peak_cap_kw": 100.0,
                "peak_grid_kw": 100.0,
                "peak_slack_max_kw": 0.0,
                "peak_slack_kwh": 0.0,
                "energy_cost": 1.0,
                "peak_slack_penalty_cost": 0.0,
                "objective_cost": 1.0,
                "peak_cap_success_flag": True,
                "TES_peak_cap_help_kwh": 0.0,
                "TES_peak_cap_help_max_kw": 0.0,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "signed_valve_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.5,
            }
        ]
    ).to_csv(phase_d / "summary.csv", index=False)
    issues = audit_root(tmp_path)
    assert any("strict mode fractionality" in issue for issue in issues)


def test_audit_flags_mainline_signed_valve_violation(tmp_path):
    phase_b = tmp_path / "phase_b_attribution"
    phase_b.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "controller": "paper_like_mpc_tes_relaxed",
                "solver_status": "optimal",
                "soc_final": 0.5,
                "terminal_soc_abs_error": 0.0,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.5,
                "signed_valve_violation_count": 2,
                "mode_integrality": "relaxed",
                "mode_fractionality_max": 0.0,
                "mode_fractionality_mean": 0.0,
                "mode_fractionality_count": 0,
                "mode_fractionality_hours": 0.0,
                "TES_discharge_during_cp_kwh_th": 0.0,
                "TES_charge_during_valley_kwh_th": 0.0,
                "grid_reduction_during_cp_kwh": 0.0,
                "cp_hours": 0.0,
            },
            {
                "controller": "storage_priority_neutral_tes",
                "solver_status": "storage_priority_neutral",
                "soc_final": 0.5,
                "terminal_soc_abs_error": 0.0,
                "soc_violation_count": 0,
                "grid_balance_violation_count": 0,
                "soc_min": 0.5,
                "soc_max": 0.5,
                "signed_valve_violation_count": 0,
                "mode_integrality": "fixed",
                "mode_fractionality_max": 0.0,
                "mode_fractionality_mean": 0.0,
                "mode_fractionality_count": 0,
                "mode_fractionality_hours": 0.0,
                "TES_discharge_during_cp_kwh_th": 0.0,
                "TES_charge_during_valley_kwh_th": 0.0,
                "grid_reduction_during_cp_kwh": 0.0,
                "cp_hours": 0.0,
            },
        ]
    ).to_csv(phase_b / "summary.csv", index=False)
    pd.DataFrame(
        [
            {"metric": "RBC_gap_neutral", "value": 1.0},
            {"metric": "RBC_gap_non_neutral", "value": 2.0},
        ]
    ).to_csv(phase_b / "attribution_table.csv", index=False)
    issues = audit_root(tmp_path)
    assert any("signed valve violation" in issue for issue in issues)
