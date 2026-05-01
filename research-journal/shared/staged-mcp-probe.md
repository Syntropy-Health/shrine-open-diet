# Staged MCP gateway — capability probe (2026-05-01)

_Authored from research-track session E1 discovery against `https://kg-mcp-test.up.railway.app`._
_Probe artifacts cached at `/tmp/mcp-probe/*.txt` for the duration of the session._

## TL;DR

The staged MCP gateway is **live and serving the unified Aura KG**. All 10 tools per `2026-04-29-mcp-gateway-design.md` are registered. **Layer B typed traversals work and return real provenance chains** when seed names match the canonical case. **Layer C `kg_hdi_check` is not finding any HDI-Safe-50 entries** (regression or unloaded panel — needs engineering attention before paper-grade run). **Layer A `kg_query` LLM synthesis is degraded** — returns `"None"` or `"no-context"` on representative queries. The panel should prefer Layer B for the v1 re-run and treat Layer A as last-resort fallback.

## Endpoint shape

| Property | Value |
|---|---|
| Base URL | `https://kg-mcp-test.up.railway.app` |
| MCP transport | Streamable HTTP at `POST /mcp` |
| Health (no auth) | `GET /health` → `{"status":"ok","mcp":"ok","scoped_server":{"status":"ok","config":"local"}}` |
| Auth | `Authorization: Bearer <MCP_API_KEY>` (Infisical: SyntropyHealth App / prod / `MCP_API_KEY`) |
| Server | `kg-mcp` v1.27.0 — supports tools, prompts (listChanged=false), resources |
| Session | `Mcp-Session-Id` header issued on `initialize`; required on subsequent calls |
| Backing scoped_server | `http://127.0.0.1:9621` (internal — surfaces in error traces, e.g. `kg_node_neighborhood` 400) |

## Tools registered (verified via `tools/list`)

All 10 tools per the design memo are live. Each carries the documented input/output schema.

| Layer | Tool | Status from probe |
|---|---|---|
| A | `kg_query` | ⚠️ degraded (`answer="None"` or `"no-context"`) |
| B | `kg_diet_to_compounds` | ✅ working — returns chains |
| B | `kg_compound_to_targets` | ✅ working with UPPERCASE seed |
| B | `kg_compound_to_diseases` | not yet probed |
| B | `kg_herb_to_diseases` | ✅ working with Latin name |
| B | `kg_herb_to_symptoms` | not yet probed |
| B | `kg_compound_to_symptoms` | not yet probed |
| C | `kg_hdi_check` | ❌ **always returns `found=false`** — investigate |
| C | `kg_bilingual_term` | ✅ working — `黄连` → `Coptidis Rhizoma` / `Huanglian` |
| C | `kg_node_neighborhood` | ⚠️ 400 from backend on `label=Curcumin` |

## Seed-casing convention (critical for panel wiring)

The Layer-B tools resolve free-text seeds against canonical entity names. The casing convention varies by entity type:

| Entity | Canonical form | Example | Failure mode |
|---|---|---|---|
| **Compound** | `UPPERCASE` | `CURCUMIN`, `QUERCETIN`, `BERBERINE` | `Curcumin` → 0 chains |
| **Herb** | Latin scientific name, title case | `Ginkgo biloba`, `Curcuma longa` | likely fails on common name |
| **Food** | Common name, title case | `Garlic`, `Ginger` | likely fails on lowercase |
| **TCM (bilingual)** | any of EN/CN/Pinyin | `黄连`, `Huanglian`, `Coptidis Rhizoma` | bilingual tool dedupes |

**Action for panel wiring (E2.2):** when an agent emits a free-text seed, the panel adapter must normalize per entity-type before calling Layer-B. Suggested helper:

```python
def normalize_seed(entity_type: Literal["compound", "herb", "food", "term"], value: str) -> str:
    if entity_type == "compound": return value.upper()
    if entity_type == "herb":     return value.title()  # naive — refine vs SymMap if needed
    if entity_type == "food":     return value.title()
    return value
```

## Probe results (representative)

### Layer B works — `kg_diet_to_compounds("Garlic")`

5 chains, depth-2: `Garlic --[FOUND_IN_FOOD]--> 1,2,3,4,6-PENTAGALLOYLGLUCOSE --[CONTAINS_COMPOUND]--> Terminalia chebula` (and 4 similar). Real evidence path with `source_id` (`duke:found_in_food`, `duke:contains_compound`) — paper-grade provenance.

### Layer B works — `kg_herb_to_diseases("Ginkgo biloba")`

5 chains, single-edge: `Ginkgo biloba --[ASSOCIATED_WITH_DISEASE]--> Abdominal pelvic pain` etc. `source_id="cmaup:plant_disease"`. Confirms Task #10's CMAUP plant-disease backbone is reachable through MCP.

### Layer C bilingual works — `kg_bilingual_term("黄连")`

```
{ "english": "Rhizoma Coptidis,Coptidis Rhizoma",
  "chinese": "黄连",
  "pinyin": "Huanglian",
  "source": "symmap",
  "confidence": 1.0 }
```

