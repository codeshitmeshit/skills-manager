from __future__ import annotations

import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from internal.git_ops import GitError
from internal.hook_runner import run


class HookRunnerTest(unittest.TestCase):
    def test_hook_runner_prints_session_start_json_and_logs_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            def fake_run_update(*, output, **kwargs) -> None:
                output.write("完成：已同步 3 个 skill 到 codex。\n")

            stdout = io.StringIO()
            with patch("internal.hook_runner.Path.home", return_value=home), patch(
                "internal.hook_runner.run_update",
                fake_run_update,
            ), redirect_stdout(stdout):
                result = run(["--cli", "codex", "--force"])

            payload = json.loads(stdout.getvalue())
            last_log = (home / ".cosh-skills" / "codex-hook-last.log").read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn("systemMessage", payload)
        self.assertIn("完成：已同步 3 个 skill", payload["systemMessage"])
        self.assertIn("codex hook exit 0", payload["systemMessage"])
        self.assertEqual(last_log, payload["systemMessage"])

    def test_hook_runner_reports_update_failure_in_json_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            def fake_run_update(*, output, **kwargs) -> None:
                output.write("[1/6] 读取配置...\n")
                raise GitError("git fetch origin 执行失败：network failed")

            stdout = io.StringIO()
            with patch("internal.hook_runner.Path.home", return_value=home), patch(
                "internal.hook_runner.run_update",
                fake_run_update,
            ), redirect_stdout(stdout):
                result = run(["--cli", "codex", "--force"])

            payload = json.loads(stdout.getvalue())
            full_log = (home / ".cosh-skills" / "codex-hook.log").read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn("git fetch origin 执行失败", payload["systemMessage"])
        self.assertIn("codex hook exit 1", payload["systemMessage"])
        self.assertEqual(full_log, payload["systemMessage"])

    def test_hook_runner_still_prints_json_when_log_write_fails(self) -> None:
        def fake_run_update(*, output, **kwargs) -> None:
            output.write("完成：已同步 3 个 skill 到 codex。\n")

        stdout = io.StringIO()
        with patch("internal.hook_runner._write_logs", side_effect=OSError("read-only")), patch(
            "internal.hook_runner.run_update",
            fake_run_update,
        ), redirect_stdout(stdout):
            result = run(["--cli", "codex"])

        payload = json.loads(stdout.getvalue())

        self.assertEqual(result, 0)
        self.assertIn("hook 日志写入失败", payload["systemMessage"])


if __name__ == "__main__":
    unittest.main()
