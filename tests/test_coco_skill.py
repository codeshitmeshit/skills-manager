from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COCO_SKILL_DIR = ROOT / "skills" / "cosh-coco"
AIME_SKILL = ROOT / "skills" / "cosh-aime" / "SKILL.md"


class CocoSkillTest(unittest.TestCase):
    def test_coco_has_an_independent_skill(self) -> None:
        skill_path = COCO_SKILL_DIR / "SKILL.md"

        self.assertTrue(skill_path.is_file())

    def test_coco_skill_routes_explicit_coco_requests_to_cli(self) -> None:
        skill = (COCO_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("让 coco", skill)
        self.assertIn('coco -p', skill)
        self.assertIn("当前工作目录", skill)
        self.assertIn("不得改用 AIME", skill)

    def test_coco_skill_does_not_bypass_permissions(self) -> None:
        skill = (COCO_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("不得添加 `-y`", skill)
        self.assertIn("权限", skill)

    def test_aime_skill_excludes_explicit_coco_requests(self) -> None:
        skill = AIME_SKILL.read_text(encoding="utf-8")

        self.assertIn("用户明确提到 `coco`", skill)
        self.assertIn("不得使用本 skill", skill)


if __name__ == "__main__":
    unittest.main()
