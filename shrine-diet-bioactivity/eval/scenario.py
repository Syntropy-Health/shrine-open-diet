"""Typed contracts for DietResearchBench-Clinical scenarios."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScenarioCategory = Literal[
    "herbal_single_symptom",
    "nutrition",
    "multi_drug_hdi",
    "tcm_bilingual",
]
ComplexityTier = Literal["low", "moderate", "high"]
Verdict = Literal["prefer", "caution", "reject", "abstain"]
EvidenceTier = Literal[
    "clinical_trial",
    "pharmacokinetic_study",
    "observational",
    "case_report_series",
    "case_report",
    "experimental",
    "in_vivo",
    "in_vitro",
    "traditional",
    "unknown",
]


class GoldStandard(BaseModel):
    expected_complexity: ComplexityTier
    expected_panel_verdict: Verdict
    expected_evidence_tier: EvidenceTier
    expected_min_chains: int = Field(ge=0)
    expected_defer: bool
    expected_red_flags: list[str] = Field(default_factory=list)
    expected_hdi_severity: Literal["severe", "moderate", "mild", "none"] = "none"
    languages: list[str] = Field(default_factory=lambda: ["en"])


class Scenario(BaseModel):
    id: str
    version: str = "v1"
    category: ScenarioCategory
    research_question: str
    gold: GoldStandard
    rationale: str
    source_citations: list[str] = Field(default_factory=list)


class BenchmarkSet(BaseModel):
    name: str = "DietResearchBench-Clinical"
    version: str = "v1"
    scenarios: list[Scenario]
