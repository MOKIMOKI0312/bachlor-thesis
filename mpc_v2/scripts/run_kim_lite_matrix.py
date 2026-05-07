"""Run Kim-lite Phase A-F matrices and write thesis-ready artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from mpc_v2.kim_lite.config import load_config, load_yaml_mapping
from mpc_v2.kim_lite.controller import run_controller_case
from mpc_v2.kim_lite.metrics import attribution_table
from mpc_v2.kim_lite.model import build_inputs
from mpc_v2.kim_lite.plotting import plot_representative_dispatch, plot_summary_bar, plot_xy


def run_matrix(
    phase: str = "all",
    config_path: str = "mpc_v2/config/kim_lite_base.yaml",
    scenario_path: str = "mpc_v2/config/kim_lite_scenarios.yaml",
    output_root: str | None = None,
) -> Path:
    cfg = load_config(config_path)
    scenarios = load_yaml_mapping(scenario_path)
    root = Path(output_root or cfg.output_root)
    root.mkdir(parents=True, exist_ok=True)
    selected = ["phase_a", "phase_b_attribution", "phase_c_tou", "phase_d_peakcap", "phase_e_signed_valve"]
    if phase != "all":
        selected = [phase]
    for item in selected:
        if item == "phase_a":
            _run_phase_a(cfg, scenarios[item], root)
        elif item == "phase_b_attribution":
            _run_phase_b(cfg, scenarios[item], root)
        elif item == "phase_c_tou":
            _run_phase_c(cfg, scenarios[item], root)
        elif item == "phase_d_peakcap":
            _run_phase_d(cfg, scenarios[item], root)
        elif item == "phase_e_signed_valve":
            _run_phase_e(cfg, scenarios[item], root)
        else:
            raise ValueError(f"unknown Kim-lite phase: {item}")
    _write_storyboard(root)
    return root


def _run_phase_a(cfg, phase_cfg, root: Path) -> None:
    phase_dir = root / "phase_a"
    inputs = build_inputs(cfg, int(phase_cfg["steps"]))
    rows = []
    for controller in phase_cfg["controllers"]:
        run_dir, summary = run_controller_case(
            cfg,
            inputs,
            controller=controller,
            case_id=controller,
            output_root=phase_dir,
        )
        rows.append(summary)
        if controller == "paper_like_mpc":
            plot_representative_dispatch(run_dir / "monitor.csv", root / "figures" / "fig_phase_a_dispatch.png", "Phase A paper-like MPC dispatch")
    pd.DataFrame(rows).to_csv(phase_dir / "summary.csv", index=False)


def _run_phase_b(cfg, phase_cfg, root: Path) -> None:
    phase_dir = root / "phase_b_attribution"
    inputs = build_inputs(cfg, int(phase_cfg["steps"]))
    rows = []
    for controller in phase_cfg["controllers"]:
        _, summary = run_controller_case(cfg, inputs, controller, controller, phase_dir)
        rows.append(summary)
    summary = pd.DataFrame(rows)
    summary.to_csv(phase_dir / "summary.csv", index=False)
    table = attribution_table(summary)
    table.to_csv(phase_dir / "attribution_table.csv", index=False)
    (phase_dir / "attribution_table.md").write_text(table.to_markdown(index=False), encoding="utf-8")
    plot_summary_bar(phase_dir / "summary.csv", root / "figures" / "fig_phase_b_cost_by_controller.png", "controller", "cost_total", "Phase B controller cost")


def _run_phase_c(cfg, phase_cfg, root: Path) -> None:
    phase_dir = root / "phase_c_tou"
    rows = []
    for scenario in phase_cfg["scenarios"]:
        inputs = build_inputs(
            cfg,
            int(phase_cfg["steps"]),
            tariff_gamma=float(scenario["spread_gamma"]),
            cp_uplift=float(scenario["critical_peak_uplift"]),
        )
        for controller in phase_cfg["controllers"]:
            case_id = f"{scenario['name']}_{controller}"
            run_dir, summary = run_controller_case(cfg, inputs, controller, case_id, phase_dir)
            summary["scenario"] = scenario["name"]
            summary["spread_gamma"] = float(scenario["spread_gamma"])
            summary["critical_peak_uplift"] = float(scenario["critical_peak_uplift"])
            rows.append(summary)
            if scenario["name"] == "base_cp20" and controller == "paper_like_mpc_tes":
                plot_representative_dispatch(run_dir / "monitor.csv", root / "figures" / "fig_tou_representative_day_dispatch.png", "TOU representative dispatch")
    rep = next(s for s in phase_cfg["scenarios"] if s["name"] == "base_cp20")
    inputs = build_inputs(cfg, int(phase_cfg["steps"]), tariff_gamma=float(rep["spread_gamma"]), cp_uplift=float(rep["critical_peak_uplift"]))
    for controller in phase_cfg["representative_controllers"]:
        case_id = f"representative_{controller}"
        _, summary = run_controller_case(cfg, inputs, controller, case_id, phase_dir)
        summary["scenario"] = "representative_base_cp20"
        summary["spread_gamma"] = float(rep["spread_gamma"])
        summary["critical_peak_uplift"] = float(rep["critical_peak_uplift"])
        rows.append(summary)
    summary = pd.DataFrame(rows)
    summary.to_csv(phase_dir / "summary.csv", index=False)
    plot_xy(phase_dir / "summary.csv", root / "figures" / "fig_tou_cost_vs_gamma.png", "spread_gamma", "cost_total", "TOU cost vs gamma")
    plot_xy(phase_dir / "summary.csv", root / "figures" / "fig_tou_arbitrage_spread_vs_gamma.png", "spread_gamma", "TES_arbitrage_spread", "TOU arbitrage spread vs gamma")


def _run_phase_d(cfg, phase_cfg, root: Path) -> None:
    phase_dir = root / "phase_d_peakcap"
    base_inputs = build_inputs(cfg, int(phase_cfg["steps"]))
    _, base_summary = run_controller_case(cfg, base_inputs, "mpc_no_tes", "mpc_no_tes_no_cap_reference", phase_dir)
    reference_peak = float(base_summary["peak_grid_kw"])
    rows = []
    for ratio in phase_cfg["cap_ratios"]:
        cap = reference_peak * float(ratio)
        for controller in phase_cfg["controllers"]:
            case_id = f"cap_{str(ratio).replace('.', 'p')}_{controller}"
            run_dir, summary = run_controller_case(cfg, base_inputs, controller, case_id, phase_dir, peak_cap_kw=cap)
            summary["cap_ratio"] = float(ratio)
            summary["peak_cap_kw"] = cap
            summary["peak_reduction_kw"] = reference_peak - float(summary["peak_grid_kw"])
            summary["cost_increase_vs_no_cap"] = float(summary["cost_total"]) - float(base_summary["cost_total"])
            rows.append(summary)
            if float(ratio) == 0.97 and controller == "paper_like_mpc_tes":
                plot_representative_dispatch(run_dir / "monitor.csv", root / "figures" / "fig_peak_window_dispatch.png", "Peak-cap representative dispatch")
    summary = pd.DataFrame(rows)
    summary.to_csv(phase_dir / "summary.csv", index=False)
    plot_xy(phase_dir / "summary.csv", root / "figures" / "fig_peak_reduction_cost_tradeoff.png", "peak_reduction_kw", "cost_increase_vs_no_cap", "Peak reduction cost tradeoff")


def _run_phase_e(cfg, phase_cfg, root: Path) -> None:
    phase_dir = root / "phase_e_signed_valve"
    inputs = build_inputs(cfg, int(phase_cfg["steps"]))
    rows = []
    for controller in phase_cfg["controllers"]:
        run_dir, summary = run_controller_case(
            cfg,
            inputs,
            controller,
            controller,
            phase_dir,
            enforce_signed_ramp=bool(phase_cfg.get("enforce_signed_ramp", True)),
        )
        rows.append(summary)
        plot_representative_dispatch(run_dir / "monitor.csv", root / "figures" / "fig_signed_valve_dispatch.png", "Signed valve dispatch")
    pd.DataFrame(rows).to_csv(phase_dir / "summary.csv", index=False)


def _write_storyboard(root: Path) -> None:
    storyboard = Path("docs/ppt_storyboard_kim_lite_20260507.md")
    storyboard.write_text(
        "\n".join(
            [
                "# Kim-lite Thesis PPT Storyboard",
                "",
                "PPT_PATH was not provided during this run, so no PPTX file was modified.",
                "",
                "1. Research question: marginal value of data-center cold-plant TES",
                "2. Reference structure: Kim et al. 2022 cold-plant TES MPC skeleton",
                "3. Why the prior MPC path was narrowed",
                "4. Paper-like boundary: Q_load, P_nonplant, PV, TES, plant mode",
                "5. MILP variables and equations",
                "6. Baselines: storage priority vs MPC",
                "7. Attribution: direct_no_tes / mpc_no_tes / storage_priority / mpc_tes",
                "8. China TOU and critical peak scenarios",
                "9. Peak-cap scenario",
                "10. Representative dispatch: price + SOC + Q_tes_net + grid",
                "11. Results: TES value and boundaries",
                "12. Conclusion and future work",
                "",
                f"Figure assets: `{root / 'figures'}`",
            ]
        ),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", default="all")
    parser.add_argument("--config", default="mpc_v2/config/kim_lite_base.yaml")
    parser.add_argument("--scenarios", default="mpc_v2/config/kim_lite_scenarios.yaml")
    parser.add_argument("--output-root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = run_matrix(args.phase, args.config, args.scenarios, args.output_root)
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
