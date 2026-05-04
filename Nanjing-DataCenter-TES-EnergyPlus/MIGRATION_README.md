# Minimal Nanjing EnergyPlus Package

This folder intentionally no longer carries the historical RL/MPC experiment
workspace. It is a clean starting point containing only:

- one TES-enabled EnergyPlus data center model,
- one Nanjing EPW weather file,
- one Jiangsu TOU price CSV,
- one Nanjing PV forecast CSV,
- one lightweight EnergyPlus runner.

EnergyPlus itself is not vendored here. Install EnergyPlus 23.1 separately or
pass its executable path to `run_energyplus_nanjing.ps1`.
