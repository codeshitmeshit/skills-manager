"""Codex hook runner for startup skill synchronization."""

from __future__ import annotations

import argparse
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from internal.errors import CoshSkillsError
from internal.update import run_update


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cosh-skills-hook")
    parser.add_argument("--cli", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output = io.StringIO()
    started_at = _timestamp()
    status = 0

    try:
        run_update(cli_name=args.cli, output=output, force=args.force)
    except CoshSkillsError as exc:
        status = int(exc.exit_code)
        output.write(str(exc) + "\n")
    except Exception as exc:  # pragma: no cover - defensive hook boundary
        status = 1
        output.write(f"未预期的 hook 错误：{exc}\n")

    finished_at = _timestamp()
    body = (
        f"[{started_at}] codex hook start\n"
        f"{output.getvalue()}"
        f"[{finished_at}] codex hook exit {status}\n"
    )
    try:
        _write_logs(body)
    except OSError as exc:
        body += f"hook 日志写入失败：{exc}\n"
    print(json.dumps({"systemMessage": body}, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_logs(body: str) -> None:
    log_dir = Path.home() / ".cosh-skills"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "codex-hook-last.log").write_text(body, encoding="utf-8")
    with (log_dir / "codex-hook.log").open("a", encoding="utf-8") as log:
        log.write(body)


if __name__ == "__main__":
    raise SystemExit(main())
