from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
NOTES_DIR = OUTPUT_DIR / "notes"
INDEX_FILE = OUTPUT_DIR / "MASTER_INDEX.md"


def main():
    lines = ["# Engineering Knowledge Master Index", ""]
    if not NOTES_DIR.exists():
        lines.append("No notes generated yet. Run scripts/collect.py first.")
    else:
        for file in sorted(NOTES_DIR.rglob("*.md")):
            rel = file.relative_to(OUTPUT_DIR)
            title = file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].replace("# ", "")
            lines.append(f"- [{title}]({rel.as_posix()})")
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Updated {INDEX_FILE}")


if __name__ == "__main__":
    main()
