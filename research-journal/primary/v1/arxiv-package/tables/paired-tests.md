# DietResearchBench-Clinical — Paired Bootstrap Tests

Comparison: Diet-OS vs each baseline system.  

Null hypothesis: Diet-OS performs no better than the baseline (mean_diff ≤ 0).  

Bonferroni correction applied: n_baselines = 5, adjusted α = 0.0100 per comparison.  

Bootstrap iterations: 1000  


| System | Metric | mean_diff | CI_lo | CI_hi | p_raw | p_adj (Bonferroni) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| single_llm | verdict_kappa | 0.476 | 0.300 | 0.650 | 0.0000 | 0.0000 |
| single_llm | ece | 0.139 | 0.002 | 0.270 | 0.0230 | 0.1150 |
| single_llm | hdi_recall | 0.717 | 0.286 | 1.000 | 0.0010 | 0.0050 |
| single_llm | provenance | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| single_llm | defer_acc | 0.147 | 0.050 | 0.275 | 0.0020 | 0.0100 |
| single_llm | bilingual | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| single_llm_rag | verdict_kappa | 0.575 | 0.425 | 0.725 | 0.0000 | 0.0000 |
| single_llm_rag | ece | 0.157 | 0.021 | 0.291 | 0.0120 | 0.0600 |
| single_llm_rag | hdi_recall | 0.717 | 0.286 | 1.000 | 0.0010 | 0.0050 |
| single_llm_rag | provenance | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| single_llm_rag | defer_acc | 0.147 | 0.050 | 0.275 | 0.0020 | 0.0100 |
| single_llm_rag | bilingual | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| yang2025 | verdict_kappa | 0.550 | 0.375 | 0.725 | 0.0000 | 0.0000 |
| yang2025 | ece | 0.213 | 0.064 | 0.357 | 0.0020 | 0.0100 |
| yang2025 | hdi_recall | 0.717 | 0.286 | 1.000 | 0.0010 | 0.0050 |
| yang2025 | provenance | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| yang2025 | defer_acc | 0.147 | 0.050 | 0.275 | 0.0020 | 0.0100 |
| yang2025 | bilingual | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| medagents | verdict_kappa | 0.575 | 0.425 | 0.725 | 0.0000 | 0.0000 |
| medagents | ece | 0.530 | 0.393 | 0.663 | 0.0000 | 0.0000 |
| medagents | hdi_recall | 0.717 | 0.286 | 1.000 | 0.0010 | 0.0050 |
| medagents | provenance | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| medagents | defer_acc | 0.147 | 0.050 | 0.275 | 0.0020 | 0.0100 |
| medagents | bilingual | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| mdagents | verdict_kappa | 0.575 | 0.425 | 0.725 | 0.0000 | 0.0000 |
| mdagents | ece | 0.539 | 0.406 | 0.672 | 0.0000 | 0.0000 |
| mdagents | hdi_recall | 0.717 | 0.286 | 1.000 | 0.0010 | 0.0050 |
| mdagents | provenance | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |
| mdagents | defer_acc | 0.147 | 0.050 | 0.275 | 0.0020 | 0.0100 |
| mdagents | bilingual | 0.000 | 0.000 | 0.000 | 1.0000 | 1.0000 |

**Interpretation:** p_adj < 0.05 (Bonferroni-adjusted) indicates Diet-OS statistically outperforms the baseline on that metric.  

Note: for ECE, lower is better; mean_diff < 0 is favourable for Diet-OS.  
