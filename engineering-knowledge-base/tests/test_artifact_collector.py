from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from collectors.artifact_collector import ArtifactCollector


class ArtifactCollectorTest(unittest.TestCase):
    def test_normalizes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notes = root / "flow.md"
            notes.write_text("# Bag flow\n\nBag becomes loaded after reconciliation.", encoding="utf-8")
            payload = root / "sample.json"
            payload.write_text(
                json.dumps({"flight": "EK001", "bag": {"status": "LOADED"}}),
                encoding="utf-8",
            )

            documents = ArtifactCollector().collect(
                {
                    "name": "slice-01-input",
                    "type": "artifact",
                    "paths": [str(notes), str(payload)],
                    "tags": ["vertical-slice-01"],
                }
            )

            self.assertEqual(2, len(documents))
            by_format = {item.metadata["artifact_format"]: item for item in documents}
            self.assertIn("Bag becomes loaded", by_format["md"].content)
            self.assertIn('"status": "LOADED"', by_format["json"].content)
            self.assertTrue(by_format["md"].metadata["artifact_sha256"])
            self.assertTrue(by_format["json"].url.startswith("file:"))

    def test_discovers_supported_files_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "docs" / "nested"
            nested.mkdir(parents=True)
            (nested / "a.md").write_text("A", encoding="utf-8")
            (nested / "ignored.bin").write_bytes(b"x")

            documents = ArtifactCollector().collect(
                {
                    "name": "recursive",
                    "type": "artifact",
                    "path": str(root / "docs"),
                    "recursive": True,
                }
            )

            self.assertEqual(["a"], [item.title for item in documents])


if __name__ == "__main__":
    unittest.main()
