"""One-command physical-system validation for the datacenter M2 model.

This is intentionally not an RL training run.  It uses scripted scenarios so
component responses can be interpreted directly:

1. EnergyPlus component isolation audit:
   - TES idle / discharge / negative source-side command / discharge-then-charge
   - low/high IT load
   - condenser pump low/high
   - CRAH fan low/high
   - tower/economizer present
2. Optional M2 environment smokes for rl_cost and rl_green wrapper stacks.

The output is a timestamped tools/m1/physical_system_check_<timestamp> folder
with command logs, summary.json, and report.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
M1 = TOOLS / "m1"
DEFAULT_EPLUS = Path(
    "C:/Users/18430/EnergyPlus-23.1.0/"
    "EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
)


def common_env() -> dict[str, str]:
    env = os.environ.copy()
    eplus = Path(env.get("EPLUS_PATH", str(DEFAULT_EPLUS)))
    env["EPLUS_PATH"] = str(eplus)
    existing_py = env.get("PYTHONPATH", "")
    parts = [str(ROOT), str(eplus)]
    if existing_py:
        parts.append(existing_py)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    return env


def run_command(
    cmd: list[str],
    out_dir: Path,
    name: str,
    env: dict[str, str],
) -> dict[str, Any]:
    started = dt.datetime.now()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    elapsed = (dt.datetime.now() - started).total_seconds()
    stdout_path = out_dir / f"{name}.stdout.txt"
    stderr_path = out_dir / f"{name}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(proc.stderr, encoding="utf-8", errors="replace")
    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_sec": elapsed,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


def audit_path_from_stdout(stdout: str) -> Path | None:
    match = re.search(r"\[audit\]\s+output:\s+(.+)", stdout)
    if not match:
        return None
    return Path(match.group(1).strip())


def metric(audit: dict[str, Any], scenario: str, metric_name: str, stat: str) -> float | None:
    for item in audit.get("scenarios", []):
        if item.get("id") != scenario:
            continue
        value = item.get("metrics", {}).get(metric_name, {}).get(stat)
        return None if value is None else float(value)
    return None


def summarize_audit(audit_path: Path) -> dict[str, Any]:
    audit = json.loads((audit_path / "audit.json").read_text(encoding="utf-8"))
    warning_categories: dict[str, int] = {}
    total_warnings = 0
    severe = 0
    fatal = 0
    scenario_table = []
    for scenario in audit.get("scenarios", []):
        counts = scenario["err"]["counts"]
        total_warnings += counts["warning"]
        severe += counts["severe"]
        fatal += counts["fatal"]
        for key, value in scenario["err"].get("categories", {}).items():
            warning_categories[key] = warning_categories.get(key, 0) + value
        scenario_table.append(
            {
                "id": scenario["id"],
                "warnings": counts["warning"],
                "severe": counts["severe"],
                "fatal": counts["fatal"],
            }
        )

    return {
        "audit_dir": str(audit_path),
        "static_fail": sum(1 for c in audit.get("static_checks", []) if not c["pass"]),
        "component_fail": sum(1 for c in audit.get("component_assertions", []) if not c["pass"]),
        "warnings": total_warnings,
        "severe": severe,
        "fatal": fatal,
        "warning_categories": dict(sorted(warning_categories.items())),
        "scenarios": scenario_table,
        "physics_metrics": {
            "tes_discharge_use_heat_abs_mean_w": metric(audit, "tes_discharge", "tes_use_heat", "abs_mean"),
            "tes_cycle_source_heat_abs_mean_w": metric(audit, "tes_cycle", "tes_source_heat", "abs_mean"),
            "tes_cycle_soc_min": metric(audit, "tes_cycle", "tes_soc", "min"),
            "tes_cycle_soc_max": metric(audit, "tes_cycle", "tes_soc", "max"),
            "chiller_low_it_cooling_mean_w": metric(audit, "chiller_low_it", "chiller_cooling", "mean"),
            "chiller_high_it_cooling_mean_w": metric(audit, "chiller_high_it", "chiller_cooling", "mean"),
            "condenser_pump_low_flow_kg_s": metric(audit, "pumps_low", "condenser_pump_flow", "mean"),
            "condenser_pump_high_flow_kg_s": metric(audit, "pumps_high", "condenser_pump_flow", "mean"),
            "crah_low_fan_flow_kg_s": metric(audit, "crah_low", "fan_flow", "mean"),
            "crah_high_fan_flow_kg_s": metric(audit, "crah_high", "fan_flow", "mean"),
            "tower_heat_abs_mean_w": metric(audit, "tower_economizer", "tower_heat", "abs_mean"),
            "economizer_heat_abs_mean_w": metric(audit, "tower_economizer", "economizer_heat", "abs_mean"),
        },
    }


def write_report(out_dir: Path, summary: dict[str, Any]) -> None:
    audit = summary["audit"]
    lines = [
        "# Physical System Check",
        "",
        f"- Created: `{summary['created_at']}`",
        f"- Overall: `{'PASS' if summary['pass'] else 'FAIL'}`",
        f"- Audit dir: `{audit.get('audit_dir')}`",
        "",
        "## Commands",
        "",
        "| Name | RC | Seconds |",
        "|---|---:|---:|",
    ]
    for cmd in summary["commands"]:
        lines.append(f"| {cmd['name']} | {cmd['returncode']} | {cmd['elapsed_sec']:.1f} |")

    lines.extend(
        [
            "",
            "## Audit Summary",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| static_fail | {audit.get('static_fail')} |",
            f"| component_fail | {audit.get('component_fail')} |",
            f"| severe | {audit.get('severe')} |",
            f"| fatal | {audit.get('fatal')} |",
            f"| warnings | {audit.get('warnings')} |",
            "",
            "## Physical Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for key, value in audit.get("physics_metrics", {}).items():
        if isinstance(value, float):
            lines.append(f"| {key} | {value:.6g} |")
        else:
            lines.append(f"| {key} | {value} |")

    lines.extend(["", "## Warning Categories", "", "| Category | Count |", "|---|---:|"])
    for key, value in audit.get("warning_categories", {}).items():
        lines.append(f"| {key} | {value} |")

    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-m2-smoke", action="store_true", help="only run EnergyPlus physical scenarios")
    parser.add_argument("--m2-steps", type=int, default=3, help="steps for each M2 smoke run")
    args = parser.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = M1 / f"physical_system_check_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    env = common_env()

    commands = []
    audit_cmd = [sys.executable, str(M1 / "verify_eplus_model_full.py")]
    audit_run = run_command(audit_cmd, out_dir, "eplus_component_audit", env)
    commands.append(audit_run)
    audit_path = audit_path_from_stdout(audit_run["stdout_text"])
    if audit_path is None:
        summary = {
            "created_at": stamp,
            "pass": False,
            "commands": [{k: v for k, v in c.items() if not k.endswith("_text")} for c in commands],
            "audit": {"error": "Could not find audit output path in stdout."},
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        write_report(out_dir, summary)
        print(f"FAIL: audit output path missing. See {out_dir}")
        return 1

    if not args.skip_m2_smoke:
        for reward in ("rl_cost", "rl_green"):
            cmd = [
                sys.executable,
                str(TOOLS / "smoke_m2_env.py"),
                "--reward-cls",
                reward,
                "--steps",
                str(args.m2_steps),
            ]
            commands.append(run_command(cmd, out_dir, f"m2_smoke_{reward}", env))

    audit_summary = summarize_audit(audit_path)
    all_ok = (
        all(c["returncode"] == 0 for c in commands)
        and audit_summary["static_fail"] == 0
        and audit_summary["component_fail"] == 0
        and audit_summary["severe"] == 0
        and audit_summary["fatal"] == 0
    )
    summary = {
        "created_at": stamp,
        "pass": all_ok,
        "commands": [{k: v for k, v in c.items() if not k.endswith("_text")} for c in commands],
        "audit": audit_summary,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(out_dir, summary)

    print(f"Physical system check: {'PASS' if all_ok else 'FAIL'}")
    print(f"Output: {out_dir}")
    print(f"Audit: {audit_summary['audit_dir']}")
    print(
        "Audit counts: "
        f"static_fail={audit_summary['static_fail']} "
        f"component_fail={audit_summary['component_fail']} "
        f"severe={audit_summary['severe']} fatal={audit_summary['fatal']} "
        f"warnings={audit_summary['warnings']}"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
