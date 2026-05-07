"""Controller orchestration for Kim-lite cases."""

from __future__ import annotations

from pathlib import Path

from mpc_v2.kim_lite.baseline import direct_no_tes, storage_priority
from mpc_v2.kim_lite.config import KimLiteConfig
from mpc_v2.kim_lite.metrics import build_monitor, summarize_monitor, write_case_outputs
from mpc_v2.kim_lite.model import KimLiteInputs, solve_paper_like_mpc


def run_controller_case(
    cfg: KimLiteConfig,
    inputs: KimLiteInputs,
    controller: str,
    case_id: str,
    output_root: str | Path,
    peak_cap_kw: float | None = None,
    enforce_signed_ramp: bool = False,
) -> tuple[Path, dict]:
    """Run a single Kim-lite controller and persist outputs."""

    normalized = controller.strip().lower()
    if normalized == "direct_no_tes":
        solution = direct_no_tes(cfg, inputs)
    elif normalized == "storage_priority" or normalized == "storage_priority_tes":
        solution = storage_priority(cfg, inputs)
        normalized = "storage_priority_tes" if controller.endswith("_tes") else "storage_priority"
    elif normalized == "mpc_no_tes":
        solution = solve_paper_like_mpc(cfg, inputs, tes_enabled=False, peak_cap_kw=peak_cap_kw)
    elif normalized in {"paper_like_mpc", "paper_like_mpc_tes"}:
        solution = solve_paper_like_mpc(
            cfg,
            inputs,
            tes_enabled=True,
            peak_cap_kw=peak_cap_kw,
            enforce_signed_ramp=enforce_signed_ramp,
        )
        normalized = "paper_like_mpc_tes" if normalized.endswith("_tes") else "paper_like_mpc"
    else:
        raise ValueError(f"unsupported Kim-lite controller: {controller}")
    monitor = build_monitor(normalized, inputs, solution, cfg)
    summary = summarize_monitor(monitor, cfg, case_id, normalized)
    run_dir = Path(output_root) / case_id
    write_case_outputs(
        run_dir,
        monitor,
        summary,
        cfg,
        {
            "controller": normalized,
            "peak_cap_kw": peak_cap_kw,
            "enforce_signed_ramp": enforce_signed_ramp,
        },
    )
    return run_dir, summary
