import json

import pandas as pd

from mpc_v2.scripts.run_validation_matrix import run_validation_matrix


def test_minimal_validation_matrix_runs(tmp_path):
    output = run_validation_matrix(
        matrix_path="mpc_v2/config/scenario_sets.yaml",
        output_root=tmp_path,
        config_path="mpc_v2/config/base.yaml",
    )
    summary_csv = output / "validation_summary.csv"
    summary_json = output / "validation_summary.json"
    assert summary_csv.exists()
    assert summary_json.exists()
    frame = pd.read_csv(summary_csv)
    data = json.loads(summary_json.read_text(encoding="utf-8"))
    assert set(frame["case_id"]) == {"rebuild_no_tes_24h", "rebuild_rbc_24h", "rebuild_mpc_24h"}
    assert len(data) == 3
