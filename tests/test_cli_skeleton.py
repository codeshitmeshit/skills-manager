from __future__ import annotations

import subprocess
import sys
import unittest

from cosh_skills.cli import build_parser, main


class CliSkeletonTest(unittest.TestCase):
    def test_build_parser_uses_expected_program_name(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.prog, "cosh-skills")

    def test_main_without_args_prints_help_successfully(self) -> None:
        self.assertEqual(main([]), 0)

    def test_module_help_runs_successfully(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cosh_skills.cli", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("cosh-skills", result.stdout)
        self.assertIn("用法：", result.stdout)


if __name__ == "__main__":
    unittest.main()
