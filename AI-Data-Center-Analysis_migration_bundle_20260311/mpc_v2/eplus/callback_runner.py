"""EnergyPlus callback runner skeleton for MPC v2.

The production EnergyPlus integration is intentionally kept behind this
interface. The default validation path uses synthetic replay so v2 can be
tested without changing the existing Sinergym/EnergyPlus chain.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallbackRunnerState:
    """Minimal callback state used to prevent duplicate per-step actions."""

    warmup_complete: bool = False
    last_solved_timestamp: str | None = None
    last_written_timestamp: str | None = None


class CallbackRunner:
    """Placeholder for EnergyPlus Runtime API callback wiring."""

    def __init__(self) -> None:
        self.state = CallbackRunnerState()

    def mark_solved(self, timestamp: str) -> None:
        if self.state.last_solved_timestamp == timestamp:
            raise RuntimeError(f"MPC already solved for timestamp {timestamp}")
        self.state.last_solved_timestamp = timestamp

    def mark_written(self, timestamp: str) -> None:
        if self.state.last_written_timestamp == timestamp:
            raise RuntimeError(f"MPC action already written for timestamp {timestamp}")
        self.state.last_written_timestamp = timestamp

    def run(self, *_args, **_kwargs) -> None:
        raise NotImplementedError(
            "Real EnergyPlus callback execution is intentionally not wired in smoke. "
            "Use EPlusAdapter for mapping and run_closed_loop.py for synthetic replay."
        )

