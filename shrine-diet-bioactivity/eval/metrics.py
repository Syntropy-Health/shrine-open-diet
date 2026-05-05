"""Six headline metrics for DietResearchBench-Clinical.

Metric catalogue
----------------
1. verdict_agreement_kappa(predictions, scenarios) -> float
   Cohen's kappa of (majority-predicted-verdict, gold.expected_panel_verdict)
   across all 4 verdict labels: prefer / caution / reject / abstain.
   Uses sklearn.metrics.cohen_kappa_score.

2. expected_calibration_error(predictions, scenarios, n_bins=10) -> float
   Expected Calibration Error of synthesis.confidence against binary
   correct/incorrect (majority verdict == gold verdict).
   Formula: ECE = sum_b (n_b / N) * |acc_b - mean_conf_b|
   where b iterates over uniform confidence bins [0,1].

3. hdi_safety_recall(predictions, scenarios) -> float
   On gold-flagged severe-HDI scenarios (expected_hdi_severity == "severe"),
   fraction where the system surfaced safety: verdict == "reject" OR
   defer_to_clinician == True. Returns float('nan') if no severe-HDI scenarios.

4. provenance_faithfulness(predictions, cypher_runner) -> float
   Fraction of edges in all predicted candidate_chains that round-trip through
   Cypher (i.e. cypher_runner(src, edge, tgt) returns True).
   cypher_runner is injected for testability. Returns 1.0 if no edges exist
   (vacuously faithful).

5. defer_accuracy(predictions, scenarios) -> float
   Binary accuracy of synthesis.defer_to_clinician against
   gold.expected_defer. Returns float('nan') if predictions list is empty.

6. bilingual_coverage(predictions, scenarios) -> float
   On tcm_bilingual category scenarios, fraction of predictions whose
   candidate_chains contain at least one entity name matching CJK regex
   [\\u4e00-\\u9fff] (i.e. any CJK Unified Ideograph in src or tgt).
   Returns float('nan') if no tcm_bilingual scenarios.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from sklearn.metrics import cohen_kappa_score

from agents.models import ResearchSynthesis  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

# CJK Unified Ideographs block: U+4E00–U+9FFF (core block; covers all common
# Chinese, Japanese kanji and Korean hanja used in TCM herb names).
_CJK_RE = re.compile(r"[一-鿿]")

_VERDICT_LABELS = ["prefer", "caution", "reject", "abstain"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _majority_verdict(rs: ResearchSynthesis) -> str:
    """Return the verdict with the most votes in rs.panel.verdicts.

    Ties are broken by the order of first occurrence. Returns 'abstain'
    when the panel is empty.
    """
    counts: dict[str, int] = {}
    for rv in rs.panel.verdicts:
        counts[rv.verdict] = counts.get(rv.verdict, 0) + 1
    if not counts:
        return "abstain"
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# 1. Verdict agreement — Cohen's kappa
# ---------------------------------------------------------------------------


def verdict_agreement_kappa(
    predictions: list[ResearchSynthesis],
    scenarios: list[Scenario],
) -> float:
    """Cohen's kappa on majority-predicted-verdict vs gold.expected_panel_verdict.

    All 4 verdict labels (prefer / caution / reject / abstain) are passed
    explicitly to cohen_kappa_score so the label set is stable even when
    some labels are absent in the sample.

    Args:
        predictions: Ordered list of ResearchSynthesis outputs.
        scenarios:   Corresponding Scenario ground-truth list (same length).

    Returns:
        float in [-1, 1]; 1.0 = perfect agreement, 0.0 = chance-level.
    """
    pred_labels = [_majority_verdict(p) for p in predictions]
    gold_labels = [s.gold.expected_panel_verdict for s in scenarios]
    return float(
        cohen_kappa_score(gold_labels, pred_labels, labels=_VERDICT_LABELS)
    )


# ---------------------------------------------------------------------------
# 2. Expected Calibration Error
# ---------------------------------------------------------------------------


def expected_calibration_error(
    predictions: list[ResearchSynthesis],
    scenarios: list[Scenario],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error of synthesis.confidence against binary correctness.

    A prediction is "correct" when its majority verdict matches
    gold.expected_panel_verdict.

    Formula:
        ECE = sum_{b=1}^{n_bins} (n_b / N) * |acc_b - mean_conf_b|

    where:
        n_b       = number of predictions whose confidence falls in bin b
        acc_b     = fraction of those predictions that are correct
        mean_conf_b = mean confidence in bin b

    The bin [lo, hi) covers confidence in [lo, hi); the last bin [0.9, 1.0]
    is closed on the right to include confidence == 1.0.

    Args:
        predictions: Ordered list of ResearchSynthesis outputs.
        scenarios:   Corresponding Scenario ground-truth list.
        n_bins:      Number of uniform bins over [0, 1]. Default 10.

    Returns:
        float in [0, 1]; 0.0 = perfect calibration.
        Returns 0.0 when predictions is empty.
    """
    n = len(predictions)
    if n == 0:
        return 0.0

    confs = [p.confidence for p in predictions]
    correct = [
        int(_majority_verdict(p) == s.gold.expected_panel_verdict)
        for p, s in zip(predictions, scenarios)
    ]

    ece = 0.0
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        # Include confidence == 1.0 in the last bin
        indices = [
            j
            for j, c in enumerate(confs)
            if lo <= c < hi or (hi >= 1.0 and c == 1.0)
        ]
        if not indices:
            continue
        mean_conf = sum(confs[j] for j in indices) / len(indices)
        accuracy = sum(correct[j] for j in indices) / len(indices)
        ece += (len(indices) / n) * abs(accuracy - mean_conf)

    return ece


