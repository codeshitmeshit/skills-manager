from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cosh-byted-superpowers-review-planner"
WORKFLOW_PATH = SKILL_DIR / "scripts" / "workflow_state.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKFLOW = load_module("byted_workflow_state", WORKFLOW_PATH)


class BytedSuperpowersWorkflowStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.work_id = "optimize-order-risk-check"
        self.work = self.root / ".superpowers" / "byted-work" / self.work_id
        (self.work / "reviews").mkdir(parents=True)
        (self.work / "evidence").mkdir()
        (self.root / "docs" / "superpowers" / "specs").mkdir(parents=True)
        (self.root / "docs" / "superpowers" / "plans").mkdir(parents=True)
        self.source_text = "# 订单风控优化技术方案\n"
        self.write_source(version=1, content=self.source_text)
        self.write_workflow()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def write_json(self, path: pathlib.Path, payload: dict) -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def write_source(self, version: int, content: str) -> None:
        source_path = self.work / "technical-design.md"
        source_path.write_text(content, encoding="utf-8")
        self.write_json(
            self.work / "source.json",
            {
                "version": version,
                "sha256": self.sha256(content),
                "path": "technical-design.md",
                "updated_at": "2026-08-02T10:00:00+08:00",
            },
        )

    def write_workflow(self, mode: str = "single") -> None:
        self.write_json(
            self.work / "workflow.json",
            {
                "work": self.work_id,
                "mode": mode,
                "state_version": 1,
                "updated_at": "2026-08-02T10:00:00+08:00",
            },
        )

    def current_binding(self) -> dict:
        source = json.loads((self.work / "source.json").read_text(encoding="utf-8"))
        return {
            "source_version": source["version"],
            "source_sha256": source["sha256"],
        }

    def write_knowledge_gate(self, status: str = "passed", **extra) -> None:
        payload = {
            **self.current_binding(),
            "status": status,
            "mode": "loaded",
            "version": "1.2.3",
            "sources": [{"role": "stability", "path": "a", "sha256": "a" * 64}],
            "updated_at": "2026-08-02T10:05:00+08:00",
            **extra,
        }
        self.write_json(self.work / "evidence" / "knowledge-gate.json", payload)

    def write_codegraph(self, status: str = "passed", code_sha: str = "code-sha") -> None:
        self.write_json(
            self.work / "evidence" / "codegraph.json",
            {
                **self.current_binding(),
                "status": status,
                "code_sha": code_sha,
                "locations": [
                    {
                        "file": "internal/order/risk.go",
                        "symbol": "shouldSkip",
                        "variable": "riskScene",
                        "type": "model.RiskScene",
                    }
                ],
                "updated_at": "2026-08-02T10:10:00+08:00",
            },
        )

    def write_review(
        self,
        reviewer: str,
        status: str = "passed",
        round_number: int = 1,
        source_version: int | None = None,
        source_sha256: str | None = None,
        code_sha: str = "code-sha",
    ) -> None:
        binding = self.current_binding()
        self.write_json(
            self.work / "reviews" / f"round-{round_number:03d}-{reviewer}.json",
            {
                "reviewer": reviewer,
                "round": round_number,
                "status": status,
                "source_version": source_version or binding["source_version"],
                "source_sha256": source_sha256 or binding["source_sha256"],
                "code_sha": code_sha,
                "stage": "completed",
                "findings": [],
                "updated_at": "2026-08-02T10:20:00+08:00",
            },
        )

    def write_complete_review_round(self) -> None:
        self.write_knowledge_gate()
        self.write_codegraph()
        for reviewer in WORKFLOW.REQUIRED_REVIEWERS:
            self.write_review(reviewer)

    def test_resolve_work_rejects_path_traversal(self) -> None:
        with self.assertRaises(WORKFLOW.DashboardError):
            WORKFLOW.resolve_work(self.root, "../outside")

    def test_list_works_returns_multiple_development_works(self) -> None:
        another = self.root / ".superpowers" / "byted-work" / "add-audit-log"
        another.mkdir()
        self.write_json(
            another / "source.json",
            {
                "version": 1,
                "sha256": "b" * 64,
                "path": "technical-design.md",
                "updated_at": "2026-08-02T09:00:00+08:00",
            },
        )
        works = WORKFLOW.list_works(self.root)
        self.assertEqual([item["name"] for item in works], ["add-audit-log", self.work_id])

    def test_source_hash_must_match_the_technical_document(self) -> None:
        source = json.loads((self.work / "source.json").read_text(encoding="utf-8"))
        source["sha256"] = "0" * 64
        self.write_json(self.work / "source.json", source)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["source"]["status"], "blocked")
        self.assertIn("SHA-256", " ".join(status["stages"]["source"]["blockers"]))

    def test_review_cannot_pass_without_all_three_current_reviewers(self) -> None:
        self.write_knowledge_gate()
        self.write_codegraph()
        self.write_review("stability")
        self.write_review("security")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn("feasibility", " ".join(status["stages"]["review"]["blockers"]))

    def test_failed_reviewer_exposes_risk_and_fix(self) -> None:
        self.write_complete_review_round()
        review_path = self.work / "reviews" / "round-001-security.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["status"] = "blocked"
        review["findings"] = [
            {
                "id": "SEC-1",
                "severity": "P0",
                "blocking": True,
                "title": "日志泄露订单标识",
                "evidence": "internal/order/risk.go:52",
                "recommendation": "复用脱敏函数后再记录",
                "status": "open",
            }
        ]
        self.write_json(review_path, review)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertEqual(status["reviews"]["findings"][0]["title"], "日志泄露订单标识")
        self.assertEqual(status["reviews"]["findings"][0]["recommendation"], "复用脱敏函数后再记录")

    def test_document_revision_invalidates_gate_codegraph_and_reviews(self) -> None:
        self.write_complete_review_round()
        old = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(old["stages"]["review"]["status"], "passed")
        self.write_source(version=2, content="# 修订后的技术方案\n")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
        self.assertEqual(status["stages"]["codegraph"]["status"], "blocked")
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertTrue(status["reviews"]["history"])

    def test_stale_code_sha_invalidates_reviews(self) -> None:
        self.write_complete_review_round()
        self.write_review("feasibility", code_sha="stale-sha")
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["review"]["status"], "blocked")
        self.assertIn("代码 SHA", " ".join(status["stages"]["review"]["blockers"]))

    def test_fallback_requires_attempt_and_versioned_generic_rules(self) -> None:
        self.write_knowledge_gate(
            status="fallback",
            mode="fallback",
            onboarding_attempted=True,
            onboarding_error="registry unavailable",
            generic_rules_version="2026-08-02",
            sources=[],
        )
        self.write_codegraph()
        for reviewer in WORKFLOW.REQUIRED_REVIEWERS:
            self.write_review(reviewer)
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["knowledge_gate"]["mode"], "fallback")
        self.assertEqual(status["stages"]["review"]["status"], "passed")
        self.assertFalse(status["stages"]["spec"]["can_advance"])

    def test_fallback_without_onboarding_evidence_is_blocked(self) -> None:
        self.write_knowledge_gate(
            status="fallback",
            mode="fallback",
            onboarding_attempted=False,
            generic_rules_version="2026-08-02",
            sources=[],
        )
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")

    def test_malformed_evidence_fails_closed(self) -> None:
        (self.work / "evidence" / "knowledge-gate.json").write_text(
            "{broken", encoding="utf-8"
        )
        status = WORKFLOW.build_status(self.root, self.work_id)
        self.assertEqual(status["stages"]["knowledge_gate"]["status"], "blocked")
        self.assertIn("JSON", " ".join(status["stages"]["knowledge_gate"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
