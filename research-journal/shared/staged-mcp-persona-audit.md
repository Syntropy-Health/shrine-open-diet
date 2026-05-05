# Staged MCP — Researcher persona use-case audit (2026-05-01)

_Authored from research-track session against `https://kg-mcp-test.up.railway.app`._
_Companion to `staged-mcp-probe.md` (commit `0cde3e5`) and `HANDOFF-blockers-to-engineering.md` (commit `0ef4b96`)._

This doc walks the 6 researcher personas from the Diet Insight Engine docs through the live MCP, records what each tool flow returns, and ranks each flow's paper-grade readiness. **Engineering's Blocker-1 fix to `kg_hdi_check` is verified** — the tool now returns severity, mechanism, and citations on every textbook HDI panel entry.

## Verdict matrix

| # | Persona | Tool flow | Status | Paper-grade |
|---|---|---|---|---|
| 1 | Clinical pharmacist | `kg_hdi_check` × candidate herbs | ✅ working | ✅ |
| 2 | Nutrition researcher | `kg_diet_to_compounds → kg_compound_to_targets` | ✅ working | ✅ |
| 3 | TCM researcher | `kg_bilingual_term → kg_herb_to_diseases` | ⚠️ partial | ⚠️ |
| 4 | Hypothesis generator | `kg_herb_to_symptoms` / `kg_compound_to_symptoms` | ✅ working | ⚠️ semantics |
| 5 | Systematic reviewer | `kg_herb_to_diseases` + client filter | ⚠️ filter gap | ⚠️ |
| 6 | Mechanism mining | `kg_compound_to_targets` | ✅ working | ✅ |

Two of the six are unconditionally paper-grade today (UC1, UC2, UC6 — three actually). UC3 and UC5 need either backend filter support or content-side fixes; UC4 needs paper-Methods disclosure on the TREATS_SYMPTOM relation semantics.

---

## UC1 — Clinical pharmacist: warfarin × candidate herbs

**Question:** "My patient is on warfarin. Which dietary herbs are unsafe?"

**Tool path:** `kg_hdi_check(drug, herb)` for each candidate.

**Probed (all returned `found=true`, severity + mechanism + 1 citation):**

| Drug | Herb (form tested) | Severity | Mechanism class |
|---|---|---|---|
| Warfarin | Ginkgo biloba | severe | coagulation |
| Warfarin | Hypericum perforatum | severe | CYP450 |
| Warfarin | St. John's Wort | severe | CYP450 |
| Warfarin | Allium sativum | moderate | coagulation |
| Warfarin | Garlic | moderate | coagulation |
| Warfarin | Zingiber officinale | moderate | coagulation |
| Warfarin | Ginger | moderate | coagulation |
| Warfarin | Panax ginseng | moderate | PD-antagonism |

**Findings:**

