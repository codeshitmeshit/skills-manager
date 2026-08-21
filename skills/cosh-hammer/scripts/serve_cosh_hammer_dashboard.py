#!/usr/bin/env python3
"""Serve the Cosh Hammer read-only projection and plugin-only controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import cosh_hammer_state as state  # noqa: E402


ASSET_DIR = SCRIPT_DIR.parent / "assets" / "dashboard"
FIXED_PORT = 57171
MAX_REQUEST_BYTES = 1024 * 1024


def _payload_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def make_handler(project: Path, configured_work: str | None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _work(self) -> str:
            query = parse_qs(urlparse(self.path).query)
            work = query.get("work", [configured_work])[0]
            if not work:
                raise state.CoshHammerError("缺少 work")
            return work

        def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = _payload_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/status":
                    self._json(state.build_status(project, self._work()))
                    return
                if parsed.path == "/healthz":
                    self._json(
                        {
                            "status": "ready",
                            "project": str(project.resolve()),
                            "work": self._work(),
                            "port": FIXED_PORT,
                        }
                    )
                    return
                if parsed.path == "/events":
                    self._events()
                    return
                self._asset(parsed.path)
            except (state.CoshHammerError, OSError, ValueError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/control":
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise state.CoshHammerError("请求体大小无效")
                command = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(command, dict):
                    raise state.CoshHammerError("控制请求必须是 JSON 对象")
                self._json(state.apply_control(project, self._work(), command))
            except (state.CoshHammerError, json.JSONDecodeError, ValueError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

        def _events(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            previous = None
            while True:
                try:
                    payload = state.build_status(project, self._work())
                    signature = hashlib.sha256(_payload_bytes({k: v for k, v in payload.items() if k != "read_at"})).hexdigest()
                    if signature != previous:
                        data = json.dumps(payload, ensure_ascii=False)
                        self.wfile.write(f"event: status\ndata: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        previous = signature
                    time.sleep(1)
                except (BrokenPipeError, ConnectionResetError):
                    return

        def _asset(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            candidate = (ASSET_DIR / relative).resolve()
            try:
                candidate.relative_to(ASSET_DIR.resolve())
            except ValueError as error:
                raise state.CoshHammerError("静态资源路径越界") from error
            if not candidate.is_file():
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            body = candidate.read_bytes()
            mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--work")
    parser.add_argument("--hammer-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1",))
    parser.add_argument("--port", type=int, default=FIXED_PORT, choices=(FIXED_PORT,))
    parser.add_argument("--open", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.hammer_root:
        state.validate_hammer_root(args.hammer_root)
    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.project.resolve(), args.work)
    )
    url = f"http://{args.host}:{args.port}/"
    if args.work:
        url += f"?work={args.work}"
    print(url, flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
