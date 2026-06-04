from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from cosh_skills.config import (
    ConfigError,
    DEFAULT_CONFIG,
    VALID_INSTALL_MODES,
    config_path,
    format_config_json,
    load_config,
    save_config,
    set_config_value,
)


class ConfigTest(unittest.TestCase):
    def test_config_path_defaults_to_home_cosh_skills_config_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)

            self.assertEqual(
                config_path(home=home),
                home / ".cosh-skills" / "config.json",
            )

    def test_load_config_returns_default_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(home=pathlib.Path(tmpdir))

        self.assertEqual(config, DEFAULT_CONFIG)
        self.assertIsNot(config, DEFAULT_CONFIG)

    def test_save_and_load_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            config = load_config(home=home)
            config["repo_path"] = "/tmp/repo"

            save_config(config, home=home)

            self.assertEqual(load_config(home=home)["repo_path"], "/tmp/repo")

    def test_load_config_merges_missing_default_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            path = config_path(home=home)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"repo_path": "/tmp/repo", "cli": {"codex": {}}}),
                encoding="utf-8",
            )

            config = load_config(home=home)

            self.assertEqual(config["repo_path"], "/tmp/repo")
            self.assertIn("claude", config["cli"])
            self.assertEqual(config["cli"]["codex"]["install_mode"], "auto")
            self.assertEqual(config["cli"]["codex"]["managed_skills"], [])

    def test_format_config_json_outputs_current_config(self) -> None:
        config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))
        config["repo_path"] = "/tmp/repo"

        rendered = format_config_json(config)

        self.assertEqual(json.loads(rendered)["repo_path"], "/tmp/repo")
        self.assertTrue(rendered.endswith("\n"))

    def test_set_repo_path(self) -> None:
        config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))

        set_config_value(config, "repo_path", "/tmp/repo")

        self.assertEqual(config["repo_path"], "/tmp/repo")

    def test_set_cli_skills_path(self) -> None:
        config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))

        set_config_value(config, "cli.codex.skills_path", "~/.codex/skills")
        set_config_value(config, "cli.claude.skills_path", "~/.claude/skills")

        self.assertEqual(config["cli"]["codex"]["skills_path"], "~/.codex/skills")
        self.assertEqual(config["cli"]["claude"]["skills_path"], "~/.claude/skills")

    def test_set_valid_install_modes(self) -> None:
        for mode in VALID_INSTALL_MODES:
            with self.subTest(mode=mode):
                config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))

                set_config_value(config, "cli.codex.install_mode", mode)

                self.assertEqual(config["cli"]["codex"]["install_mode"], mode)

    def test_rejects_unknown_config_key_with_allowed_keys(self) -> None:
        config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))

        with self.assertRaises(ConfigError) as caught:
            set_config_value(config, "cli.codex.unknown", "value")

        message = str(caught.exception)
        self.assertIn("非法配置项", message)
        self.assertIn("repo_path", message)
        self.assertIn("cli.codex.skills_path", message)

    def test_rejects_invalid_install_mode_with_allowed_values(self) -> None:
        config = load_config(home=pathlib.Path("/tmp/does-not-need-to-exist"))

        with self.assertRaises(ConfigError) as caught:
            set_config_value(config, "cli.codex.install_mode", "invalid")

        message = str(caught.exception)
        self.assertIn("非法 install_mode", message)
        self.assertIn("auto", message)
        self.assertIn("copy", message)
        self.assertIn("cli", message)
        self.assertIn("link", message)


if __name__ == "__main__":
    unittest.main()
