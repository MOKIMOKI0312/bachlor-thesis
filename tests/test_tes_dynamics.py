import pytest

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.core.tes_model import TESModel, TESParams


def test_tes_charge_then_discharge_moves_soc_in_expected_directions():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    model = TESModel(TESParams.from_config(cfg["tes"]), cfg["time"]["dt_hours"])
    soc0 = 0.5
    charged = model.next_soc(soc0, q_ch_tes_kw_th=1000.0, q_dis_tes_kw_th=0.0)
    discharged = model.next_soc(charged, q_ch_tes_kw_th=0.0, q_dis_tes_kw_th=1000.0)
    assert charged > soc0
    assert discharged < charged


def test_tes_rejects_simultaneous_charge_and_discharge():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    model = TESModel(TESParams.from_config(cfg["tes"]), cfg["time"]["dt_hours"])
    with pytest.raises(ValueError, match="cannot charge and discharge"):
        model.next_soc(0.5, q_ch_tes_kw_th=1.0, q_dis_tes_kw_th=1.0)
