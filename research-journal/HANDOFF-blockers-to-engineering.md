# Handoff — Blockers from Research Session to Engineering Session

_Authored 2026-05-01 by the research-track session. Counterpart to `HANDOFF-research-via-mcp.md` (engineering → research)._

This doc reports blockers the research session hit while probing `https://kg-mcp-test.up.railway.app`. Full probe data: `research-journal/shared/staged-mcp-probe.md` (commit `0cde3e5`).

The research session is **paused on E2 (panel wiring) and E3 (v1 re-run)** until at least Blocker 1 is resolved. Blockers 2–4 are non-fatal but degrade signal quality.

---

## Status table

| # | Severity | Blocker | Owner | Gate |
|---|---|---|---|---|
| **1** | **🔴 critical** | `kg_hdi_check` returns `found=false` on every textbook HDI entry | engineering | nulls `hdi_recall` metric — paper claim **C1 untestable** until fixed |
| 2 | 🟡 high | `kg_query` Layer A returns `"None"` / `"[no-context]"` | engineering | panel falls back to Layer B (acceptable per design memo §2); document in Limitations |
| 3 | 🟢 medium | `kg_node_neighborhood` 400 on `label=<name>` | engineering | research can avoid this tool |
| 4 | 🟢 low | Seed-casing convention undocumented | engineering | research will normalize client-side as workaround |

---

## Blocker 1 — `kg_hdi_check` finds nothing

**Severity:** critical. The HDI Recall metric (paper claim C1, "KG ablation") cannot be computed without this tool returning hits for the gold panel.

**Reproduce:**
```bash
KEY=$(infisical secrets get MCP_API_KEY \
  --projectId 687cab01-ccc1-4789-99a9-1214bd268f2b --env prod --plain)

# (After initialize + Mcp-Session-Id capture per HANDOFF-research-via-mcp.md)
curl -X POST https://kg-mcp-test.up.railway.app/mcp \
  -H "Authorization: Bearer $KEY" -H "Mcp-Session-Id: $SESSION" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
    "name":"kg_hdi_check",
    "arguments":{"drug":"Warfarin","herb":"Ginkgo biloba"}}}'
```

**Observed:** `{"found":false,"severity":null,"mechanism_class":null,"evidence_tier":null,"citations":[]}`

**Probed variants (all `found=false`):**
- `(Warfarin, Ginkgo biloba)` — coagulation, textbook
- `(warfarin, Ginkgo biloba)` — lowercase drug
- `(Warfarin, St. John's Wort)` — CYP450 induction, textbook
- `(warfarin, Hypericum perforatum)` — Latin name for SJW
- `(Cyclosporine, St. John's Wort)` — severe CYP3A4

**Context:** `scope-state-snapshot.md` (2026-04-29) shows `INTERACTS_WITH = 50` edges in Aura under `scope='shared'`. The data is in the graph; the lookup contract is what's broken.

**Hypotheses (engineering to confirm):**
1. Lookup keys on `entity_id` (e.g., `drug:WARFARIN`, `herb:GINKGO_BILOBA`), not on free-text name. The MCP tool needs a name→id resolution step the research session can't see from outside.
2. Lookup is case-/punctuation-sensitive. `St. John's Wort` vs `St_Johns_Wort` vs the canonical form in HDI-Safe-50.
3. The HDI-Safe-50 panel was loaded under a different node label or relationship type than `kg_hdi_check` is scanning.
4. The 50 edges are present but the `mechanism_class` / `severity` / `evidence_tier` properties weren't stamped during ingest, so the lookup matches but returns nulls — except probe shows `found=false`, so this is unlikely.

**Acceptance criteria for "fixed":**

```bash
# All four pairs return found=true with non-null severity + mechanism_class + ≥1 citation:
("Warfarin", "Ginkgo biloba")     → severity in {moderate, severe}, mechanism: coagulation
("Warfarin", "St. John's Wort")   → severity: severe, mechanism: CYP450
("Cyclosporine", "St. John's Wort") → severity: severe, mechanism: CYP450
("MAOI", "St. John's Wort")       → severity: severe, mechanism: serotonergic
```

(If the canonical form is genuinely `Hypericum perforatum` not `St. John's Wort`, please document and the research session will update its gold-mapping.)

**Diagnostic Cypher engineering can run directly against Aura:**
```cypher
MATCH (a)-[r:INTERACTS_WITH]->(b)
WHERE r.scope = 'shared'
RETURN a.entity_id, a.name, type(r), b.entity_id, b.name,
       r.severity, r.mechanism_class, r.evidence_tier
LIMIT 20;
```

This will surface what entity_id and name forms are actually in the graph for the 50 HDI panel edges — the answer dictates the seed format the MCP tool needs to accept.

---

## Blocker 2 — `kg_query` Layer A degraded

