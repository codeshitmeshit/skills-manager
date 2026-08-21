#!/usr/bin/env python3
"""Start the fixed-port dashboard and return only after it is ready."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import cosh_hammer_state as state  # noqa: E402


FIXED_PORT = 57172


def wait_until_ready(
    health_url: str, *, project: Path, work: str, timeout: float = 10
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") != "ready":
                raise state.CoshHammerError("观察板健康检查未返回 ready")
            if payload.get("project") != str(project.resolve()) or payload.get("work") != work:
                raise state.CoshHammerError("固定端口已被其他 project/work 的观察板占用")
            return payload
        except state.CoshHammerError:
            raise
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.1)
    raise state.CoshHammerError(f"观察板未在期限内就绪：{last_error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--hammer-root", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1",))
    parser.add_argument("--port", type=int, default=FIXED_PORT, choices=(FIXED_PORT,))
    parser.add_argument("--no-open", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project = args.project.resolve()
    state.validate_hammer_root(args.hammer_root)
    # work 必须先由 init 固化，防止启动一个没有需求身份的旁路服务。
    launch = state.plugin_root(project, args.work) / "launch" / "launch.json"
    if not launch.is_file():
        raise SystemExit("work 尚未 init，不能启动观察板")
    health = f"http://{args.host}:{args.port}/healthz?work={args.work}"
    url = f"http://{args.host}:{args.port}/?work={args.work}"
    reused = False
    try:
        wait_until_ready(health, project=project, work=args.work, timeout=0.3)
        reused = True
        process = None
    except state.CoshHammerError as error:
        if "其他 project/work" in str(error):
            raise SystemExit(str(error)) from error
        root = state.plugin_root(project, args.work)
        log_path = root / "dashboard" / "server.log"
        state._assert_plugin_destination(root, log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("ab")
        command = [
            sys.executable,
            str(SCRIPT_DIR / "serve_cosh_hammer_dashboard.py"),
            "--project",
            str(project),
            "--work",
            args.work,
            "--hammer-root",
            str(args.hammer_root.resolve()),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log.close()
        try:
            wait_until_ready(health, project=project, work=args.work)
        except Exception:
            if process.poll() is None:
                process.terminate()
            raise
    state.record_dashboard_runtime(
        project,
        args.work,
        {
            "status": "ready",
            "pid": process.pid if process else None,
            "reused": reused,
            "url": url,
            "ready_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    if not args.no_open:
        webbrowser.open(url)
    print(f"READY {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