This is paper-quality: confidence=1.0, source-attributed.

### Layer C HDI check — broken or unloaded

Probed four canonical HDI panel entries; all returned `found=false`:
- `(Warfarin, Ginkgo biloba)` — textbook coagulation interaction
- `(Warfarin, St. John's Wort)` — CYP450 induction
- `(warfarin, Hypericum perforatum)` — same as above with Latin name
- `(Cyclosporine, St. John's Wort)` — severe CYP3A4 induction

**Hypotheses for the failure:**

1. The HDI-Safe-50 panel has only 50 edges in the live graph (per `scope-state-snapshot.md`: `INTERACTS_WITH = 50`). The lookup may key on entity_id rather than name — both `drug` and `herb` strings need to match canonical IDs the staged endpoint expects.
2. The lookup may not normalize case or punctuation (`St. John's Wort` vs `St_Johns_Wort` vs `St. Johns Wort`).
3. The HDI-Safe-50 panel may not be wired through `kg_hdi_check` yet on the staged endpoint despite being in the graph.

**Impact:** if `kg_hdi_check` doesn't return matches, the v1 `hdi_recall` metric will be 0 across all systems just as in Run 4. The metric requires the system to retrieve gold HDI claims — and the panel agents will rely on this tool. **This is the highest-priority blocker for paper-grade signal.**

**Recommended action:** message engineering — share the four (drug, herb) pairs probed; request either (a) confirmation of the canonical name format, or (b) fix to normalize at the lookup layer.

### Layer A LLM synthesis — degraded

| Mode | Query | Response |
|---|---|---|
| `mix` | "What compounds in ginger reduce CINV?" | `answer="None"`, refs=[] |
| `local` | "Curcumin" | `answer="None"`, refs=[] |
| `naive` | "ginger CINV" | `answer="Sorry, I'm not able to provide an answer to that question.[no-context]"`, refs=[] |

The `[no-context]` suffix in `naive` mode tells us retrieval found no context; the LLM's "Sorry…" is a refusal templated when context is empty. The `mix`/`local` `answer="None"` likely indicates the upstream LLM call (free-tier Nemotron) returned the literal string `"None"` or timed out — consistent with postmortem §9d's free-tier observations.

**Impact:** the panel must NOT depend on `kg_query` for primary information. Use Layer B for grounded retrieval.

## Implications for the v1 re-run plan

**Updated E2 (panel wiring) — narrower than originally planned:**

- **Use Layer B as the primary information path** for all retrieval-using roles. This was already the design intent per `mcp-gateway-design.md` §2 ("LightRAG `mix`/`hybrid` covers general NL Q&A but is not enough for the publication's panel agents because of (1) no traversal-pattern guarantees ..."). The probe confirms Layer A is degraded enough to *force* this design.
- **Implement seed-casing normalization** in `agents/tools/kg_query.py` adapter before Layer-B calls.
- **Skip `kg_hdi_check`** in the panel until engineering signals it's fixed. Until then, Safety Reviewer falls back to `kg_node_neighborhood` (which has its own 400 issue) or to direct kg_query (degraded). **Neither is a real substitute** — the HDI Recall metric stays null until `kg_hdi_check` works.
- **`kg_query` Layer A** stays as last-resort fallback for the Defer / CRS roles whose work isn't retrieval-driven.

**Decision needed before E2 starts coding:**

1. Wait for `kg_hdi_check` fix? (Recommended — without it, the headline `hdi_recall` metric is null and the C1 falsifiable claim can't be tested.)
2. Or proceed with E2 + E3 against the test split with Layer A degraded + HDI metric expected to null, and document the residual issue in Limitations? (Faster, but produces a degraded paper signal similar to Run 4.)

## Reproducing the probe

```bash
KEY=$(infisical secrets get MCP_API_KEY \
  --projectId 687cab01-ccc1-4789-99a9-1214bd268f2b \
  --env prod --plain)

# 1. Initialize (capture Mcp-Session-Id from response headers)
curl -i -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"x","version":"0"}}}'

SESSION=<from Mcp-Session-Id header>

# 2. Notify initialized
curl -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" -H "Mcp-Session-Id: $SESSION" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. List tools
curl -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" -H "Mcp-Session-Id: $SESSION" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 4. Call a tool
curl -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" -H "Mcp-Session-Id: $SESSION" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"kg_diet_to_compounds","arguments":{"seed":"Garlic","top_k":5}}}'
```

## Open questions for engineering

1. **`kg_hdi_check` lookup keying:** what canonical form does the lookup expect for `drug` and `herb`? Is the HDI-Safe-50 panel actually wired through this tool on the staged endpoint?
2. **`kg_query` Layer A LLM:** `"None"` vs `"[no-context]"` — is this free-tier rate-limit, embedder dim mismatch (per postmortem §9c blocker 5), or a config issue specific to the staged endpoint?
3. **`kg_node_neighborhood` 400:** what is the expected `label` parameter format? Does it want a node ID or a Neo4j label?
4. **Seed normalization:** should the staged endpoint case-fold seeds itself before lookup, or is the convention that callers must normalize? (Either is fine; pick one and document.)
