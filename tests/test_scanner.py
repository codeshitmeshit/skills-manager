from __future__ import annotations

import pathlib
import tempfile
import unittest

from internal.scanner import ScanError, Skill, scan_skills


class ScannerTest(unittest.TestCase):
    def test_missing_skills_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)

            with self.assertRaises(ScanError) as caught:
                scan_skills(repo)

        self.assertIn("未找到 skills 目录", str(caught.exception))
        self.assertIn(str(repo / "skills"), str(caught.exception))

    def test_scans_only_first_level_skill_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            nested = skill / "nested-helper"
            nested.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Git Helper\n", encoding="utf-8")
            (nested / "SKILL.md").write_text("# Nested\n", encoding="utf-8")

            result = scan_skills(repo)

        self.assertEqual([item.name for item in result.skills], ["git-helper"])

    def test_accepts_directories_that_contain_skill_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            source = repo / "skills" / "docs-helper"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("# Docs Helper\n", encoding="utf-8")

            result = scan_skills(repo)

        self.assertEqual(
            result.skills,
            [Skill(name="docs-helper", path=source)],
        )
        self.assertEqual(result.warnings, [])

    def test_reads_cli_scope_from_inline_frontmatter_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            source = repo / "skills" / "docs-helper"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\n"
                "name: docs-helper\n"
                "description: Help with docs.\n"
                "cli_scope: [codex, claude]\n"
                "---\n\n"
                "# Docs Helper\n",
                encoding="utf-8",
            )

            result = scan_skills(repo)

        self.assertEqual(
            result.skills,
            [Skill(name="docs-helper", path=source, cli_scope=("codex", "claude"))],
        )

    def test_reads_cli_scope_from_block_frontmatter_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            source = repo / "skills" / "docs-helper"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\n"
                "name: docs-helper\n"
                "description: Help with docs.\n"
                "cli_scope:\n"
                "  - codex\n"
                "  - cursor\n"
                "---\n\n"
                "# Docs Helper\n",
                encoding="utf-8",
            )

            result = scan_skills(repo)

        self.assertEqual(result.skills[0].cli_scope, ("codex", "cursor"))

    def test_invalid_cli_scope_fails_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            source = repo / "skills" / "docs-helper"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\n"
                "name: docs-helper\n"
                "description: Help with docs.\n"
                "cli_scope: [not-a-cli]\n"
                "---\n\n"
                "# Docs Helper\n",
                encoding="utf-8",
            )

            with self.assertRaises(ScanError) as caught:
                scan_skills(repo)

        self.assertIn("cli_scope 包含不支持的 CLI", str(caught.exception))

    def test_warns_and_skips_directory_without_skill_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            valid = repo / "skills" / "git-helper"
            invalid = repo / "skills" / "assets"
            valid.mkdir(parents=True)
            invalid.mkdir()
            (valid / "SKILL.md").write_text("# Git Helper\n", encoding="utf-8")
            (invalid / "logo.png").write_text("not a skill\n", encoding="utf-8")

            result = scan_skills(repo)

        self.assertEqual([item.name for item in result.skills], ["git-helper"])
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("assets", result.warnings[0])
        self.assertIn("SKILL.md", result.warnings[0])

    def test_ignores_regular_files_in_skills_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skills_dir = repo / "skills"
            valid = skills_dir / "git-helper"
            valid.mkdir(parents=True)
            (valid / "SKILL.md").write_text("# Git Helper\n", encoding="utf-8")
            (skills_dir / "README.md").write_text("ignore me\n", encoding="utf-8")

            result = scan_skills(repo)

        self.assertEqual([item.name for item in result.skills], ["git-helper"])
        self.assertEqual(result.warnings, [])

    def test_returns_skills_in_stable_name_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            for name in ("z-helper", "a-helper", "m-helper"):
                skill = repo / "skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

            result = scan_skills(repo)

        self.assertEqual(
            [item.name for item in result.skills],
            ["a-helper", "m-helper", "z-helper"],
        )


if __name__ == "__main__":
    unittest.main()
