"""Command line entry point for cosh-skills."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from internal import __version__
from internal.config import (
    format_config_json,
    load_config,
    save_config,
    set_config_value,
)
from internal.errors import CoshSkillsError, ExitCode
from internal.hooks import initialize_cli_hook
from internal.skill_check import check_skills_or_raise
from internal.skill_metadata import SUPPORTED_CLIS
from internal.update import run_update


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_usage(self) -> str:
        return _localize_argparse_text(super().format_usage())

    def format_help(self) -> str:
        return _localize_argparse_text(super().format_help())

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：错误：{_localize_argparse_error(message)}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(
        prog="cosh-skills",
        description="管理本地 skill 仓库，并将 skill 同步到支持的 CLI 工具。",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="显示版本号并退出。",
    )
    subparsers = parser.add_subparsers(dest="command")

    update = subparsers.add_parser(
        "update",
        help="更新指定 CLI 的 skills。",
        description="更新本地 skill 仓库，并同步到指定 CLI 的 skills 目录。",
    )
    update.add_argument("--cli", required=True, type=_supported_cli, help="目标 CLI。")
    update.add_argument("--repo-path", help="本地 skill 仓库路径，第一次使用时可通过该参数写入配置。")
    update.add_argument("--backup", action="store_true", help="覆盖同名目标 skill 前先备份。")
    update.add_argument("--verify", action="store_true", help="同步后尝试执行 CLI 识别校验。")
    update.add_argument("--strict-verify", action="store_true", help="CLI 识别校验失败时阻断本次更新。")
    update.add_argument(
        "--force",
        action="store_true",
        help="本地分支领先远程时仍使用本地提交继续同步；不会覆盖未提交修改。",
    )
    update.set_defaults(handler=_handle_update)

    init = subparsers.add_parser(
        "init",
        help="初始化指定 CLI 的启动 hook。",
        description="为指定 CLI 添加启动 hook，并写入基础配置。",
    )
    init.add_argument("--cli", required=True, type=_supported_cli, help="目标 CLI。")
    init.add_argument(
        "--force",
        action="store_true",
        help="写入的启动 hook 使用 update --force，以便本地分支领先远程时仍继续同步。",
    )
    init.set_defaults(handler=_handle_init)

    config = subparsers.add_parser(
        "config",
        help="查看或修改 cosh-skills 配置。",
        description="查看或修改 cosh-skills 配置文件。",
    )
    config_subparsers = config.add_subparsers(dest="config_command", required=True)

    config_get = config_subparsers.add_parser("get", help="打印当前配置。")
    config_get.set_defaults(handler=_handle_config_get)

    config_set = config_subparsers.add_parser("set", help="设置允许修改的配置项。")
    config_set.add_argument("key", help="配置项名称。")
    config_set.add_argument("value", help="配置项值。")
    config_set.set_defaults(handler=_handle_config_set)

    check = subparsers.add_parser(
        "check",
        help="检查 skills 是否符合标准。",
        description="检查 skills 目录下的 SKILL.md 是否符合基础标准。",
    )
    check.add_argument("--repo-path", default=".", help="要检查的 skill 仓库路径，默认是当前目录。")
    check.set_defaults(handler=_handle_check)

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = list(argv) if argv is not None else sys.argv[1:]

    if not args:
        parser.print_help()
        return int(ExitCode.SUCCESS)

    parsed = parser.parse_args(args)
    if not hasattr(parsed, "handler"):
        parser.print_help()
        return int(ExitCode.SUCCESS)
    parsed.handler(parsed)
    return int(ExitCode.SUCCESS)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except CoshSkillsError as exc:
        print(str(exc), file=sys.stderr)
        return int(exc.exit_code)


def _supported_cli(value: str) -> str:
    if value in SUPPORTED_CLIS:
        return value
    raise argparse.ArgumentTypeError(
        "当前版本只支持：\n"
        + "\n".join(f"- {item}" for item in SUPPORTED_CLIS)
        + "\n\n暂不支持：\n"
        f"- {value}"
    )


def _handle_update(args: argparse.Namespace) -> None:
    run_update(
        cli_name=args.cli,
        repo_path=args.repo_path,
        backup=args.backup,
        verify_cli=args.verify or args.strict_verify,
        strict_verify=args.strict_verify,
        force=args.force,
    )


def _handle_init(args: argparse.Namespace) -> None:
    result = initialize_cli_hook(cli_name=args.cli, force=args.force)
    status = "已添加" if result.added else "已存在"
    print(f"{status} {result.cli_name} 启动 hook：{result.hook_path}")
    print(f"hook 命令：{result.command}")
    print(f"skill 仓库路径：{result.repo_path}")
    print(f"{result.cli_name} skills 路径：{result.skills_path}")
    if args.cli == "codex":
        print("提示：Codex 需要通过 /hooks 信任新增或变更的非托管 hook 后才会执行。")


def _handle_config_get(args: argparse.Namespace) -> None:
    print(format_config_json(load_config()), end="")


def _handle_config_set(args: argparse.Namespace) -> None:
    config = load_config()
    set_config_value(config, args.key, args.value)
    save_config(config)


def _handle_check(args: argparse.Namespace) -> None:
    result = check_skills_or_raise(args.repo_path)
    print(f"skill 标准检查通过：共检查 {result.checked} 个 skill。")


def _localize_argparse_text(text: str) -> str:
    replacements = (
        ("usage:", "用法："),
        ("positional arguments:", "位置参数："),
        ("options:", "选项："),
        ("optional arguments:", "选项："),
        ("show this help message and exit", "显示帮助信息并退出。"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def _localize_argparse_error(message: str) -> str:
    if message == "argument --cli: expected one argument":
        return "参数 --cli 需要提供一个值。\n\n当前版本支持：\n{items}".format(
            items="\n".join(f"- {item}" for item in SUPPORTED_CLIS)
        )

    replacements = (
        ("the following arguments are required:", "缺少必填参数："),
        ("unrecognized arguments:", "无法识别的参数："),
        ("invalid choice:", "非法选项："),
        ("argument", "参数"),
        ("expected one argument", "需要提供一个参数"),
        ("expected at least one argument", "至少需要提供一个参数"),
    )
    for source, target in replacements:
        message = message.replace(source, target)
    return message


if __name__ == "__main__":
    raise SystemExit(main())
