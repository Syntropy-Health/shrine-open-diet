# Paper 1 Design — Pre-Fetched Retrieval and Role-Priored Tools for Multi-Agent Clinical Research

_Authored 2026-05-03. Brainstorming session output._
_Two-paper split decision in `2026-04-26-v1-postmortem-and-next-steps.md` §7._
_Companion v2 plan: `2026-04-29-v2-benchmark-expansion.md`._

---

## 1. Context & decisions

### Two-paper split

| | Paper 1 (this design) | Paper 2 (v2, deferred) |
|---|---|---|
| Target | **ML4H 2026 Findings** (4 pp, non-archival) + arXiv | CHIL 2027 / npj Digital Medicine "Agentic AI" |
| Dataset | DietResearchBench-Clinical v1 (n=40, single-author) | v2 (n=200, A1+A2 IAA κ≥0.6) |
| Headline | **Architecture** — pre-fetched retrieval + role-priored tools | Clinical-grade benchmark + system |
| Status | Design approved; ready to draft | 3-month annotation pipeline pending |

### Approved framing decisions

| Decision | Choice | Rationale |
|---|---|---|
| Publication target | α — ML4H Findings 4 pp non-archival + arXiv | Lower reviewer bar; non-archival permits later journal resubmit; ~4-month timeline |
| Headline contribution | **Architecture-headline (option A)** | Strongest claim is architectural; benchmark released as resource without resource-paper scrutiny |
| LLM | Free-tier OpenRouter Nemotron-3-nano-30B | Deliberate "constrained-inference" framing; Qwen-3-235B swap doesn't strengthen headline claims; consistent across all baselines |
| Orchestration | Stay on AG2 v0.12 (Apache 2.0, AG2AI fork) | Sufficient; Pydantic-AI defer to v2 ablation; explicitly avoid AutoGen v0.4 (Microsoft maintenance mode) |
| Clinician co-author | Defer to v2 | Locks us to Findings track but unlocks fastest path |
| JingFang baseline | Cite-only, no reproduction | Reproducing adds 1 week; differentiation in Related Work prose suffices for Findings |

---

## 2. Goal & headline contribution

**Working title:** "Pre-Fetched Retrieval and Role-Priored Tools for Multi-Agent Clinical Research over Diet, Herb, and TCM Knowledge Graphs"

**Three contributions stated up-front in the Introduction:**

1. **`diet_os`** — a 6-role AG2 multi-agent system (Dietitian, Pharmacologist, TCM Practitioner, Clinical Research Scientist, Safety Reviewer, Defer-to-Clinician) for clinical research over a 5M-edge unified diet/herb/TCM knowledge graph queried via streamable-HTTP MCP. Pre-fetched typed-traversal retrieval bundles replace LLM-driven tool calls under constrained inference (free-tier 30B Nemotron).

2. **Bonferroni-significant verdict-κ uplift and structural HDI Recall separation** over MedAgents, MDAgents, and yang2025 baselines on `DietResearchBench-Clinical` v1 — the headline architectural-ablation result.

3. **`DietResearchBench-Clinical`** — a 40-scenario v1 reference benchmark spanning herbal single-symptom, nutrition single-nutrient, multi-drug HDI, and TCM bilingual scenarios with a 6-metric evaluation panel (verdict κ, ECE, HDI Recall, provenance faithfulness, defer accuracy, bilingual coverage).

### Innovation gaps claimed (post R1 literature scan)

1. **Domain-specific KG fusion** — no prior published system unifies herbs + phytochemical compounds + foods + molecular targets + diseases + nutritional profiles at 5M edges bridging Western dietetics + TCM
2. **Bilingual food-bioactive reasoning in one agent round** — combines OpenNutrition (326K foods) + FooDB (4.1M compound-food pairs) + SymMap bilingual TCM cross-walk
3. **First public HDI + diet-bioactive + TCM crosswalk benchmark** — neither TCM-Eval, TCM-5CEval, AgentClinic, nor any drug-drug interaction benchmark covers this intersection

---

## 3. Paper outline (4 pp ML4H Findings)

