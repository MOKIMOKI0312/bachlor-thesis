## Migration Bundle

This folder contains the minimal runnable source content for migrating the AI-Data-Center-Analysis project into another codebase.

Included folders:
- `Code/`: paper-level training, evaluation, and optimization entry scripts
- `Data/`: weather, workload traces, building models, grid data, and author-provided pretrained models
- `sinergym/`: local environment definitions and EnergyPlus bridge code used by the project
- `tools/`: local helper scripts for evaluation, training probes, checkpoint evaluation, and job monitoring

Included file:
- `README.md`: original project readme

Not included:
- `EnergyPlus-23.1.0/`: local runtime installation; reinstall or copy separately if you want the bundle to run standalone on another machine
- `Eplus-env-*` folders: generated training/evaluation outputs only
- `training_jobs/`: background job manifests and logs only

Recommended migration target:
- Copy this bundle into the new project under a dedicated subfolder, for example `vendor/ai_data_center_analysis/`
- Preserve the relative structure of `Code/`, `Data/`, `sinergym/`, and `tools/`

Runtime note:
- The project expects EnergyPlus 23.1.0 plus the local `sinergym/` package on `PYTHONPATH`
- If you also want the exact local runnable setup, copy or reinstall EnergyPlus and recreate the Python environment
