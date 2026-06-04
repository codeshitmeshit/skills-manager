from __future__ import annotations

import pathlib
import tempfile
import unittest
from unittest import mock

from internal.config import load_config
from internal.installer import InstallError, install_managed_skills, install_skills, sync_skill
from internal.scanner import Skill


def make_skill(root: pathlib.Path, name: str) -> Skill:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (skill / "data.txt").write_text("source\n", encoding="utf-8")
    return Skill(name=name, path=skill)


class InstallerTest(unittest.TestCase):
    def test_auto_mode_is_treated_as_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            target = root / "target-skills"

            result = install_skills(
                [skill],
                cli_name="codex",
                cli_config={"install_mode": "auto", "skills_path": str(target)},
                use_rsync=False,
            )

            self.assertEqual(result.installed, ["git-helper"])
            self.assertTrue((target / "git-helper" / "SKILL.md").is_file())

    def test_missing_skills_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = make_skill(pathlib.Path(tmpdir) / "repo-skills", "git-helper")

            with self.assertRaises(InstallError) as caught:
                install_skills(
                    [skill],
                    cli_name="codex",
                    cli_config={"install_mode": "copy", "skills_path": None},
                    use_rsync=False,
                )

        self.assertIn("未配置 codex 的 skills_path", str(caught.exception))

    def test_copy_installs_skill_to_target_name_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "docs-helper")
            target = root / "target-skills"

            install_skills(
                [skill],
                cli_name="claude",
                cli_config={"install_mode": "copy", "skills_path": str(target)},
                use_rsync=False,
            )

            self.assertTrue((target / "docs-helper" / "SKILL.md").is_file())
            self.assertFalse((target / "cosh" / "docs-helper").exists())

    def test_overwrite_deletes_files_removed_from_source_for_single_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            target = root / "target-skills"
            existing = target / "git-helper"
            existing.mkdir(parents=True)
            (existing / "old.txt").write_text("old\n", encoding="utf-8")

            sync_skill(skill, target, use_rsync=False)

            self.assertFalse((existing / "old.txt").exists())
            self.assertTrue((existing / "SKILL.md").is_file())

    def test_sync_does_not_delete_other_user_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            target = root / "target-skills"
            user_skill = target / "user-helper"
            user_skill.mkdir(parents=True)
            (user_skill / "SKILL.md").write_text("# user\n", encoding="utf-8")

            sync_skill(skill, target, use_rsync=False)

            self.assertTrue((user_skill / "SKILL.md").is_file())

    def test_backup_copies_existing_skill_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            target = root / "target-skills"
            existing = target / "git-helper"
            existing.mkdir(parents=True)
            (existing / "SKILL.md").write_text("# existing\n", encoding="utf-8")
            backups = root / "backups"

            result = install_skills(
                [skill],
                cli_name="codex",
                cli_config={"install_mode": "copy", "skills_path": str(target)},
                backup=True,
                backup_root=backups,
                timestamp="20260605-103000",
                use_rsync=False,
            )

            backup_path = backups / "codex" / "git-helper" / "20260605-103000"
            self.assertEqual(result.backups, [backup_path])
            self.assertEqual((backup_path / "SKILL.md").read_text(encoding="utf-8"), "# existing\n")

    def test_backup_is_not_created_when_target_skill_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            backups = root / "backups"

            result = install_skills(
                [skill],
                cli_name="codex",
                cli_config={"install_mode": "copy", "skills_path": str(root / "target")},
                backup=True,
                backup_root=backups,
                timestamp="20260605-103000",
                use_rsync=False,
            )

            self.assertEqual(result.backups, [])
            self.assertFalse(backups.exists())

    def test_cli_and_link_modes_are_not_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = make_skill(pathlib.Path(tmpdir) / "repo-skills", "git-helper")
            for mode in ("cli", "link"):
                with self.subTest(mode=mode):
                    with self.assertRaises(InstallError) as caught:
                        install_skills(
                            [skill],
                            cli_name="codex",
                            cli_config={"install_mode": mode, "skills_path": str(pathlib.Path(tmpdir) / "target")},
                        )

                    self.assertIn(f"当前版本暂未实现 {mode} 安装模式", str(caught.exception))

    def test_invalid_install_mode_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = make_skill(pathlib.Path(tmpdir) / "repo-skills", "git-helper")

            with self.assertRaises(InstallError) as caught:
                install_skills(
                    [skill],
                    cli_name="codex",
                    cli_config={"install_mode": "invalid", "skills_path": str(pathlib.Path(tmpdir) / "target")},
                )

        self.assertIn("非法 install_mode", str(caught.exception))

    @mock.patch("internal.installer.shutil.which", return_value="/usr/bin/rsync")
    @mock.patch("internal.installer.subprocess.run")
    def test_uses_rsync_when_available(self, run: mock.Mock, which: mock.Mock) -> None:
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            skill = make_skill(root / "repo-skills", "git-helper")
            target = root / "target-skills"

            sync_skill(skill, target, use_rsync=True)

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/rsync", "-a", "--delete"])
        self.assertTrue(command[3].endswith("/"))
        self.assertTrue(command[4].endswith("/"))

    def test_managed_install_persists_current_skill_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            config = load_config(home=root)
            target = root / "codex-skills"
            config["cli"]["codex"]["skills_path"] = str(target)
            skills = [
                make_skill(root / "repo-skills", "git-helper"),
                make_skill(root / "repo-skills", "doc-helper"),
            ]

            result = install_managed_skills(
                skills,
                config=config,
                cli_name="codex",
                config_home=root,
                use_rsync=False,
            )
            saved = load_config(home=root)

            self.assertEqual(result.installed, ["git-helper", "doc-helper"])
            self.assertEqual(saved["cli"]["codex"]["managed_skills"], ["git-helper", "doc-helper"])

    def test_managed_install_removes_previously_managed_removed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            config = load_config(home=root)
            target = root / "codex-skills"
            stale = target / "stale-helper"
            stale.mkdir(parents=True)
            (stale / "SKILL.md").write_text("# stale\n", encoding="utf-8")
            config["cli"]["codex"]["skills_path"] = str(target)
            config["cli"]["codex"]["managed_skills"] = ["git-helper", "stale-helper"]
            skill = make_skill(root / "repo-skills", "git-helper")

            result = install_managed_skills(
                [skill],
                config=config,
                cli_name="codex",
                config_home=root,
                use_rsync=False,
            )

            self.assertEqual(result.removed, ["stale-helper"])
            self.assertFalse(stale.exists())
            self.assertEqual(load_config(home=root)["cli"]["codex"]["managed_skills"], ["git-helper"])

    def test_managed_install_does_not_delete_user_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            config = load_config(home=root)
            target = root / "codex-skills"
            user_skill = target / "user-helper"
            user_skill.mkdir(parents=True)
            (user_skill / "SKILL.md").write_text("# user\n", encoding="utf-8")
            config["cli"]["codex"]["skills_path"] = str(target)
            config["cli"]["codex"]["managed_skills"] = ["git-helper"]
            skill = make_skill(root / "repo-skills", "git-helper")

            install_managed_skills(
                [skill],
                config=config,
                cli_name="codex",
                config_home=root,
                use_rsync=False,
            )

            self.assertTrue((user_skill / "SKILL.md").is_file())

    def test_managed_removed_skill_is_not_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            config = load_config(home=root)
            target = root / "codex-skills"
            stale = target / "stale-helper"
            stale.mkdir(parents=True)
            (stale / "SKILL.md").write_text("# stale\n", encoding="utf-8")
            config["cli"]["codex"]["skills_path"] = str(target)
            config["cli"]["codex"]["managed_skills"] = ["stale-helper"]
            backups = root / "backups"

            result = install_managed_skills(
                [],
                config=config,
                cli_name="codex",
                config_home=root,
                backup=True,
                backup_root=backups,
                timestamp="20260605-103000",
                use_rsync=False,
            )

            self.assertEqual(result.removed, ["stale-helper"])
            self.assertFalse(stale.exists())
            self.assertFalse(backups.exists())

    def test_managed_state_is_isolated_by_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            config = load_config(home=root)
            config["cli"]["codex"]["skills_path"] = str(root / "codex-skills")
            config["cli"]["claude"]["skills_path"] = str(root / "claude-skills")
            config["cli"]["claude"]["managed_skills"] = ["claude-helper"]
            skill = make_skill(root / "repo-skills", "git-helper")

            install_managed_skills(
                [skill],
                config=config,
                cli_name="codex",
                config_home=root,
                use_rsync=False,
            )
            saved = load_config(home=root)

            self.assertEqual(saved["cli"]["codex"]["managed_skills"], ["git-helper"])
            self.assertEqual(saved["cli"]["claude"]["managed_skills"], ["claude-helper"])


if __name__ == "__main__":
    unittest.main()