```
Abstract                                    150 words
Introduction                                ~0.5 pp
   Hook: clinical research teams as multi-agent systems
   3 contributions stated explicitly
Related Work                                ~0.4 pp
   - Multi-agent clinical reasoning: MedAgents, MDAgents, yang2025, AgentClinic, ClinicalAgent
   - TCM multi-agent: JingFang (cite-only)
   - KG-grounded MAS: AMG-RAG, MedRAG, OpenTCM
   - Threat: Wu et al. 2025 "Safer Therapy" (addressed in Discussion)
System: diet_os                             ~0.7 pp + 1 architecture figure
   - Architecture: triage → retrieve_for_question → 6-role panel → calibrator → synthesis
   - Pre-fetched retrieval bundle (Option A) — rationale: free-tier Nemotron tool-call hallucination
   - Role-priored Layer-B/C tools (Dietitian → kg_diet_to_compounds + kg_compound_to_symptoms; etc.)
   - 5-mode LightRAG / typed-Cypher MCP gateway
Benchmark: DietResearchBench-Clinical       ~0.4 pp
   - 40 scenarios × 4 categories
   - GoldStandard schema; 6-metric panel
   - v2 expansion (n=200, IAA) referenced as companion paper
Experimental Setup                          ~0.3 pp + cost & latency table
   - Free-tier Nemotron-30B; AG2 v0.12; Aura 8GB; MCP staged endpoint
   - 6 baselines: single_llm, single_llm_rag, yang2025, medagents, mdagents, diet_os
   - Test split n=9; full n=40 reported
Results                                     ~0.7 pp + 2 figures (matrix + heatmap)
   - Headline matrix: full-40 mean [95% CI bootstrap]
   - Paired bootstrap with Bonferroni correction (5 comparisons, α'=0.01)
   - Per-category breakdown heatmap (herbal/nutrition/HDI/TCM × 6 systems)
   - Failure-mode taxonomy: 10 case studies classified by agent-role failure
Discussion                                  ~0.3 pp
   - C1 (HDI Recall) and C2 (verdict κ): paper-grade
   - C3 (provenance) source-attribution-based; full Cypher round-trip deferred
   - C5 (ECE) limitation: free-tier uncalibrated; Platt/isotonic deferred to v2
   - **Wu et al. "Safer Therapy" rebuttal**: their single-GP-vs-MDT setup tests
     debate-style consensus on medication conflict; our HDI Recall structural
     ablation tests KG-grounding (orthogonal axis). The two findings co-exist:
     debate alone is insufficient; KG-grounded retrieval is what produces HDI signal.
Limitations                                 ~0.2 pp
   - n=40 single-author gold (v2 addresses)
   - Free-tier Nemotron variance + JSON quality (workaround documented)
   - AG2-specific orchestration; Pydantic-AI ablation deferred
   - HDI-Safe-50 covers ~X% of universe (per E5 KG coverage audit)
Future Work + Conclusion                    ~0.2 pp
   - v2 benchmark expansion (n=200 + IAA)
   - Pydantic-AI orchestration ablation
   - Paid-tier LLM ablation (Qwen-3-235B / GPT-5)
   - Calibrator post-hoc on held-out fold
References                                  overflow page
Appendix (if space): scenario examples, tool schemas, prompt listings
```

---

## 4. Enrichment work plan

Estimated total: ~2 work days (~14-15 hours) before drafting begins.

| ID | Task | Description | Effort | Outputs |
|---|---|---|---|---|
| E1 | **Full-40 matrix run** | All 6 baselines × all 40 scenarios via `make eval-run --split=all` (or extend runner) | 1.5 hr wall-clock + 30 min setup | New results dir; updated summary.md |
| E2 | **Source-attribution provenance metric** | Add `--cypher-runner=source-attribution` flag to `eval/report.py`. Runner returns True iff edge.source_id starts with one of `cmaup:`, `duke:`, `herb2:`, `symmap:`, `hdi-safe-50:`. Tested via TDD. | 30 min | Provenance metric becomes a real number in summary.md |
| E3 | **Per-category breakdown** | Slice existing results by `scenario.category`. Add a heatmap renderer to `eval/report.py`. | 1 hr | New `category_breakdown.md` + `category_heatmap.png` |
| E4 | **Failure-mode taxonomy** | Pull 10 case studies (3 successes + 7 failures) from full-40 run. Classify failures by agent role: triage misclassification, retrieval seed-norm failure, panel mis-vote, moderator hallucination, calibrator under-confidence. Markdown table. | 4 hr | `research-journal/shared/results/<run>/failure_taxonomy.md` |
| E5 | **KG coverage audit** | Compare HDI-Safe-50 (50 entries) against NIH ODS herb-drug interactions list (~250 entries) and NCCIH herb-drug factsheets (~100 entries). Report % overlap. Inform HDI Recall denominator interpretation. | 4 hr | `docs/kg-coverage-audit.md` with overlap table |
| E6 | **Cost + latency telemetry** | 20-line `cost_tracker` decorator on AG2 `ConversableAgent.generate_reply`. Captures token in/out + wall-clock per role × scenario. Export to `cost_latency.csv` per run. | 2 hr | `agents/cost_tracker.py` + `cost_latency.csv` per run + paper table |
| E7 | **JingFang cite-only block** | Read JingFang paper carefully. Write 1 paragraph in Related Work + 1 row in comparison-table footnotes. | 1 hr | Related Work prose |
| E8 | **Wu et al. "Safer Therapy" rebuttal** | Write Discussion subsection arguing our finding is orthogonal (axis: KG-grounding), not contradictory. | 1 hr | Discussion prose |

---

## 5. Comparison set & positioning

### Baselines we run (all in `eval/baselines/`)

| Baseline | What it ablates | Cite |
|---|---|---|
| `single_llm` | No tools, no panel, no KG | — (control) |
| `single_llm_rag` | Naive RAG over the same KG | — (control) |
| `yang2025` | 2-role dietitian-pharmacist | Yang et al. 2025 |
| `medagents` | n-role debate, no KG | Tang et al. EMNLP 2024 |
| `mdagents` | Adaptive routing, no KG | Kim et al. NeurIPS 2024 |
| **`diet_os`** | **Full system: 6 roles + KG-grounded retrieval bundle** | **This paper** |

