"""Generate a post-ingest KG metrics snapshot for the paper Methods section.

Reads live counts from Neo4j Aura and writes a Markdown report with
node / edge breakdowns, source distribution (decoded from the LightRAG
chunk source_id encoding ``{source}:{batch_label}``), bilingual coverage
for Herb nodes, and HDI-Safe 50 mechanism-class coverage.

Run:
    python generate_snapshot.py
    python generate_snapshot.py --out /tmp/snapshot.md
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from config_loader import load_data_sources

# Project root = shrine-diet-bioactivity/ (one level above this file)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _query(session, cypher: str) -> list[dict]:
    return [dict(r) for r in session.run(cypher)]


def _resolve_snapshot_path() -> Path:
    cfg = load_data_sources()
    raw = Path(cfg.paths.ingestion_snapshot)
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw).resolve()


def generate(out_path: Path) -> None:
    """Connect to Aura, query metrics, write the snapshot Markdown."""
    load_dotenv(PROJECT_ROOT / ".env")
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    pwd = os.environ["NEO4J_PASSWORD"]

    with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
        with driver.session() as s:
            # Node counts by entity_type (typed labels set post-ingest).
            node_counts = _query(
                s,
                "MATCH (n) WHERE n.entity_type IS NOT NULL "
                "RETURN n.entity_type AS type, count(n) AS n "
                "ORDER BY n DESC",
            )
            # Fallback: count by labels if entity_type missing.
            label_counts = _query(
                s,
                "MATCH (n) RETURN labels(n) AS labels, count(n) AS n "
                "ORDER BY n DESC",
            )
            edge_counts = _query(
                s,
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS n "
                "ORDER BY n DESC",
            )
            # Source attribution lives on file_path because LightRAG
            # rewrites source_id to the MD5-hashed chunk_id. The ingest
            # pipeline (ingest_unified.ingest_batch + ingest_hdi) sets
            # file_path = upstream source name verbatim.
            sources = _query(
                s,
                """
                MATCH (n) WHERE n.file_path IS NOT NULL
                RETURN n.file_path AS src, count(n) AS n ORDER BY n DESC
                """,
            )
            edge_sources = _query(
                s,
                """
                MATCH ()-[r]->() WHERE r.file_path IS NOT NULL
                RETURN r.file_path AS src, count(r) AS n ORDER BY n DESC
                """,
            )
            # Bilingual coverage — Herb nodes carrying CN names.
            bilingual = _query(
                s,
                """
                MATCH (h:Herb)
                RETURN
                  count(h) AS total,
                  sum(CASE WHEN h.chinese_name IS NOT NULL OR h.name_cn IS NOT NULL
                           THEN 1 ELSE 0 END) AS with_cn,
                  sum(CASE WHEN h.english_name IS NOT NULL OR h.name_en IS NOT NULL
                           THEN 1 ELSE 0 END) AS with_en,
                  sum(CASE WHEN h.pinyin IS NOT NULL OR h.pinyin_name IS NOT NULL
                           THEN 1 ELSE 0 END) AS with_pinyin
                """,
            )
            # HDI-Safe 50 coverage by mechanism class.
            hdi_cov = _query(
                s,
                """
                MATCH ()-[r:INTERACTS_WITH]->()
                RETURN coalesce(r.mechanism_class, 'unspecified') AS mech,
                       count(r) AS n
                ORDER BY mech
                """,
            )
            # Severity breakdown for the safety reviewer.
            hdi_sev = _query(
                s,
                """
                MATCH ()-[r:INTERACTS_WITH]->()
                RETURN coalesce(r.severity, 'unspecified') AS severity,
                       count(r) AS n
                ORDER BY severity
                """,
            )

    bi = bilingual[0] if bilingual else {
        "total": 0,
        "with_cn": 0,
        "with_en": 0,
        "with_pinyin": 0,
    }

    lines: list[str] = [
        "# KG Ingestion Snapshot",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()}_",
        f"_Aura instance: {uri.split('//')[1].split('.')[0]}_",
        "",
        "## Node counts by type",
        "",
        "| Entity type | Count |",
        "|---|---|",
    ]
    if node_counts:
        lines.extend(f"| {r['type']} | {r['n']:,} |" for r in node_counts)
    else:
        # Fallback when entity_type isn't populated yet.
        lines.append("| _(entity_type not yet populated; showing label counts)_ | |")
        lines.extend(
            f"| {','.join(r['labels']) or '(unlabeled)'} | {r['n']:,} |"
            for r in label_counts
        )

    lines += [
        "",
        "## Edge counts by type",
        "",
        "| Relationship type | Count |",
        "|---|---|",
        *[f"| {r['type']} | {r['n']:,} |" for r in edge_counts],
        "",
        "## Source distribution (nodes)",
        "",
        "| Source prefix | Node count |",
        "|---|---|",
        *[f"| {r['src'] or '(none)'} | {r['n']:,} |" for r in sources],
        "",
        "## Source distribution (edges)",
        "",
        "| Source prefix | Edge count |",
        "|---|---|",
        *[f"| {r['src'] or '(none)'} | {r['n']:,} |" for r in edge_sources],
        "",
        "## Bilingual coverage",
        "",
        "| Total Herbs | With CN | With EN | With Pinyin |",
        "|---|---|---|---|",
        f"| {bi['total']:,} | {bi['with_cn']:,} | {bi['with_en']:,} "
        f"| {bi['with_pinyin']:,} |",
        "",
        "## HDI-Safe 50 coverage",
        "",
        "_Mechanism class breakdown — should match the curated"
        " hdi_safe_50.json mix._",
        "",
        "| Mechanism class | Edges |",
        "|---|---|",
        *[f"| {r['mech']} | {r['n']:,} |" for r in hdi_cov],
        "",
        "_Severity breakdown — for the Safety Reviewer agent._",
        "",
        "| Severity | Edges |",
        "|---|---|",
        *[f"| {r['severity']} | {r['n']:,} |" for r in hdi_sev],
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output Markdown path (default: from data_sources.yaml)",
    )
    args = parser.parse_args()
    out_path = args.out or _resolve_snapshot_path()
    generate(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
