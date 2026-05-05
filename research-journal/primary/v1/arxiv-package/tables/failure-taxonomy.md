# diet_os failure-mode taxonomy
_Generated from 20260504T042540Z. n_classified=40, n_failures=40, n_successes=0._

## Summary by failure mode

| Mode | Count |
|---|---:|
| retrieval_empty | 27 |
| panel_mis_vote | 7 |
| calibrator_under_confidence | 6 |

## Selected case studies

### case-hdi-001-sjw-sertraline — retrieval_empty

- Gold verdict: `reject`
- Predicted majority verdict: `caution`
- candidate_chains: 0
- Confidence: 0.016
- Triage rationale: eval-preset from gold.expected_complexity=high
- Source rationale: HDI-001: Hypericum inhibits serotonin/NE/dopamine reuptake; combined with sertraline (SSRI) produces additive serotonerg

### case-hdi-002-sjw-warfarin — retrieval_empty

- Gold verdict: `reject`
- Predicted majority verdict: `caution`
- candidate_chains: 0
- Confidence: 0.016
- Triage rationale: eval-preset from gold.expected_complexity=high
- Source rationale: HDI-015: SJW induces CYP2C9 (S-warfarin's main metabolic enzyme) and CYP3A4, lowering INR within 1-2 weeks of co-adminis

### case-hdi-003-grapefruit-simvastatin — calibrator_under_confidence

- Gold verdict: `reject`
- Predicted majority verdict: `reject`
- candidate_chains: 10
- Confidence: 0.000
- Triage rationale: eval-preset from gold.expected_complexity=high
- Source rationale: HDI-021: Furanocoumarins in grapefruit irreversibly inhibit intestinal CYP3A4, raising simvastatin AUC up to 15-fold and

### case-hdi-005-ginkgo-aspirin — calibrator_under_confidence

- Gold verdict: `caution`
- Predicted majority verdict: `caution`
- candidate_chains: 20
- Confidence: 0.020
- Triage rationale: eval-preset from gold.expected_complexity=moderate
- Source rationale: HDI-032: Additive antiplatelet effect — ginkgolide B blocks PAF-mediated aggregation while aspirin inhibits COX-1. Publi

### case-hdi-004-licorice-furosemide — panel_mis_vote

- Gold verdict: `reject`
- Predicted majority verdict: `caution`
- candidate_chains: 20
- Confidence: 0.000
- Triage rationale: eval-preset from gold.expected_complexity=high
- Source rationale: HDI-047: Glycyrrhizin inhibits 11β-HSD2, producing pseudo-hyperaldosteronism with hypokalemia, sodium retention, and hyp

### case-hdi-009-kava-alprazolam — panel_mis_vote

- Gold verdict: `reject`
- Predicted majority verdict: `caution`
- candidate_chains: 20
- Confidence: 0.016
- Triage rationale: eval-preset from gold.expected_complexity=high
- Source rationale: HDI-025: Kavalactones modulate CYP1A2/2C9/2C19/3A4 and have intrinsic GABAergic activity additive to benzodiazepines. Ca
