"""Small M2 checkpoint guards shared by training/evaluation scripts."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


M2_AGENT_ACTION_DIM = 4
M2_FIXED_FAN_VALUE = 1.0


def checkpoint_action_dim(checkpoint: str | Path) -> int:
    """Read the saved SB3 action-space dimension without loading the policy.

    C5 fix: SB3's serialized ``action_space`` has used both ``_shape`` and
    ``shape`` across versions/plugins. We accept either, validate the value
    looks like a (length-1) shape tuple, and emit the available keys when
    parsing fails so the failure is debuggable instead of a vague
    'unreadable checkpoint'.
    """
    path = Path(checkpoint)
    try:
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("data").decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not inspect checkpoint action_space: {path}") from exc

    action_space = data.get("action_space")
    if not isinstance(action_space, dict):
        raise RuntimeError(
            f"Checkpoint has no dict-shaped action_space: {path} "
            f"(got type={type(action_space).__name__})"
        )

    # Try both common SB3 serialization keys.
    shape = action_space.get("_shape") or action_space.get("shape")
    if not shape or not isinstance(shape, (list, tuple)) or len(shape) == 0:
        keys = sorted(action_space.keys())
        raise RuntimeError(
            f"Checkpoint has no readable action_space shape: {path}. "
            f"Tried keys ['_shape', 'shape']; available action_space keys: {keys}"
        )
    return int(shape[0])


def assert_m2_4d_checkpoint(checkpoint: str | Path) -> None:
    action_dim = checkpoint_action_dim(checkpoint)
    if action_dim != M2_AGENT_ACTION_DIM:
        raise RuntimeError(
            f"Refusing M2 checkpoint with action_dim={action_dim}. "
            f"M2-F1 fixed-fan runs require action_dim={M2_AGENT_ACTION_DIM}; "
            "old 5D checkpoints/replay buffers must not be resumed or evaluated."
        )
