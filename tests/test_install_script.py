from __future__ import annotations

import os
import pathlib
import stat
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install.sh"


class InstallScriptTest(unittest.TestCase):
    def run_install_script(self) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            log_path = tmp_path / "python-args.log"
            fake_python = bin_dir / "python3"
            fake_python.write_text(
                "#!/usr/bin/env sh\n"
                "printf '%s\\n' \"$@\" >> \"$FAKE_PYTHON_LOG\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["FAKE_PYTHON_LOG"] = str(log_path)
            env["HOME"] = str(tmp_path / "home")

            result = subprocess.run(
                [str(INSTALL_SCRIPT)],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            result.python_log = log_path.read_text(encoding="utf-8")
            result.home_path = pathlib.Path(env["HOME"])
            return result

    def test_install_script_exists(self) -> None:
        self.assertTrue(INSTALL_SCRIPT.exists())

    def test_install_script_runs_without_arguments(self) -> None:
        result = self.run_install_script()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_script_installs_editable_package_dependencies(self) -> None:
        result = self.run_install_script()

        self.assertIn("-m\npip\ninstall\n-e\n", result.python_log)
        self.assertIn(str(ROOT), result.python_log)

    def test_install_script_does_not_request_business_parameters(self) -> None:
        result = self.run_install_script()
        output = result.stdout + result.stderr

        self.assertNotIn("repo_path", output)
        self.assertNotIn("skills_path", output)
        self.assertNotIn("--cli", output)

    def test_install_script_prints_zsh_and_bash_alias_guidance(self) -> None:
        result = self.run_install_script()

        self.assertIn("~/.zshrc", result.stdout)
        self.assertIn("~/.bashrc", result.stdout)
        self.assertIn("alias cosh-skills=", result.stdout)
        self.assertIn("python3 -m internal.cli", result.stdout)

    def test_install_script_does_not_modify_shell_rc_files(self) -> None:
        result = self.run_install_script()

        self.assertFalse((result.home_path / ".zshrc").exists())
        self.assertFalse((result.home_path / ".bashrc").exists())

    def test_install_script_rejects_unexpected_arguments(self) -> None:
        result = subprocess.run(
            [str(INSTALL_SCRIPT), "--cli", "codex"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not accept arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
