import json

import pytest

from mpc_v2.phase3_sizing.energyplus_online import (
    tes_capacity_to_tank_volume_m3,
    tes_power_to_flow_kg_s,
    write_scenario_model,
)


def test_tes_capacity_to_tank_volume_uses_water_delta_t_formula():
    volume = tes_capacity_to_tank_volume_m3(18)
    assert volume == pytest.approx(18_000 / (1.163 * (12.0 - 6.67)))


def test_tes_power_to_flow_matches_fixed_power_delta_t():
    flow = tes_power_to_flow_kg_s(4500)
    assert flow == pytest.approx(4500 / (4.186 * (12.0 - 6.67)))


def test_write_scenario_model_updates_tank_and_ems_flow(tmp_path):
    model = {
        "ThermalStorage:ChilledWater:Mixed": {
            "Chilled Water Tank": {
                "tank_volume": 1400,
                "nominal_cooling_capacity": 9767442,
                "tank_recovery_time": 4,
            }
        },
        "EnergyManagementSystem:Program": {
            "P_5": {
                "lines": [
                    {"program_line": "SET Max_Flow = 389.0"},
                    {"program_line": "SET Flow = @Abs TES_Signal * Max_Flow"},
                ]
            },
            "P_8": {"lines": [{"program_line": "SET Flow_Now = @Abs TES_Signal_Now * 389.0"}]},
        },
    }
    src = tmp_path / "base.epJSON"
    dst = tmp_path / "scenario.epJSON"
    src.write_text(json.dumps(model), encoding="utf-8")
    write_scenario_model(src, dst, tes_capacity_mwh_th=18, q_abs_max_kw_th=4500)
    out = json.loads(dst.read_text(encoding="utf-8"))
    tank = out["ThermalStorage:ChilledWater:Mixed"]["Chilled Water Tank"]
    assert tank["tank_volume"] > 1400
    assert tank["nominal_cooling_capacity"] == 4_500_000
    program_text = json.dumps(out["EnergyManagementSystem:Program"])
    assert "389.0" not in program_text
    assert "201." in program_text
