# shrine-diet-bioactivity/agents/tools/kg_query.py
"""KG-query tool — LightRAG native semantic retrieval only.

No SQLite fallback by design. If LightRAG is unreachable, the call
raises KGQueryError so the calling agent sees a clear failure rather
than a silently-degraded retrieval.
"""
from __future__ import annotations

import os
from typing import Literal

import requests

from agents.models import KGEdge, KGResult, ProvenanceChain  # type: ignore[import-not-found]

QueryMode = Literal["local", "global", "hybrid", "naive", "mix"]
_VALID_MODES = {"local", "global", "hybrid", "naive", "mix"}


class KGQueryError(RuntimeError):
    pass


def _lightrag_query(question: str, mode: QueryMode) -> dict:
    base = os.environ.get("LIGHTRAG_BASE_URL", "http://localhost:9621")
    try:
        r = requests.post(
            f"{base}/query",
            json={"query": question, "mode": mode},
            timeout=30,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise KGQueryError(f"LightRAG unreachable at {base}: {e}") from e
    data = r.json()
    return {
        "chains": data.get("chains", []),
        "node_count": data.get("node_count", 0),
        "edge_count": data.get("edge_count", 0),
    }


def kg_query(question: str, mode: QueryMode = "hybrid") -> KGResult:
    """Query the unified diet KG via LightRAG `/query`; return typed chains.

    Raises KGQueryError if LightRAG is unreachable. There is no fallback —
    semantic retrieval over the graph ontology is the contract.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; valid: {sorted(_VALID_MODES)}")
    raw = _lightrag_query(question, mode)
    chains = [
        ProvenanceChain(edges=[KGEdge(**e) for e in c["edges"]])
        for c in raw["chains"]
    ]
    return KGResult(
        chains=chains,
        raw_subgraph_node_count=raw["node_count"],
        raw_subgraph_edge_count=raw["edge_count"],
        query_mode=mode,
    )
