from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processors.analysis_writer import AnalysisWriter
from processors.state_store import StateStore

STATE_FILE = ROOT / "output" / "state" / "inbox-state.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and apply an AI analysis JSON result to durable knowledge artifacts.")
    parser.add_argument("analysis_file", type=Path)
    args = parser.parse_args()

    data = json.loads(args.analysis_file.read_text(encoding="utf-8"))
    writer = AnalysisWriter(ROOT)
    artifacts = writer.apply(data)

    state = StateStore(STATE_FILE)
    source_id = data["source_id"]
    item = state.get(source_id) or {}
    url = item.get("url", "")
    state.mark(source_id, url, "ANALYZED", knowledge_artifacts=artifacts, analysis_error=None)

    print(json.dumps(artifacts, indent=2))


if __name__ == "__main__":
    main()