### Cited differentiation (Related Work + comparison footnotes)

| System | Why we cite | Why we don't reproduce |
|---|---|---|
| JingFang (2025) | Closest TCM-MAS competitor | Prescription-only, no Western nutrition, no bilingual; reproducing diverges from our Diet+TCM scope |
| OpenTCM (2025) | Closest KG+TCM competitor | TCM-only KG; ours is superset |
| AMG-RAG (2025) | Closest agentic-KG MAS | Live PubMed retrieval; orthogonal to our pre-fetched typed-Cypher approach |
| MedRAG (2025) | Hierarchical KG-EHR fusion | EHR-grounded; our KG is ontology-grounded |
| AgentClinic (2024) | Multi-modal sequential simulation | Different evaluation paradigm (sequential consultation); our static-question setup is a separate axis |
| TCM-Eval / TCM-5CEval (2025) | TCM benchmark prior art | Knowledge-only QA; no panel deliberation evaluation |

### Threats explicitly addressed

- **Wu et al. 2025 "Safer Therapy":** finding that single GP ≈ MDT MAS for medication conflict. **Our rebuttal:** their axis is debate consensus; our axis is KG-grounding. HDI Recall structural separation (0.498 vs 0.000) shows debate without KG cannot recover HDI claims; debate with KG can. The two findings co-exist on orthogonal axes.

---

## 6. Schedule

| Day | Activity |
|---|---|
| Day 1 | E1 + E2 + E3 (full-40 + provenance + per-category) |
| Day 2 | E4 + E5 + E6 (failure taxonomy + KG coverage + cost telemetry) |
| Day 3 | Drafting: Methods (System + Benchmark + Experimental Setup) + figures |
| Day 4 | Drafting: Results + Discussion + statistical tables |
| Day 5 | Drafting: Intro + Related Work + Limitations + Future Work; E7 + E8 prose |
| Day 6 | Self-review + figure polish + bibliography (`research-journal/shared/bibliography.bib`) |
| Day 7 | arXiv submission (cs.AI + cs.IR + q-bio.QM cross-list); buffer for fixes |

Then queue ML4H 2026 Findings submission when the call opens (~Sep 8 deadline).

---

## 7. Risks ranked

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | Free-tier Nemotron rate-limits choke full-40 run mid-stream | High | Resumable runner already supports per-system manifests; chunk by system if needed |
| 2 | Failure taxonomy on n=40 thin (some cells <3 samples) | Medium | Classify what's there; tag thinness in caption |
| 3 | KG coverage audit reveals HDI-Safe-50 < 20% of HDI universe | Medium | Document as metric-denominator caveat; doesn't kill the structural ablation |
| 4 | Wu et al. rebuttal framing read as "moving the goalposts" | Low-medium | Be explicit about axis distinction; show the data-grounded counter |
| 5 | Aura 8GB / staged MCP gateway downtime during full-40 | Low | Engineering session monitors; we have non-staged Cypher fallback if needed |
| 6 | arXiv reviewers (informal) flag missing clinician co-author | Medium | Limitations section + v2 plan acknowledge; ML4H Findings tolerates |
| 7 | Drafting overruns 5 days | Medium | Day 7 buffer; v2 paper absorbs anything cut for length |

---

## 8. Out of scope (deferred to v2 / paper 2)

- Inter-Annotator Agreement (κ≥0.6 between A1 RD + A2 PharmD)
- n=200 expansion across 7-category coverage matrix
- Difficulty stratification (easy/medium/hard)
- Calibrator post-hoc Platt/isotonic on held-out fold
- External validity transfer to MedQA / BioASQ / AgentClinic format
- Multi-seed variance reporting
- Pydantic-AI orchestration ablation (1.5-day migration documented)
- Paid-tier LLM ablation (Qwen-3-235B / GPT-5 / Sonnet 4.6)
- Cypher round-trip provenance verification (vs. source-attribution proxy)
- Bilingual metric redesign (read panel deliberation text, not just candidate_chains)
- UC5 "systematic review" persona via `kg_disease_to_herbs` (engineering-side toolkit extension)

Each item is tracked in `2026-04-29-v2-benchmark-expansion.md` or
`research-journal/shared/e2-panel-mcp-wiring-results.md` for v2 paper.

---

## 9. Spec self-review

Inline checklist applied:

- **Placeholders:** none. Every section has concrete content.
- **Internal consistency:** §3 outline matches §4 enrichment plan E4 (failure taxonomy referenced in Results); §5 comparison set matches Related Work in §3 outline. ✅
- **Scope check:** focused on a single 4-pp paper. v2 + Pydantic-AI + paid-LLM all explicitly out-of-scope per §8. ✅
- **Ambiguity:** "JingFang cite-only" specifies 1 paragraph + 1 footnote-row, no reproduction. "Source-attribution provenance" specifies the prefix list. ✅
- **One open ambiguity worth flagging:** §6 Day 7 buffer assumes arXiv submission completes Day 6; if not, Day 7 absorbs. Acceptable.

Spec is ready for handoff to writing-plans.
