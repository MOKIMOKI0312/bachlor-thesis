"""Run configured closed-loop validation scenarios."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.scripts.run_closed_loop import run_closed_loop


def run_validation_matrix(
    config_path: str | Path = "mpc_v2/config/base.yaml",
    scenario_path: str | Path = "mpc_v2/config/scenario_sets.yaml",
    scenario_set: str = "thesis_core",
    sensitivity_set: str | None = None,
    steps: int | None = None,
    output_dir: str | Path = "runs/final_mpc_validation",
    max_workers: int = 1,
    resume_existing: bool = False,
) -> Path:
    """Run each scenario in a named set and write a summary table."""

    scenario_cfg = load_yaml(scenario_path)
    if sensitivity_set:
        scenario_items = _expand_sensitivity_set(scenario_cfg["sensitivity_sets"][sensitivity_set])
    else:
        scenario_names = scenario_cfg["scenario_sets"][scenario_set]
        scenarios = scenario_cfg["scenarios"]
        scenario_items = [(scenario_id, scenarios[scenario_id]) for scenario_id in scenario_names]
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    derived_peak_refs: dict[str, float] = {}
    resolved_items: list[tuple[str, dict]] = []
    for scenario_id, scenario in scenario_items:
        scenario = dict(scenario)
        source_id = scenario.get("peak_cap_reference_source")
        if source_id and scenario.get("peak_cap_reference_kw") in (None, ""):
            if source_id not in derived_peak_refs:
                if source_id not in scenarios:
                    raise KeyError(f"peak cap reference scenario not found: {source_id}")
                ref_dir = _run_one_scenario(
                    config_path=config_path,
                    root=root,
                    scenario_id=str(source_id),
                    scenario=dict(scenarios[source_id]),
                    steps=steps,
                    resume_existing=resume_existing,
                )
                ref_summary = json.loads((ref_dir / "episode_summary.json").read_text(encoding="utf-8"))
                derived_peak_refs[source_id] = float(ref_summary["peak_grid_kw"])
            scenario["peak_cap_reference_kw"] = derived_peak_refs[source_id]
        resolved_items.append((scenario_id, scenario))

    rows = []
    run_dirs: list[Path]
    if max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    _run_one_scenario,
                    config_path,
                    root,
                    scenario_id,
                    scenario,
                    steps,
                    resume_existing,
                )
                for scenario_id, scenario in resolved_items
            ]
            run_dirs = [future.result() for future in futures]
    else:
        run_dirs = [
            _run_one_scenario(
                config_path=config_path,
                root=root,
                scenario_id=scenario_id,
                scenario=scenario,
                steps=steps,
                resume_existing=resume_existing,
            )
            for scenario_id, scenario in resolved_items
        ]

    for (scenario_id, scenario), run_dir in zip(resolved_items, run_dirs):
        summary = json.loads((run_dir / "episode_summary.json").read_text(encoding="utf-8"))
        summary["run_dir"] = str(run_dir)
        source_id = scenario.get("peak_cap_reference_source")
        if source_id:
            summary["peak_cap_reference_source"] = str(source_id)
            summary["peak_cap_reference_kw"] = float(scenario["peak_cap_reference_kw"])
        rows.append(summary)
    frame = pd.DataFrame(rows)
    frame.to_csv(root / "validation_summary.csv", index=False)
    (root / "validation_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return root


def _run_one_scenario(
    config_path: str | Path,
    root: Path,
    scenario_id: str,
    scenario: dict,
    steps: int | None,
    resume_existing: bool = False,
) -> Path:
    if resume_existing:
        existing = root / scenario_id / "episode_summary.json"
        if existing.exists():
            return existing.parent
    return run_closed_loop(
        config_path=config_path,
        case_id=scenario_id,
        steps=int(steps if steps is not None else scenario.get("closed_loop_steps", 0)) or None,
        output_root=root,
        pv_error_sigma=float(scenario.get("pv_error_sigma", 0.0)),
        controller_mode=str(scenario.get("controller_type", "mpc")),
        tariff_multiplier=float(scenario.get("tariff_multiplier", 1.0)),
        outdoor_offset_c=float(scenario.get("outdoor_offset_c", 0.0)),
        pv_scale=float(scenario.get("pv_scale", 1.0)),
        demand_charge_rate=(
            float(scenario["demand_charge_rate"])
            if "demand_charge_rate" in scenario
            else float(scenario["demand_charge_currency_per_kw_day"])
            if "demand_charge_currency_per_kw_day" in scenario
            else None
        ),
        demand_charge_basis=scenario.get("demand_charge_basis"),
        demand_charge_multiplier=float(scenario.get("demand_charge_multiplier", 1.0)),
        horizon_steps_override=(int(scenario["horizon_steps"]) if "horizon_steps" in scenario else None),
        w_terminal=(float(scenario["w_terminal"]) if "w_terminal" in scenario else None),
        w_spill=(float(scenario["w_spill"]) if "w_spill" in scenario else None),
        w_cycle=(float(scenario["w_cycle"]) if "w_cycle" in scenario else None),
        w_peak_slack=(float(scenario["w_peak_slack"]) if "w_peak_slack" in scenario else None),
        soc_target=(float(scenario["soc_target"]) if "soc_target" in scenario else None),
        initial_soc=(float(scenario["initial_soc"]) if "initial_soc" in scenario else None),
        peak_cap_kw=(
            float(scenario["peak_cap_kw"])
            if scenario.get("peak_cap_kw") not in (None, "")
            else None
        ),
        peak_cap_ratio=(float(scenario["peak_cap_ratio"]) if "peak_cap_ratio" in scenario else None),
        peak_cap_reference_kw=(
            float(scenario["peak_cap_reference_kw"]) if scenario.get("peak_cap_reference_kw") not in (None, "") else None
        ),
        tariff_template=scenario.get("tariff_template"),
        tariff_gamma=(float(scenario["tariff_gamma"]) if "tariff_gamma" in scenario else None),
        cp_uplift=(float(scenario["cp_uplift"]) if "cp_uplift" in scenario else None),
        float_share=(float(scenario["float_share"]) if "float_share" in scenario else None),
        dr_enabled=(bool(scenario["dr_enabled"]) if "dr_enabled" in scenario else None),
        dr_event_type=scenario.get("dr_event_type"),
        dr_reduction_frac=(float(scenario["dr_reduction_frac"]) if "dr_reduction_frac" in scenario else None),
        dr_start_hour=(float(scenario["dr_start_hour"]) if "dr_start_hour" in scenario else None),
        dr_duration_hours=(float(scenario["dr_duration_hours"]) if "dr_duration_hours" in scenario else None),
        dr_event_day_index=(int(scenario["dr_event_day_index"]) if "dr_event_day_index" in scenario else None),
        dr_event_start_timestamp=scenario.get("dr_event_start_timestamp"),
        dr_baseline_kw=(float(scenario["dr_baseline_kw"]) if "dr_baseline_kw" in scenario else None),
        dr_compensation_cny_per_kwh=(
            float(scenario["dr_compensation_cny_per_kwh"]) if "dr_compensation_cny_per_kwh" in scenario else None
        ),
    )


def _expand_sensitivity_set(spec: dict) -> list[tuple[str, dict]]:
    base = dict(spec.get("base", {}))
    matrix = spec.get("matrix", {})
    if not matrix:
        return [(str(spec.get("case_id", "sensitivity_case")), base)]
    keys = list(matrix)
    rows = []
    for values in itertools.product(*(matrix[key] for key in keys)):
        scenario = dict(base)
        scenario.update(dict(zip(keys, values)))
        suffix = "_".join(f"{key}-{_slug(value)}" for key, value in zip(keys, values))
        prefix = str(spec.get("case_prefix", "sensitivity"))
        rows.append((f"{prefix}_{suffix}", scenario))
    return rows


def _slug(value) -> str:
    return str(value).replace(".", "p").replace("-", "m")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="mpc_v2/config/base.yaml")
    parser.add_argument("--scenarios", default="mpc_v2/config/scenario_sets.yaml")
    parser.add_argument("--scenario-set", default="thesis_core")
    parser.add_argument("--sensitivity-set", default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--output-dir", default="runs/final_mpc_validation")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args()
    print(
        run_validation_matrix(
            config_path=args.config,
            scenario_path=args.scenarios,
            scenario_set=args.scenario_set,
            sensitivity_set=args.sensitivity_set,
            steps=args.steps,
            output_dir=args.output_dir,
            max_workers=args.max_workers,
            resume_existing=args.resume_existing,
        )
    )


if __name__ == "__main__":
    main()
