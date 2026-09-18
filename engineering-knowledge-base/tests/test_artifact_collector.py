from __future__ import annotations

import json

from collectors.artifact_collector import ArtifactCollector


def test_artifact_collector_normalizes_markdown_and_json(tmp_path) -> None:
    notes = tmp_path / "flow.md"
    notes.write_text("# Bag flow\n\nBag becomes loaded after reconciliation.", encoding="utf-8")
    payload = tmp_path / "sample.json"
    payload.write_text(json.dumps({"flight": "EK001", "bag": {"status": "LOADED"}}), encoding="utf-8")

    documents = ArtifactCollector().collect(
        {
            "name": "slice-01-input",
            "type": "artifact",
            "paths": [str(notes), str(payload)],
            "tags": ["vertical-slice-01"],
        }
    )

    assert len(documents) == 2
    by_format = {item.metadata["artifact_format"]: item for item in documents}
    assert "Bag becomes loaded" in by_format["md"].content
    assert '"status": "LOADED"' in by_format["json"].content
    assert by_format["md"].metadata["artifact_sha256"]
    assert by_format["json"].url.startswith("file:")


def test_artifact_collector_discovers_supported_files_recursively(tmp_path) -> None:
    nested = tmp_path / "docs" / "nested"
    nested.mkdir(parents=True)
    (nested / "a.md").write_text("A", encoding="utf-8")
    (nested / "ignored.bin").write_bytes(b"x")

    documents = ArtifactCollector().collect(
        {
            "name": "recursive",
            "type": "artifact",
            "path": str(tmp_path / "docs"),
            "recursive": True,
        }
    )

    assert [item.title for item in documents] == ["a"]