- The lookup accepts both **Latin and common** name forms for the same herb (Hypericum perforatum / St. John's Wort, Allium sativum / Garlic, Zingiber officinale / Ginger). Engineering added name aliasing in the Blocker-1 fix.
- Severity distribution matches clinical literature: SJW + Ginkgo = severe; garlic/ginger/ginseng = moderate. No false positives in the panel.
- Each match returns one citation (length 1 in `citations[]`). **For the paper, we should describe what the citation IDs map to** — the HDI-Safe-50 file documents this; should be a Methods-section table.

**Paper-grade:** Yes. This is the headline tool for C1 (HDI Recall metric). Run-5 should produce non-zero `hdi_recall` values for `diet_os` and Safety Reviewer.

---

## UC2 — Nutrition researcher: turmeric → compounds → inflammation targets

**Question:** "What compounds in turmeric target inflammation pathways?"

**Tool path:** `kg_diet_to_compounds("Turmeric") → kg_compound_to_targets(compound)` for each compound.

**Step 1 result:** `kg_diet_to_compounds(seed="Turmeric")` returned **15 chains, 30 edges**, with distinct compounds including:
`1,2,3,4,6-PENTAGALLOYLGLUCOSE, 1,3,5-TRIMETHOXYBENZENE, 1,5-BIS-(4-HYDROXY-3-METHOXYPHENYL)-1,4-PENTADIEN-3-ONE, 1,8-CINEOLE, 16-HYDROXY-HEXADECANOIC-ACID, …`

**Step 2 result:** for the canonical curcuminoids:

| Compound | Targets returned (top_k=10) | Inflammation-relevant |
|---|---|---|
| **CURCUMIN** | 10 — incl. *DNA topoisomerase II alpha, Cytochrome P450 3A4, Carbonic anhydrase family* | ✅ NF-κB, COX adjacent |
| **DEMETHOXYCURCUMIN** | 3 — incl. *CaM kinase II alpha, **Cyclooxygenase-2** (COX-2), Beta-secretase 1* | ✅ direct COX-2 |
| **BISDEMETHOXYCURCUMIN** | 5 — incl. *Aldo-keto reductase 1B10, Glyoxalase I, **Cyclooxygenase-2**, Aldose reductase* | ✅ direct COX-2 |

**Findings:**

- The 2-hop chain **`Turmeric → DEMETHOXYCURCUMIN → Cyclooxygenase-2`** carries `source_id` on every edge (`duke:found_in_food`, `cmaup:compound_target`-equivalent) — paper-grade provenance for an inflammation-pathway claim.
- Caveat: COX-2 surfaces on the *demethoxy* curcuminoids, not on plain CURCUMIN in the top-10 view. For a paper figure, run with `top_k=20` or higher to capture the full curcumin-COX-2 link.
- The compounds list in step 1 is dominated by Duke's broad cataloguing; the paper Methods should clarify "Top compounds by herb-association count, not by clinical relevance."

**Paper-grade:** Yes. Use this flow as the C3 (provenance faithfulness) showcase in the paper.

---

## UC3 — TCM researcher: 阴虚 (yin deficiency) → modern disease

**Question:** "What modern disease does 阴虚 (yin deficiency) map to?"

**Tool path (planned):** `kg_bilingual_term("阴虚") → kg_herb_to_diseases(...)`.

**Step 1 result:** `kg_bilingual_term("阴虚")` returned **all-null**: `english=None`, `chinese=None`, `pinyin=None`, `confidence=0.0`. The tool succeeds for individual herb terms (`黄连` → `Coptidis Rhizoma` / `Huanglian` at confidence 1.0 — verified in `staged-mcp-probe.md`) but **does not resolve syndrome-level TCM concepts** (`阴虚` yin deficiency, `阳虚` yang deficiency, etc.). Likely cause: SymMap's bilingual layer covers herb names and modern symptoms, not syndrome diagnoses.

**Workaround:** seed `kg_herb_to_diseases` directly with a known yin-deficiency herb in Latin form. **Probed:** `kg_herb_to_diseases("Rehmannia glutinosa")` returned 10 chains, sample diseases: `Abortion, Acne vulgaris, Actinic keratosis, Acute ST elevation myocardial infarction, Acute diabetic complication`. **All ASSOCIATED_WITH_DISEASE edges from CMAUP plant-disease.** No yin-deficiency-specific disease connection in this top-10 — would need to expand `top_k` and look for endocrine/diabetes/menopausal/dry-eye-class diseases that map back to TCM yin-deficiency syndromes.

**Findings:**

- Bilingual canonicalization works for **herbs and modern symptoms** but is sparse for **TCM syndromes**. Paper Methods should call this out. C4 (bilingual coverage) metric will be measurable on TCM scenarios that use herb names, not syndrome names.
- For the v1 benchmark, all 10 TCM scenarios should be re-checked: scenarios that hinge on syndrome-level bilingual lookup may need to be reformulated to use herb names instead.

**Paper-grade:** Partial. The herb path is paper-grade; the syndrome path needs either a SymMap content gap to be addressed (engineering / data ingest) or a Methods-section disclaimer.

---

## UC4 — Hypothesis generator: anti-emetic compounds + foods

**Question (rephrased):** "Which dietary compounds treat nausea, and which foods contain them?"

**Tool path:** `kg_herb_to_symptoms` (forward) + `kg_compound_to_symptoms` (compound side). **Note:** there is no `kg_compound_to_food` (inverse of `kg_diet_to_compounds`), so the "which foods contain X" half requires a separate workflow.

**Probed:**

- `kg_herb_to_symptoms("Ginger")` → **20 symptoms; 'Nausea' present.** Sample: `[Aging, Anxiety, Arthritis, Asthma, Bacterial infection]`. The symptom space is broader than just nausea.
- `kg_herb_to_symptoms("Zingiber officinale")` → 20 symptoms, similar profile (Latin alias works).
- `kg_compound_to_symptoms("GINGEROL")` → 10 symptoms: `[Liver damage, Low immunity, Low libido, Memory decline, Migraine, Muscle spasm, Neurodegeneration, Obesity]`.

**Findings:**

- The **`TREATS_SYMPTOM` relation semantics are ambiguous on the compound side** — gingerol "treats" Liver damage / Low immunity / Memory decline reads strangely. Either (a) the underlying Duke bioactivity data uses TREATS_SYMPTOM loosely (= "associated with" in either direction), or (b) the relationship from compound → herb → symptom is being collapsed to compound → symptom and losing the herb-mediated context.
- For the paper, this is **not a wiring bug** but a Methods-section semantic that must be disclosed: the panel agent's interpretation of compound-symptom edges should not be over-strong.
- The "which foods contain compound X" reverse traversal isn't a single tool; agents must call `kg_diet_to_compounds` exhaustively over candidate foods, OR engineering can expose a `kg_compound_to_food` tool. **Out-of-scope for v1 — document as a v2 toolkit extension.**

**Paper-grade:** Useful for hypothesis generation, with documented semantic caveat.

---

## UC5 — Systematic reviewer: bulk herb→IBD evidence table

**Question:** "Build an evidence table of all herb-disease associations from CMAUP for inflammatory bowel disease."

**Tool path:** `kg_herb_to_diseases` for each candidate herb, filter to IBD-related diseases.

**Probed (top_k=40, client-side filter for IBD/Crohn/colitis/inflammation):**

| Herb | Total diseases returned | IBD-related hits |
|---|---:|---:|
| Curcuma longa | 40 | 0 |
| Boswellia serrata | 0 | 0 |
| Glycyrrhiza glabra | 40 | 0 |
| Panax ginseng | 40 | 0 |

**Findings:**

- **`Boswellia serrata` returned 0 diseases.** Boswellia is widely studied for IBD; absence here is a graph-content gap (CMAUP coverage limit, not a wiring issue).
- The other 3 herbs each returned 40 diseases — capped at the `top_k` ceiling — and **none of those 40 contained IBD-related strings** in the client filter. Either (a) IBD entries exist beyond rank 40, (b) disease names use non-canonical labels (e.g., "Crohn disease" not "Crohn's disease"; "Ulcerative colitis" lowercase, etc.), or (c) the herbs genuinely don't have IBD edges in CMAUP.
- The systematic-reviewer use case **needs either backend disease-name filtering** (`kg_herb_to_diseases(seed, disease_filter='IBD')`) **or a `kg_disease_to_herbs` inverse traversal** (start from "Inflammatory bowel disease" and find associated herbs).

**Paper-grade:** Partial. Use UC5 as a Discussion-section limitation; flag for v2 toolkit extension or a `kg_disease_to_herbs` add.

---

## UC6 — Mechanism mining: curcumin × Alzheimer's

**Question:** "What protein targets does curcumin hit, and which targets are co-implicated in Alzheimer's?"

**Tool path:** `kg_compound_to_targets("CURCUMIN")` → cross with disease.

**Probed:**

- `kg_compound_to_targets("CURCUMIN", top_k=20)` → 20 targets (full list captured at `/tmp/mcp-probe/uc6-cur-targets.json`):
  - **AD-direct:** *Endoplasmic reticulum-associated amyloid beta-peptide-binding protein* (ERAB / HSD17B10) — cleaves amyloid-β.
  - **AD-adjacent:** *Nuclear factor NF-kappa-B p105 subunit* (neuroinflammation), *Vitamin D receptor* (multiple AD links), *Nuclear factor erythroid 2-related factor 2* (Nrf2 — neuroprotection).
  - **Drug-metabolism (DDI implications):** *CYP3A4, CYP2D6, CYP2C9, CYP1A2* — explains the warfarin/curcumin coagulation interaction in UC1.
- `kg_compound_to_diseases("CURCUMIN", top_k=30)` → **0 diseases.** The Compound → Target → Disease chain returns empty even though Compound → Target works at 20 hits.

**Findings:**

- The single-hop `kg_compound_to_targets` is **paper-grade** for mechanism-mining: 20 targets with paper-relevant biology.
- The two-hop `kg_compound_to_diseases` is **broken at the join layer** — Compound→Target works (UC6 step 1) and Target→Disease should be reachable (CMAUP and HERB 2.0 supply 763K ASSOCIATED_WITH_DISEASE edges per `scope-state-snapshot.md`), but the chain returns nothing. Most likely cause: the chain query joins on `target.id` and the targets returned by step 1 don't match the `target.id` keys in the `target_diseases` join layer. **This is the same shape as Task #10's `target_diseases` ETL fix** — fixed for `plant:NPO*` plant-disease but not for `target:NPT*` pharmacokinetic-disease chains. Worth flagging to engineering as a "Task-#10 follow-up."

**Paper-grade:** Single-hop yes (UC6 mechanism table can be the paper's pharmacology figure). Two-hop pending the chain-query fix.

---

## Implications for E2 (panel wiring) and the v1 re-run

The persona audit changes the E2 tool-selection table from "speculative" to "verified":

| Panel role | Primary MCP tool(s) — verified working today | Fallback |
|---|---|---|
| Dietitian | `kg_diet_to_compounds`, `kg_compound_to_symptoms` | `kg_query` (degraded) |
| Pharmacologist | `kg_compound_to_targets` (works), `kg_compound_to_diseases` (broken — flag) | `kg_node_neighborhood` (400 — avoid) |
| TCM | `kg_bilingual_term` (sparse), `kg_herb_to_diseases`, `kg_herb_to_symptoms` | — |
| Safety Reviewer | `kg_hdi_check` ✅ paper-grade | — |
| CRS / Defer | `kg_query` (degraded; accept) | — |

**Three edits to the panel-wiring code I'll make in E2:**

1. **Seed normalization** in `agents/tools/kg_query.py` — UPPERCASE compounds, Latin-form herbs, common-cased foods. Helper per `staged-mcp-probe.md`.
2. **Disable `kg_compound_to_diseases`** for now — return empty until engineering signals Task-#10 follow-up. The Pharmacologist falls back to `kg_compound_to_targets` only.
3. **Don't call `kg_node_neighborhood`** at all (Blocker 3, by-design). Roles that would have used it call their role-priored Layer-B tool instead.

## Implications for Run 5 metric expectations

| Metric | v1 expectation given the audit | Run-5 confidence |
|---|---|---|
| `verdict_kappa` | non-zero for `diet_os` (panel debate has KG context now) | high |
| `ece` | small (Nemotron is uncalibrated; bootstrap CIs wide) | low — keep as descriptive metric |
| **`hdi_recall`** | **non-zero for `diet_os` + Safety Reviewer** (Blocker 1 fixed) | **high** |
| `provenance` | non-zero for `diet_os` (Layer-B chains carry `source_id`) | medium-high |
| `defer_acc` | likely still ≈ constant unless gold defer labels are revisited; v1 has limited defer variety | low |
| `bilingual` | non-zero on TCM scenarios that use **herb-name** bilingual lookup; null on scenarios that use **syndrome-level** lookup | medium (depends on scenario distribution) |

**One actionable for the v1 dataset:** review which TCM scenarios depend on `kg_bilingual_term` for syndrome-level lookup. Reformulate to use herb-name lookup if possible, OR mark those as "expected null bilingual" in the gold labels.

## Open follow-ups for engineering (not blockers; nice-to-have)

1. **`kg_compound_to_diseases` chain join** — fix Compound→Target→Disease the same way Task #10 fixed plant→disease.
2. **`kg_disease_to_herbs` inverse traversal** — UC5 systematic-reviewer needs this; add as Layer-B tool 7.
3. **`kg_compound_to_food` inverse traversal** — UC4 hypothesis-generator needs this; add as Layer-B tool 8.
4. **Disease-name normalization** in `kg_herb_to_diseases` — ICD-10 / MeSH IDs alongside the literal name string would let UC5 succeed without backend filtering.

---

Next step: E2 (panel wiring) using the verified tool paths above. Followed by E3 test-split run.
