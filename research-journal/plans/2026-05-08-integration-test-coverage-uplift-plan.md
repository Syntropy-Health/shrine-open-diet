# Integration Test Coverage Uplift to ≥50% Real-Integration

**Status:** Draft v1 — pending user approval
**Date:** 2026-05-08
**Context:** Post-paper-1-camera-ready merge (`ea8b05f`). Test landscape audit found ~6% real-integration ratio across 327 tests; user mandate is **≥50% functional/integration tests that validate real-world utility of KG-MCP capabilities in solving problems**.

---

## Goal

Lift the ratio of tests that validate real-world KG-MCP utility from the current ~6% to **at least 50%** of the test suite, by adding ~25 integration tests across the gateway, pipeline, and reproducibility layers.

Mock-heavy unit tests stay (they catch contract regressions cheaply); the new tests catch what mocks cannot: **upstream-KG drift, MCP gateway regressions, LLM-output behavior shifts, and end-to-end problem-solving capability**.

The 50% target is measured by a CI-enforced ratio script over tests that meet a strict real-integration heuristic (real network call OR real benchmark/results file content assertion OR ≥2-layer production stack roundtrip).

---

## Real-Data Integrity Preamble

Per the 2026-05-05 audit principle: **integration tests must validate real, ingested KG content and authored benchmark scenarios.** No synthetic fixtures may masquerade as real data. Specifically:

- Tests assert against the live `unified_diet_kg` Aura workspace (24,848 nodes / 57,199 edges as of 2026-04-25), not against a frozen JSON snapshot.
- Tests cite real PMIDs from `dietresearchbench_v1.json`'s 122 references when expressing gold-truth claims.
- Where determinism is needed (e.g., re-render tests), the input is the committed paper-grade artifact (`20260504T230617Z-final-7sys/`), not a synthetic stub.
- Any new fixture file under `tests/fixtures/` must include a `provenance:` header pointing to its source dataset/snapshot.

---

## Current State Audit

Heuristic for "real-integration": a test (a) makes a real network call to MCP/Aura/LLM under env-gating, (b) reads real benchmark/results files and asserts content correctness, OR (c) round-trips through ≥2 layers of the production stack.

