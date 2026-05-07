"""Generate the full China TOU/DR monthly scenario matrix."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


WEATHERS = {
    "hot": 4.0,
    "mild": -4.0,
}
CONTROLLERS = {
    "direct_no_tes": "no_tes",
    "mpc_no_tes": "mpc_no_tes",
    "rbc_tes": "rbc",
    "mpc_tes": "mpc",
}
NOTICE = {
    "day_ahead": {"duration_hours": 2.0, "compensation_cny_per_kwh": 3.0},
    "fast": {"duration_hours": 1.0, "compensation_cny_per_kwh": 4.2},
    "realtime": {"duration_hours": 0.5, "compensation_cny_per_kwh": 4.8},
}


def generate_china_matrix(profile: str = "month") -> dict[str, Any]:
    """Return a scenario YAML mapping for pilot or month runs."""

    if profile not in {"pilot", "month", "pilot_soc_neutral", "month_soc_neutral"}:
        raise ValueError("profile must be pilot, month, pilot_soc_neutral, or month_soc_neutral")
    is_pilot = profile.startswith("pilot")
    soc_neutral = profile.endswith("soc_neutral")
    steps = 96 if is_pilot else 2880
    event_day_index = 0 if is_pilot else 19
    scenario_sets: dict[str, list[str]] = {
        "china_tou_screening_full": [],
        "china_tou_full_compare_full": [],
        "china_peakcap_full": [],
        "china_dr_event_full": [],
        "china_robustness_full": [],
        "china_all_full": [],
    }
    scenarios: dict[str, dict[str, Any]] = {}

    def add(set_name: str, scenario_id: str, spec: dict[str, Any]) -> None:
        scenarios[scenario_id] = _with_defaults(spec, steps, soc_neutral=soc_neutral)
        scenario_sets[set_name].append(scenario_id)
        scenario_sets["china_all_full"].append(scenario_id)

    for gamma in [0, 0.5, 1.0, 1.5, 2.0]:
        for cp in [0.0, 0.2]:
            for weather, offset in WEATHERS.items():
                for label, controller in {"mpc_no_tes": "mpc_no_tes", "mpc_tes": "mpc"}.items():
                    add(
                        "china_tou_screening_full",
                        f"tou_screen_g{_slug(gamma)}_cp{_slug(cp)}_{weather}_{label}",
                        {
                            "controller_type": controller,
                            "outdoor_offset_c": offset,
                            "tariff_template": "beijing",
                            "tariff_gamma": gamma,
                            "cp_uplift": cp,
                            "float_share": 0.8,
                        },
                    )

    full_templates = {
        "flat": {"tariff_gamma": 0.0, "cp_uplift": 0.0},
        "base": {"tariff_gamma": 1.0, "cp_uplift": 0.0},
        "base_cp20": {"tariff_gamma": 1.0, "cp_uplift": 0.2},
        "highspread_cp20": {"tariff_gamma": 2.0, "cp_uplift": 0.2},
    }
    for template_name, tariff in full_templates.items():
        for weather, offset in WEATHERS.items():
            for label, controller in CONTROLLERS.items():
                add(
                    "china_tou_full_compare_full",
                    f"tou_full_{template_name}_{weather}_{label}",
                    {
                        "controller_type": controller,
                        "outdoor_offset_c": offset,
                        "tariff_template": "beijing",
                        "float_share": 0.8,
                        **tariff,
                    },
                )

    scenarios["peakcap_reference_hot_mpc_no_tes"] = _with_defaults(
        {
            "controller_type": "mpc_no_tes",
            "outdoor_offset_c": WEATHERS["hot"],
            "tariff_template": "beijing",
            "tariff_gamma": 1.0,
            "cp_uplift": 0.2,
            "float_share": 0.8,
        },
        steps,
        soc_neutral=soc_neutral,
    )
    for ratio in [1.0, 0.99, 0.97, 0.95]:
        for eta in [5, 10, 20]:
            for label, controller in {"mpc_no_tes": "mpc_no_tes", "mpc_tes": "mpc"}.items():
                add(
                    "china_peakcap_full",
                    f"peakcap_r{_slug(ratio)}_eta{eta}_{label}",
                    {
                        "controller_type": controller,
                        "outdoor_offset_c": WEATHERS["hot"],
                        "tariff_template": "beijing",
                        "tariff_gamma": 1.0,
                        "cp_uplift": 0.2,
                        "float_share": 0.8,
                        "peak_cap_ratio": ratio,
                        "peak_cap_reference_source": "peakcap_reference_hot_mpc_no_tes",
                        "w_peak_slack": float(eta * 1000),
                    },
                )

    for notice, notice_spec in NOTICE.items():
        for reduction in [0.05, 0.10, 0.15]:
            for label, controller in {"mpc_no_tes": "mpc_no_tes", "mpc_tes": "mpc"}.items():
                add(
                    "china_dr_event_full",
                    f"dr_{notice}_r{_slug(reduction)}_{label}",
                    {
                        "controller_type": controller,
                        "outdoor_offset_c": WEATHERS["hot"],
                        "tariff_template": "beijing",
                        "tariff_gamma": 1.0,
                        "cp_uplift": 0.2,
                        "float_share": 0.8,
                        "dr_enabled": True,
                        "dr_event_type": notice,
                        "dr_reduction_frac": reduction,
                        "dr_start_hour": 18.0,
                        "dr_event_day_index": event_day_index,
                        "dr_baseline_kw": 19000.0,
                        **notice_spec,
                    },
                )

    reps = {
        "base_cp20": {"tariff_gamma": 1.0, "cp_uplift": 0.2, "dr_enabled": False},
        "dr_day_ahead_10": {
            "tariff_gamma": 1.0,
            "cp_uplift": 0.2,
            "dr_enabled": True,
            "dr_event_type": "day_ahead",
            "dr_reduction_frac": 0.10,
            "dr_start_hour": 18.0,
            "dr_duration_hours": 2.0,
            "dr_event_day_index": event_day_index,
            "dr_baseline_kw": 19000.0,
            "dr_compensation_cny_per_kwh": 3.0,
        },
    }
    for rep_name, rep in reps.items():
        for soc0 in [0.2, 0.5, 0.8]:
            for label, controller in {"mpc_no_tes": "mpc_no_tes", "mpc_tes": "mpc"}.items():
                add(
                    "china_robustness_full",
                    f"robust_{rep_name}_soc{_slug(soc0)}_{label}",
                    {
                        "controller_type": controller,
                        "outdoor_offset_c": WEATHERS["hot"],
                        "tariff_template": "beijing",
                        "float_share": 0.8,
                        "initial_soc": soc0,
                        "soc_target": soc0,
                        **rep,
                    },
                )
        for horizon in [24, 48, 96]:
            for label, controller in {"mpc_no_tes": "mpc_no_tes", "mpc_tes": "mpc"}.items():
                add(
                    "china_robustness_full",
                    f"robust_{rep_name}_h{int(horizon / 4)}_{label}",
                    {
                        "controller_type": controller,
                        "outdoor_offset_c": WEATHERS["hot"],
                        "tariff_template": "beijing",
                        "float_share": 0.8,
                        "horizon_steps": horizon,
                        **rep,
                    },
                )

    return {
        "metadata": {
            "profile": profile,
            "closed_loop_steps": steps,
            "dt_minutes": 15,
            "episode_days": steps / 96,
            "event_day_index": event_day_index,
            "soc_neutral_terminal": soc_neutral,
            "expected_run_count_excluding_derived_references": len(scenario_sets["china_all_full"]),
        },
        "scenario_sets": scenario_sets,
        "scenarios": scenarios,
    }


def write_china_matrix(path: str | Path, profile: str = "month") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = generate_china_matrix(profile=profile)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _with_defaults(spec: dict[str, Any], steps: int, soc_neutral: bool = False) -> dict[str, Any]:
    merged = {
        "closed_loop_steps": steps,
        "horizon_steps": 48,
        "pv_error_sigma": 0.0,
    }
    merged.update(spec)
    if soc_neutral:
        merged.setdefault("soc_target", float(merged.get("initial_soc", 0.5)))
        merged.setdefault("w_terminal", 50000.0)
        merged.setdefault("truncate_horizon_to_episode", True)
    return merged


def _slug(value: float) -> str:
    text = f"{float(value):g}"
    return text.replace(".", "p").replace("-", "m")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=["pilot", "month", "pilot_soc_neutral", "month_soc_neutral"],
        default="month",
    )
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    output = args.output or f"mpc_v2/config/generated_china_matrix_{args.profile}.yaml"
    print(write_china_matrix(output, profile=args.profile))


if __name__ == "__main__":
    main()
