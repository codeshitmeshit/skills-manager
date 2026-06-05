from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from internal.config import config_path, load_config
from internal.hooks import (
    HookInitError,
    build_update_command,
    initialize_cli_hook,
    install_codex_session_start_hook,
)


class HooksTest(unittest.TestCase):
    def test_build_update_command_uses_python_module_entrypoint(self) -> None:
        command = build_update_command(
            cli_name="codex",
            python_bin="/usr/bin/python3",
            repo_path=pathlib.Path("/tmp/skills-manager"),
        )

        self.assertIn("$HOME/.cosh-skills/codex-hook.log", command)
        self.assertIn("$HOME/.cosh-skills/codex-hook-last.log", command)
        self.assertIn(
            "PYTHONPATH=/tmp/skills-manager /usr/bin/python3 -m internal.cli update --cli codex",
            command,
        )
        self.assertIn("codex hook start", command)
        self.assertIn("codex hook exit", command)

    def test_build_update_command_without_repo_path_uses_python_module_entrypoint(self) -> None:
        command = build_update_command(cli_name="codex", python_bin="/usr/bin/python3")

        self.assertIn("/usr/bin/python3 -m internal.cli update --cli codex", command)

    def test_build_update_command_can_include_force(self) -> None:
        command = build_update_command(cli_name="codex", python_bin="/usr/bin/python3", force=True)

        self.assertIn("/usr/bin/python3 -m internal.cli update --cli codex --force", command)

    def test_install_codex_session_start_hook_creates_hooks_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = pathlib.Path(tmpdir) / ".codex" / "hooks.json"

            added = install_codex_session_start_hook(
                hook_path=hook_path,
                command="/usr/bin/python3 -m internal.cli update --cli codex",
            )

            document = json.loads(hook_path.read_text(encoding="utf-8"))

        self.assertTrue(added)
        self.assertEqual(
            document["hooks"]["SessionStart"][0]["hooks"][0]["command"],
            "/usr/bin/python3 -m internal.cli update --cli codex",
        )
        self.assertEqual(document["hooks"]["SessionStart"][0]["matcher"], "startup|resume")

    def test_install_codex_session_start_hook_preserves_existing_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = pathlib.Path(tmpdir) / ".codex" / "hooks.json"
            hook_path.parent.mkdir()
            hook_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]
                        }
                    }
                ),
                encoding="utf-8",
            )

            install_codex_session_start_hook(
                hook_path=hook_path,
                command="/usr/bin/python3 -m internal.cli update --cli codex",
            )

            document = json.loads(hook_path.read_text(encoding="utf-8"))

        self.assertIn("Stop", document["hooks"])
        self.assertIn("SessionStart", document["hooks"])

    def test_install_codex_session_start_hook_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = pathlib.Path(tmpdir) / ".codex" / "hooks.json"
            command = "/usr/bin/python3 -m internal.cli update --cli codex"

            first = install_codex_session_start_hook(hook_path=hook_path, command=command)
            second = install_codex_session_start_hook(hook_path=hook_path, command=command)

            document = json.loads(hook_path.read_text(encoding="utf-8"))

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(document["hooks"]["SessionStart"]), 1)

    def test_install_codex_session_start_hook_replaces_old_update_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = pathlib.Path(tmpdir) / ".codex" / "hooks.json"
            hook_path.parent.mkdir()
            hook_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [
                                {
                                    "matcher": "startup|resume",
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "/usr/bin/python3 -m internal.cli update --cli codex",
                                            "statusMessage": "Updating cosh skills",
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            command = (
                "PYTHONPATH=/tmp/skills-manager "
                "/usr/bin/python3 -m internal.cli update --cli codex"
            )

            added = install_codex_session_start_hook(hook_path=hook_path, command=command)

            document = json.loads(hook_path.read_text(encoding="utf-8"))

        self.assertTrue(added)
        self.assertEqual(len(document["hooks"]["SessionStart"]), 1)
        self.assertEqual(document["hooks"]["SessionStart"][0]["hooks"][0]["command"], command)

    def test_initialize_cli_hook_writes_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            repo_path = home / "skills-manager"

            result = initialize_cli_hook(
                cli_name="codex",
                home=home,
                repo_path=repo_path,
                python_bin="/usr/bin/python3",
            )

            config = load_config(home=home)
            hook_document = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))

        self.assertTrue(result.added)
        self.assertEqual(config["repo_path"], str(repo_path))
        self.assertEqual(config["cli"]["codex"]["skills_path"], "~/.codex/skills")
        self.assertEqual(
            hook_document["hooks"]["SessionStart"][0]["hooks"][0]["command"],
            (
                "mkdir -p \"$HOME/.cosh-skills\" && { "
                "printf '[%s] codex hook start\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\"; "
                f"PYTHONPATH={repo_path} /usr/bin/python3 -m internal.cli update --cli codex; "
                "hook_status=$?; "
                "printf '[%s] codex hook exit %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" \"$hook_status\"; "
                "} > $HOME/.cosh-skills/codex-hook-last.log 2>&1; "
                "cat $HOME/.cosh-skills/codex-hook-last.log >> $HOME/.cosh-skills/codex-hook.log; "
                "cat $HOME/.cosh-skills/codex-hook-last.log; "
                "if [ \"$hook_status\" -ne 0 ]; then "
                "printf 'cosh-skills update failed during Codex startup. See %s for full log.\\n' "
                "$HOME/.cosh-skills/codex-hook.log >&2; "
                "fi; "
                "exit \"$hook_status\""
            ),
        )

    def test_initialize_cli_hook_rejects_claude_for_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(HookInitError) as caught:
                initialize_cli_hook(cli_name="claude", home=pathlib.Path(tmpdir))

        self.assertIn("暂只支持 codex", str(caught.exception))

    def test_initialize_cli_hook_can_write_force_update_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            initialize_cli_hook(
                cli_name="codex",
                home=home,
                repo_path=home / "repo",
                python_bin="/usr/bin/python3",
                force=True,
            )

            hook_document = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))

        self.assertIn("--force", hook_document["hooks"]["SessionStart"][0]["hooks"][0]["command"])

    def test_initialize_cli_hook_does_not_overwrite_existing_skills_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            path = config_path(home=home)
            path.parent.mkdir()
            path.write_text(
                json.dumps(
                    {
                        "cli": {
                            "codex": {
                                "skills_path": "/custom/codex/skills",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            initialize_cli_hook(
                cli_name="codex",
                home=home,
                repo_path=home / "repo",
                python_bin="/usr/bin/python3",
            )

            config = load_config(home=home)

        self.assertEqual(config["cli"]["codex"]["skills_path"], "/custom/codex/skills")


if __name__ == "__main__":
    unittest.main()
