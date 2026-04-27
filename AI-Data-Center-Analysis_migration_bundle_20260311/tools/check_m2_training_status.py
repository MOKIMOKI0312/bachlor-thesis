"""Summarize long-running M2 training jobs.

Intended for Windows Task Scheduler.  The script reads run_m2_training.py status
JSON files plus probe/latest_step.json when available, checks recorded PIDs, and
writes both Markdown and JSON summaries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.05)
    return {"error": f"failed to read {path}: {last_error}"}


def pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception:
        return False
    return str(pid) in result.stdout


def tail_csv(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 2:
        return {"path": str(path), "rows": max(0, len(lines) - 1)}
    return {
        "path": str(path),
        "rows": len(lines) - 1,
        "header": lines[0],
        "last": lines[-1],
    }


def summarize_status(path: Path, pid_map: dict[str, Any], workspace_hint: Path | None = None) -> dict[str, Any]:
    status = load_json(path)
    name = path.stem.replace("_status", "")
    if name == "status":
        name = path.parent.name
    pid = pid_map.get(name)
    item: dict[str, Any] = {
        "name": name,
        "status_file": str(path),
        "pid": pid,
        "pid_alive": pid_alive(int(pid)) if pid is not None else None,
        "status": status,
    }
    workspace: Path | None = None
    probe_dir: Path | None = None
    progress_file: Path | None = None
    if isinstance(status, dict) and "error" not in status:
        if status.get("workspace_path"):
            workspace = Path(status["workspace_path"])
        if status.get("probe_dir"):
            probe_dir = Path(status["probe_dir"])
        if status.get("progress_file"):
            progress_file = Path(status["progress_file"])
    elif workspace_hint is not None:
        workspace = workspace_hint
        probe_dir = workspace / "probe"
        progress_file = workspace / "progress.csv"

    if workspace is not None:
        item["workspace_path"] = str(workspace)
        item["latest_step"] = load_json(probe_dir / "latest_step.json") if probe_dir else None
        item["progress_tail"] = tail_csv(progress_file) if progress_file else None
        item["workspace_exists"] = workspace.exists()
    return item


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# M2 Training Status",
        "",
        f"- Checked at: `{summary['checked_at']}`",
        f"- Label: `{summary['label']}`",
        "",
        "| Job | PID | Alive | Finished | Timesteps | Approx Episode | Elapsed h | Workspace |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for item in summary["jobs"]:
        status = item.get("status") or {}
        latest = item.get("latest_step") or {}
        elapsed_h = None
        if isinstance(status, dict) and status.get("elapsed_seconds") is not None:
            elapsed_h = float(status["elapsed_seconds"]) / 3600.0
        lines.append(
            "| {name} | {pid} | {alive} | {finished} | {steps} | {episode} | {elapsed} | `{workspace}` |".format(
                name=item["name"],
                pid=item.get("pid", ""),
                alive=item.get("pid_alive"),
                finished=status.get("finished") if isinstance(status, dict) else None,
                steps=(
                    status.get("num_timesteps")
                    if isinstance(status, dict) and status.get("num_timesteps") is not None
                    else latest.get("timestep")
                ),
                episode=(
                    status.get("approx_episode")
                    if isinstance(status, dict) and status.get("approx_episode") is not None
                    else latest.get("episode")
                ),
                elapsed="" if elapsed_h is None else f"{elapsed_h:.2f}",
                workspace=(
                    status.get("workspace_path", "")
                    if isinstance(status, dict) and status.get("workspace_path")
                    else item.get("workspace_path", "")
                ),
            )
        )

    lines.extend(["", "## Latest Steps", ""])
    for item in summary["jobs"]:
        latest = item.get("latest_step") or {}
        obs = latest.get("observations", {}) if isinstance(latest, dict) else {}
        actions = latest.get("actions", {}) if isinstance(latest, dict) else {}
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- reward: `{latest.get('reward')}`",
                f"- time_elapsed_hours: `{latest.get('time_elapsed_hours')}`",
                f"- air_temperature: `{obs.get('air_temperature')}`",
                f"- TES_SOC: `{obs.get('TES_SOC')}`",
                f"- TES_avg_temp: `{obs.get('TES_avg_temp')}`",
                f"- TES_DRL: `{actions.get('TES_DRL')}`",
                f"- price_current_norm: `{obs.get('price_current_norm')}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="m2_training")
    parser.add_argument("--status-files", nargs="+", required=True)
    parser.add_argument("--pid-file")
    parser.add_argument("--workspace-dirs", nargs="*")
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-output")
    args = parser.parse_args()

    pid_map: dict[str, Any] = {}
    if args.pid_file:
        raw = load_json(Path(args.pid_file))
        if isinstance(raw, dict):
            pid_map = raw

    workspace_dirs = [Path(p) for p in (args.workspace_dirs or [])]
    summary = {
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "jobs": [
            summarize_status(
                Path(p),
                pid_map,
                workspace_dirs[index] if index < len(workspace_dirs) else None,
            )
            for index, p in enumerate(args.status_files)
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(output, summary)
    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
