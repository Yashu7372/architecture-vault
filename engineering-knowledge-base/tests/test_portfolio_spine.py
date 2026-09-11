from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_portfolio_spine import build_spine


class PortfolioSpineBuilderTest(unittest.TestCase):
    def test_builds_articles_labs_relationships_and_provenance(self):
        with TemporaryDirectory() as directory:
            graph_root = Path(directory)
            (graph_root / "graph").mkdir(parents=True)
            (graph_root / "knowledge" / "ai-engineering").mkdir(parents=True)
            (graph_root / "architectures").mkdir(parents=True)

            (graph_root / "graph" / "nodes.yaml").write_text(
                """
version: 0.1.0
nodes:
  - id: context-engineering
    name: Context Engineering
    type: capability
    domain: ai-engineering
    maturity: LEARNING
    summary: Builds bounded task-specific context.
  - id: forge
    name: Forge AI Engineering Control Plane
    type: project
    domain: ai-engineering
    maturity: LEARNING
    summary: Governed AI-assisted engineering control plane.
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graph_root / "graph" / "relationships.yaml").write_text(
                """
version: 0.1.0
relationships:
  - from: context-engineering
    relation: USED_BY
    to: forge
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graph_root / "knowledge" / "ai-engineering" / "context-engineering.md").write_text(
                """
# Context Engineering

**Graph ID:** `context-engineering`
**Type:** capability
**Domain:** ai-engineering
**Maturity:** LEARNING

## Problem

Repositories are too large for every task.

## Mental model

Build the smallest trustworthy context.

## Principle

Use deterministic relationships and provenance.
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graph_root / "architectures" / "forge-ai-engineering-control-plane.md").write_text(
                """
# Forge — AI Engineering Control Plane

## Problem

Long-running AI engineering needs governance and recovery.

## Reference flow

Request to workflow to workers to verification to evidence.
""".strip()
                + "\n",
                encoding="utf-8",
            )

            spine = build_spine(graph_root)

            self.assertEqual("portfolio-spine.v1", spine["schema_version"])
            self.assertEqual(2, len(spine["items"]))
            by_id = {item["node_id"]: item for item in spine["items"]}
            self.assertEqual("article", by_id["context-engineering"]["kind"])
            self.assertEqual("lab", by_id["forge"]["kind"])
            self.assertEqual("Repositories are too large for every task.", by_id["context-engineering"]["two_minute_read"]["problem"])
            self.assertEqual("Build the smallest trustworthy context.", by_id["context-engineering"]["two_minute_read"]["mental_model"])
            self.assertEqual("USED_BY", by_id["context-engineering"]["relationships"][0]["relation"])
            self.assertTrue(by_id["context-engineering"]["provenance"][0]["path"].endswith("context-engineering.md"))
            self.assertTrue(by_id["forge"]["provenance"][0]["path"].endswith("forge-ai-engineering-control-plane.md"))

    def test_requires_graph_contract_files(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                build_spine(Path(directory))


if __name__ == "__main__":
    unittest.main()
