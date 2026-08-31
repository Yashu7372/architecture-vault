import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_portfolio_candidates.py"
SPEC = importlib.util.spec_from_file_location("portfolio_candidate_export", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PortfolioCandidateExportTests(unittest.TestCase):
    def taxonomy(self):
        return {
            "concepts": [
                {
                    "id": "transactional-outbox",
                    "name": "Transactional Outbox",
                    "domain": "architecture-patterns",
                    "aliases": ["outbox pattern"],
                    "keywords": ["outbox table", "atomic publish", "cdc"],
                },
                {
                    "id": "idempotency",
                    "name": "Idempotency",
                    "domain": "architecture-patterns",
                    "aliases": ["idempotent consumer"],
                    "keywords": ["deduplication", "duplicate event"],
                },
            ]
        }

    def chunks(self):
        return [
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "heading": "Outbox",
                "text": "The Transactional Outbox stores an outbox table and uses atomic publish semantics. Idempotency handles a duplicate event.",
                "source_name": "source-a",
                "url": "https://example.com/a",
            },
            {
                "chunk_id": "c2",
                "document_id": "d2",
                "heading": "Delivery",
                "text": "An outbox pattern still needs an idempotent consumer when duplicate event delivery occurs.",
                "source_name": "source-b",
                "url": "https://example.com/b",
            },
            {
                "chunk_id": "c3",
                "document_id": "d3",
                "heading": "Reliability",
                "text": "Transactional Outbox and Idempotency are commonly combined for reliable event delivery and deduplication.",
                "source_name": "source-c",
                "url": "https://example.com/c",
            },
        ]

    def test_explicit_seed_terms_become_evidence_backed_candidates(self):
        result = module.build_candidate_export(self.taxonomy(), self.chunks())
        by_id = {item["concept_id"]: item for item in result["concepts"]}
        self.assertEqual("portfolio-candidates.v1", result["schema_version"])
        self.assertEqual("candidate-only", result["authority"])
        self.assertEqual({"transactional-outbox", "idempotency"}, set(by_id))
        self.assertEqual("EXTRACTED", by_id["transactional-outbox"]["evidence_state"])
        self.assertGreaterEqual(by_id["transactional-outbox"]["statistics"]["source_documents"], 2)
        self.assertTrue(by_id["transactional-outbox"]["evidence"])

    def test_repeated_cooccurrence_can_create_inferred_relationship_candidate(self):
        result = module.build_candidate_export(self.taxonomy(), self.chunks())
        pairs = {
            (item["subject_concept_id"], item["predicate"], item["object_concept_id"])
            for item in result["relationships"]
        }
        self.assertIn(("idempotency", "STRONGLY_RELATED_TO", "transactional-outbox"), pairs)
        self.assertTrue(all(item["status"] == "CANDIDATE" for item in result["relationships"]))

    def test_single_keyword_does_not_create_weak_candidate(self):
        taxonomy = {
            "concepts": [
                {
                    "id": "weak",
                    "name": "A Concept Never Named",
                    "domain": "test",
                    "aliases": [],
                    "keywords": ["cache", "ttl"],
                }
            ]
        }
        chunks = [{"chunk_id": "c1", "document_id": "d1", "heading": "x", "text": "cache only"}]
        result = module.build_candidate_export(taxonomy, chunks)
        self.assertEqual([], result["concepts"])


if __name__ == "__main__":
    unittest.main()
