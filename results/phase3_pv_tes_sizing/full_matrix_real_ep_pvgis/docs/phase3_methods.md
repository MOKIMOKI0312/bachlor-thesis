# Phase 3 Methods

This phase evaluates a technical recommended capacity range, not an economic optimum.

- PV capacity scan: 0, 10, 20, 40, and 60 MWp.
- TES capacity scan: 0, 9, 18, 36, and 72 MWh_th.
- Critical peak uplift: explicit 16:00 <= hour < 20:00 window with delta = 0.2 in the main matrix.
- Data boundary: real EPW weather drives annual EnergyPlus no-control baseline profiles; PV uses PVGIS 20 MWp profiles; price uses the Jiangsu 2025 TOU curve.
- Controller boundary: Kim-lite relaxed MPC-style dispatch over EnergyPlus-derived annual load/weather profiles with signed TES ramping and fixed TES power.
- Recommendation rule: choose the smallest PV-TES pair meeting 90% of the maximum CP suppression and peak-reduction effects while retaining PV self-consumption and SOC acceptability.
- Limitation: technical recommendation only, no CAPEX, no LCOE, no NPV, and no economic optimum.
