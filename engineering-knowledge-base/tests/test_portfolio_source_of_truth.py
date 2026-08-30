from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


class PortfolioSourceOfTruthTests(unittest.TestCase):
    def test_machine_readable_contract_freezes_canonical_branch(self):
        contract = yaml.safe_load(
            (ROOT / "config" / "portfolio-knowledge-contract.yaml").read_text(encoding="utf-8")
        ) or {}
        self.assertEqual("canonical", contract["status"])
        self.assertGreaterEqual(contract["version"], 4)
        self.assertEqual(
            "feature/portfolio-knowledge-source-of-truth",
            contract["source_of_truth"]["branch"],
        )
        self.assertEqual(
            "Yashu7372/enterprise-architecture-graph",
            contract["promotion"]["to"],
        )
        self.assertFalse(contract["automation"]["raw_runtime_output_committed"])
        self.assertFalse(contract["promotion"]["raw_article_body_allowed"])
        self.assertEqual("config/capabilities.yaml", contract["capability_model"]["registry"])
        self.assertTrue(contract["incremental_refresh"]["failure_behavior"]["preserve_last_good_source_snapshot"])
        self.assertFalse(contract["incremental_refresh"]["automatic_promotion"])

    def test_canonical_context_and_runner_exist(self):
        context = REPO_ROOT / "PORTFOLIO_KNOWLEDGE_SYSTEM.md"
        runner = ROOT / "scripts" / "run_portfolio_knowledge_pipeline.py"
        capability_registry = ROOT / "config" / "capabilities.yaml"
        validator = ROOT / "scripts" / "validate_capabilities.py"
        self.assertTrue(context.is_file())
        self.assertTrue(runner.is_file())
        self.assertTrue(capability_registry.is_file())
        self.assertTrue(validator.is_file())
        self.assertIn(
            "feature/portfolio-knowledge-source-of-truth",
            context.read_text(encoding="utf-8"),
        )

    def test_all_supported_collector_types_have_implementations(self):
        required = {
            "catalog_collector.py",
            "web_collector.py",
            "substack_collector.py",
            "github_collector.py",
            "arxiv_collector.py",
            "pdf_collector.py",
            "youtube_collector.py",
        }
        actual = {path.name for path in (ROOT / "collectors").glob("*_collector.py")}
        self.assertTrue(required <= actual, required - actual)

    def test_every_supported_collector_type_is_a_declared_capability(self):
        data = yaml.safe_load(
            (ROOT / "config" / "capabilities.yaml").read_text(encoding="utf-8")
        ) or {}
        capabilities = data.get("capabilities", [])
        declared = {
            source_type
            for capability in capabilities
            for source_type in capability.get("source_types", [])
        }
        self.assertEqual(
            {"catalog", "web", "substack", "github", "arxiv", "pdf", "youtube"},
            declared,
        )
        for capability in capabilities:
            with self.subTest(capability=capability.get("id")):
                self.assertEqual("collector", capability.get("kind"))
                self.assertFalse(capability.get("side_effects", {}).get("external_writes", True))

    def test_source_groups_reference_known_sources(self):
        manual = yaml.safe_load(
            (ROOT / "config" / "sources.manual.yaml").read_text(encoding="utf-8")
        ) or {}
        generated = yaml.safe_load(
            (ROOT / "config" / "sources.generated.yaml").read_text(encoding="utf-8")
        ) or {}
        groups = yaml.safe_load(
            (ROOT / "config" / "source-groups.yaml").read_text(encoding="utf-8")
        ) or {}

        names = {
            source["name"]
            for source in manual.get("sources", []) + generated.get("sources", [])
        }
        self.assertIn("portfolio-enterprise-architecture-graph", names)

        for group_name, group in groups.get("groups", {}).items():
            with self.subTest(group=group_name):
                sources = group.get("sources", [])
                self.assertTrue(sources)
                self.assertEqual(len(sources), len(set(sources)))
                self.assertEqual([], sorted(set(sources) - names))

    def test_scheduled_research_and_daily_learning_are_separated(self):
        data = yaml.safe_load(
            (ROOT / "config" / "source-groups.yaml").read_text(encoding="utf-8")
        ) or {}
        scheduled = set(data["groups"]["scheduled-public"]["sources"])
        daily = set(data["groups"]["daily-learning"]["sources"])
        self.assertNotIn("ai-agent-mastery-substack", scheduled)
        self.assertNotIn("sdcourse-python-js", scheduled)
        self.assertNotIn("sdcourse-java-spring", scheduled)
        self.assertEqual({"sdcourse-python-js", "sdcourse-java-spring"}, daily)

    def test_canonical_group_connects_research_learning_and_portfolio(self):
        data = yaml.safe_load(
            (ROOT / "config" / "source-groups.yaml").read_text(encoding="utf-8")
        ) or {}
        canonical = set(data["groups"]["canonical-public"]["sources"])
        self.assertIn("system-design-academy", canonical)
        self.assertIn("arxiv-agentic-rag", canonical)
        self.assertIn("sdcourse-python-js", canonical)
        self.assertIn("portfolio-enterprise-architecture-graph", canonical)


if __name__ == "__main__":
    unittest.main()
