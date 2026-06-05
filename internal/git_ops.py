"""Git repository checks and update flow."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from internal.errors import CoshSkillsError, ExitCode


class GitError(CoshSkillsError):
    """Raised when the skill repository cannot be updated safely."""

    exit_code = ExitCode.RUNTIME_ERROR


@dataclass(frozen=True)
class GitUpdateResult:
    default_branch: str
    before_commit: str
    after_commit: str
    updated: bool


def ensure_repo_path(repo_path: str | Path | None) -> Path:
    if repo_path is None or str(repo_path).strip() == "":
        raise GitError(
            "未配置 skill 仓库路径。\n\n"
            "第一次使用请执行：\n"
            "cosh-skills update --cli codex --repo-path /path/to/cosh-skills\n\n"
            "或者：\n"
            "cosh-skills config set repo_path /path/to/cosh-skills"
        )

    path = Path(repo_path).expanduser()
    if not path.exists():
        raise GitError(f"skill 仓库路径不存在：{path}")
    if not path.is_dir():
        raise GitError(f"skill 仓库路径不是目录：{path}")
    return path


def ensure_git_repo(repo: Path) -> None:
    result = _git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise GitError(f"当前路径不是合法 git 仓库：{repo}")


def ensure_worktree_clean(repo: Path) -> None:
    result = _git(repo, "status", "--porcelain")
    if result.stdout.strip():
        raise GitError(
            "检测到 skill 仓库存在未提交修改，已停止更新。\n"
            "请先 commit、stash 或手动处理本地修改后再执行 update。"
        )


def default_branch(repo: Path) -> str:
    result = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    ref_name = result.stdout.strip() if result.returncode == 0 else ""
    prefix = "origin/"
    if ref_name.startswith(prefix):
        return ref_name.removeprefix(prefix)

    upstream = _git(
        repo,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    upstream_ref = upstream.stdout.strip() if upstream.returncode == 0 else ""
    if upstream_ref.startswith(prefix):
        return upstream_ref.removeprefix(prefix)

    for candidate in ("main", "master"):
        remote_ref = f"refs/remotes/origin/{candidate}"
        if _git(repo, "show-ref", "--verify", "--quiet", remote_ref, check=False).returncode == 0:
            return candidate

    raise GitError(
        "无法识别 origin 默认主分支。\n"
        "请在 skill 仓库中执行：git remote set-head origin -a\n"
        "或确认当前分支已设置 upstream。"
    )


def current_branch(repo: Path) -> str:
    return _git(repo, "branch", "--show-current").stdout.strip()


def current_commit(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def checkout_branch(repo: Path, branch: str) -> None:
    if current_branch(repo) != branch:
        _git(repo, "checkout", branch)


def fetch_origin(repo: Path) -> None:
    _git(repo, "fetch", "origin")


def update_repo(repo_path: str | Path | None, *, force: bool = False) -> GitUpdateResult:
    repo = ensure_repo_path(repo_path)
    ensure_git_repo(repo)
    ensure_worktree_clean(repo)

    branch = default_branch(repo)
    checkout_branch(repo, branch)
    fetch_origin(repo)

    before = current_commit(repo, branch)
    remote_ref = f"origin/{branch}"
    remote = current_commit(repo, remote_ref)
    if before != remote and _is_ancestor(repo, remote, before):
        if not force:
            raise GitError(
                "检测到 skill 仓库本地提交领先远程，已停止更新。\n"
                "如果确认要使用本地提交同步，请添加 --force。"
            )
    elif before != remote:
        _pull(repo)

    after = current_commit(repo, branch)
    return GitUpdateResult(
        default_branch=branch,
        before_commit=before,
        after_commit=after,
        updated=before != after,
    )


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    return result.returncode == 0


def _pull(repo: Path) -> None:
    result = _git(repo, "pull", check=False)
    if result.returncode != 0:
        raise GitError(
            "git pull 发生冲突，已停止更新。\n"
            "请进入 skill 仓库手动解决冲突。"
        )


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GitError(f"git {' '.join(args)} 执行失败：{detail}")
    return result
