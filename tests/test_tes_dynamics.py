import math

import pytest

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.core.tes_model import TESModel, TESParams


def test_tes_soc_dynamics_use_thermal_power_units():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    params = TESParams.from_config(cfg["tes"])
    model = TESModel(params, dt_hours=cfg["time"]["dt_hours"])
    soc0 = 0.5
    idle = model.next_soc(soc0, q_ch_tes_kw_th=0.0, q_dis_tes_kw_th=0.0)
    charged = model.next_soc(soc0, q_ch_tes_kw_th=1000.0, q_dis_tes_kw_th=0.0)
    discharged = model.next_soc(soc0, q_ch_tes_kw_th=0.0, q_dis_tes_kw_th=1000.0)
    assert idle < soc0
    assert charged > idle
    assert discharged < idle


def test_tes_rejects_nonfinite_values():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    params = TESParams.from_config(cfg["tes"])
    model = TESModel(params, dt_hours=cfg["time"]["dt_hours"])
    with pytest.raises(ValueError, match="finite"):
        model.next_soc(math.nan, q_ch_tes_kw_th=0.0, q_dis_tes_kw_th=0.0)
