"""Realtime training probe and dashboard snapshot helpers for data-center runs."""

from __future__ import annotations

import csv
import ctypes
import json
import math
import os
import time
from collections import deque
from functools import partial
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Union

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from sinergym.utils.logger import CSVLogger


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _safe_scalar(value: Any) -> Optional[Union[int, float, str, bool]]:
    if value is None:
        return None
    if isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    return None


def _safe_list(values: Union[np.ndarray, Sequence[Any]]) -> List[Any]:
    if isinstance(values, np.ndarray):
        return values.tolist()
    return list(values)


def _safe_map(names: Sequence[str], values: Union[np.ndarray, Sequence[Any]]) -> Dict[str, Any]:
    mapped: Dict[str, Any] = {}
    for name, value in zip(names, _safe_list(values)):
        scalar = _safe_scalar(value)
        mapped[name] = scalar if scalar is not None else value
    return mapped


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _pid_is_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False

    if pid_int <= 0:
        return False

    if os.name == "nt":
        process_query_limited_information = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid_int)
        if handle == 0:
            return False
        kernel32.CloseHandle(handle)
        return True

    try:
        os.kill(pid_int, 0)
        return True
    except OSError:
        return False
    except SystemError:
        return False


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")


def _write_csv_rows(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _fmt_number(value: Any, digits: int = 3) -> str:
    scalar = _safe_scalar(value)
    if scalar is None:
        return "--"
    if isinstance(scalar, bool):
        return "true" if scalar else "false"
    if isinstance(scalar, int):
        return str(scalar)
    if isinstance(scalar, float):
        return f"{scalar:.{digits}f}"
    return str(scalar)


def _fmt_seconds(value: Any) -> str:
    scalar = _safe_scalar(value)
    if scalar is None:
        return "--"
    total = int(float(scalar))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _tail_jsonl(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists() or limit <= 0:
        return []
    rows: Deque[Dict[str, Any]] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(rows)


def _tail_csv(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists() or limit <= 0:
        return []
    rows: Deque[Dict[str, Any]] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return list(rows)


def _normalize_csv_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        current: Dict[str, Any] = {}
        for key, value in row.items():
            if value in ("", None):
                current[key] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                current[key] = value
                continue
            if number.is_integer():
                current[key] = int(number)
            else:
                current[key] = number
        normalized.append(current)
    return normalized


class RealtimeProbeSink:
    """Writes low-cost realtime files for the training dashboard."""

    def __init__(
        self,
        workspace_path: Union[str, Path],
        observation_variables: Sequence[str],
        action_variables: Sequence[str],
        recent_step_window: int = 192,
        step_sample_interval: int = 12,
    ) -> None:
        self.workspace_path = Path(workspace_path)
        self.probe_dir = self.workspace_path / "probe"
        self.probe_dir.mkdir(parents=True, exist_ok=True)
        self.observation_variables = list(observation_variables)
        self.action_variables = list(action_variables)
        self.recent_step_window = recent_step_window
        self.step_sample_interval = max(1, step_sample_interval)
        self.recent_steps: Deque[Dict[str, Any]] = deque(maxlen=recent_step_window)
        self.latest_step_path = self.probe_dir / "latest_step.json"
        self.recent_steps_path = self.probe_dir / "recent_steps.json"
        self.step_samples_path = self.probe_dir / "step_samples.jsonl"
        self.episode_samples_path = self.probe_dir / "episode_samples.jsonl"
        self.training_updates_path = self.probe_dir / "training_updates.jsonl"
        self.metadata_path = self.probe_dir / "metadata.json"
        self.dashboard_snapshot_path = self.probe_dir / "dashboard_snapshot.json"
        self._write_metadata()

    def _write_metadata(self) -> None:
        _write_json(
            self.metadata_path,
            {
                "workspace_path": str(self.workspace_path),
                "probe_dir": str(self.probe_dir),
                "observation_variables": self.observation_variables,
                "action_variables": self.action_variables,
                "recent_step_window": self.recent_step_window,
                "step_sample_interval": self.step_sample_interval,
                "created_epoch": time.time(),
            },
        )

    def record_step(
        self,
        episode: int,
        obs: Union[np.ndarray, Sequence[Any]],
        action: Union[np.ndarray, Sequence[Any]],
        terminated: bool,
        truncated: bool,
        info: Dict[str, Any],
    ) -> None:
        payload = {
            "episode": episode,
            "timestep": int(info.get("timestep", 0) or 0),
            "time_elapsed_hours": _safe_scalar(info.get("time_elapsed(hours)")),
            "reward": _safe_scalar(info.get("reward")),
            "energy_term": _safe_scalar(info.get("energy_term")),
            "comfort_term": _safe_scalar(info.get("comfort_term")),
            "abs_energy_penalty": _safe_scalar(info.get("abs_energy_penalty")),
            "abs_comfort_penalty": _safe_scalar(info.get("abs_comfort_penalty")),
            "total_power_demand": _safe_scalar(info.get("total_power_demand")),
            "total_temperature_violation": _safe_scalar(info.get("total_temperature_violation")),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "wall_clock_epoch": time.time(),
            "observations": _safe_map(self.observation_variables, obs),
            "actions": _safe_map(self.action_variables, action),
        }
        self.recent_steps.append(payload)
        _write_json(self.latest_step_path, payload)
        _write_json(self.recent_steps_path, {"steps": list(self.recent_steps), "updated_epoch": time.time()})

        timestep = payload["timestep"]
        if timestep == 1 or timestep % self.step_sample_interval == 0 or terminated or truncated:
            sample = {
                "episode": payload["episode"],
                "timestep": payload["timestep"],
                "time_elapsed_hours": payload["time_elapsed_hours"],
                "reward": payload["reward"],
                "energy_term": payload["energy_term"],
                "comfort_term": payload["comfort_term"],
                "total_power_demand": payload["total_power_demand"],
                "total_temperature_violation": payload["total_temperature_violation"],
                "wall_clock_epoch": payload["wall_clock_epoch"],
            }
            _append_jsonl(self.step_samples_path, sample)

    def record_episode(self, summary: Dict[str, Any]) -> None:
        _append_jsonl(self.episode_samples_path, summary)

    def record_training_update(self, payload: Dict[str, Any]) -> None:
        _append_jsonl(self.training_updates_path, payload)


class ProbeCSVLogger(CSVLogger):
    """CSV logger with realtime probe side effects."""

    def __init__(
        self,
        monitor_header: str,
        progress_header: str,
        log_progress_file: str,
        log_file: Optional[str] = None,
        flag: bool = True,
        observation_variables: Optional[Sequence[str]] = None,
        action_variables: Optional[Sequence[str]] = None,
        recent_step_window: int = 192,
        step_sample_interval: int = 12,
    ) -> None:
        super().__init__(monitor_header, progress_header, log_progress_file, log_file, flag)
        self.workspace_path = Path(log_progress_file).resolve().parent
        self.current_episode = 0
        self.probe = RealtimeProbeSink(
            workspace_path=self.workspace_path,
            observation_variables=observation_variables or [],
            action_variables=action_variables or [],
            recent_step_window=recent_step_window,
            step_sample_interval=step_sample_interval,
        )

    def log_step(
        self,
        obs: List[Any],
        action: Union[int, np.ndarray, List[Any]],
        terminated: bool,
        truncated: bool,
        info: Dict[str, Any],
    ) -> None:
        super().log_step(obs, action, terminated, truncated, info)
        if self.flag:
            self.probe.record_step(
                episode=self.current_episode,
                obs=obs,
                action=action if isinstance(action, (np.ndarray, list, tuple)) else [action],
                terminated=terminated,
                truncated=truncated,
                info=info,
            )

    def set_log_file(self, new_log_file: str) -> None:
        super().set_log_file(new_log_file)
        try:
            episode_dir = Path(new_log_file).resolve().parent.name
            self.current_episode = int(episode_dir.split("-")[-1])
        except (ValueError, IndexError):
            self.current_episode += 1

    def _build_episode_summary(self, episode: int) -> Dict[str, Any]:
        total_timesteps = self.episode_data["total_timesteps"]
        if total_timesteps:
            comfort_violation = (
                self.episode_data["comfort_violation_timesteps"] / total_timesteps * 100
            )
        else:
            comfort_violation = None

        def _sum(values: List[Any]) -> Optional[float]:
            return float(np.sum(values)) if values else None

        def _mean(values: List[Any]) -> Optional[float]:
            return float(np.mean(values)) if values else None

        return {
            "episode_num": episode,
            "cumulative_reward": _sum(self.episode_data["rewards"]),
            "mean_reward": _mean(self.episode_data["rewards"]),
            "cumulative_reward_energy_term": _sum(self.episode_data["reward_energy_terms"]),
            "mean_reward_energy_term": _mean(self.episode_data["reward_energy_terms"]),
            "cumulative_reward_comfort_term": _sum(self.episode_data["reward_comfort_terms"]),
            "mean_reward_comfort_term": _mean(self.episode_data["reward_comfort_terms"]),
            "cumulative_abs_energy_penalty": _sum(self.episode_data["abs_energy_penalties"]),
            "mean_abs_energy_penalty": _mean(self.episode_data["abs_energy_penalties"]),
            "cumulative_abs_comfort_penalty": _sum(self.episode_data["abs_comfort_penalties"]),
            "mean_abs_comfort_penalty": _mean(self.episode_data["abs_comfort_penalties"]),
            "cumulative_power_demand": _sum(self.episode_data["total_power_demands"]),
            "mean_power_demand": _mean(self.episode_data["total_power_demands"]),
            "cumulative_temperature_violation": _sum(self.episode_data["total_temperature_violations"]),
            "mean_temperature_violation": _mean(self.episode_data["total_temperature_violations"]),
            "comfort_violation_time_pct": comfort_violation,
            "length_timesteps": total_timesteps,
            "time_elapsed_hours": _safe_scalar(self.episode_data["total_time_elapsed"]),
            "wall_clock_epoch": time.time(),
        }

    def log_episode(self, episode: int) -> None:
        summary = self._build_episode_summary(episode)
        super().log_episode(episode)
        if self.flag:
            self.probe.record_episode(summary)


class StatusCallback(BaseCallback):
    """Writes coarse training status and sampled SB3 metrics to disk."""

    def __init__(
        self,
        status_file: Path,
        workspace_path: Path,
        timesteps_per_episode: int,
        started: float,
        update_every_steps: int = 500,
    ) -> None:
        super().__init__()
        self.status_file = Path(status_file)
        self.workspace_path = Path(workspace_path)
        self.timesteps_per_episode = max(1, timesteps_per_episode)
        self.started = started
        self.update_every_steps = max(1, update_every_steps)
        metadata = _read_json(self.workspace_path / "probe" / "metadata.json") or {}
        self.probe_dir = Path(metadata.get("probe_dir", self.workspace_path / "probe"))

    def _approx_episode(self) -> int:
        completed = int(self.num_timesteps // self.timesteps_per_episode)
        has_partial = (self.num_timesteps % self.timesteps_per_episode) != 0
        if completed == 0 and self.num_timesteps > 0:
            return 1
        return completed + (1 if has_partial else 0)

    def _collect_logger_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        for key, value in getattr(self.logger, "name_to_value", {}).items():
            scalar = _safe_scalar(value)
            if scalar is not None:
                metrics[key] = scalar
        return metrics

    def _payload(self, finished: bool = False) -> Dict[str, Any]:
        return {
            "num_timesteps": int(self.num_timesteps),
            "approx_episode": int(self._approx_episode()),
            "elapsed_seconds": time.perf_counter() - self.started,
            "last_update_epoch": time.time(),
            "workspace_path": str(self.workspace_path),
            "probe_dir": str(self.probe_dir),
            "progress_file": str(self.workspace_path / "progress.csv"),
            "finished": finished,
            "training_metrics": self._collect_logger_metrics(),
        }

    def _on_training_start(self) -> None:
        payload = self._payload(finished=False)
        _write_json(self.status_file, payload)
        metadata = _read_json(self.probe_dir / "metadata.json")
        if metadata is not None:
            _append_jsonl(self.probe_dir / "training_updates.jsonl", payload)

    def _on_step(self) -> bool:
        if self.num_timesteps % self.update_every_steps != 0:
            return True

        payload = self._payload(finished=False)
        _write_json(self.status_file, payload)
        metadata = _read_json(self.probe_dir / "metadata.json")
        if metadata is not None:
            _append_jsonl(self.probe_dir / "training_updates.jsonl", payload)
        return True

    def _on_training_end(self) -> None:
        payload = self._payload(finished=True)
        _write_json(self.status_file, payload)
        metadata = _read_json(self.probe_dir / "metadata.json")
        if metadata is not None:
            _append_jsonl(self.probe_dir / "training_updates.jsonl", payload)


def make_probe_logger_factory(
    observation_variables: Sequence[str],
    action_variables: Sequence[str],
    recent_step_window: int = 192,
    step_sample_interval: int = 12,
):
    return partial(
        ProbeCSVLogger,
        observation_variables=list(observation_variables),
        action_variables=list(action_variables),
        recent_step_window=recent_step_window,
        step_sample_interval=step_sample_interval,
    )


def _resolve_workspace_path(manifest: Dict[str, Any]) -> Optional[Path]:
    status = _read_json(Path(manifest["status_file"])) if manifest.get("status_file") else None
    if status and status.get("workspace_path"):
        return Path(status["workspace_path"])

    stdout_log = Path(manifest.get("stdout_log", ""))
    if stdout_log.exists():
        text = stdout_log.read_text(encoding="utf-8", errors="replace")
        marker = '"workspace_path": "'
        idx = text.rfind(marker)
        if idx != -1:
            start = idx + len(marker)
            end = text.find('"', start)
            if end != -1:
                raw_path = text[start:end]
                return Path(raw_path.encode("utf-8").decode("unicode_escape"))
    return None


def build_dashboard_snapshot(manifest_path: Union[str, Path], persist: bool = True) -> Dict[str, Any]:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    status_path = Path(manifest["status_file"]) if manifest.get("status_file") else None
    status = _read_json(status_path) if status_path else None
    workspace_path = _resolve_workspace_path(manifest)
    stdout_path = Path(manifest.get("stdout_log", ""))
    stderr_path = Path(manifest.get("stderr_log", ""))

    pid_alive = _pid_is_alive(manifest.get("pid"))

    probe_dir = workspace_path / "probe" if workspace_path else None
    latest_step = _read_json(probe_dir / "latest_step.json") if probe_dir else None
    recent_steps_payload = _read_json(probe_dir / "recent_steps.json") if probe_dir else None
    recent_steps = recent_steps_payload.get("steps", []) if recent_steps_payload else []
    training_updates = _tail_jsonl(probe_dir / "training_updates.jsonl", 120) if probe_dir else []
    progress_rows = _normalize_csv_rows(_tail_csv(workspace_path / "progress.csv", 120)) if workspace_path else []
    episode_samples = _tail_jsonl(probe_dir / "episode_samples.jsonl", 120) if probe_dir else []
    step_samples = _tail_jsonl(probe_dir / "step_samples.jsonl", 240) if probe_dir else []

    latest_episode = progress_rows[-1] if progress_rows else None
    best_episode = None
    if progress_rows:
        best_episode = max(
            progress_rows,
            key=lambda row: float(row.get("cumulative_reward") or float("-inf")),
        )

    snapshot = {
        "job": {
            "job_name": manifest.get("job_name"),
            "pid": manifest.get("pid"),
            "pid_alive": pid_alive,
            "started_epoch": manifest.get("started_epoch"),
            "repo": manifest.get("repo"),
            "manifest_path": str(manifest_path),
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        },
        "status": status or {},
        "workspace": {
            "workspace_path": str(workspace_path) if workspace_path else None,
            "probe_dir": str(probe_dir) if probe_dir else None,
            "progress_file": str(workspace_path / "progress.csv") if workspace_path else None,
        },
        "latest_step": latest_step,
        "recent_steps": recent_steps,
        "step_samples": step_samples,
        "training_updates": training_updates,
        "progress_rows": progress_rows,
        "episode_samples": episode_samples,
        "latest_episode": latest_episode,
        "best_episode": best_episode,
        "summary": {
            "completed_episodes": len(progress_rows),
            "latest_mean_reward": latest_episode.get("mean_reward") if latest_episode else None,
            "latest_cumulative_reward": latest_episode.get("cumulative_reward") if latest_episode else None,
            "best_cumulative_reward": best_episode.get("cumulative_reward") if best_episode else None,
            "last_training_metrics": (training_updates[-1].get("training_metrics") if training_updates else {}) if training_updates else {},
        },
    }

    if persist and probe_dir:
        _write_json(probe_dir / "dashboard_snapshot.json", snapshot)
    return snapshot


def export_dashboard_artifacts(
    snapshot: Dict[str, Any],
    output_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, str]:
    workspace_path = snapshot.get("workspace", {}).get("workspace_path")
    if workspace_path is None:
        raise ValueError("Snapshot does not contain a workspace_path.")

    reports_dir = Path(output_dir) if output_dir is not None else Path(workspace_path) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    snapshot_json_path = reports_dir / "dashboard_snapshot.json"
    episodes_csv_path = reports_dir / "episodes.csv"
    step_samples_csv_path = reports_dir / "step_samples.csv"
    training_updates_csv_path = reports_dir / "training_updates.csv"
    summary_json_path = reports_dir / "summary.json"
    report_md_path = reports_dir / "training_report.md"

    _write_json(snapshot_json_path, snapshot)
    _write_csv_rows(episodes_csv_path, snapshot.get("progress_rows", []))
    _write_csv_rows(step_samples_csv_path, snapshot.get("step_samples", []))
    _write_csv_rows(training_updates_csv_path, snapshot.get("training_updates", []))
    _write_json(summary_json_path, snapshot.get("summary", {}))

    job = snapshot.get("job", {})
    status = snapshot.get("status", {})
    workspace = snapshot.get("workspace", {})
    summary = snapshot.get("summary", {})
    latest_episode = snapshot.get("latest_episode") or {}
    best_episode = snapshot.get("best_episode") or {}
    latest_step = snapshot.get("latest_step") or {}

    report_lines = [
        "# Training Report",
        "",
        "## Run Summary",
        "",
        f"- Job: `{job.get('job_name', '--')}`",
        f"- PID alive: `{job.get('pid_alive', False)}`",
        f"- Training finished: `{status.get('finished', False)}`",
        f"- Timesteps: `{_fmt_number(status.get('num_timesteps'), 0)}`",
        f"- Approx episode: `{_fmt_number(status.get('approx_episode'), 0)}`",
        f"- Elapsed: `{_fmt_seconds(status.get('elapsed_seconds'))}`",
        f"- Workspace: `{workspace.get('workspace_path', '--')}`",
        "",
        "## Episode Metrics",
        "",
        f"- Completed episodes: `{_fmt_number(summary.get('completed_episodes'), 0)}`",
        f"- Latest cumulative reward: `{_fmt_number(summary.get('latest_cumulative_reward'))}`",
        f"- Latest mean reward: `{_fmt_number(summary.get('latest_mean_reward'))}`",
        f"- Best cumulative reward: `{_fmt_number(summary.get('best_cumulative_reward'))}`",
        f"- Latest comfort violation (%): `{_fmt_number(latest_episode.get('comfort_violation_time (%)') or latest_episode.get('comfort_violation_time_pct'))}`",
        f"- Latest mean power demand: `{_fmt_number(latest_episode.get('mean_power_demand'))}`",
        "",
        "## Latest Step Snapshot",
        "",
        f"- Latest step episode: `{_fmt_number(latest_step.get('episode'), 0)}`",
        f"- Latest timestep: `{_fmt_number(latest_step.get('timestep'), 0)}`",
        f"- Reward: `{_fmt_number(latest_step.get('reward'))}`",
        f"- Energy term: `{_fmt_number(latest_step.get('energy_term'))}`",
        f"- Comfort term: `{_fmt_number(latest_step.get('comfort_term'))}`",
        f"- Total power demand: `{_fmt_number(latest_step.get('total_power_demand'))}`",
        f"- Total temperature violation: `{_fmt_number(latest_step.get('total_temperature_violation'))}`",
        "",
        "## Files",
        "",
        f"- Snapshot JSON: `{snapshot_json_path}`",
        f"- Summary JSON: `{summary_json_path}`",
        f"- Episodes CSV: `{episodes_csv_path}`",
        f"- Step samples CSV: `{step_samples_csv_path}`",
        f"- Training updates CSV: `{training_updates_csv_path}`",
        f"- Stdout log: `{job.get('stdout_log', '--')}`",
        f"- Stderr log: `{job.get('stderr_log', '--')}`",
        "",
        "## Best Episode",
        "",
        f"- Episode number: `{_fmt_number(best_episode.get('episode_num'), 0)}`",
        f"- Cumulative reward: `{_fmt_number(best_episode.get('cumulative_reward'))}`",
        f"- Mean reward: `{_fmt_number(best_episode.get('mean_reward'))}`",
    ]
    report_md_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "reports_dir": str(reports_dir),
        "report_md": str(report_md_path),
        "snapshot_json": str(snapshot_json_path),
        "summary_json": str(summary_json_path),
        "episodes_csv": str(episodes_csv_path),
        "step_samples_csv": str(step_samples_csv_path),
        "training_updates_csv": str(training_updates_csv_path),
    }


def discover_training_jobs(repo: Union[str, Path]) -> List[Dict[str, Any]]:
    repo = Path(repo).resolve()
    jobs_dir = repo / "training_jobs"
    if not jobs_dir.exists():
        return []

    jobs: List[Dict[str, Any]] = []
    for manifest_path in sorted(jobs_dir.glob("*/manifest.json"), reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        status = _read_json(Path(manifest["status_file"])) if manifest.get("status_file") else None
        jobs.append(
            {
                "job_name": manifest.get("job_name"),
                "manifest_path": str(manifest_path.resolve()),
                "pid": manifest.get("pid"),
                "started_epoch": manifest.get("started_epoch"),
                "workspace_path": status.get("workspace_path") if status else None,
                "finished": bool(status.get("finished")) if status else False,
                "num_timesteps": status.get("num_timesteps") if status else None,
                "approx_episode": status.get("approx_episode") if status else None,
            }
        )
    return jobs


def discover_job_groups(repo: Union[str, Path]) -> List[Dict[str, Any]]:
    jobs = discover_training_jobs(repo)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for job in jobs:
        job_name = job.get("job_name") or ""
        if "-seed" in job_name:
            prefix = job_name.rsplit("-seed", 1)[0]
            groups.setdefault(prefix, []).append(job)

    payload: List[Dict[str, Any]] = []
    for prefix, members in sorted(groups.items()):
        ordered = sorted(members, key=lambda item: item["job_name"])
        payload.append(
            {
                "prefix": prefix,
                "count": len(ordered),
                "jobs": [item["job_name"] for item in ordered],
                "active_jobs": sum(0 if item.get("finished") else 1 for item in ordered),
            }
        )
    return payload


def build_group_snapshot(
    repo: Union[str, Path],
    prefix: Optional[str] = None,
    job_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    repo = Path(repo).resolve()
    jobs = discover_training_jobs(repo)

    selected_jobs: List[Dict[str, Any]]
    if job_names:
        target_names = set(job_names)
        selected_jobs = [job for job in jobs if job["job_name"] in target_names]
        group_name = ",".join(sorted(target_names))
    elif prefix:
        selected_jobs = [job for job in jobs if job["job_name"].startswith(prefix)]
        group_name = prefix
    else:
        raise ValueError("Either prefix or job_names must be provided.")

    selected_jobs = sorted(selected_jobs, key=lambda item: item["job_name"])
    members: List[Dict[str, Any]] = []
    for job in selected_jobs:
        snapshot = build_dashboard_snapshot(job["manifest_path"], persist=True)
        status = snapshot.get("status", {})
        latest_episode = snapshot.get("latest_episode") or {}
        latest_step = snapshot.get("latest_step") or {}
        members.append(
            {
                "job_name": job["job_name"],
                "manifest_path": job["manifest_path"],
                "finished": bool(job.get("finished")),
                "pid": job.get("pid"),
                "status": status,
                "summary": snapshot.get("summary", {}),
                "latest_episode": latest_episode,
                "latest_step": latest_step,
                "progress_rows": snapshot.get("progress_rows", []),
                "recent_steps": snapshot.get("recent_steps", []),
                "step_samples": snapshot.get("step_samples", []),
                "training_updates": snapshot.get("training_updates", []),
            }
        )

    members_sorted = sorted(
        members,
        key=lambda item: float(item["summary"].get("best_cumulative_reward") or float("-inf")),
        reverse=True,
    )
    leaderboard = [
        {
            "job_name": item["job_name"],
            "finished": item["finished"],
            "num_timesteps": item["status"].get("num_timesteps"),
            "approx_episode": item["status"].get("approx_episode"),
            "latest_cumulative_reward": item["summary"].get("latest_cumulative_reward"),
            "best_cumulative_reward": item["summary"].get("best_cumulative_reward"),
            "latest_mean_reward": item["summary"].get("latest_mean_reward"),
            "temp_violation": item["latest_step"].get("total_temperature_violation"),
            "power_demand": item["latest_step"].get("total_power_demand"),
        }
        for item in members_sorted
    ]

    return {
        "repo_root": str(repo),
        "group_name": group_name,
        "member_count": len(members_sorted),
        "members": members_sorted,
        "leaderboard": leaderboard,
        "generated_epoch": time.time(),
    }
