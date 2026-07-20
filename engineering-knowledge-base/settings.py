from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent


def resolve_output_dir() -> Path:
    explicit_root = os.getenv("ENGINEERING_KNOWLEDGE_ROOT")
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    shared_knowledge_root = os.getenv("DNBMS_KNOWLEDGE_ROOT")
    if shared_knowledge_root:
        return Path(shared_knowledge_root).expanduser().resolve() / "architecture-vault"

    return PROJECT_ROOT / "output"


OUTPUT_DIR = resolve_output_dir()
