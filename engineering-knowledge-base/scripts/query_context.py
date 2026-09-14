from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from settings import OUTPUT_DIR

DB_FILE = OUTPUT_DIR / "context" / "context.sqlite"


def compact(text: str, limit: int = 900) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def normalize_fts_query(query: str) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z0-9_.+-]+", query) if len(token) > 1]
    return " OR ".join(f'"{token}"' for token in tokens) or query


def fts_available(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT value FROM metadata WHERE key = 'fts5_available'").fetchone()
    return bool(row and row[0] == "true")


def search(
    connection: sqlite3.Connection,
    query: str,
    limit: int,
    source: str | None,
    tag: str | None,
) -> list[dict]:
    filters = []
    params: list[object] = []
    if source:
        filters.append("d.source_name = ?")
        params.append(source)
    if tag:
        filters.append("EXISTS (SELECT 1 FROM tags t WHERE t.document_id = d.document_id AND t.tag = ?)")
        params.append(tag)
    where_suffix = f" AND {' AND '.join(filters)}" if filters else ""

    if fts_available(connection):
        sql = f"""
            SELECT
                c.chunk_id, c.document_id, d.title, d.url, d.source_name,
                d.published_date, c.heading, c.text, c.token_estimate,
                bm25(chunks_fts, 0.0, 0.0, 4.0, 2.0, 1.0, 1.5) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            JOIN documents d ON d.document_id = c.document_id
            WHERE chunks_fts MATCH ?{where_suffix}
            ORDER BY rank
            LIMIT ?
        """
        try:
            rows = connection.execute(sql, [normalize_fts_query(query), *params, limit]).fetchall()
        except sqlite3.OperationalError:
            rows = []
    else:
        rows = []

    if not rows:
        tokens = [token for token in re.findall(r"[A-Za-z0-9_.+-]+", query) if len(token) > 1]
        patterns = [f"%{token}%" for token in tokens[:8]] or [f"%{query}%"]
        term_clause = " OR ".join("(c.text LIKE ? OR c.heading LIKE ? OR d.title LIKE ?)" for _ in patterns)
        like_params = [value for pattern in patterns for value in (pattern, pattern, pattern)]
        sql = f"""
            SELECT
                c.chunk_id, c.document_id, d.title, d.url, d.source_name,
                d.published_date, c.heading, c.text, c.token_estimate, 0.0 AS rank
            FROM chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE ({term_clause}){where_suffix}
            ORDER BY d.title, c.ordinal
            LIMIT ?
        """
        rows = connection.execute(sql, [*like_params, *params, limit]).fetchall()

    columns = [
        "chunk_id",
        "document_id",
        "title",
        "url",
        "source_name",
        "published_date",
        "heading",
        "text",
        "token_estimate",
        "rank",
    ]
    return [dict(zip(columns, row)) for row in rows]


def related_documents(connection: sqlite3.Connection, document_ids: list[str], limit: int = 8) -> list[dict]:
    if not document_ids:
        return []
    placeholders = ",".join("?" for _ in document_ids)
    rows = connection.execute(
        f"""
        SELECT d.document_id, d.title, d.url, COUNT(*) AS shared_tags
        FROM tags seed
        JOIN tags candidate ON candidate.tag = seed.tag
        JOIN documents d ON d.document_id = candidate.document_id
        WHERE seed.document_id IN ({placeholders})
          AND candidate.document_id NOT IN ({placeholders})
        GROUP BY d.document_id, d.title, d.url
        ORDER BY shared_tags DESC, d.title
        LIMIT ?
        """,
        [*document_ids, *document_ids, limit],
    ).fetchall()
    return [
        {"document_id": row[0], "title": row[1], "url": row[2], "shared_tags": row[3]}
        for row in rows
    ]


def render_markdown(query: str, results: list[dict], related: list[dict]) -> str:
    lines = [f"# Context Pack: {query}", ""]
    if not results:
        lines.append("No matching context found.")
        return "\n".join(lines)

    seen_documents = set()
    for index, result in enumerate(results, start=1):
        seen_documents.add(result["document_id"])
        date = f" · {result['published_date']}" if result.get("published_date") else ""
        lines.extend(
            [
                f"## {index}. {result['title']}",
                f"Source: {result['source_name']}{date}",
                f"URL: {result['url']}",
                f"Section: {result['heading']}",
                "",
                compact(result["text"]),
                "",
            ]
        )

    if related:
        lines.extend(["## Related Documents", ""])
        for item in related:
            lines.append(f"- [{item['title']}]({item['url']}) — {item['shared_tags']} shared tags")
    lines.extend(["", f"Retrieved chunks: {len(results)} from {len(seen_documents)} documents."])
    return "\n".join(lines)


def main() -> None:
    parser = ArgumentParser(description="Query the local architecture context layer.")
    parser.add_argument("query", help="Natural-language or keyword search query.")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--source")
    parser.add_argument("--tag")
    parser.add_argument("--related", type=int, default=6, help="Number of tag-related documents to append.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    if not DB_FILE.exists():
        raise FileNotFoundError(f"Run scripts/build_context.py first; missing {DB_FILE}")

    with sqlite3.connect(DB_FILE) as connection:
        results = search(connection, args.query, args.limit, args.source, args.tag)
        document_ids = list(dict.fromkeys(result["document_id"] for result in results))
        related = related_documents(connection, document_ids, args.related) if args.related else []

    if args.format == "json":
        print(json.dumps({"query": args.query, "results": results, "related": related}, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(args.query, results, related))


if __name__ == "__main__":
    main()
