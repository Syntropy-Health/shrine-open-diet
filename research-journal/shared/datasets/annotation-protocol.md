# DietResearchBench-Clinical — Clinician Annotation Protocol

## Goal

Expand the v1 seed benchmark from 40 to ≥ 200 scenarios with dietitian +
pharmacist + (where applicable) TCM-trained-clinician sign-off per scenario.

## Per-scenario fields

- `id`: case-NNN-shortdesc (unique across versions)
- `category`: one of `{herbal_single_symptom, nutrition, multi_drug_hdi, tcm_bilingual}`
- `research_question`: framed as a clinician would ask (PICO-style if applicable). For
  `tcm_bilingual` scenarios, the question MUST contain the Chinese herb name (汉字) so
  bilingual retrieval is exercised.
- `gold.expected_complexity`: solo / multi-disciplinary / integrated-care
  (`low` / `moderate` / `high`)
- `gold.expected_panel_verdict`: `prefer` / `caution` / `reject` / `abstain`
- `gold.expected_evidence_tier`: highest tier substantiating the verdict
  (`clinical_trial` > `pharmacokinetic_study` > `observational` > `case_report_series` >
  `case_report` > `experimental` > `in_vivo` > `in_vitro` > `traditional` > `unknown`)
- `gold.expected_min_chains`: minimum count of provenance chains the system should produce
- `gold.expected_defer`: `true` if the question warrants clinician-only judgment
- `gold.expected_red_flags`: structured tags such as `pregnancy`, `anticoagulant_therapy`,
  `hepatic_impairment`, `serotonin_syndrome`, etc.
- `gold.expected_hdi_severity`: only meaningful for `multi_drug_hdi` category
  (`severe` / `moderate` / `mild` / `none`)
- `gold.languages`: `["en"]` or `["en", "zh"]` for TCM
- `rationale`: 1-3 sentence justification (cited)
- `source_citations`: PMIDs (preferred), HDI-Safe-50 ids (`HDI-NNN`), guideline names,
  or canonical TCM references (e.g. `黄帝内经 — 消渴 chapter`).

## Inter-annotator agreement

Two annotators per scenario, blinded to each other's verdicts. Cohen's κ ≥ 0.70 to keep
the scenario; below 0.60 → discard or rescope. Track agreement per category — TCM
scenarios are expected to require a third TCM-trained adjudicator.

## Citation hierarchy

1. **PubMed-indexed primary source** (RCT, meta-analysis, PK study) — preferred.
   Format: `Author YYYY PMID:NNNNNNNN`.
2. **MSK About Herbs** / **NIH LiverTox** — secondary safety reference.
3. **HDI-Safe 50** entries (`HDI-001` … `HDI-050`) — internal curated dataset, used as
   the canonical interaction reference.
4. **Classical TCM text** — e.g. `神农本草经 — 当归 entry`,
   `黄帝内经 — 消渴 chapter` — only when no modern primary source exists.

## Publication

- **v1** = 40 scenarios (this curation, hand-built from MSK / LiverTox / HDI-Safe 50 /
  classical TCM canon).
- **v2** = ≥ 200 scenarios after clinician annotation rounds.

All versions pinned by the `version` field on `BenchmarkSet`. Splits manifests
(e.g. `splits_seed42.json`) reference `benchmark_version` for reproducibility.

## Known v1 limitations

- Stratification across (category × complexity) is uneven at N=40 — entity-leakage
  guarantees CANNOT be enforced (some entities such as St. John's Wort appear across
  multiple multi-drug HDI scenarios). The v1 splits manifest documents this.
- Single-annotator (no inter-annotator κ yet). v2 closes this gap.
- TCM scenarios rely partially on Chinese-language clinical literature that lacks PubMed
  indexing; classical canon citations stand in but should be supplemented with CNKI /
  Wanfang citations in v2.
