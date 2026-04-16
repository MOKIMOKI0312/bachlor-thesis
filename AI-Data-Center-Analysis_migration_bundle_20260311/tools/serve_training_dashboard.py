import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sinergym.utils.training_monitor import (
    build_dashboard_snapshot,
    build_group_snapshot,
    discover_job_groups,
    discover_training_jobs,
)


class DashboardHandler(BaseHTTPRequestHandler):
    repo_root: Path = Path.cwd()
    html_path: Path = Path(__file__).with_name("training_dashboard.html")
    compare_html_path: Path = Path(__file__).with_name("training_compare_dashboard.html")

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        body = self.html_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_compare_html(self):
        body = self.compare_html_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _resolve_manifest(self, query):
        manifest_values = query.get("manifest", [])
        if manifest_values:
            manifest_path = Path(manifest_values[0]).resolve()
            if manifest_path.exists():
                return manifest_path

        job_values = query.get("job", [])
        if not job_values:
            return None

        job_name = job_values[0]
        for item in discover_training_jobs(self.repo_root):
            if item["job_name"] == job_name:
                return Path(item["manifest_path"])
        return None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send_html()
        if parsed.path in ("/compare", "/compare.html"):
            return self._send_compare_html()

        if parsed.path == "/api/jobs":
            jobs = discover_training_jobs(self.repo_root)
            return self._send_json({"repo_root": str(self.repo_root), "jobs": jobs})

        if parsed.path == "/api/job-groups":
            groups = discover_job_groups(self.repo_root)
            return self._send_json({"repo_root": str(self.repo_root), "groups": groups})

        if parsed.path == "/api/snapshot":
            query = parse_qs(parsed.query)
            manifest_path = self._resolve_manifest(query)
            if manifest_path is None:
                return self._send_json({"error": "job or manifest query parameter is required"}, status=HTTPStatus.BAD_REQUEST)
            try:
                snapshot = build_dashboard_snapshot(manifest_path=manifest_path, persist=True)
            except FileNotFoundError:
                return self._send_json({"error": f"manifest not found: {manifest_path}"}, status=HTTPStatus.NOT_FOUND)
            except json.JSONDecodeError:
                return self._send_json({"error": f"manifest is invalid JSON: {manifest_path}"}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json(snapshot)

        if parsed.path == "/api/group-snapshot":
            query = parse_qs(parsed.query)
            prefix = query.get("prefix", [None])[0]
            jobs = query.get("job", [])
            try:
                snapshot = build_group_snapshot(self.repo_root, prefix=prefix, job_names=jobs or None)
            except ValueError as exc:
                return self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return self._send_json(snapshot)

        self._send_json({"error": f"Unknown route: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--compare-prefix")
    args = parser.parse_args()

    DashboardHandler.repo_root = args.repo.resolve()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    dashboard_url = f"http://{args.host}:{args.port}/"
    if args.job:
        dashboard_url += f"?job={args.job}"
    elif args.compare_prefix:
        dashboard_url = f"http://{args.host}:{args.port}/compare?prefix={args.compare_prefix}"
    print(
        json.dumps(
            {
                "repo_root": str(DashboardHandler.repo_root),
                "dashboard_url": dashboard_url,
                "jobs_api": f"http://{args.host}:{args.port}/api/jobs",
            },
            indent=2,
        ),
        flush=True,
    )
    if args.open_browser:
        webbrowser.open(dashboard_url)
    server.serve_forever()


if __name__ == "__main__":
    main()
