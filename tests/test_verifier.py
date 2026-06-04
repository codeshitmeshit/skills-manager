from __future__ import annotations

import pathlib
import tempfile
import unittest

from cosh_skills.scanner import Skill
from cosh_skills.verifier import VerificationError, verify_cli_recognition, verify_installation


def make_installed_skill(root: pathlib.Path, name: str) -> Skill:
    source = root / "repo" / name
    target = root / "target" / name
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    (source / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (target / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return Skill(name=name, path=source)


class VerifierTest(unittest.TestCase):
    def test_file_verification_passes_for_installed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_installed_skill(root, "git-helper")

            result = verify_installation([skill], root / "target")

        self.assertTrue(result.file_verified)
        self.assertEqual(result.warnings, [])

    def test_file_verification_fails_when_skill_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            source = root / "repo" / "git-helper"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("# git\n", encoding="utf-8")
            skill = Skill(name="git-helper", path=source)

            with self.assertRaises(VerificationError) as caught:
                verify_installation([skill], root / "target")

        self.assertIn("同步失败", str(caught.exception))
        self.assertIn("git-helper", str(caught.exception))

    def test_file_verification_fails_when_skill_md_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            source = root / "repo" / "git-helper"
            target = root / "target" / "git-helper"
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            (source / "SKILL.md").write_text("# git\n", encoding="utf-8")
            skill = Skill(name="git-helper", path=source)

            with self.assertRaises(VerificationError) as caught:
                verify_installation([skill], root / "target")

        self.assertIn("SKILL.md", str(caught.exception))

    def test_cli_recognition_placeholder_fails_with_warning(self) -> None:
        result = verify_cli_recognition("codex", ["git-helper"])

        self.assertFalse(result.recognized)
        self.assertIn("暂未实现", result.message)

    def test_verify_option_does_not_block_when_cli_recognition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_installed_skill(root, "git-helper")

            result = verify_installation(
                [skill],
                root / "target",
                cli_name="codex",
                verify_cli=True,
                strict_verify=False,
            )

        self.assertTrue(result.file_verified)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("CLI 识别校验未通过", result.warnings[0])

    def test_strict_verify_blocks_when_cli_recognition_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_installed_skill(root, "git-helper")

            with self.assertRaises(VerificationError) as caught:
                verify_installation(
                    [skill],
                    root / "target",
                    cli_name="codex",
                    verify_cli=True,
                    strict_verify=True,
                )

        self.assertIn("CLI 识别校验失败", str(caught.exception))

    def test_custom_cli_recognizer_can_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_installed_skill(root, "git-helper")

            result = verify_installation(
                [skill],
                root / "target",
                cli_name="codex",
                verify_cli=True,
                strict_verify=True,
                cli_recognizer=lambda cli_name, skill_names: (True, "ok"),
            )

        self.assertTrue(result.cli_verified)
        self.assertEqual(result.warnings, [])


if __name__ == "__main__":
    unittest.main()
