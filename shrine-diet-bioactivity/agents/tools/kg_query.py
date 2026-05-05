# shrine-diet-bioactivity/agents/tools/kg_query.py
"""kg_query — Layer A natural-language fallback over the staged MCP gateway.

This is the **fallback** tool. The panel's primary information path is the
typed Layer-B traversals in `kg_tools.py` (kg_compound_to_targets,
kg_herb_to_diseases, etc.) which return paper-grade provenance chains.

`kg_query` is kept for:
  - The Defer / CRS roles whose work isn't retrieval-driven.
  - Backwards-compat with existing tests + assembly.py registration.
  - Any prompt where no role-prior fits.

Per the persona audit (research-journal/shared/staged-mcp-persona-audit.md),
Layer A often returns `answer="None"` or `[no-context]` on free-tier
Nemotron — agents should not hard-depend on this tool's answer text.
"""
from __future__ import annotations

from typing import Literal

from agents.models import KGResult  # type: ignore[import-not-found]
from agents.tools.mcp_client import MCPError

QueryMode = Literal["local", "global", "hybrid", "naive", "mix"]
_VALID_MODES = {"local", "global", "hybrid", "naive", "mix"}


class KGQueryError(RuntimeError):
    """Wraps transport / protocol errors from the underlying KG gateway."""


def _lightrag_query(question: str, mode: QueryMode) -> dict:
    """Internal seam — kept for mock compatibility with existing tests.

    Calls the MCP gateway's `kg_query` Layer A tool and returns a chain-
    shape compatible with the existing KGResult builder. Layer A returns
    a natural-language answer (no chains), so `chains` is always [] and
    counts are 0; the answer text is preserved on the `answer` key for
    future use, but the existing KGResult does not surface it.

    Tests can mock this function at the boundary (returning a non-empty
    `chains` list) without depending on the live MCP gateway.
    """
    # Local import keeps the test suite from requiring requests/MCP env vars
    # when it mocks this function.
    from agents.tools.mcp_client import default_client

    try:
        result = default_client().call_tool(
            "kg_query",
            {"question": question, "mode": mode, "top_k": 40},
        )
    except MCPError as e:
        raise KGQueryError(str(e)) from e

    return {
        "chains": [],
        "node_count": 0,
        "edge_count": 0,
        "answer": result.get("answer", ""),
        "references": result.get("references", []),
    }


def kg_query(question: str, mode: QueryMode = "mix") -> KGResult:
    """Query the unified diet KG via the MCP gateway; return typed chains.

    Returns a KGResult whose `chains` is empty when Layer A is used
    (Layer A returns NL answers, not chains). Panel agents that need
    chains should call kg_tools.kg_* Layer-B traversals instead.

    Raises KGQueryError on transport failure.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; valid: {sorted(_VALID_MODES)}")
    raw = _lightrag_query(question, mode)
    # Backwards-compat: build KGResult from the raw seam shape. If a test
    # mocks `_lightrag_query` to return non-empty chains, those are honored.
    from agents.models import KGEdge, ProvenanceChain  # type: ignore[import-not-found]
    chains = [
        ProvenanceChain(edges=[KGEdge(**e) for e in c.get("edges", [])])
        for c in raw.get("chains", [])
    ]
    return KGResult(
        chains=chains,
        raw_subgraph_node_count=raw.get("node_count", 0),
        raw_subgraph_edge_count=raw.get("edge_count", 0),
        query_mode=mode,
    )
