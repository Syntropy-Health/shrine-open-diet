"""JMIR Yang 2025 two-agent behavioral pattern baseline.

Based on: Yang et al., JMIR (2025) — two-agent behavioral intervention system.
Agent A: barrier-identifier — maps dietary adherence barriers across 8 categories
         derived from the 28-barrier taxonomy (condensed from JMIR supplementary).
Agent B: strategy-executor — generates dietary strategies given the identified barriers.

No KG retrieval. Two sequential LLM calls. Returns ResearchSynthesis with
a single Dietitian RoleVerdict synthesizing both agents' outputs.
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

# Agent A: 28-barrier taxonomy condensed to 8 categories per Yang et al. JMIR 2025
_BARRIER_AGENT_SYSTEM = """\
You are the Barrier Identification Agent in a two-agent dietary research system
(Yang et al. JMIR 2025 behavioral pattern).

Your task: identify which of the 8 barrier categories apply to the given
research question. The 8 barrier categories are:
  motivational   — lack of motivation, readiness, or engagement
  knowledge      — insufficient dietary or clinical knowledge
  access         — limited access to foods, supplements, or healthcare
  social         — social pressure, cultural norms, family/peer influences
  time           — time constraints, busy schedule, meal prep burden
  financial      — cost barriers, economic constraints
  cultural       — cultural food practices, beliefs, traditional preferences
  medical        — comorbidities, medications, contraindications, safety concerns

For the research question provided, emit a JSON object:
  barriers: list of relevant category names from the 8 above
  barrier_rationale: brief explanation of each identified barrier
  research_context: what clinical outcome is being researched

Emit ONLY valid JSON. No markdown fences. No preamble.
"""

# Agent B: strategy executor
_STRATEGY_AGENT_SYSTEM = """\
You are the Strategy Execution Agent in a two-agent dietary research system
(Yang et al. JMIR 2025 behavioral pattern).

Given a research question and identified barriers, generate evidence-informed
dietary strategies and assess intervention feasibility.

Emit a JSON object:
  verdict: one of prefer|caution|reject|abstain
  strategies: list of actionable strategy strings
  support: list of evidence-based reasons supporting the intervention
  concerns: list of concerns (safety, evidence gaps, barrier-related risks)
  notes: overall assessment

Emit ONLY valid JSON. No markdown fences. No preamble.
"""


def run(scenario: Scenario) -> ResearchSynthesis:
    """Yang 2025 two-agent sequential behavioral pattern."""
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-placeholder"),
    )

    # --- Agent A: barrier identification ---
    barrier_reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _BARRIER_AGENT_SYSTEM},
            {"role": "user", "content": scenario.research_question},
        ],
        temperature=0,
        max_tokens=400,
        extra_body={"seed": 42},
    )
    barrier_raw = barrier_reply.choices[0].message.content or "{}"
    barrier_obj = _parse_json(barrier_raw)

    # --- Agent B: strategy execution, informed by barrier analysis ---
    strategy_context = (
        f"Research question: {scenario.research_question}\n\n"
        f"Barrier analysis:\n{json.dumps(barrier_obj, indent=2)}"
    )
    strategy_reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _STRATEGY_AGENT_SYSTEM},
            {"role": "user", "content": strategy_context},
        ],
        temperature=0,
        max_tokens=500,
        extra_body={"seed": 42},
    )
    strategy_raw = strategy_reply.choices[0].message.content or "{}"
    strategy_obj = _parse_json(strategy_raw)

    verdict = _coerce_verdict(strategy_obj.get("verdict", "abstain"))
    rq = ResearchQuestion(text=scenario.research_question)
    triage = Triage(
        complexity="low",
        rationale="yang2025 two-agent behavioral baseline (no triage step)",
        red_flags=[],
    )

    # Synthesize barrier notes into concerns
    barrier_notes = barrier_obj.get("barrier_rationale", "")
    combined_concerns = strategy_obj.get("concerns", [])
    if barrier_notes:
        combined_concerns = [f"Barrier context: {barrier_notes}"] + combined_concerns

    panel = PanelDeliberation(
        verdicts=[
            RoleVerdict(
                role="Dietitian",
                verdict=verdict,
                support=strategy_obj.get("support", strategy_obj.get("strategies", [])),
                concerns=combined_concerns,
                notes=strategy_obj.get("notes", ""),
            )
        ],
        dissent=[],
        moderator_summary=strategy_obj.get("notes", ""),
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
