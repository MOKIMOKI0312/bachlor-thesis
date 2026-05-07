"""Demand-response and peak-cap event helpers for closed-loop scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DRConfig:
    """Configuration for deterministic DR and dynamic peak-cap scenarios."""

    enabled: bool = False
    event_id: str = "dr_event"
    event_type: str = "day_ahead"
    start_hour: float = 18.0
    duration_hours: float = 2.0
    reduction_frac: float = 0.10
    baseline_kw: float | None = None
    compensation_cny_per_kwh: float = 0.0
    response_threshold: float = 0.50
    peak_cap_ratio: float | None = None
    peak_cap_reference_kw: float | None = None
    episode_start_timestamp: datetime | None = None
    event_day_index: int | None = None
    event_start_timestamp: datetime | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "DRConfig":
        config = config or {}
        enabled = bool(config.get("enabled", False))
        baseline = config.get("baseline_kw", None)
        ratio = config.get("peak_cap_ratio", None)
        reference = config.get("peak_cap_reference_kw", None)
        episode_start = config.get("episode_start_timestamp", None)
        event_day_index = config.get("event_day_index", None)
        event_start = config.get("event_start_timestamp", None)
        params = cls(
            enabled=enabled,
            event_id=str(config.get("event_id", "dr_event")),
            event_type=str(config.get("event_type", config.get("notice_type", "day_ahead"))),
            start_hour=float(config.get("start_hour", 18.0)),
            duration_hours=float(config.get("duration_hours", 2.0)),
            reduction_frac=float(config.get("reduction_frac", config.get("r_dr", 0.10))),
            baseline_kw=None if baseline in (None, "") else float(baseline),
            compensation_cny_per_kwh=float(config.get("compensation_cny_per_kwh", 0.0)),
            response_threshold=float(config.get("response_threshold", 0.50)),
            peak_cap_ratio=None if ratio in (None, "") else float(ratio),
            peak_cap_reference_kw=None if reference in (None, "") else float(reference),
            episode_start_timestamp=_parse_optional_timestamp(episode_start),
            event_day_index=None if event_day_index in (None, "") else int(event_day_index),
            event_start_timestamp=_parse_optional_timestamp(event_start),
        )
        params.validate()
        return params

    def validate(self) -> None:
        if self.event_type not in {"day_ahead", "fast", "realtime", "peak_cap"}:
            raise ValueError(f"unsupported DR event_type: {self.event_type}")
        if not 0.0 <= self.start_hour < 24.0:
            raise ValueError("DR start_hour must be in [0, 24)")
        if self.duration_hours <= 0.0 or self.duration_hours > 24.0:
            raise ValueError("DR duration_hours must be in (0, 24]")
        if not 0.0 <= self.reduction_frac <= 1.0:
            raise ValueError("DR reduction_frac must be in [0, 1]")
        if self.baseline_kw is not None and self.baseline_kw < 0.0:
            raise ValueError("DR baseline_kw must be non-negative")
        if self.compensation_cny_per_kwh < 0.0:
            raise ValueError("DR compensation must be non-negative")
        if not 0.0 <= self.response_threshold <= 1.0:
            raise ValueError("DR response_threshold must be in [0, 1]")
        if self.peak_cap_ratio is not None and not 0.0 <= self.peak_cap_ratio <= 1.0:
            raise ValueError("peak_cap_ratio must be in [0, 1]")
        if self.peak_cap_reference_kw is not None and self.peak_cap_reference_kw < 0.0:
            raise ValueError("peak_cap_reference_kw must be non-negative")
        if self.event_day_index is not None and self.event_day_index < 0:
            raise ValueError("event_day_index must be non-negative")


@dataclass(frozen=True)
class DRSeries:
    """DR fields aligned to a forecast horizon."""

    dr_flag: list[int]
    dr_notice_type: list[str]
    dr_req_kw: list[float]
    dr_baseline_kw: list[float]
    dynamic_peak_cap_kw: list[float]
    dr_event_id: list[str]
    dr_compensation_cny_per_kwh: list[float]


class DRService:
    """Build per-timestep DR metadata and dynamic grid caps."""

    def __init__(self, config: DRConfig | dict[str, Any] | None = None):
        self.config = config if isinstance(config, DRConfig) else DRConfig.from_config(config)

    def build(
        self,
        timestamps: Sequence[datetime],
        estimated_baseline_kw: Sequence[float],
    ) -> DRSeries:
        if len(timestamps) != len(estimated_baseline_kw):
            raise ValueError("timestamps and estimated_baseline_kw length mismatch")
        baseline_est = np.asarray(estimated_baseline_kw, dtype=float)
        if np.any(~np.isfinite(baseline_est)) or np.any(baseline_est < -1e-9):
            raise ValueError("estimated baseline power must be finite and non-negative")

        flags: list[int] = []
        notice: list[str] = []
        req: list[float] = []
        baseline: list[float] = []
        caps: list[float] = []
        event_ids: list[str] = []
        comp: list[float] = []

        static_cap = self._static_peak_cap()
        for ts, estimate in zip(timestamps, baseline_est):
            base_kw = float(self.config.baseline_kw if self.config.baseline_kw is not None else estimate)
            is_event = self.config.enabled and self._in_event_window(ts)
            requested = base_kw * self.config.reduction_frac if is_event else 0.0
            event_cap = base_kw - requested if is_event else -1.0
            cap = event_cap if is_event else static_cap
            flags.append(1 if is_event else 0)
            notice.append(self.config.event_type if is_event else "")
            req.append(max(0.0, requested))
            baseline.append(max(0.0, base_kw if is_event else 0.0))
            caps.append(float(cap) if cap is not None else -1.0)
            event_ids.append(self.config.event_id if is_event else "")
            comp.append(self.config.compensation_cny_per_kwh if is_event else 0.0)
        return DRSeries(
            dr_flag=flags,
            dr_notice_type=notice,
            dr_req_kw=req,
            dr_baseline_kw=baseline,
            dynamic_peak_cap_kw=caps,
            dr_event_id=event_ids,
            dr_compensation_cny_per_kwh=comp,
        )

    def _static_peak_cap(self) -> float | None:
        if self.config.peak_cap_ratio is None or self.config.peak_cap_reference_kw is None:
            return None
        return self.config.peak_cap_ratio * self.config.peak_cap_reference_kw

    def _in_event_window(self, timestamp: datetime) -> bool:
        if self.config.event_start_timestamp is not None:
            start = self.config.event_start_timestamp
            end = start + timedelta(hours=self.config.duration_hours)
            return start <= timestamp < end
        if self.config.event_day_index is not None:
            episode_start = self.config.episode_start_timestamp or datetime(2025, 7, 1)
            start = (
                episode_start.replace(hour=0, minute=0, second=0, microsecond=0)
                + timedelta(days=self.config.event_day_index, hours=self.config.start_hour)
            )
            end = start + timedelta(hours=self.config.duration_hours)
            return start <= timestamp < end
        hour = timestamp.hour + timestamp.minute / 60.0
        end_hour = self.config.start_hour + self.config.duration_hours
        if end_hour <= 24.0:
            return self.config.start_hour <= hour < end_hour
        return hour >= self.config.start_hour or hour < (end_hour - 24.0)


EVENT_COLUMNS = [
    "event_id",
    "scenario_id",
    "event_type",
    "event_window",
    "baseline_energy_kwh",
    "requested_reduction_kwh",
    "served_reduction_kwh",
    "response_rate",
    "tes_event_discharge_kwh_th",
    "event_temp_violation_dh",
    "dr_revenue_cny",
]


def summarize_dr_events(monitor: pd.DataFrame, dt_hours: float, temp_max_c: float) -> pd.DataFrame:
    """Aggregate event-level DR metrics from a closed-loop monitor table."""

    if "dr_flag" not in monitor.columns or not bool((monitor["dr_flag"] > 0).any()):
        return pd.DataFrame(columns=EVENT_COLUMNS)
    rows = []
    event_frame = monitor[monitor["dr_flag"] > 0].copy()
    for event_id, frame in event_frame.groupby("dr_event_id", dropna=False):
        event_id = str(event_id or "dr_event")
        baseline_energy = float((frame["dr_baseline_kw"] * dt_hours).sum())
        requested = float((frame["dr_req_kw"] * dt_hours).sum())
        served_series = (frame["dr_baseline_kw"] - frame["grid_import_kw"]).clip(lower=0.0)
        served = float((served_series * dt_hours).sum())
        response_rate = served / requested if requested > 1e-9 else 0.0
        threshold = float(frame.get("dr_response_threshold", pd.Series([0.50])).iloc[0])
        compensation = float(frame.get("dr_compensation_cny_per_kwh", pd.Series([0.0])).max())
        revenue = served * compensation if response_rate >= threshold else 0.0
        timestamps = frame["timestamp"].astype(str)
        temp_violation = (frame["room_temp_c"] - float(temp_max_c)).clip(lower=0.0)
        rows.append(
            {
                "event_id": event_id,
                "scenario_id": str(frame["scenario_id"].iloc[0]),
                "event_type": str(frame["dr_notice_type"].replace("", np.nan).dropna().iloc[0])
                if bool((frame["dr_notice_type"] != "").any())
                else "",
                "event_window": f"{timestamps.iloc[0]} to {timestamps.iloc[-1]}",
                "baseline_energy_kwh": baseline_energy,
                "requested_reduction_kwh": requested,
                "served_reduction_kwh": served,
                "response_rate": response_rate,
                "tes_event_discharge_kwh_th": float((frame["q_dis_tes_kw_th"] * dt_hours).sum()),
                "event_temp_violation_dh": float((temp_violation * dt_hours).sum()),
                "dr_revenue_cny": revenue,
            }
        )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _parse_optional_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "").replace("T", " "))
    raise ValueError(f"unsupported timestamp value: {value!r}")