**Severity:** high. The general-purpose NL Q&A tool is non-functional on representative queries.

**Reproduce:**
```bash
# mode=mix, common query
{"name":"kg_query","arguments":{"question":"What compounds in ginger reduce CINV?","mode":"mix","top_k":20}}
→ {"answer":"None","references":[],"scope_filter":["shared"]}

# mode=local
{"name":"kg_query","arguments":{"question":"Curcumin","mode":"local","top_k":10}}
→ {"answer":"None","references":[],"scope_filter":["shared"]}

# mode=naive (no LLM, just retrieval)
{"name":"kg_query","arguments":{"question":"ginger CINV","mode":"naive","top_k":5}}
→ {"answer":"Sorry, I'm not able to provide an answer to that question.[no-context]","references":[]}
```

**Hypotheses (engineering to confirm):**
1. Free-tier Nemotron rate-limit (20 RPM) is dropping calls and the upstream returns `"None"`.
2. Vector index dimension mismatch (per postmortem §9c blocker 5: `Embedding dim mismatch, expected: 2048, but loaded: 768`). Did the re-embed migration (Task #11) complete on the staged Railway instance, or is it still on the local-dev cache?
3. Server config: the `/health` payload reports `"config":"local"` — is that intentional for a Railway-staged endpoint, or should it be `production`?

**Workaround in research session:** the panel will use Layer B (typed traversals) as primary path, per `mcp-gateway-design.md` §2's argued design intent. Layer A becomes last-resort fallback for the Defer / CRS roles only. Documented in Limitations.

**Acceptance criteria for "fixed":** `kg_query("Does ginger reduce CINV?","mix",20)` returns a non-trivial `answer` string with ≥1 entry in `references`.

---

## Blocker 3 — `kg_node_neighborhood` 400

**Severity:** medium. Working around it; not blocking the eval.

**Reproduce:**
```bash
{"name":"kg_node_neighborhood","arguments":{"seed":"Curcumin","max_depth":1,"max_nodes":20}}
→ Error executing tool kg_node_neighborhood:
   Client error '400 Bad Request' for url
   'http://127.0.0.1:9621/graphs?label=Curcumin&max_depth=1&max_nodes=20'
```

The 400 leaks the upstream `scoped_server` URL — minor information disclosure to consumers. Backend rejects `label=Curcumin` (likely expects an entity_id format like `compound:curcumin`).

**Workaround:** research session avoids this tool; agents use the role-priored Layer-B traversals instead.

**Acceptance criteria:** either accept a name-style label and case-fold it to the canonical entity_id, or document that the parameter must be a node ID and update the tool's input schema description accordingly.

---

## Blocker 4 — Seed-casing convention undocumented

**Severity:** low. Workaround is straightforward but should be documented or auto-normalized.

**Observed:**

| Entity type | Form that works | Form that fails |
|---|---|---|
| Compound | `CURCUMIN`, `QUERCETIN`, `BERBERINE` | `Curcumin`, `curcumin` |
| Herb | `Ginkgo biloba` (Latin title-case) | likely common name fails |
| Food | `Garlic` (common title-case) | likely lowercase fails |
| TCM term | bilingual any of EN/CN/Pinyin works | — |

**Recommendation:** either (a) the staged endpoint case-folds seeds against a canonical-name index server-side, or (b) the tool's input schema documents the case convention per entity-type and the design memo §3 is updated to match. Either is fine; pick one.

**Workaround:** research session will implement a `normalize_seed(entity_type, value)` helper in `agents/tools/kg_query.py` adapter:
```python
def normalize_seed(entity_type: Literal["compound", "herb", "food", "term"], value: str) -> str:
    if entity_type == "compound": return value.upper()
    if entity_type == "herb":     return value.title()
    if entity_type == "food":     return value.title()
    return value
```

---

## What the research session will do while waiting

While Blocker 1 is open, the research session works on items that don't depend on `kg_hdi_check`:

- **E4.1, E4.2** — paper draft scaffold + Methods pre-write from existing memos (zero KG dependency)
- **E4.6** — related work bibliography pull (web research only)
- **Read-only audits** of `staged-mcp-probe.md` results and the postmortem

The research session does **not** touch `lightrag/`, `mcp/`, `ingest_*.py`, `bootstrap_scope.py`, `migrate_embeddings_to_aura.py`, `scoped_server.py`, `scripts/capture_scope_state.py`, or the Aura graph.

---

## Signal back to research session

Engineering, please reply by:
1. Updating this doc with hypothesis confirmation and ETA per blocker.
2. Or pinging via the project channel that the staged endpoint passes the Blocker-1 acceptance criteria.

Once Blocker 1 is green, the research session resumes E2 (panel wiring with Layer B) and E3 (v1 re-run on test split).
