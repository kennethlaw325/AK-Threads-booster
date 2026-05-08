"""Serve the AK Threads Booster local panel.

This is intentionally dependency-free so any user can launch the optional UI
without installing a frontend toolchain.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path


def find_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).expanduser().resolve()
    else:
        cwd = Path.cwd().resolve()
        root = cwd if (cwd / "panel" / "index.html").exists() else Path(__file__).resolve().parents[1]

    if not (root / "panel" / "index.html").exists():
        raise SystemExit(f"Could not find panel/index.html under {root}")
    return root


def find_port(host: str, requested: int) -> int:
    for port in range(requested, requested + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No available port found from {requested} to {requested + 49}")


def newest_file(root: Path, names: tuple[str, ...], max_depth: int = 3) -> Path | None:
    """Find newest file in `root` matching one of `names`.

    Bounded recursion (default 3 levels) keeps `node_modules`, vault
    folders, and other deep trees from blowing up the manifest endpoint
    on rich workspaces. The data files we actually care about all live
    within 1-2 levels of the workspace root.
    """
    if not root.exists():
        return None
    matches: list[Path] = []
    wanted = set(names)
    root_depth = len(root.parts)

    def _walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for child in directory.iterdir():
                if child.is_dir():
                    _walk(child, depth + 1)
                elif child.name in wanted and ".legacy-" not in child.name:
                    matches.append(child)
        except (PermissionError, OSError):
            return

    _walk(root, 0)
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def pick_data_root(root: Path, explicit_data_root: str | None) -> Path:
    candidates: list[Path] = []
    if explicit_data_root:
        candidates.append(Path(explicit_data_root).expanduser())
    env_root = os.environ.get("AK_THREADS_DATA_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend([Path.cwd(), root, root.parent / "threads data"])

    for candidate in candidates:
        resolved = candidate.resolve()
        if newest_file(resolved, ("threads_daily_tracker.json",)):
            return resolved
    return candidates[0].resolve() if candidates else root


def resolve_data_files(data_root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    tracker = newest_file(data_root, ("threads_daily_tracker.json",))
    if tracker:
        files["tracker"] = tracker

    text_keys = {
        "next_move_queue.md": ("next_move_queue.md",),
        "account_state.md": ("account_state.md",),
        "brand_voice.md": ("brand_voice.md",),
        "style_guide.md": ("style_guide.md", "寫作風格指南.md"),
        "posts_by_date.md": ("posts_by_date.md", "歷史貼文-按時間排序.md"),
        "posts_by_topic.md": ("posts_by_topic.md", "歷史貼文-按主題分類.md"),
        "comments.md": ("comments.md", "留言記錄.md"),
    }
    for key, names in text_keys.items():
        found = newest_file(data_root, names)
        if found:
            files[key] = found
    return files


class PanelRequestHandler(http.server.SimpleHTTPRequestHandler):
    data_files: dict[str, Path] = {}
    data_root: Path | None = None
    skill_root: Path | None = None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/__data/manifest.json":
            self.send_manifest()
            return
        if parsed.path == "/__data/tracker.json":
            self.send_data_file("tracker", "application/json; charset=utf-8")
            return
        if parsed.path.startswith("/__data/text/"):
            key = urllib.parse.unquote(parsed.path.removeprefix("/__data/text/"))
            self.send_data_file(key, "text/plain; charset=utf-8")
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/__action/rebuild-compiled":
            self.rebuild_compiled()
            return
        self.send_error(404, "Action not found")

    def send_data_file(self, key: str, content_type: str) -> None:
        path = self.data_files.get(key)
        if not path or not path.exists():
            self.send_error(404, "Data file not found")
            return
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status: int, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def rebuild_compiled(self) -> None:
        tracker = self.data_files.get("tracker")
        root = self.skill_root
        if not tracker or not tracker.exists() or not root:
            self.send_json(404, {"ok": False, "error": "Tracker or skill root not found"})
            return
        script = root / "scripts" / "build_compiled_memory.py"
        if not script.exists():
            self.send_json(404, {"ok": False, "error": "build_compiled_memory.py not found"})
            return
        output_dir = tracker.parent / "compiled"
        command = [sys.executable, str(script), "--tracker", str(tracker), "--output-dir", str(output_dir)]
        # 300s timeout: build_voice_distillation + compiled-memory builders
        # process the entire post history. On a year of daily posts this
        # routinely exceeds the previous 60s ceiling, so the request handler
        # would crash with `subprocess.TimeoutExpired` instead of returning
        # a structured error.
        try:
            completed = subprocess.run(
                command, cwd=str(root), capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired as exc:
            self.send_json(
                504,
                {
                    "ok": False,
                    "error": "build_compiled_memory.py exceeded the 300s rebuild timeout",
                    "stdout": (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                },
            )
            return
        if completed.returncode != 0:
            self.send_json(500, {"ok": False, "error": completed.stderr or completed.stdout})
            return
        if self.data_root:
            self.data_files.update(resolve_data_files(self.data_root))
        self.send_json(200, {"ok": True, "output_dir": str(output_dir), "stdout": completed.stdout})

    def send_manifest(self) -> None:
        required = [
            "tracker",
            "brand_voice.md",
            "style_guide.md",
            "posts_by_date.md",
            "posts_by_topic.md",
            "comments.md",
            "next_move_queue.md",
            "account_state.md",
        ]
        files = {}
        for key in required:
            path = self.data_files.get(key)
            files[key] = {
                "found": bool(path and path.exists()),
                "path": str(path) if path else "",
                "bytes": path.stat().st_size if path and path.exists() else 0,
            }
        payload = json.dumps(
            {
                "data_root": str(self.data_root or ""),
                "files": files,
                "found_count": sum(1 for item in files.values() if item["found"]),
                "required_count": len(required),
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the optional local panel.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="Preferred port. Default: 8765")
    parser.add_argument("--root", help="Workspace root containing panel/index.html")
    parser.add_argument("--data-root", help="User data root. The server searches it for tracker and companion files.")
    parser.add_argument("--open", action="store_true", help="Open the panel in the default browser")
    args = parser.parse_args()

    root = find_root(args.root)
    data_root = pick_data_root(root, args.data_root)
    data_files = resolve_data_files(data_root)
    port = find_port(args.host, args.port)
    handler_class = type(
        "BoundPanelRequestHandler",
        (PanelRequestHandler,),
        {"data_files": data_files, "data_root": data_root, "skill_root": root},
    )
    handler = functools.partial(handler_class, directory=str(root))

    # ThreadingTCPServer so a slow request (e.g. compiled-memory rebuild)
    # does not block the manifest endpoint the panel polls. Single-threaded
    # TCPServer froze the UI for the duration of every rebuild.
    with socketserver.ThreadingTCPServer((args.host, port), handler) as server:
        server.daemon_threads = True
        url = f"http://{args.host}:{port}/panel/index.html"
        print(f"AK Threads Booster panel: {url}", flush=True)
        print(f"Data root: {data_root}", flush=True)
        if data_files:
            for key, path in sorted(data_files.items()):
                print(f"Data file [{key}]: {path}", flush=True)
        else:
            print("Data file: none found; panel will use sample data.", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
