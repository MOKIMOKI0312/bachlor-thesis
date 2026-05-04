"""Compatibility adapter from EnergyPlus/Sinergym data to MPC v2 schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mpc_v2.core.io_schemas import Action, Observation, SchemaValidationError, parse_timestamp


class EPlusAdapter:
    """Map obs/info/action dictionaries without monkey-patching existing wrappers."""

    def __init__(self, dt_h: float = 0.25):
        if abs(dt_h - 0.25) > 1e-9:
            raise ValueError(f"EPlusAdapter requires dt_h=0.25, got {dt_h}")
        self.dt_h = dt_h
        self._last_read_timestamp: datetime | None = None
        self._last_write_timestamp: datetime | None = None

    def observation_from_mapping(self, obs: dict[str, Any], info: dict[str, Any] | None = None) -> Observation:
        """Convert a loose obs/info mapping to the strict v2 observation schema."""

        merged = dict(info or {})
        merged.update(obs)
        timestamp = parse_timestamp(_first_present(merged, ["timestamp", "time", "datetime"]))
        observation = Observation(
            timestamp=timestamp,
            dt_h=float(merged.get("dt_h", self.dt_h)),
            air_temperature_C=float(_first_present(merged, ["air_temperature_C", "air_temperature", "zone_air_temperature"])),
            outdoor_drybulb_C=float(_first_present(merged, ["outdoor_drybulb_C", "outdoor_temperature", "oa_temperature"])),
            ite_power_kw=float(_first_present(merged, ["ite_power_kw", "it_power_kw", "ITE_power_kw"])),
            facility_power_kw=float(_first_present(merged, ["facility_power_kw", "Electricity:Facility", "facility_kw"])),
            tes_soc=float(_first_present(merged, ["tes_soc", "TES_SOC", "soc"])),
            tes_tank_temp_C=float(_first_present(merged, ["tes_tank_temp_C", "TES_Tank_Temperature", "tank_temperature_C"])),
            current_pv_kw=float(_first_present(merged, ["current_pv_kw", "pv_kw", "PV_power_kw"])),
            current_price_usd_per_mwh=float(_first_present(merged, ["current_price_usd_per_mwh", "price_usd_per_mwh", "tou_price"])),
            chiller_cop=float(_first_present(merged, ["chiller_cop", "COP", "chiller_COP"])),
            pue_actual=float(_first_present(merged, ["pue_actual", "PUE", "pue"])),
        )
        observation.validate()
        if self._last_read_timestamp == observation.timestamp:
            raise SchemaValidationError(f"duplicate read timestamp: {observation.timestamp}")
        self._last_read_timestamp = observation.timestamp
        return observation

    def action_to_mapping(self, action: Action, timestamp: datetime | None = None) -> dict[str, float]:
        """Convert a strict v2 action to actuator-friendly scalar values."""

        action.validate()
        if timestamp is not None:
            if self._last_write_timestamp == timestamp:
                raise SchemaValidationError(f"duplicate write timestamp: {timestamp}")
            self._last_write_timestamp = timestamp
        mapping = {
            "tes_signed_target": action.tes_signed_target,
            "tes_charge_kwth": action.tes_charge_kwth,
            "tes_discharge_kwth": action.tes_discharge_kwth,
        }
        if action.crah_supply_temp_sp_C is not None:
            mapping["crah_supply_temp_sp_C"] = action.crah_supply_temp_sp_C
        if action.chiller_lwt_sp_C is not None:
            mapping["chiller_lwt_sp_C"] = action.chiller_lwt_sp_C
        if action.ct_pump_speed_frac is not None:
            mapping["ct_pump_speed_frac"] = action.ct_pump_speed_frac
        return mapping


def _first_present(mapping: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    raise SchemaValidationError(f"missing any of fields: {names}")

