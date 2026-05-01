# `kg-mcp` — KG MCP Gateway

Production MCP server over the unified diet ⇄ food ⇄ compound ⇄ symptom ⇄ disease knowledge graph in Neo4j Aura. Speaks the [Model Context Protocol](https://modelcontextprotocol.io) so any MCP-compatible client (Claude Desktop, agent SDKs, custom clients) can query the KG with deterministic, scope-filtered Cypher behind 10 typed tools.

## Live deployment

| | |
|---|---|
| **URL** | `https://kg-mcp-test.up.railway.app` |
| **MCP endpoint** | `POST /mcp` (streamable-HTTP transport) |
| **Health (no auth)** | `GET /health` |
| **MCP server name / version** | `kg-mcp` / per `mcp` SDK |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  AURA NEO4J (sole data layer; durable)                  │
│  166K+ nodes, 5M+ edges                                 │
│  scope='shared' on every node and edge                  │
│  Native vector + per-relationship-type indexes          │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ neo4j+s://
                          │
┌─────────────────────────────────────────────────────────┐
│  RAILWAY (stateless compute; restartable)               │
│  ┌──────────────────────────────────────────────┐       │
│  │ scoped_server  (FastAPI, internal :9621)     │       │
│  │   /query /traverse /hdi_check                │       │
│  │   /bilingual_term /graphs                    │       │
│  └──────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────┐       │
│  │ kg-mcp gateway (FastMCP HTTP, public /mcp)   │       │
│  │   10 typed tools + auth middleware           │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

The Railway container is restartable; it holds zero data. All state is in Aura. NCBI enrichment writes flow through the scoped server back to Aura.

## Authentication

Every `/mcp*` request requires `Authorization: Bearer <token>`. Two valid token sources:

1. **Static API key** (CI / admin smoke / scripts)
   - Stored in Infisical → `SyntropyHealth App` / `prod` / `MCP_API_KEY`
   - Constant-time compared with the server-side env var

2. **Clerk JWT** (admin sign-in via Google)
   - Verified against Clerk JWKS at `clerk.syntropyhealth.bio`
   - Token's `email` claim must be in `MCP_ADMIN_EMAILS` (comma-separated allow-list)
   - Currently allow-listed: `mymm.psu@gmail.com`

`/health` is the only public path (Railway healthcheck reaches it without a token).

Full auth contract + rotation procedure: [`mcp-auth-contract.md`](../../../.claude/projects/-home-mo-projects-SyntropyHealth/memory/mcp-auth-contract.md) (admin-only memory doc).

## Quick smoke

```bash
KEY=$(infisical secrets get MCP_API_KEY \
  --projectId 687cab01-ccc1-4789-99a9-1214bd268f2b \
  --env prod --plain)

# 1. Health (no auth)
curl -fsS https://kg-mcp-test.up.railway.app/health

# 2. MCP initialize handshake
curl -fsS -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2024-11-05","capabilities":{},
                 "clientInfo":{"name":"smoke","version":"0.1"}}}'
```

A complete Python smoke that initializes a session and calls each tool: [`tests/e2e/test_live_endpoints.py`](tests/e2e/test_live_endpoints.py). Set `KG_MCP_E2E_URL` and `KG_MCP_API_KEY` in env to run with `pytest -m e2e`.

## Tool catalog (10 tools, 3 layers)

Every tool returns Pydantic-validated structured output. Schemas in [`src/kg_mcp/schemas.py`](src/kg_mcp/schemas.py).

### Layer A — General Q&A (1 tool)

| Tool | Input | Output | When to use |
|---|---|---|---|
| `kg_query` | `question: str`, `mode: Literal["mix","hybrid","local","global","naive"]="mix"`, `top_k: int=40` | `{answer, references, scope_filter}` | Open-ended natural-language exploration. Default fallback when no Layer-B tool fits. ⚠️ See Limitations §1. |

### Layer B — Role-priored deterministic traversals (6 tools)

These tools enforce a fixed `(start_label, edge_type, depth)` and return typed `ProvenanceChain`s — exactly the shape paper provenance metrics expect.

All Layer-B tools accept `seed: str` and `top_k: int=20`. Seed matches against the start node's `entity_id`, `common_name`, any `aliases[]`, or `pubchem_cid` (Compound only, after Phase 2 NCBI overlay).

| Tool | Pattern | Example seed | Used by |
|---|---|---|---|
| `kg_diet_to_compounds` | `Food → bioactive Compound` (FOUND_IN_FOOD ↔ CONTAINS_COMPOUND, depth 2) | `"Garlic"` | Dietitian agent |
| `kg_compound_to_targets` | `Compound → Target` (TARGETS_PROTEIN, depth 1) | `"CURCUMIN"`, `"curcumin"`, `969516` (CID) | Pharmacologist |
| `kg_compound_to_diseases` | `Compound → Target → Disease` (depth-2 chain) | `"CURCUMIN"` | Pharmacologist; provenance |
| `kg_herb_to_diseases` | `Herb → Disease` (ASSOCIATED_WITH_DISEASE, depth 1) | `"Astragalus membranaceus"` | TCM, Pharmacologist |
| `kg_herb_to_symptoms` | `Herb → Symptom` (TREATS_SYMPTOM, depth 1) | `"Zingiber officinale"`, `"Ginger"` (after Phase 0) | TCM, Dietitian |
| `kg_compound_to_symptoms` | `Compound → Herb → Symptom` (composite, depth 2) | `"CURCUMIN"` | Dietitian (mechanism→clinical) |

### Layer C — Lookup primitives (3 tools)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `kg_hdi_check` | `drug: str`, `herb: str` | `{found, severity, mechanism_class, evidence_tier, citations}` | Curated 50-pair Herb-Drug Interaction panel. Phase 0 alias-matching means natural names work: `("Warfarin", "St. John's Wort")` ✅ |
| `kg_bilingual_term` | `term: str` (any of EN/CN/Pinyin) | `{english, chinese, pinyin, source, confidence}` | SymMap 2.0 TCM herb canonicalization. `黄连` → `{english: "Coptis chinensis", chinese: "黄连", pinyin: "Huanglian"}` |
| `kg_node_neighborhood` | `seed: str`, `max_depth: int=2`, `max_nodes: int=200` | `{nodes, edges}` | Generic fallback when no role-priored tool fits. ⚠️ Currently 400s on free-text labels — see Limitations §3. |

## Worked examples

### Compound pharmacology

```python
# kg_compound_to_targets("CURCUMIN") → typed Cypher chain
{
  "chains": [
    {"edges": [{"src_id": "CURCUMIN", "tgt_id": "Histone-lysine N-methyltransferase MLL",
                "rel_type": "TARGETS_PROTEIN",
                "description": "CURCUMIN targets Histone-lysine N-methyltransferase MLL (Potency: 44668.4)",
                "source_id": "duke:targets_protein"}]},
    {"edges": [{"src_id": "CURCUMIN", "tgt_id": "DNA topoisomerase II alpha",
                "rel_type": "TARGETS_PROTEIN",
                "description": "CURCUMIN targets DNA topoisomerase II alpha (IC50: 15000.0)",
                "source_id": "duke:targets_protein"}]}
  ],
  "raw_subgraph_edge_count": 2
}
```

### Herb-disease (CMAUP)

```python
# kg_herb_to_diseases("Astragalus membranaceus")
{
  "chains": [
    {"edges": [{"src_id": "Astragalus membranaceus", "tgt_id": "Acne vulgaris",
                "rel_type": "ASSOCIATED_WITH_DISEASE",
                "description": "CMAUP plant-disease association",
                "source_id": "cmaup:plant_disease"}]},
    ...
  ]
}
```

### Drug-herb interaction (HDI-Safe-50)

```python
# kg_hdi_check(drug="Warfarin", herb="St. John's Wort")
# Phase 0 fix: matches via Herb.aliases = ["St. John's Wort", "Hypericum perforatum"]
#              and Drug entity_id = "Drug:Warfarin" with prefix-strip
{"found": true, "severity": "severe", "mechanism_class": "CYP450",
 "evidence_tier": "case_report_series", "citations": ["hdi-safe-50:HDI-001"]}
```

### Bilingual TCM

```python
# kg_bilingual_term("黄连")
{"english": "Rhizoma Coptidis,Coptidis Rhizoma", "chinese": "黄连",
 "pinyin": "Huanglian", "source": "symmap", "confidence": 1.0}
```

## Capabilities

The KG can answer any deterministic query along these mission axes:

| Axis | Edges | Source | Aura count |
|---|---|---|---|
| Food → bioactive Compound | `FOUND_IN_FOOD` | Duke + FooDB | 4.13M |
| Herb → Compound | `CONTAINS_COMPOUND` | Duke + FooDB | 85K |
| Compound → Target | `TARGETS_PROTEIN` | Duke + CMAUP | 6.5K |
| Compound → Disease (via Target) | composite chain | Duke + CMAUP | depth-2 traversal |
| Herb → Disease | `ASSOCIATED_WITH_DISEASE` | CMAUP + HERB 2.0 | 763K |
| Herb → Symptom | `TREATS_SYMPTOM` | Duke + SymMap | 41.8K |
| Drug ↔ Herb interaction | `INTERACTS_WITH` | curated HDI-Safe-50 | 50 |
| TCM bilingual canonicalization | node-level alias | SymMap 2.0 | ~4K Herbs |

Per-source provenance, license, and refresh procedure: [`shrine-diet-bioactivity/data/manifest.yaml`](../shrine-diet-bioactivity/data/manifest.yaml) and [`docs/DATASET_PROVENANCE.md`](../docs/DATASET_PROVENANCE.md).

## Limitations (read before using in production)

1. **Layer A (`kg_query`) is degraded.** Returns `"None"` or `"[no-context]"` on representative queries. Root cause is orthogonal to data quality (vector index dim mismatch + free-tier LLM rate limits) — tracked as [issue #5](https://github.com/Syntropy-Health/shrine-diet-bioactivity/issues/5). **Use Layer B (typed traversals) as the primary retrieval path**; Layer A is a documented fallback only.
2. **HDI lookup limited to the curated 50-pair panel.** Not exhaustive. `kg_hdi_check` only finds interactions explicitly in `research-journal/shared/hdi_safe_50.json` (NIH ODS / MSK About Herbs / LiverTox sources). Negative results are not safety guarantees.
3. **`kg_node_neighborhood` 400s on free-text labels.** Tracked as [issue #6](https://github.com/Syntropy-Health/shrine-diet-bioactivity/issues/6). Use the role-priored Layer-B tools instead.
4. **Compound seed-resolution depth.** Phase 2 PubChem overlay covers ~30–40% of the ~7K Duke compounds (non-canonical compound names don't all resolve to PubChem CIDs). Compounds without a PubChem match still need their canonical Duke `entity_id` (typically uppercase). For known canonical names (CURCUMIN, QUERCETIN, BERBERINE) Layer B is reliable; for novel names users may need to consult `data/manifest.yaml`.
5. **Nutrition enrichment is sparse.** Only 647 of 962 FooDB-aware Foods carry `nutrition_100g` (algorithmic plateau in fuzzy-bridge — not an NCBI-solvable gap).
6. **English / Latin / 中文 / Pinyin only.** Other languages not modeled.
7. **`scope_filter` defaults to `["shared"]`.** Tenant-scoped reads need explicit `["shared", "tenant:<slug>"]` and a tenant write path that's intentionally restricted.

## Refresh cadence

| Slot | Source | Procedure | Last refresh |
|---|---|---|---|
| Aura graph (entity ingest) | per-source SQLite + `lightrag/ingest_*.py` | `make lightrag-ingest-local` | see `scope-state-snapshot.md` |
| HDI-Safe-50 panel | curated JSON | `python lightrag/ingest_hdi.py` | 2026-04 |
| Herb/Drug aliases | from HDI JSON | `python scripts/enrich_hdi_aliases.py` | 2026-05-01 |
| MeSH UID overlay | NCBI E-utilities | `python scripts/ncbi/phase_1_mesh_overlay.py --resume` | 2026-05-01 |
| PubChem CID + synonyms | NCBI PubChem | `python scripts/ncbi/phase_2_pubchem_overlay.py --resume` | 2026-05-01 |

## Run locally

```bash
# Prerequisites:
#   - scoped_server running on :9621 (cd shrine-diet-bioactivity && make lightrag-server)
#   - .env with NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, OPENROUTER_API_KEY
#   - MCP_API_KEY (or MCP_AUTH_DISABLED=true for unguarded local dev)

cd mcp
pip install -e .
MCP_TRANSPORT=stdio python -m kg_mcp.server
```

For HTTP transport (the Railway-deployed shape):

```bash
MCP_TRANSPORT=streamable-http MCP_PORT=8080 \
MCP_DISABLE_DNS_REBINDING_PROTECTION=true \
MCP_API_KEY=<some-test-key> \
python -m kg_mcp.server
```

## Layout

```
mcp/
├── README.md                        ← you are here
├── pyproject.toml
├── src/kg_mcp/
│   ├── __init__.py
│   ├── schemas.py                   ← Pydantic input/output models
│   ├── client.py                    ← async httpx wrapper for scoped_server
│   ├── tools.py                     ← pure async tool functions
│   ├── auth.py                      ← Bearer-token middleware (static + Clerk)
│   └── server.py                    ← FastMCP wiring + /health route + auth wrap
└── tests/
    ├── unit/                        ← 69 tests, ~89% coverage
    └── e2e/                         ← live-endpoint tests (opt-in via env)
```

## Boundary contract

This package never:
- writes to the KG (use scoped_server's `/documents/custom_kg` for tenant-scoped writes)
- holds Aura credentials directly (delegates to scoped_server)
- runs Cypher on its own (Layer B/C tools delegate to typed scoped_server endpoints)

This package always:
- enforces Bearer-token auth on every `/mcp*` request
- propagates `scope_filter=["shared"]` by default to scoped_server
- validates inputs/outputs against Pydantic schemas before/after every tool

## See also

- **Researcher's guide** (question-first): [`docs/RESEARCHER_GUIDE.md`](../docs/RESEARCHER_GUIDE.md) — pick your persona, map question → tool, worked walkthroughs
- **Design**: [`research-journal/plans/2026-04-29-mcp-gateway-design.md`](../research-journal/plans/2026-04-29-mcp-gateway-design.md) — toolkit + design tensions + 4 trade-off considerations
- **NCBI enrichment**: [`research-journal/plans/2026-05-01-ncbi-enrichment-and-entity-resolution-design.md`](../research-journal/plans/2026-05-01-ncbi-enrichment-and-entity-resolution-design.md) — current data-overlay plan
- **Auth contract**: `~/.claude/projects/.../memory/mcp-auth-contract.md`
- **Open issues**: [#5 (Layer A degraded)](https://github.com/Syntropy-Health/shrine-diet-bioactivity/issues/5) · [#6 (kg_node_neighborhood 400)](https://github.com/Syntropy-Health/shrine-diet-bioactivity/issues/6) · [#7 (paper-source ingestion)](https://github.com/Syntropy-Health/shrine-diet-bioactivity/issues/7)
