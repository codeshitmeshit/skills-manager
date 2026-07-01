from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CliCommandTest(unittest.TestCase):
    def run_cli(
        self,
        *args: str,
        home: pathlib.Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if home is not None:
            env["HOME"] = str(home)
        return subprocess.run(
            [sys.executable, "-m", "internal.cli", *args],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_update_cli_codex_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "codex", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_cli_claude_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "claude", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_cli_qwen_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "qwen", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_cli_openclaw_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "openclaw", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_cli_hermes_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "hermes", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_cli_cursor_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("update", "--cli", "cursor", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置 skill 仓库路径", result.stderr)

    def test_update_rejects_unsupported_cli(self) -> None:
        result = self.run_cli("update", "--cli", "all")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("当前版本只支持", result.stderr)
        self.assertIn("codex", result.stderr)
        self.assertIn("claude", result.stderr)
        self.assertIn("qwen", result.stderr)
        self.assertIn("openclaw", result.stderr)
        self.assertIn("hermes", result.stderr)
        self.assertIn("cursor", result.stderr)

    def test_update_requires_cli(self) -> None:
        result = self.run_cli("update")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--cli", result.stderr)

    def test_init_cli_codex_writes_hook_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "codex", home=home)

            hooks = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
            config = json.loads((home / ".cosh-skills" / "config.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex 需要通过 /hooks 信任", result.stdout)
        self.assertIn("-m internal.hook_runner --cli codex", hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"])
        self.assertEqual(config["repo_path"], str(ROOT))
        self.assertEqual(config["cli"]["codex"]["skills_path"], "~/.codex/skills")

    def test_init_cli_claude_is_not_implemented_yet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("init", "--cli", "claude", home=pathlib.Path(tmpdir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("暂只支持 codex、qwen、openclaw", result.stderr)

    def test_init_cli_qwen_writes_hook_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "qwen", home=home)

            settings = json.loads((home / ".qwen" / "settings.json").read_text(encoding="utf-8"))
            config = json.loads((home / ".cosh-skills" / "config.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Codex 需要通过 /hooks 信任", result.stdout)
        self.assertIn("-m internal.hook_runner --cli qwen", settings["hooks"]["SessionStart"][0]["hooks"][0]["command"])
        self.assertEqual(config["repo_path"], str(ROOT))
        self.assertEqual(config["cli"]["qwen"]["skills_path"], "~/.qwen/skills")

    def test_init_cli_qwen_force_writes_force_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "qwen", "--force", home=home)

            settings = json.loads((home / ".qwen" / "settings.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--force", settings["hooks"]["SessionStart"][0]["hooks"][0]["command"])

    def test_init_cli_openclaw_writes_hook_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "openclaw", home=home)

            openclaw = json.loads((home / ".openclaw" / "openclaw.json").read_text(encoding="utf-8"))
            config = json.loads((home / ".cosh-skills" / "config.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Codex 需要通过 /hooks 信任", result.stdout)
        self.assertIn(
            "-m internal.hook_runner --cli openclaw",
            openclaw["hooks"]["SessionStart"][0]["hooks"][0]["command"],
        )
        self.assertEqual(config["repo_path"], str(ROOT))
        self.assertEqual(config["cli"]["openclaw"]["skills_path"], "~/.openclaw/skills")

    def test_init_cli_openclaw_force_writes_force_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "openclaw", "--force", home=home)

            openclaw = json.loads((home / ".openclaw" / "openclaw.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--force", openclaw["hooks"]["SessionStart"][0]["hooks"][0]["command"])

    def test_init_cli_force_writes_force_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            result = self.run_cli("init", "--cli", "codex", "--force", home=home)

            hooks = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--force", hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"])

    def test_update_cli_without_value_lists_supported_clis(self) -> None:
        result = self.run_cli("update", "--cli")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("参数 --cli 需要提供一个值", result.stderr)
        self.assertIn("当前版本支持", result.stderr)
        self.assertIn("codex", result.stderr)
        self.assertIn("claude", result.stderr)
        self.assertIn("openclaw", result.stderr)
        self.assertIn("hermes", result.stderr)
        self.assertIn("cursor", result.stderr)

    def test_update_rejects_first_version_unsupported_parameters(self) -> None:
        for arg in ("--branch", "--skill", "--install-mode", "--skills-path"):
            with self.subTest(arg=arg):
                result = self.run_cli("update", "--cli", "codex", arg, "value")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("无法识别的参数", result.stderr)

    def test_update_accepts_stage_three_options_then_reaches_repo_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli(
                "update",
                "--cli",
                "codex",
                "--repo-path",
                "/tmp/cosh-skills",
                "--backup",
                "--verify",
                "--strict-verify",
                "--force",
                home=pathlib.Path(tmpdir),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("无法识别的参数", result.stderr)
        self.assertIn("skill 仓库路径不存在", result.stderr)

    def test_config_get_prints_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli("config", "get", home=pathlib.Path(tmpdir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)["repo_path"])

    def test_config_set_writes_allowed_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            set_result = self.run_cli(
                "config",
                "set",
                "repo_path",
                "/tmp/repo",
                home=home,
            )
            get_result = self.run_cli("config", "get", home=home)

        self.assertEqual(set_result.returncode, 0, set_result.stderr)
        self.assertEqual(get_result.returncode, 0, get_result.stderr)
        self.assertEqual(json.loads(get_result.stdout)["repo_path"], "/tmp/repo")

    def test_config_set_rejects_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_cli(
                "config",
                "set",
                "cli.codex.unknown",
                "value",
                home=pathlib.Path(tmpdir),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("非法配置项", result.stderr)

    def test_check_repo_path_passes_for_current_repository(self) -> None:
        result = self.run_cli("check", "--repo-path", str(ROOT))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill 标准检查通过", result.stdout)


if __name__ == "__main__":
    unittest.main()
