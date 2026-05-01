"""Small M2 checkpoint guards shared by training/evaluation scripts."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


M2_AGENT_ACTION_DIM = 4
M2_FIXED_FAN_VALUE = 1.0


def checkpoint_action_dim(checkpoint: str | Path) -> int:
    """Read the saved SB3 action-space dimension without loading the policy."""
    path = Path(checkpoint)
    try:
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("data").decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not inspect checkpoint action_space: {path}") from exc

    action_space = data.get("action_space")
    shape = action_space.get("_shape") if isinstance(action_space, dict) else None
    if not shape:
        raise RuntimeError(f"Checkpoint has no readable action_space._shape: {path}")
    return int(shape[0])


def assert_m2_4d_checkpoint(checkpoint: str | Path) -> None:
    action_dim = checkpoint_action_dim(checkpoint)
    if action_dim != M2_AGENT_ACTION_DIM:
        raise RuntimeError(
            f"Refusing M2 checkpoint with action_dim={action_dim}. "
            f"M2-F1 fixed-fan runs require action_dim={M2_AGENT_ACTION_DIM}; "
            "old 5D checkpoints/replay buffers must not be resumed or evaluated."
        )
