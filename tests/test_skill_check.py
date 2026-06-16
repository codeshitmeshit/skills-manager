from __future__ import annotations

import pathlib
import tempfile
import unittest

from internal.skill_check import SkillCheckError, check_skills, check_skills_or_raise


class SkillCheckTest(unittest.TestCase):
    def test_valid_skill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: git-helper\n"
                "description: Help with git workflows.\n"
                "---\n\n"
                "# Git Helper\n\n"
                "Use this skill for git workflow help.\n",
                encoding="utf-8",
            )

            result = check_skills(repo)

        self.assertTrue(result.ok)
        self.assertEqual(result.checked, 1)
        self.assertEqual(result.errors, [])

    def test_valid_cli_scope_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: git-helper\n"
                "description: Help with git workflows.\n"
                "cli_scope:\n"
                "  - cursor\n"
                "  - hermes\n"
                "---\n\n"
                "# Git Helper\n",
                encoding="utf-8",
            )

            result = check_skills(repo)

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_invalid_cli_scope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: git-helper\n"
                "description: Help with git workflows.\n"
                "cli_scope: unknown\n"
                "---\n\n"
                "# Git Helper\n",
                encoding="utf-8",
            )

            result = check_skills(repo)

        self.assertFalse(result.ok)
        self.assertIn("cli_scope 必须是 CLI 名称列表", "\n".join(result.errors))

    def test_unknown_cli_scope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: git-helper\n"
                "description: Help with git workflows.\n"
                "cli_scope: [not-a-cli]\n"
                "---\n\n"
                "# Git Helper\n",
                encoding="utf-8",
            )

            result = check_skills(repo)

        self.assertFalse(result.ok)
        self.assertIn("cli_scope 包含不支持的 CLI", "\n".join(result.errors))

    def test_missing_skills_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_skills(pathlib.Path(tmpdir))

        self.assertFalse(result.ok)
        self.assertIn("未找到 skills 目录", result.errors[0])

    def test_missing_skill_md_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            (repo / "skills" / "git-helper").mkdir(parents=True)

            result = check_skills(repo)

        self.assertFalse(result.ok)
        self.assertIn("缺少 SKILL.md", result.errors[0])

    def test_invalid_name_and_metadata_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "Bad_Name"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: other-name\n"
                "description: \n"
                "---\n\n"
                "No title here.\n",
                encoding="utf-8",
            )

            result = check_skills(repo)

        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("目录名只能使用小写字母", joined)
        self.assertIn("name 必须等于目录名", joined)
        self.assertIn("必须提供非空 description", joined)
        self.assertIn("正文必须包含一级标题", joined)

    def test_missing_frontmatter_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            skill = repo / "skills" / "git-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Git Helper\n", encoding="utf-8")

            result = check_skills(repo)

        self.assertFalse(result.ok)
        self.assertIn("YAML front matter", "\n".join(result.errors))

    def test_check_skills_or_raise_uses_combined_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)

            with self.assertRaises(SkillCheckError) as caught:
                check_skills_or_raise(repo)

        self.assertIn("skill 标准检查失败", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
