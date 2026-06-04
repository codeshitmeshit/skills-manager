from __future__ import annotations

import pathlib
import tempfile
import unittest

import cosh_skills
from cosh_skills.errors import CoshSkillsError, ExitCode


class ProjectSkeletonTest(unittest.TestCase):
    def test_package_exposes_version(self) -> None:
        self.assertIsInstance(cosh_skills.__version__, str)
        self.assertTrue(cosh_skills.__version__)

    def test_pyproject_declares_console_script(self) -> None:
        pyproject = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("cosh-skills = \"cosh_skills.cli:main\"", pyproject)

    def test_base_error_uses_runtime_failure_exit_code(self) -> None:
        self.assertEqual(CoshSkillsError.exit_code, ExitCode.RUNTIME_ERROR)

    def test_tests_can_create_isolated_temp_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir) / "home"
            repo = pathlib.Path(tmpdir) / "repo"
            skills = pathlib.Path(tmpdir) / "skills"

            home.mkdir()
            repo.mkdir()
            skills.mkdir()

            self.assertTrue(home.is_dir())
            self.assertTrue(repo.is_dir())
            self.assertTrue(skills.is_dir())


if __name__ == "__main__":
    unittest.main()
