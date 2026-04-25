"""Zero-shot single-LLM baseline — no tools, no retrieval.

Lower bound: represents a system with no KG access and no multi-agent deliberation.
Direct OpenRouter call to nvidia/nemotron-3-nano-30b-a3b:free.
Returns a ResearchSynthesis with a single Dietitian RoleVerdict.
"""
from __future__ import annotations

import json
import os

from openai import OpenAI

from agents.models import (  # type: ignore[import-not-found]
    ConfidenceComponents,
    PanelDeliberation,
    ResearchQuestion,
    ResearchSynthesis,
    RoleVerdict,
    Triage,
)
from eval.scenario import Scenario  # type: ignore[import-not-found]

_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

_SYSTEM = """\
You are a clinical research assistant. Given a research question about a
herbal/dietary intervention, emit a JSON object with fields:
  verdict: one of prefer|caution|reject|abstain
  support: list of bullet-point strings supporting the intervention
  concerns: list of bullet-point strings raising concerns
  notes: short qualitative summary

Emit ONLY valid JSON. No markdown fences. No preamble.
"""


def run(scenario: Scenario) -> ResearchSynthesis:
    """Zero-shot single-LLM baseline. No tools, no retrieval."""
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-placeholder"),
    )
    reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": scenario.research_question},
        ],
        temperature=0,
        max_tokens=500,
        extra_body={"seed": 42},
    )
    raw = reply.choices[0].message.content or "{}"
    obj = _parse_json(raw)

    verdict = _coerce_verdict(obj.get("verdict", "abstain"))
    rq = ResearchQuestion(text=scenario.research_question)
    triage = Triage(
        complexity="low",
        rationale="single-LLM baseline (no triage step)",
        red_flags=[],
    )
    panel = PanelDeliberation(
        verdicts=[
            RoleVerdict(
                role="Dietitian",
                verdict=verdict,
                support=obj.get("support", []),
                concerns=obj.get("concerns", []),
                notes=obj.get("notes", ""),
            )
        ],
        dissent=[],
        moderator_summary=obj.get("notes", ""),
    )
    components = ConfidenceComponents(
        evidence_tier=0.3,
        hdi_risk=0.0,
        question_fit=0.5 if verdict == "prefer" else 0.2,
    )
    confidence = _simple_confidence(components)
    return ResearchSynthesis(
        question=rq,
        triage=triage,
        candidate_chains=[],
        panel=panel,
        confidence=confidence,
        components=components,
        defer_to_clinician=False,
    )


def _parse_json(raw: str) -> dict:
    """Extract the first JSON object from raw text."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return {}


def _coerce_verdict(v: str) -> str:
    allowed = {"prefer", "caution", "reject", "abstain"}
    return v if v in allowed else "abstain"


def _simple_confidence(c: ConfidenceComponents) -> float:
    eps = 1e-6
    score = (
        max(c.evidence_tier, eps) ** 0.5
        * max(1.0 - c.hdi_risk, eps) ** 0.3
        * max(c.question_fit, eps) ** 0.2
    )
    return min(max(score, 0.0), 1.0)
