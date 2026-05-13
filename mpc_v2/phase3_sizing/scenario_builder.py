"""Scenario matrix construction for Phase 3 PV-TES sizing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.phase3_sizing.schema import Phase3Scenario, make_scenario_id


def load_phase3_config(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def load_locations_config(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def build_scenario_matrix(
    phase3_cfg: dict[str, Any],
    locations_cfg: dict[str, Any],
    output_root: str | Path,
    location_filter: str | None = None,
    include_stress_uplift: bool = False,
) -> list[Phase3Scenario]:
    """Build location x PV x TES x critical-peak scenarios."""

    locations = locations_cfg.get("locations", [])
    if not isinstance(locations, list) or not locations:
        raise ValueError("phase3 locations config must contain a non-empty locations list")
    if location_filter:
        allowed = {item.strip() for item in location_filter.split(",") if item.strip()}
        locations = [loc for loc in locations if str(loc.get("id")) in allowed]
        if not locations:
            raise ValueError(f"location_filter matched no locations: {location_filter}")

    pv_values = [float(v) for v in phase3_cfg["pv"]["capacities_mwp"]]
    tes_values = [float(v) for v in phase3_cfg["tes"]["capacities_mwh_th"]]
    cp_cfg = phase3_cfg["critical_peak"]
    uplift_values = [float(v) for v in cp_cfg["uplift_values"]]
    if include_stress_uplift:
        uplift_values.extend(float(v) for v in cp_cfg.get("optional_stress_uplift_values", []))
    uplift_values = sorted(set(uplift_values))
    window_set = str(cp_cfg.get("default_window_set", "evening"))
    controller = str(phase3_cfg.get("controller", {}).get("name", "paper_like_mpc_tes_relaxed"))
    root = Path(output_root)

    scenarios: list[Phase3Scenario] = []
    for location in locations:
        location_id = str(location["id"])
        for pv in pv_values:
            for tes in tes_values:
                for uplift in uplift_values:
                    scenario_id = make_scenario_id(location_id, pv, tes, uplift)
                    scenarios.append(
                        Phase3Scenario(
                            scenario_id=scenario_id,
                            location_id=location_id,
                            pv_capacity_mwp=pv,
                            tes_capacity_mwh_th=tes,
                            critical_peak_uplift=uplift,
                            critical_peak_window_set=window_set,
                            controller=controller,
                            run_dir=root / "runs" / scenario_id,
                        )
                    )
    return scenarios


def scenario_manifest_frame(scenarios: list[Phase3Scenario]) -> pd.DataFrame:
    """Return the manifest table with the task-required columns."""

    return pd.DataFrame([scenario.to_manifest_row() for scenario in scenarios])


def write_scenario_manifest(scenarios: list[Phase3Scenario], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scenario_manifest_frame(scenarios).to_csv(path, index=False)
    return path
