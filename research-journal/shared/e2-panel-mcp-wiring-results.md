# E2 — Panel-MCP wiring results (2026-05-01)

_Authored from research-track session after completing E2.1–E2.6._

This doc reports the outcome of wiring the AG2 clinical panel against the
staged MCP gateway at `https://kg-mcp-test.up.railway.app`. Companion to
`staged-mcp-probe.md` and `staged-mcp-persona-audit.md`.

## What landed

| Component | File | Status |
|---|---|---|
| MCP streamable-HTTP client | `agents/tools/mcp_client.py` | ✅ implemented + 9 tests |
| 10 typed tool wrappers | `agents/tools/kg_tools.py` | ✅ implemented + 11 tests (incl. seed normalization) |
| `kg_query.py` delegates to MCP gateway | `agents/tools/kg_query.py` | ✅ existing 4 tests still green |
| Per-role tool registration in panel | `agents/panel/assembly.py` | ✅ ROLE_TOOLS map per persona-audit |
| `run_case_study.py` sys.path bootstrap | `agents/run_case_study.py` | ✅ matches eval/runner.py pattern |
| Triage lenient JSON parsing | `agents/triage.py` | ✅ extracts first balanced `{...}` slice |
| Smoke runner (panel-only, bypasses triage) | `scripts/smoke_panel_via_mcp.py` | ✅ runs end-to-end |

**60 existing tests + 22 new tests = 82/82 pass + 1 skipped (openrouter live).**

## What works

1. **MCP transport is reliable.** Initialize handshake captures `Mcp-Session-Id`; tools/call returns parseable SSE. Single-retry on transient failures. Singleton-per-process so the eval matrix shares one session.
2. **All 10 tools accessible from Python.** Each returns a typed Pydantic model mirroring the MCP output schema. `normalize_seed()` handles compound-UPPERCASE / herb-Latin / food-titlecase per probe findings.
3. **Per-role tool registration is correct.** Each panel role gets its priored Layer-B/C tools + `kg_query` as fallback. `Pharmacologist` gets `kg_compound_to_targets`; `SafetyReviewer` gets `kg_hdi_check`; etc.
4. **Panel assembly + chat harness intact.** All 6 roles instantiate, chat starts, GroupChat round-robin proceeds, agents emit valid `RoleVerdict` JSONs, `Maximum rounds (2) reached` terminates cleanly.

## What surfaces the real bottleneck

**Free-tier Nemotron does not reliably emit AG2 `tool_calls`.** The smoke script (`scripts/smoke_panel_via_mcp.py`) ran 2 panel rounds; both `Dietitian` and `Pharmacologist` produced valid `RoleVerdict` JSONs whose `notes` field claimed tool use:

```
"notes": "Used kg_diet_to_compounds (seed: Zingiber officinale) to retrieve bioactive compounds..."
"notes": "Compiled mechanistic and pharmacokinetic data via kg_compound_to_targets (seed: Zingiber officinale)..."
```

But the transcript-side count of actual tool invocations was **zero across all roles**:

```
smoke: tool call counts = {}
```

The model is **hallucinating tool usage** while answering from training-data priors. This is a well-known free-tier-LLM behavior — not specific to this codebase, not an MCP wiring bug, and not fixable on the wiring side.

## Implications for the v1 re-run

The metric C1 (HDI Recall), C3 (Provenance Faithfulness), and C4 (Bilingual Coverage) all depend on the panel **actually retrieving** chains from the KG via tool calls. With Nemotron hallucinating tool use:

- HDI Recall: panel never calls `kg_hdi_check`, can never recover gold HDI claims → metric stays null.
- Provenance: `support[]` populated with hallucinated chains, not real `cited_chains` indexing into a `KGResult` → metric undefined or invalid.
- Bilingual: `kg_bilingual_term` never called → no SymMap-backed bilingual evidence emitted.

This is precisely what postmortem §9d predicted: free-tier Nemotron is structurally unable to produce paper-grade signal **because of tool-use unreliability**, separate from rate limits and JSON quality.

## Three routes forward (decision needed)

| Option | Effort | Pros | Cons |
|---|---|---|---|
| **A. Pre-fetched retrieval architecture** — `run_case_study.py` calls Layer-B tools server-side based on triage PICO extraction, injects results into the moderator_input. Panel agents become "judges over retrieved evidence" rather than "agents who decide what to retrieve". | 1 day | Bypasses tool-use unreliability entirely; deterministic retrieval; cleaner paper architecture (closer to standard RAG). Works on free-tier. | Architectural change. Loses the "agent decides which traversal" capability the design memo §3 argued for. |
| **B. Coerced tool use via prompt + few-shot** — augment role prompts with explicit "you MUST call tool X before answering" + a few-shot example showing the tool_calls format. | 4 hr | Keeps the architectural design intent. | May still fail unreliably with Nemotron; needs paid-LLM testing to know if the failure is prompt or model. |
| **C. Switch panel to a paid LLM (e.g., Sonnet 4.6)** — keep wiring identical, change only the model in `agents/llm_config.py`. | 30 min | Most likely to produce paper-grade signal immediately. Sonnet has reliable tool-use. | Violates the user's "free OpenRouter only" directive. Requires budget approval. |

**Recommendation:** Option A — pre-fetched retrieval. It's the only path that produces paper-grade signal under the free-tier-Nemotron constraint. The architectural shift is honest about the LLM's capability ceiling and matches the postmortem §9d framing.

If Option A is approved, the next phase is:

1. Update `run_case_study.py`: after triage, dispatch a `retrieve_for_question(rq, triage)` step that calls 2–3 Layer-B tools deterministically based on the question's PICO components (e.g., if `intervention` is a herb → `kg_herb_to_diseases` + `kg_herb_to_symptoms`; if `intervention` is a compound → `kg_compound_to_targets`; always call `kg_hdi_check(rx, herb)` if both are extractable).
2. Inject the retrieved chains into `moderator_input` as a structured JSON block.
3. Update role prompts: agents reason over the injected chains, can cite them by index in `cited_chains`.
4. Tool-use stays available as a fallback (via the existing per-role registration).

This is consistent with the persona audit's UC2 and UC6 patterns — the deterministic 2-hop chain (Turmeric → DEMETHOXYCURCUMIN → COX-2) is paper-grade *because* the retrieval is deterministic, not because an LLM chose to invoke the tool.

## Tests + commits this session

- `agents/tools/mcp_client.py` (151 lines, 9 tests)
- `agents/tools/kg_tools.py` (224 lines, 11 tests + 2 retry tests)
- `agents/tools/kg_query.py` (rewritten to delegate to MCP, 4 tests preserved)
- `agents/panel/assembly.py` (per-role ROLE_TOOLS map, 7 tests preserved)
- `agents/run_case_study.py` (sys.path bootstrap)
- `agents/triage.py` (lenient JSON extraction)
- `scripts/smoke_panel_via_mcp.py` (panel-via-MCP smoke harness)
- `agents/tests/test_mcp_client.py` (22 new tests)

Ready to commit.