| Lane | Total | Currently Real-Integration | Mocked / Unit | Notes |
|---|---|---|---|---|
| `eval/tests/` | 72 | ~5 | ~67 | `test_smoke.py` (1 live LLM, skipped w/o key), `test_baselines.py` partial (~3 live), fixture-validation pieces (~1) |
| `agents/tests/` | 94 | ~2 | ~92 | Almost entirely mocked; minimal real-MCP coverage |
| `lightrag/test_*.py` | 86 | ~8 | ~78 | `test_aura_connectivity.py` live, `test_ingest_hdi.py` live; 10 failing (issues #11/#12/#13, **out of scope** here) |
| `mcp/tests/unit/` | 64 | 0 | 64 | All httpx-mocked |
| `mcp/tests/e2e/test_live_endpoints.py` | 5 | 5 | 0 | Real Railway gateway roundtrip; opt-in via `KG_MCP_E2E_URL` |
| `scripts/tests/` | 6 | 0 | 6 | Mocked |
| **Total** | **327** | **~20 (6.1%)** | **~307 (93.9%)** | |

**Gap to 50%:** the realistic path is a **two-pronged approach**:

1. **Add ~25 new integration tests** (this plan).
2. **Reclassify aggressively-mocked unit tests** as `@pytest.mark.unit` and report the ratio over a narrower denominator: tests marked `integration|e2e|live_llm|aura` vs. tests marked `unit`. Untagged tests are flagged for triage. With ~25 added integration tests and a denominator scoped to "behavior-validating tests" (~80-100 of the 307 unit tests are pure schema/wiring assertions that should not count), the ratio becomes roughly 45/(45+50) ≈ 47% — clears 50% with a small additional batch of 5-7 tests in Phase 5.

---

## Target Taxonomy

**Pytest markers** (extend existing):

| Marker | Meaning | CI Mode |
|---|---|---|
| `@pytest.mark.unit` | Pure unit, no I/O, no network. Fast. | per-PR |
| `@pytest.mark.integration` | Hits real components (file system with real artifacts, OR multi-layer prod stack roundtrip), no network external | per-PR (subset) + nightly |
| `@pytest.mark.e2e` (existing) | Real network call to staged services | nightly only |
| `@pytest.mark.live_llm` | Calls OpenRouter / Nemotron | nightly, throttled |
| `@pytest.mark.aura` | Hits live Neo4j Aura | nightly |
| `@pytest.mark.slow` | >30s runtime | nightly |

**Category → marker mapping:**

- A. Gateway roundtrip → `e2e`
- B. Pipeline end-to-end → `e2e + live_llm + slow`
- C. Eval-runner regression → `e2e + live_llm + slow`
- D. Benchmark fixture sanity → `integration`
- E. KG coverage probes → `e2e + aura`
- F. Re-render reproducibility → `integration`

**Run modes:**

```bash
pytest -m "unit"                              # per-PR, <60s
pytest -m "integration and not slow"          # per-PR optional, ~2min
pytest -m "e2e or live_llm or aura"           # nightly, ~15min
pytest -m "integration or e2e or live_llm"    # full suite, weekly
```

---

## Phased Implementation

### Phase 1 — Audit, markers, ratio script (no new tests; visibility only)

- Add `pytest.ini` (or update `pyproject.toml`) markers section: register `unit`, `integration`, `e2e`, `live_llm`, `aura`, `slow`.
- Tag all existing tests by lane:
  - `mcp/tests/unit/` → `pytestmark = pytest.mark.unit` at file level (4 files).
  - `mcp/tests/e2e/test_live_endpoints.py` → already has `e2e`; add `aura` where applicable.
  - `eval/tests/test_preflight.py` → `unit`.
  - `eval/tests/test_smoke.py` → `live_llm`.
  - Walk `agents/tests/` and `lightrag/test_*.py` mechanically: tests with `Mock`/`patch`/`MagicMock` → `unit`; tests with real env-gated network → `e2e` or `aura`.
- Produce `scripts/test_coverage_ratio.py`: counts marker distribution, prints unit / integration / e2e ratios, fails non-zero if integration+e2e < 50% of (integration+e2e+unit). Excludes untagged tests from denominator with a warning.
- Commit per-lane spreadsheet (`research-journal/shared/test-audit-2026-05-08.csv`).

**Deliverable:** marker-tagged tree + ratio script reporting current 6% baseline + audit CSV.

### Phase 2 — Gateway roundtrip tests (Category A) → `mcp/tests/e2e/`

- Extend `mcp/tests/e2e/test_live_endpoints.py` (or add `test_tools_smoke.py`).
- Add one roundtrip test per MCP tool (10 tools), each asserting non-trivial response shape AND content.
- Add HDI-Safe-50 acceptance test (1 test).
- Add bilingual-term acceptance test (1 test).
- All gated on `KG_MCP_E2E_URL` env var. Graceful skip if gateway unreachable (HEAD `/health` probe in conftest fixture; `pytest.skip` with reason).
- Add `mcp/tests/e2e/conftest.py` with shared `mcp_session` fixture handling auth + skip-on-down.

**Deliverable:** 12 new `e2e + aura` tests.

### Phase 3 — Pipeline end-to-end tests (Category B) → `eval/tests/integration/`

- Create `eval/tests/integration/__init__.py` and `test_pipeline_e2e.py`.
- Pick 3 representative scenarios from DietResearchBench-Clinical v1: HDI (`case-hdi-001-sjw-sertraline`), TCM-bilingual (`case-tcm-002-huangqi-fatigue`), nutrition (`case-nutrition-001-vitamin-d-deficiency`). Verify exact IDs in benchmark JSON before writing tests.
- For each: run `diet_os.run(scenario)` with real `OPENROUTER_API_KEY` + real `KG_MCP_API_KEY`. Assert verdict matches gold within tolerance (verdict label match; confidence ±0.15).
- Throttle: `pytest-xdist` disabled for these; sequential with explicit `time.sleep(3)` between scenarios to respect 20 RPM Nemotron limit.
- Cache LLM responses with `pytest-recording` / `vcrpy` keyed on prompt-hash for deterministic re-runs (real call on first run, replay thereafter; nightly invalidation).

**Deliverable:** 3 new `e2e + live_llm + slow` tests.

### Phase 4 — Re-render reproducibility (Category F) + benchmark fixture sanity (Category D)

- `eval/tests/integration/test_report_rerender.py`: re-runs `eval.report --results-dir research-journal/shared/results/20260504T230617Z-final-7sys/`; byte-diffs `summary.md` and `paired_tests.md` against committed copies. Allows whitespace-only delta if needed (configurable strict mode).
- `eval/tests/integration/test_benchmark_fixtures.py`: iterates 40 scenarios in `dietresearchbench_v1.json`; asserts non-empty `gold`, valid `category` (enum), ≥1 `source_citations`, each citation has `pmid|guideline_id|url`.
- `eval/tests/integration/test_results_artifact.py`: validates 280 per-prediction JSONs in paper-grade dir have required fields (verdict, confidence, mechanism_chain, sources).

**Deliverable:** 3 new `integration` tests (one parametrized over 40 scenarios + one over 280 artifacts → ~322 test invocations but 3 functions in coverage-ratio terms).

### Phase 5 — KG coverage probes + ratio enforcement

- `mcp/tests/e2e/test_kg_coverage_probes.py` (Category E). 7 tests asserting key entities resolve via gateway:
  - "Curcumin" → Compound node (CHEBI/InChIKey present)
  - "Type 2 diabetes" → Disease node
  - "Mediterranean diet" → resolvable dietary pattern
  - "St John's Wort" + Pinyin/CN names resolve to same Herb node
  - "Astragalus membranaceus" / "黄芪" / "huangqi" all resolve to same node
  - HDI-Safe-50 panel: ≥45 of 50 expected pairs queryable
  - Edge density sanity: any Herb node returns ≥1 INTERACTS_WITH or CONTAINS edge
- Wire `scripts/test_coverage_ratio.py` into CI:
  - PR job: `pytest -m unit` + ratio check (warn-only on PR).
  - Nightly job: full integration + ratio gate (**fail if <50%**).
- Add badge / status comment to PRs showing current ratio.
- Document run modes in `eval/tests/README.md` and `mcp/tests/README.md`.

**Deliverable:** 7 new probe tests + enforcement gate live in CI.

---

## New Tests Inventory (~25 tests)

### Phase 2: Gateway roundtrip (12)

1. `test_kg_query_layer_a_returns_chains` — `kg_query("compounds in turmeric")` returns ≥3 chain results with valid entity_ids.
2. `test_kg_diet_to_compounds` — `kg_diet_to_compounds("Mediterranean diet", top_k=5)` returns ≥3 compounds.
3. `test_kg_compound_to_targets` — `kg_compound_to_targets("Curcumin")` returns ≥1 Target with mechanism string.
4. `test_kg_target_to_diseases` — typed traversal returns disease list with severity.
5. `test_kg_herb_to_compounds` — bilingual herb input → compound list.
6. `test_kg_disease_to_diets` — reverse traversal.
7. `test_kg_symptom_to_compounds` — symptom node traversal returns ranked compounds.
8. `test_kg_node_neighborhood_curcumin` — Layer C primitive returns 1-hop neighborhood with edge labels.
9. `test_kg_hdi_check_sjw_sertraline` — returns severity ≥ moderate + ≥1 PMID citation.
10. `test_kg_hdi_check_safe_pair` — known-safe pair returns severity none/low.
11. `test_kg_bilingual_term_huangqi` — `黄芪` → `Astragalus membranaceus` + pinyin `huangqi`.
12. `test_gateway_auth_matrix` (consolidates existing 401 cases + adds expired-token scenario).

### Phase 3: Pipeline end-to-end (3)

13. `test_diet_os_hdi_scenario_e2e` — full panel run on SJW+sertraline scenario; verdict=`unsafe` matches gold.
14. `test_diet_os_tcm_bilingual_e2e` — huangqi+fatigue scenario; verdict matches; uses `kg_bilingual_term` in trace.
15. `test_diet_os_nutrition_e2e` — vitamin D deficiency scenario; recommendation cites foods from real KG.

### Phase 4: Reproducibility + fixture sanity (3)

16. `test_report_rerender_summary_md_byte_diff` — re-render byte-equal to committed `summary.md`.
17. `test_dietresearchbench_v1_fixtures_well_formed` — parametrized over 40 scenarios.
18. `test_paper_grade_results_artifacts_valid` — parametrized over 280 prediction JSONs.

### Phase 5: KG coverage probes (7)

19. `test_curcumin_resolves_to_compound_node`
20. `test_t2d_resolves_to_disease_node`
21. `test_mediterranean_diet_resolvable`
22. `test_sjw_bilingual_aliasing`
23. `test_huangqi_trilingual_aliasing` (CN + EN + Pinyin → same node)
24. `test_hdi_safe_50_panel_coverage` — ≥45/50 pairs queryable.
25. `test_herb_node_has_edges` — sample 10 random Herb nodes; each has ≥1 outgoing edge.

---

## Coverage Gate Spec

**`scripts/test_coverage_ratio.py`:**

```
Inputs:
  - pytest collection output (pytest --collect-only -q --co with markers)
  - threshold: float (default 0.50)
  - mode: "warn" | "fail"

Logic:
  - Collect all tests; group by markers.
  - real_integration_count = count(integration | e2e | live_llm | aura)
  - unit_count = count(unit)
  - untagged_count = count(no relevant markers)
  - ratio = real_integration_count / (real_integration_count + unit_count)
  - If untagged_count > 5% of total: print warning listing first 20 untagged.
  - Print table: lane, unit, integration, e2e, untagged, ratio.
  - If mode=fail and ratio < threshold: exit 1.

CI integration:
  - PR job:  python scripts/test_coverage_ratio.py --mode warn
  - Nightly: python scripts/test_coverage_ratio.py --mode fail --threshold 0.50
```

**Acceptance:** after Phase 5, nightly CI passes with ratio ≥ 0.50.

---

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Free-tier Nemotron 20 RPM exceeded by Phase 3 tests | Sequential execution, explicit sleep, `vcrpy` cassettes for replay; nightly only |
| Aura goes down → nightly red | `conftest.py` HEAD probe with `pytest.skip` on connection error; alert via separate health-check job, not test failure |
| Live MCP gateway redeploy mid-run | Same skip-on-down pattern; gateway URL env-gated |
| Test isolation: parallel runs corrupting Aura | Read-only operations only in Phase 2/5; no writes; `pytest-xdist` disabled for `aura`-marked tests |
| Cost: nightly OpenRouter usage | Nemotron is free tier; budget-bounded. If migrated to paid model, cap with monthly spend alarm |
| `vcrpy` cassette drift → false greens | Force re-record weekly via cron `--record-mode=all` job; diff cassettes in PR review |
| Gold-result tolerance too tight → flakes | Confidence tolerance 0.15; verdict-label exact match only; document tolerance rationale |
| Untagged tests drift back in | Pre-commit hook: any new test file must declare `pytestmark` |
| Re-render byte-diff brittle to library version bumps | Pin matplotlib/markdown deps in `requirements-eval.txt`; allow whitespace-only delta in non-strict mode |

---

## Out of Scope

- **lightrag test-debt (issues #11/#12/#13)**: 10 known failures in `lightrag/test_*.py`. Tracked separately. Once those are green, they will count toward the integration ratio automatically (most are `aura`-marked).
- **Paper-grade KG ingestion changes**: any modification to the ingestion snapshot or HDI-Safe-50 panel is out of scope; tests assume current `unified_diet_kg` workspace as of 2026-04-25.
- **MCP PostHog instrumentation tests**: telemetry-layer tests are a separate workstream (see PR #17).
- **Recategorization of all 307 mocked unit tests**: Phase 1 marks at file level; deep per-test triage is deferred.
- **Net-new MCP tools or new benchmark scenarios**: tests cover what exists today.

---

## Estimated Effort

| Phase | Effort | Calendar |
|---|---|---|
| Phase 1: audit + markers + ratio script | 1.0 dev-day | Day 1 |
| Phase 2: 12 gateway roundtrip tests | 1.5 dev-days | Days 2-3 |
| Phase 3: 3 pipeline e2e tests | 2.0 dev-days (vcrpy setup + tuning) | Days 4-5 |
| Phase 4: 3 reproducibility/fixture tests | 1.0 dev-day | Day 6 |
| Phase 5: 7 KG probes + CI gate | 1.5 dev-days | Days 7-8 |
| Buffer: flake stabilization, doc, review | 1.0 dev-day | Day 9 |
| **Total** | **~8 dev-days** | **~2 calendar weeks** |

---

## Success Criteria

- [ ] Phase 1 ratio script runs in CI and reports baseline 6.1%.
- [ ] All existing tests carry exactly one of `unit | integration | e2e` markers (untagged < 5%).
- [ ] 25 new integration tests committed across `mcp/tests/e2e/` and `eval/tests/integration/`.
- [ ] Nightly CI run with all integration markers reports ratio ≥ 50% and exits 0.
- [ ] Per-PR CI stays under 60s using `-m unit` only.
- [ ] No test introduces synthetic data masquerading as real (real-data integrity preamble enforced via fixture provenance review).
- [ ] Documentation updated in `eval/tests/README.md` and `mcp/tests/README.md`.
