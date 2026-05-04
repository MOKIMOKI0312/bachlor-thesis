import math

import pytest

from mpc_v2.core.io_schemas import load_yaml
from mpc_v2.core.tes_model import TESModel, TESParams


def test_tes_charge_discharge_and_loss_dynamics():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    params = TESParams.from_config(cfg["tes"])
    model = TESModel(params, dt_h=0.25)
    soc0 = 0.5
    charged = model.next_soc(soc0, q_ch_kw=1000.0, q_dis_kw=0.0)
    idle = model.next_soc(soc0, q_ch_kw=0.0, q_dis_kw=0.0)
    discharged = model.next_soc(soc0, q_ch_kw=0.0, q_dis_kw=1000.0)
    assert charged > idle
    assert discharged < idle
    assert idle < soc0


@pytest.mark.parametrize(
    ("soc", "q_ch_kw", "q_dis_kw"),
    [
        (math.nan, 0.0, 0.0),
        (math.inf, 0.0, 0.0),
        (0.5, math.nan, 0.0),
        (0.5, math.inf, 0.0),
        (0.5, 0.0, math.nan),
        (0.5, 0.0, math.inf),
    ],
)
def test_tes_next_soc_rejects_nan_and_inf_inputs(soc, q_ch_kw, q_dis_kw):
    cfg = load_yaml("mpc_v2/config/base.yaml")
    params = TESParams.from_config(cfg["tes"])
    model = TESModel(params, dt_h=0.25)
    with pytest.raises(ValueError, match="finite"):
        model.next_soc(soc, q_ch_kw=q_ch_kw, q_dis_kw=q_dis_kw)


def test_tes_model_rejects_nonfinite_dt_and_params():
    cfg = load_yaml("mpc_v2/config/base.yaml")
    params = TESParams.from_config(cfg["tes"])
    with pytest.raises(ValueError, match="dt_h must be finite"):
        TESModel(params, dt_h=math.nan)
    bad_params = TESParams(**{**params.__dict__, "effective_capacity_kwh": math.inf})
    with pytest.raises(ValueError, match="effective_capacity_kwh must be finite"):
        TESModel(bad_params, dt_h=0.25)
