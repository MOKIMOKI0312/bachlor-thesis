"""TOU tariff templates and China-style floating/non-floating price splits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class TariffConfig:
    """Configuration for deterministic tariff transformations."""

    template: str = "jiangsu_csv"
    gamma: float = 1.0
    cp_uplift: float = 0.0
    float_share: float = 1.0

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "TariffConfig":
        config = config or {}
        params = cls(
            template=str(config.get("template", "jiangsu_csv")),
            gamma=float(config.get("gamma", 1.0)),
            cp_uplift=float(config.get("cp_uplift", config.get("cp_uplift_frac", 0.0))),
            float_share=float(config.get("float_share", 1.0)),
        )
        params.validate()
        return params

    def validate(self) -> None:
        if self.template not in {"none", "jiangsu_csv", "beijing", "guangdong_cold_storage"}:
            raise ValueError(f"unsupported tariff template: {self.template}")
        if self.gamma < 0:
            raise ValueError("tariff gamma must be non-negative")
        if self.cp_uplift < 0:
            raise ValueError("critical-peak uplift must be non-negative")
        if not 0.0 <= self.float_share <= 1.0:
            raise ValueError("tariff float_share must be in [0, 1]")


@dataclass(frozen=True)
class TariffSeries:
    """Tariff values aligned to a forecast horizon."""

    price_total: list[float]
    price_float: list[float]
    price_nonfloat: list[float]
    tou_stage: list[str]
    cp_flag: list[int]
    template: str


class TariffService:
    """Apply policy-oriented TOU transforms to a base hourly tariff series."""

    def __init__(self, config: TariffConfig | dict[str, Any] | None = None, reference_price_mean: float | None = None):
        self.config = config if isinstance(config, TariffConfig) else TariffConfig.from_config(config)
        self.reference_price_mean = None if reference_price_mean is None else float(reference_price_mean)
        if self.reference_price_mean is not None and self.reference_price_mean < 0:
            raise ValueError("reference_price_mean must be non-negative")

    def apply(
        self,
        timestamps: Sequence[datetime],
        base_price: Sequence[float],
        multiplier: float = 1.0,
    ) -> TariffSeries:
        """Return total, floating, non-floating, TOU stage, and critical-peak flags.

        The base price is interpreted as the existing all-in tariff.  The
        configured ``float_share`` splits it into a time-varying energy component
        and a fixed add-on component.  ``gamma`` only scales the floating
        component around its mean, matching the China TOU sensitivity design in
        the review report.
        """

        if len(timestamps) != len(base_price):
            raise ValueError("timestamps and base_price length mismatch")
        base = np.asarray(base_price, dtype=float) * float(multiplier)
        if np.any(~np.isfinite(base)) or np.any(base < -1e-9):
            raise ValueError("base tariff values must be finite and non-negative")

        stages = [self.stage_at(ts) for ts in timestamps]
        cp_flags = [1 if self.is_critical_peak(ts) else 0 for ts in timestamps]
        nonfloat = base * (1.0 - self.config.float_share)
        base_float = base * self.config.float_share

        if self.config.template == "guangdong_cold_storage":
            scaled_float = self._guangdong_cold_storage_float(base_float, stages, multiplier=float(multiplier))
        else:
            scaled_float = self._gamma_scaled_float(base_float, multiplier=float(multiplier))

        if self.config.cp_uplift:
            scaled_float = np.asarray(
                [
                    value * (1.0 + self.config.cp_uplift) if flag else value
                    for value, flag in zip(scaled_float, cp_flags)
                ],
                dtype=float,
            )
        scaled_float = np.maximum(0.0, scaled_float)
        total = scaled_float + nonfloat
        return TariffSeries(
            price_total=total.astype(float).tolist(),
            price_float=scaled_float.astype(float).tolist(),
            price_nonfloat=nonfloat.astype(float).tolist(),
            tou_stage=stages,
            cp_flag=cp_flags,
            template=self.config.template,
        )

    def stage_at(self, timestamp: datetime) -> str:
        """Classify a timestamp into valley/flat/peak for the selected template."""

        hour = timestamp.hour + timestamp.minute / 60.0
        if self.config.template in {"beijing", "guangdong_cold_storage"}:
            if hour >= 23.0 or hour < 7.0:
                return "valley"
            if 10.0 <= hour < 13.0 or 17.0 <= hour < 21.0:
                return "peak"
            return "flat"
        return "csv"

    def is_critical_peak(self, timestamp: datetime) -> bool:
        """Return whether Beijing-style summer critical peak pricing applies."""

        if self.config.template != "beijing":
            return False
        if timestamp.month not in {6, 7, 8}:
            return False
        hour = timestamp.hour + timestamp.minute / 60.0
        return (11.0 <= hour < 13.0) or (16.0 <= hour < 17.0)

    def _gamma_scaled_float(self, base_float: np.ndarray, multiplier: float) -> np.ndarray:
        if len(base_float) == 0:
            return base_float
        mean_float = self._reference_float_mean(base_float, multiplier)
        return mean_float + self.config.gamma * (base_float - mean_float)

    def _guangdong_cold_storage_float(
        self,
        base_float: np.ndarray,
        stages: Sequence[str],
        multiplier: float,
    ) -> np.ndarray:
        if len(base_float) == 0:
            return base_float
        mean_float = self._reference_float_mean(base_float, multiplier)
        coefficients = {"peak": 1.65, "flat": 1.0, "valley": 0.25, "csv": 1.0}
        template_float = np.asarray([mean_float * coefficients.get(stage, 1.0) for stage in stages], dtype=float)
        if self.config.gamma == 1.0:
            return template_float
        return mean_float + self.config.gamma * (template_float - mean_float)

    def _reference_float_mean(self, base_float: np.ndarray, multiplier: float) -> float:
        if self.reference_price_mean is None:
            return float(np.mean(base_float))
        return self.reference_price_mean * float(multiplier) * self.config.float_share
