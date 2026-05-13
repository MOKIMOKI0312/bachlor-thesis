"""Shared schemas for Phase 3 PV-TES sizing runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Phase3Scenario:
    """One Phase 3 capacity and critical-peak scenario."""

    scenario_id: str
    location_id: str
    pv_capacity_mwp: float
    tes_capacity_mwh_th: float
    critical_peak_uplift: float
    critical_peak_window_set: str
    controller: str
    run_dir: Path
    status: str = "pending"

    def to_manifest_row(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "location_id": self.location_id,
            "pv_capacity_mwp": self.pv_capacity_mwp,
            "tes_capacity_mwh_th": self.tes_capacity_mwh_th,
            "critical_peak_uplift": self.critical_peak_uplift,
            "critical_peak_window_set": self.critical_peak_window_set,
            "controller": self.controller,
            "run_dir": str(self.run_dir),
            "status": self.status,
        }


def make_scenario_id(location_id: str, pv_capacity_mwp: float, tes_capacity_mwh_th: float, uplift: float) -> str:
    """Return the stable Phase 3 scenario id required by the task spec."""

    pv_text = _capacity_text(pv_capacity_mwp)
    tes_text = _capacity_text(tes_capacity_mwh_th)
    uplift_pct = int(round(float(uplift) * 100.0))
    return f"phase3_{location_id}_pv{pv_text}mwp_tes{tes_text}mwh_cp{uplift_pct:02d}"


def _capacity_text(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return ("%g" % value).replace(".", "p")
