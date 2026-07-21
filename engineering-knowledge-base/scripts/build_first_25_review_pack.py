from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import mimetypes
import re
import shutil

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
LEARNING_DIR = ROOT / "learning" / "sdcourse-first-25"
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
SOURCE_RE = re.compile(r"^- Source:\s*(https?://\S+)", re.MULTILINE)


def parse_args():
    parser = ArgumentParser(description="Build the SDCourse Days 1-25 private review pack.")
    parser.add_argument("--source", default="sdcourse-python-js")
    parser.add_argument("--days", type=int, default=25)
    parser.add_argument("--download-images", action="store_true")
    return parser.parse_args()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def extract_images(markdown: str) -> list[dict[str, str]]:
    images = []
    seen = set()
    for alt, url in IMAGE_RE.findall(markdown):
        url = url.rstrip(".,")
        if url in seen:
            continue
        seen.add(url)
        images.append({"alt": alt.strip() or "Public source image", "url": url})
    return images


def extension_for(url: str, content_type: str | None) -> str:
    extension = Path(urlparse(url).path).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return extension
    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip())
    return guessed or ".img"


def download_image(
    session: requests.Session,
    url: str,
    target_dir: Path,
    index: int,
) -> Path | None:
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.lower().startswith("image/"):
            return None
        if not response.content or len(response.content) > 12 * 1024 * 1024:
            return None
        digest = hashlib.sha256(url.encode()).hexdigest()[:10]
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"image-{index:02d}-{digest}{extension_for(url, content_type)}"
        path.write_bytes(response.content)
        return path
    except Exception:
        return None


def diagram_explanation(day: int, title: str) -> str:
    if day <= 7:
        focus = "the local data path, the state owned by each process, and the exact checkpoint or durability boundary"
    elif day <= 14:
        focus = "the client/server transport path, buffering, acknowledgement, security, and overload behaviour"
    elif day <= 21:
        focus = "the boundary between wire format, schema validation, canonical event representation, and enrichment"
    else:
        focus = "partition placement, replication, node ownership, coordination, failover, and stale-writer protection"
    return (
        f"Read this image in the context of Day {day} ({title}). Identify {focus}. "
        "For every arrow, ask who owns retries, when an acknowledgement is safe, what state survives restart, "
        "and which metric proves that the transition is healthy."
    )


def build_review_pack(source: str, days: int, download_images: bool) -> Path:
    overview_source = LEARNING_DIR / "FIRST_25_OVERVIEW.md"
    if not overview_source.exists():
        raise FileNotFoundError(f"Missing committed overview: {overview_source}")

    curriculum_file = OUTPUT_DIR / "courses" / source / "CURRICULUM_CONTEXT.json"
    curriculum = load_json(curriculum_file, [])
    by_day = {int(item["day"]): item for item in curriculum if int(item.get("day", 0)) <= days}
    if len(by_day) != days:
        raise RuntimeError(f"Expected {days} curriculum entries, found {len(by_day)}")

    pack_dir = OUTPUT_DIR / "course-overviews" / source / f"first-{days}"
    assets_dir = pack_dir / "assets"
    pack_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(overview_source, pack_dir / "FIRST_25_OVERVIEW.md")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 SDCourse personal learning review pack"})
    catalog = [
        f"# Public Image Catalog — SDCourse Days 1–{days}",
        "",
        "> Images are copied only into this private workflow artifact when anonymous download succeeds. "
        "The committed repository contains original explanations and source URLs, not copied article image binaries.",
        "",
    ]
    index = [
        f"# SDCourse Days 1–{days} Review Pack",
        "",
        "- [Master overview](FIRST_25_OVERVIEW.md)",
        "- [Public image catalog](PUBLIC_IMAGE_CATALOG.md)",
        "- Daily source and completed lessons are under `../../daily-learning/` in the artifact.",
        "",
        "## Daily status",
        "",
    ]

    for day in range(1, days + 1):
        lesson = by_day[day]
        folder = OUTPUT_DIR / "daily-learning" / source / f"day-{day:03d}"
        source_file = folder / "01-public-source.md"
        lesson_file = folder / "02-completed-lesson.md"
        status_file = folder / "STATUS.json"
        status = load_json(status_file, {})
        source_text = source_file.read_text(encoding="utf-8") if source_file.exists() else ""
        article_match = SOURCE_RE.search(source_text)
        article_url = article_match.group(1) if article_match else lesson.get("article_url", "")
        images = extract_images(source_text)

        index.extend(
            [
                f"### Day {day}: {lesson['title']}",
                "",
                f"- Access: `{status.get('access_level', 'unknown')}`",
                f"- Public source: `{source_file.relative_to(OUTPUT_DIR)}`",
                f"- Original detailed lesson: `{lesson_file.relative_to(OUTPUT_DIR)}`",
                f"- Public images captured: {len(images)}",
                f"- Article: {article_url}",
                "",
            ]
        )
        catalog.extend(
            [
                f"## Day {day}: {lesson['title']}",
                "",
                f"- Access observed: `{status.get('access_level', 'unknown')}`",
                f"- Article: {article_url}",
                "",
            ]
        )
        if not images:
            catalog.extend(
                [
                    "No Markdown image URL was present in the anonymous public capture for this run.",
                    "",
                ]
            )
            continue

        for image_index, image in enumerate(images, start=1):
            local = None
            if download_images:
                local = download_image(
                    session,
                    image["url"],
                    assets_dir / f"day-{day:03d}",
                    image_index,
                )
            if local:
                rendered = local.relative_to(pack_dir).as_posix()
            else:
                rendered = image["url"]
            catalog.extend(
                [
                    f"### Image {image_index}: {image['alt']}",
                    "",
                    f"![{image['alt']}]({rendered})",
                    "",
                    f"- Source URL: {image['url']}",
                    f"- Offline artifact: `{local.relative_to(pack_dir)}`" if local else "- Offline artifact: download failed; source URL retained",
                    "",
                    diagram_explanation(day, lesson["title"]),
                    "",
                ]
            )

    (pack_dir / "PUBLIC_IMAGE_CATALOG.md").write_text("\n".join(catalog), encoding="utf-8")
    (pack_dir / "REVIEW_PACK_INDEX.md").write_text("\n".join(index), encoding="utf-8")
    return pack_dir


def main():
    args = parse_args()
    print(build_review_pack(args.source, args.days, args.download_images))


if __name__ == "__main__":
    main()
