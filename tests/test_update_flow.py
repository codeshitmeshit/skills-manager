from __future__ import annotations

import io
import pathlib
import subprocess
import tempfile
import unittest

from cosh_skills.config import load_config, save_config
from cosh_skills.git_ops import GitError
from cosh_skills.update import run_update
from cosh_skills.verifier import VerificationError


def git(repo: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def commit_all(repo: pathlib.Path, message: str) -> str:
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Test User",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        message,
    )
    return git(repo, "rev-parse", "HEAD").stdout.strip()


class UpdateFlowTest(unittest.TestCase):
    def test_update_without_git_changes_still_syncs_and_updates_config(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            skills_path = home / "codex-skills"
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(skills_path)
            save_config(config, home=home)
            output = io.StringIO()

            result = run_update(
                cli_name="codex",
                home=home,
                output=output,
                use_rsync=False,
            )
            saved = load_config(home=home)

            self.assertFalse(result.git_updated)
            self.assertEqual(result.synced_count, 1)
            self.assertTrue((skills_path / "git-helper" / "SKILL.md").is_file())
            self.assertEqual(saved["last_repo_commit"], result.commit)
            self.assertEqual(saved["cli"]["codex"]["last_commit"], result.commit)
            self.assertIsNotNone(saved["cli"]["codex"]["last_updated_at"])
            self.assertEqual(saved["cli"]["codex"]["managed_skills"], ["git-helper"])
            self.assertIn("[1/6] 读取配置", output.getvalue())
            self.assertIn("完成：已同步 1 个 skill 到 codex。", output.getvalue())

    def test_update_pulls_git_changes_then_syncs(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            skills_path = home / "codex-skills"
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(skills_path)
            save_config(config, home=home)
            before = git(repo, "rev-parse", "HEAD").stdout.strip()
            remote_commit = add_remote_skill(repo, "doc-helper")

            result = run_update(
                cli_name="codex",
                home=home,
                output=io.StringIO(),
                use_rsync=False,
            )

            self.assertTrue(result.git_updated)
            self.assertNotEqual(result.commit, before)
            self.assertEqual(result.commit, remote_commit)
            self.assertTrue((skills_path / "git-helper" / "SKILL.md").is_file())
            self.assertTrue((skills_path / "doc-helper" / "SKILL.md").is_file())

    def test_repo_path_argument_is_persisted_after_success(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            config = load_config(home=home)
            config["cli"]["codex"]["skills_path"] = str(home / "codex-skills")
            save_config(config, home=home)

            run_update(
                cli_name="codex",
                repo_path=repo,
                home=home,
                output=io.StringIO(),
                use_rsync=False,
            )

            self.assertEqual(load_config(home=home)["repo_path"], str(repo))

    def test_repo_path_argument_is_persisted_before_later_update_failure(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            config = load_config(home=home)
            config["cli"]["codex"]["skills_path"] = str(home / "codex-skills")
            save_config(config, home=home)
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

            with self.assertRaises(GitError):
                run_update(
                    cli_name="codex",
                    repo_path=repo,
                    home=home,
                    output=io.StringIO(),
                    use_rsync=False,
                )

            self.assertEqual(load_config(home=home)["repo_path"], str(repo))

    def test_strict_verify_failure_does_not_write_success_state(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(home / "codex-skills")
            save_config(config, home=home)

            with self.assertRaises(VerificationError):
                run_update(
                    cli_name="codex",
                    home=home,
                    output=io.StringIO(),
                    use_rsync=False,
                    verify_cli=True,
                    strict_verify=True,
                )
            saved = load_config(home=home)

        self.assertIsNone(saved["last_repo_commit"])
        self.assertIsNone(saved["cli"]["codex"]["last_commit"])
        self.assertIsNone(saved["cli"]["codex"]["last_updated_at"])
        self.assertEqual(saved["cli"]["codex"]["managed_skills"], [])

    def test_step_logs_include_all_update_phases(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(home / "codex-skills")
            save_config(config, home=home)
            output = io.StringIO()

            run_update(
                cli_name="codex",
                home=home,
                output=output,
                use_rsync=False,
            )
            text = output.getvalue()

        for step in (
            "[1/6] 读取配置",
            "[2/6] 检查 skill 仓库",
            "[3/6] 更新 skill 仓库",
            "[4/6] 扫描合法 skill",
            "[5/6] 同步到 codex",
            "[6/6] 校验安装结果",
        ):
            self.assertIn(step, text)


def add_remote_skill(repo: pathlib.Path, name: str) -> str:
    remote_url = git(repo, "remote", "get-url", "origin").stdout.strip()
    with tempfile.TemporaryDirectory() as tmpdir:
        work = pathlib.Path(tmpdir) / "remote-work"
        subprocess.run(
            ["git", "clone", remote_url, str(work)],
            check=True,
            capture_output=True,
            text=True,
        )
        skill = work / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
        commit = commit_all(work, f"add {name}")
        git(work, "push", "origin", "main")
        return commit


class _RemoteSkillRepo:
    def __enter__(self) -> pathlib.Path:
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        seed = root / "seed"
        remote = root / "remote.git"
        clone = root / "clone"

        skill = seed / "skills" / "git-helper"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# git-helper\n", encoding="utf-8")
        git(seed, "init", "-b", "main")
        commit_all(seed, "initial skill")
        git(seed, "clone", "--bare", ".", str(remote))
        subprocess.run(
            ["git", "clone", str(remote), str(clone)],
            check=True,
            capture_output=True,
            text=True,
        )
        git(clone, "remote", "set-head", "origin", "-a")
        self.path = clone
        return clone

    def __exit__(self, exc_type, exc, tb) -> None:
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
