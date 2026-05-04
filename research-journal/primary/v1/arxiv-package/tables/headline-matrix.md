# DietResearchBench-Clinical — Evaluation Summary

Systems: single_llm, single_llm_rag, yang2025, medagents, mdagents, diet_os  

All values: mean [95% CI bootstrap]. '—' = metric undefined for this system/split.


| System | Verdict κ | ECE | HDI Recall | Provenance | Defer Acc | Bilingual |
| --- | --- | --- | --- | --- | --- | --- |
| single_llm | 0.055 [0.011, 0.114] | 0.326 [0.228, 0.400] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.548 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| single_llm_rag | -0.013 [-0.045, 0.000] | 0.397 [0.397, 0.397] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.548 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| yang2025 | 0.017 [0.000, 0.056] | 0.341 [0.294, 0.380] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.548 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| medagents | 0.000 [0.000, 0.000] | 0.024 [0.019, 0.030] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.548 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| mdagents | 0.000 [0.000, 0.000] | 0.015 [0.009, 0.021] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.548 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| diet_os | 0.251 [0.061, 0.451] | 0.542 [0.400, 0.680] | 0.709 [0.333, 1.000] | 1.000 [1.000, 1.000] | 0.696 [0.550, 0.825] | 0.000 [0.000, 0.000] |

## Metric abbreviations

| Key | Full name |
| --- | --- |
| verdict_kappa | Verdict κ |
| ece | ECE |
| hdi_recall | HDI Recall |
| provenance | Provenance |
| defer_acc | Defer Acc |
| bilingual | Bilingual |
