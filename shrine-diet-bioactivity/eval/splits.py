"""Stratified split machinery for DietResearchBench-Clinical."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Iterable

from eval.scenario import BenchmarkSet, Scenario  # type: ignore[import-not-found]

_HERB_HINTS: set[str] = {
    "ginger", "turmeric", "garlic", "ginseng", "ginkgo", "valerian", "echinacea",
    "saw palmetto", "peppermint", "ashwagandha", "milk thistle", "licorice",
    "kava", "ephedra", "yohimbe", "schisandra", "astragalus", "danshen",
    "danggui", "huangqi", "shengma", "wuweizi", "mahuang", "huanglian",
    "banlangen", "gouqi", "berberine", "cohosh", "schisandrin",
    "grapefruit", "psyllium", "probiotics", "magnesium", "zinc",
    "folate", "iron", "fiber", "omega-3", "vitamin",
    "mediterranean", "dash",
    # Chinese (CJK) tokens — primary herb names appearing in tcm_bilingual scenarios
    "当归", "黄芪", "升麻", "五味子", "麻黄", "黄连", "丹参", "板蓝根", "枸杞",
    "当归补血汤",
}
_DRUG_HINTS: set[str] = {
    "sertraline", "warfarin", "statins", "simvastatin", "furosemide",
    "aspirin", "clopidogrel", "saquinavir", "alprazolam", "clonidine",
    "metformin", "tacrolimus", "cyclosporine", "indinavir", "irinotecan",
    "tamoxifen", "paclitaxel", "vinblastine", "felodipine", "midazolam",
    "metoprolol", "amlodipine", "spironolactone", "lisinopril", "digoxin",
    "fexofenadine", "phenelzine", "fluoxetine", "citalopram", "duloxetine",
    "venlafaxine", "tranylcypromine", "tramadol", "sumatriptan", "paroxetine",
    "ferrous", "icosapent",
}


def _tokens(s: str) -> list[str]:
    """Tokenize alphanumeric and CJK runs; lowercase Latin tokens, leave CJK as-is."""
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z][A-Za-z\-]+|[一-鿿]+", s):
        if raw.isascii():
            tok = raw.lower()
            if len(tok) > 2:
                out.append(tok)
        else:
            # CJK runs are kept verbatim (already meaningful at character level)
            out.append(raw)
    return out


def primary_entity(s: Scenario) -> str:
    """Extract the primary herb / intervention token; fall back to first hint match
    or the first content word in the research question."""
    toks = _tokens(s.research_question)
    for t in toks:
        if t in _HERB_HINTS:
            return t
    for t in toks:
        if t in _DRUG_HINTS:
            return t
    return toks[0] if toks else ""


def stratified_split(
    bench: BenchmarkSet,
    ratios: tuple[float, float, float] = (0.6, 0.2, 0.2),
    seed: int = 42,
) -> tuple[list[Scenario], list[Scenario], list[Scenario]]:
    """Stratify by (category, expected_complexity) -> (train, val, test).

    Deterministic given seed; rounds to nearest integer per stratum.
    Each stratum contributes at least one scenario to train.
    """
    if not (abs(sum(ratios) - 1.0) < 1e-6):
        raise ValueError(f"ratios must sum to 1.0, got {sum(ratios)}")
    rng = random.Random(seed)
    strata: dict[tuple[str, str], list[Scenario]] = {}
    for s in bench.scenarios:
        strata.setdefault((s.category, s.gold.expected_complexity), []).append(s)
    train: list[Scenario] = []
    val: list[Scenario] = []
    test: list[Scenario] = []
    for _key, items in sorted(strata.items()):
        items_shuffled = items[:]
        rng.shuffle(items_shuffled)
        n = len(items_shuffled)
        n_train = max(1, round(n * ratios[0]))
        n_val = max(0, round(n * ratios[1]))
        # Ensure we don't overshoot
        n_train = min(n_train, n)
        n_val = min(n_val, n - n_train)
        train.extend(items_shuffled[:n_train])
        val.extend(items_shuffled[n_train : n_train + n_val])
        test.extend(items_shuffled[n_train + n_val :])
    return train, val, test


def check_no_entity_leakage(train: Iterable[Scenario], test: Iterable[Scenario]) -> None:
    """Raise ValueError if any test scenario shares its primary entity with any train
    scenario. The leakage guard bounds our generalization claim to unseen herbs/drugs."""
    train_entities = {primary_entity(s) for s in train if primary_entity(s)}
    overlapping = [s.id for s in test if primary_entity(s) in train_entities]
    if overlapping:
        raise ValueError(
            f"entity leakage detected: {len(overlapping)} test scenarios share primary "
            f"entity with train: {overlapping[:5]}{'…' if len(overlapping) > 5 else ''}"
        )


def persist_splits(
    bench: BenchmarkSet,
    out: Path,
    seed: int = 42,
    enforce_leakage_guard: bool = True,
) -> dict:
    """Write splits manifest to disk for reproducibility.

    When ``enforce_leakage_guard`` is False, the manifest records that entity
    overlap may exist between train and test (necessary for v1 at N=40).
    Returns the manifest dict that was written.
    """
    train, val, test = stratified_split(bench, seed=seed)
    leakage_status: dict[str, object] = {"enforced": enforce_leakage_guard}
    if enforce_leakage_guard:
        check_no_entity_leakage(train, test)
        leakage_status["overlapping_test_ids"] = []
    else:
        train_entities = {primary_entity(s) for s in train if primary_entity(s)}
        overlapping = [s.id for s in test if primary_entity(s) in train_entities]
        leakage_status["overlapping_test_ids"] = overlapping
        leakage_status["note"] = (
            "v1 benchmark (N=40) cannot guarantee entity disjointness — multiple "
            "scenarios share primary entities (e.g. St. John's Wort across HDI cases). "
            "Generalization claims must be limited to symptom × intervention combinations, "
            "not unseen entities. v2 (N>=200) is expected to satisfy the guard."
        )
    manifest = {
        "seed": seed,
        "benchmark_version": bench.version,
        "ratios": [0.6, 0.2, 0.2],
        "leakage_guard": leakage_status,
        "train_ids": [s.id for s in train],
        "val_ids": [s.id for s in val],
        "test_ids": [s.id for s in test],
    }
    out.write_text(json.dumps(manifest, indent=2))
    return manifest
