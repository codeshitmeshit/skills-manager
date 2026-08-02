from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

from internal.git_ops import (
    GitError,
    GitUpdateResult,
    current_branch,
    default_branch,
    ensure_git_repo,
    ensure_repo_path,
    ensure_worktree_clean,
    update_repo,
)
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


class GitOpsTest(unittest.TestCase):
    def test_repo_path_missing_value_fails(self) -> None:
        with self.assertRaises(GitError) as caught:
            ensure_repo_path(None)

        self.assertIn("未配置 skill 仓库路径", str(caught.exception))

    def test_repo_path_that_does_not_exist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = pathlib.Path(tmpdir) / "missing"

            with self.assertRaises(GitError) as caught:
                ensure_repo_path(str(missing))

        self.assertIn("不存在", str(caught.exception))

    def test_non_git_repo_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)

            with self.assertRaises(GitError) as caught:
                ensure_git_repo(repo)

        self.assertIn("不是合法 git 仓库", str(caught.exception))

    def test_dirty_worktree_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)
            git(repo, "init", "-b", "main")
            (repo / "file.txt").write_text("initial\n", encoding="utf-8")
            commit_all(repo, "initial")
            (repo / "file.txt").write_text("dirty\n", encoding="utf-8")

            with self.assertRaises(GitError) as caught:
                ensure_worktree_clean(repo)

        self.assertIn("存在未提交修改", str(caught.exception))

    def test_default_branch_is_read_from_origin_head(self) -> None:
        with self.remote_repo() as repo:
            self.assertEqual(default_branch(repo), "main")

    def test_default_branch_falls_back_to_current_upstream(self) -> None:
        with self.remote_repo() as repo:
            git(repo, "remote", "set-head", "origin", "-d")

            self.assertEqual(default_branch(repo), "main")

    def test_default_branch_falls_back_to_origin_main_ref(self) -> None:
        with self.remote_repo() as repo:
            git(repo, "remote", "set-head", "origin", "-d")
            git(repo, "branch", "--unset-upstream")

            self.assertEqual(default_branch(repo), "main")

    def test_update_repo_fetches_pulls_and_switches_to_default_branch(self) -> None:
        with self.remote_repo() as repo:
            git(repo, "checkout", "-b", "feature")
            before = git(repo, "rev-parse", "main").stdout.strip()
            self.add_remote_commit(repo, "remote update")

            result = update_repo(repo)

            self.assertIsInstance(result, GitUpdateResult)
            self.assertEqual(current_branch(repo), "main")
            self.assertNotEqual(result.after_commit, before)
            self.assertTrue(result.updated)
            self.assertEqual(result.default_branch, "main")

    def test_update_repo_without_new_commits_still_succeeds(self) -> None:
        with self.remote_repo() as repo:
            before = git(repo, "rev-parse", "HEAD").stdout.strip()

            result = update_repo(repo)

            self.assertFalse(result.updated)
            self.assertEqual(result.before_commit, before)
            self.assertEqual(result.after_commit, before)

    def test_update_repo_local_ahead_requires_force(self) -> None:
        with self.remote_repo() as repo:
            (repo / "skill.txt").write_text("local ahead\n", encoding="utf-8")
            commit_all(repo, "local ahead")

            with self.assertRaises(GitError) as caught:
                update_repo(repo)

        self.assertIn("本地提交领先远程", str(caught.exception))
        self.assertIn("--force", str(caught.exception))

    def test_update_repo_local_ahead_succeeds_with_force(self) -> None:
        with self.remote_repo() as repo:
            (repo / "skill.txt").write_text("local ahead\n", encoding="utf-8")
            local_commit = commit_all(repo, "local ahead")

            result = update_repo(repo, force=True)

            self.assertFalse(result.updated)
            self.assertEqual(result.before_commit, local_commit)
            self.assertEqual(result.after_commit, local_commit)

    def test_pull_conflict_fails_with_manual_resolution_message(self) -> None:
        with self.remote_repo() as repo:
            (repo / "skill.txt").write_text("local change\n", encoding="utf-8")
            commit_all(repo, "local conflicting change")
            self.add_remote_commit(repo, "remote conflicting change", content="remote change\n")

            with self.assertRaises(GitError) as caught:
                update_repo(repo)

        self.assertIn("git pull 发生冲突", str(caught.exception))

    def remote_repo(self) -> "_RemoteRepo":
        return _RemoteRepo()

    def add_remote_commit(
        self,
        repo: pathlib.Path,
        message: str,
        *,
        content: str = "remote update\n",
    ) -> str:
        remote_url = git(repo, "remote", "get-url", "origin").stdout.strip()
        with GitTemporaryDirectory() as tmpdir:
            work = pathlib.Path(tmpdir) / "remote-work"
            subprocess.run(
                ["git", "clone", remote_url, str(work)],
                check=True,
                capture_output=True,
                text=True,
            )
            (work / "skill.txt").write_text(content, encoding="utf-8")
            commit = commit_all(work, message)
            git(work, "push", "origin", "main")
            return commit


class _RemoteRepo:
    def __enter__(self) -> pathlib.Path:
        self.tmp = GitTemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        seed = root / "seed"
        remote = root / "remote.git"
        clone = root / "clone"

        seed.mkdir()
        git(seed, "init", "-b", "main")
        (seed / "skill.txt").write_text("initial\n", encoding="utf-8")
        commit_all(seed, "initial")
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
