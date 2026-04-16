import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sinergym.utils.training_monitor import build_dashboard_snapshot, export_dashboard_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    snapshot = build_dashboard_snapshot(args.manifest, persist=not args.no_persist)
    exports = export_dashboard_artifacts(snapshot, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "job_name": snapshot.get("job", {}).get("job_name"),
                "workspace_path": snapshot.get("workspace", {}).get("workspace_path"),
                "summary": snapshot.get("summary", {}),
                "exports": exports,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
