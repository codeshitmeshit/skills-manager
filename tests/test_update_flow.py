from __future__ import annotations

import io
import pathlib
import subprocess
import tempfile
import unittest

from internal.config import load_config, save_config
from internal.git_ops import GitError
from internal.update import run_update
from internal.verifier import VerificationError
from tests._temp_utils import GitTemporaryDirectory


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

    def test_update_skips_skills_outside_cli_scope(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            skills_path = home / "codex-skills"
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(skills_path)
            save_config(config, home=home)
            add_local_skill(repo, "codex-helper", cli_scope=("codex", "qwen"))
            add_local_skill(repo, "claude-helper", cli_scope=("claude",))
            commit_all(repo, "add scoped skills")
            output = io.StringIO()

            result = run_update(
                cli_name="codex",
                home=home,
                output=output,
                force=True,
                use_rsync=False,
            )
            saved = load_config(home=home)

            self.assertEqual(result.synced_count, 2)
            self.assertEqual(result.skipped_count, 1)
            self.assertTrue((skills_path / "git-helper" / "SKILL.md").is_file())
            self.assertTrue((skills_path / "codex-helper" / "SKILL.md").is_file())
            self.assertFalse((skills_path / "claude-helper").exists())
            self.assertEqual(
                saved["cli"]["codex"]["managed_skills"],
                ["codex-helper", "git-helper"],
            )
            self.assertIn("已跳过 1 个不适用于 codex 的 skill。", output.getvalue())
            self.assertIn("完成：已同步 2 个 skill 到 codex。", output.getvalue())

    def test_update_allows_openclaw_and_hermes_scoped_skill(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            openclaw_path = home / "openclaw-skills"
            hermes_path = home / "hermes-skills"
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["openclaw"]["skills_path"] = str(openclaw_path)
            config["cli"]["hermes"]["skills_path"] = str(hermes_path)
            save_config(config, home=home)
            add_local_skill(repo, "openclaw-agent-guide", cli_scope=("openclaw", "hermes"))
            commit_all(repo, "add openclaw scoped skill")

            openclaw_result = run_update(
                cli_name="openclaw",
                home=home,
                output=io.StringIO(),
                force=True,
                use_rsync=False,
            )
            hermes_result = run_update(
                cli_name="hermes",
                home=home,
                output=io.StringIO(),
                force=True,
                use_rsync=False,
            )

            self.assertEqual(openclaw_result.skipped_count, 0)
            self.assertEqual(hermes_result.skipped_count, 0)
            self.assertTrue((openclaw_path / "openclaw-agent-guide" / "SKILL.md").is_file())
            self.assertTrue((hermes_path / "openclaw-agent-guide" / "SKILL.md").is_file())

    def test_update_removes_previously_managed_skill_that_is_now_out_of_scope(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            skills_path = home / "codex-skills"
            old_skill = skills_path / "claude-helper"
            old_skill.mkdir(parents=True)
            (old_skill / "SKILL.md").write_text("# old\n", encoding="utf-8")
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(skills_path)
            config["cli"]["codex"]["managed_skills"] = ["git-helper", "claude-helper"]
            save_config(config, home=home)
            add_local_skill(repo, "claude-helper", cli_scope=("claude",))
            commit_all(repo, "add claude scoped skill")

            run_update(
                cli_name="codex",
                home=home,
                output=io.StringIO(),
                force=True,
                use_rsync=False,
            )
            saved = load_config(home=home)

            self.assertFalse(old_skill.exists())
            self.assertEqual(saved["cli"]["codex"]["managed_skills"], ["git-helper"])

    def test_update_with_force_syncs_local_ahead_commit(self) -> None:
        with _RemoteSkillRepo() as repo, tempfile.TemporaryDirectory() as tmpdir:
            home = pathlib.Path(tmpdir)
            skills_path = home / "codex-skills"
            config = load_config(home=home)
            config["repo_path"] = str(repo)
            config["cli"]["codex"]["skills_path"] = str(skills_path)
            save_config(config, home=home)
            local_skill = repo / "skills" / "local-helper"
            local_skill.mkdir()
            (local_skill / "SKILL.md").write_text("# local helper\n", encoding="utf-8")
            local_commit = commit_all(repo, "add local helper")

            result = run_update(
                cli_name="codex",
                home=home,
                output=io.StringIO(),
                force=True,
                use_rsync=False,
            )

            self.assertFalse(result.git_updated)
            self.assertEqual(result.commit, local_commit)
            self.assertTrue((skills_path / "local-helper" / "SKILL.md").is_file())

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
    with GitTemporaryDirectory() as tmpdir:
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


def add_local_skill(repo: pathlib.Path, name: str, *, cli_scope: tuple[str, ...] | None = None) -> None:
    skill = repo / "skills" / name
    skill.mkdir(parents=True)
    if cli_scope is None:
        scope_text = ""
    else:
        scope_text = "cli_scope:\n" + "".join(f"  - {item}\n" for item in cli_scope)
    (skill / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {name} description.\n"
        f"{scope_text}"
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )


class _RemoteSkillRepo:
    def __enter__(self) -> pathlib.Path:
        self.tmp = GitTemporaryDirectory()
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
