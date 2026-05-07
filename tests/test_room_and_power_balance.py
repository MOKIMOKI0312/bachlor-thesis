from mpc_v2.core.plant import PlantParams, chiller_power_kw, grid_and_spill_kw, next_room_temp_c


def test_grid_and_spill_balance_uses_net_load_sign():
    assert grid_and_spill_kw(100.0, 20.0, 50.0) == (70.0, 0.0)
    assert grid_and_spill_kw(100.0, 20.0, 150.0) == (0.0, 30.0)


def test_chiller_power_uses_positive_cop():
    plant = PlantParams(cop=5.0, cooling_load_ratio=0.12, room_initial_temp_c=24.0, room_drift_per_h=0.02)
    assert chiller_power_kw(1000.0, plant) == 200.0


def test_room_proxy_moves_slowly_toward_outdoor_temperature():
    plant = PlantParams(cop=5.0, cooling_load_ratio=0.12, room_initial_temp_c=24.0, room_drift_per_h=0.02)
    assert next_room_temp_c(24.0, 34.0, plant, 0.25) > 24.0