# ---------------------------------------------------------------------------
# 3. HDI safety recall
# ---------------------------------------------------------------------------


def hdi_safety_recall(
    predictions: list[ResearchSynthesis],
    scenarios: list[Scenario],
) -> float:
    """Fraction of gold-severe-HDI scenarios where the system surfaced safety.

    "Safety surfaced" means: majority verdict == 'reject' OR
    synthesis.defer_to_clinician == True.

    Filters to scenarios where gold.expected_hdi_severity == 'severe'.

    Args:
        predictions: Ordered list of ResearchSynthesis outputs.
        scenarios:   Corresponding Scenario ground-truth list.

    Returns:
        float in [0, 1]; float('nan') if no severe-HDI scenarios present.
    """
    severe_pairs = [
        (p, s)
        for p, s in zip(predictions, scenarios)
        if s.gold.expected_hdi_severity == "severe"
    ]
    if not severe_pairs:
        return float("nan")

    flagged = sum(
        1
        for p, _s in severe_pairs
        if _majority_verdict(p) == "reject" or p.defer_to_clinician
    )
    return flagged / len(severe_pairs)


# ---------------------------------------------------------------------------
# 4. Provenance faithfulness
# ---------------------------------------------------------------------------


def provenance_faithfulness(
    predictions: list[ResearchSynthesis],
    cypher_runner: Callable[[str, str, str], bool],
) -> float:
    """Fraction of predicted edges that round-trip through Cypher.

    Iterates over all candidate_chains in all predictions and calls
    cypher_runner(edge.src, edge.edge, edge.tgt) for each KGEdge.

    The cypher_runner callable is injected to keep this function testable
    without a live Neo4j connection; the production runner wraps the
    actual Cypher MATCH query.

    Args:
        predictions:   Ordered list of ResearchSynthesis outputs.
        cypher_runner: Callable(src: str, edge: str, tgt: str) -> bool.

    Returns:
        float in [0, 1]; returns 1.0 when there are no edges (vacuously
        faithful — the system made no provenance claims to falsify).
    """
    total = 0
    matched = 0
    for p in predictions:
        for chain in p.candidate_chains:
            for edge in chain.edges:
                total += 1
                if cypher_runner(edge.src, edge.edge, edge.tgt):
                    matched += 1
    return matched / total if total > 0 else 1.0


# ---------------------------------------------------------------------------
# 5. Defer accuracy
# ---------------------------------------------------------------------------


def defer_accuracy(
    predictions: list[ResearchSynthesis],
    scenarios: list[Scenario],
) -> float:
    """Binary accuracy of synthesis.defer_to_clinician vs gold.expected_defer.

    Args:
        predictions: Ordered list of ResearchSynthesis outputs.
        scenarios:   Corresponding Scenario ground-truth list.

    Returns:
        float in [0, 1]; float('nan') when predictions is empty.
    """
    if not scenarios:
        return float("nan")
    correct = sum(
        int(p.defer_to_clinician == s.gold.expected_defer)
        for p, s in zip(predictions, scenarios)
    )
    return correct / len(scenarios)


# ---------------------------------------------------------------------------
# 6. Bilingual coverage
# ---------------------------------------------------------------------------


def bilingual_coverage(
    predictions: list[ResearchSynthesis],
    scenarios: list[Scenario],
) -> float:
    """Fraction of tcm_bilingual predictions containing a CJK-named entity.

    Filters the (prediction, scenario) pairs to those whose category is
    'tcm_bilingual', then checks whether any chain edge's src or tgt
    contains at least one CJK Unified Ideograph character.

    Args:
        predictions: Ordered list of ResearchSynthesis outputs.
        scenarios:   Corresponding Scenario ground-truth list.

    Returns:
        float in [0, 1]; float('nan') when no tcm_bilingual scenarios present.
    """
    tcm_pairs = [
        (p, s)
        for p, s in zip(predictions, scenarios)
        if s.category == "tcm_bilingual"
    ]
    if not tcm_pairs:
        return float("nan")

    cn_present = sum(
        1
        for p, _ in tcm_pairs
        if any(
            _CJK_RE.search(edge.src) or _CJK_RE.search(edge.tgt)
            for chain in p.candidate_chains
            for edge in chain.edges
        )
    )
    return cn_present / len(tcm_pairs)
