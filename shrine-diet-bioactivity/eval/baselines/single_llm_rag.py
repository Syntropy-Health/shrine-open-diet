"""Single-LLM + LightRAG naive-mode retrieval baseline.

Identical to single_llm but injects a flat RAG context from LightRAG naive mode
into the system prompt. Gracefully degrades to no-retrieval if LightRAG is
unreachable (KGQueryError is caught, baseline proceeds without context).
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
from agents.tools.kg_query import KGQueryError, kg_query  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

_BARRIER_AGENT_SYSTEM = """\
You are a clinical research assistant with access to a knowledge graph context.
Given a research question about a herbal/dietary intervention and (optionally)
retrieved KG evidence chains, emit a JSON object with fields:
  verdict: one of prefer|caution|reject|abstain
  support: list of bullet-point strings supporting the intervention
  concerns: list of bullet-point strings raising concerns
  notes: short qualitative summary

Use the provided KG evidence to ground your claims where available.
Emit ONLY valid JSON. No markdown fences. No preamble.
"""


def _build_kg_context(scenario: Scenario) -> str:
    """Retrieve naive-mode KG context; return empty string on failure."""
    try:
        result = kg_query(scenario.research_question, mode="naive")
        if not result.chains:
            return ""
        lines = []
        for i, chain in enumerate(result.chains[:5]):  # cap at 5 chains for context length
            for edge in chain.edges:
                lines.append(
                    f"  [{i}] {edge.src} --{edge.edge}--> {edge.tgt} "
                    f"(evidence: {edge.evidence_tier}, weight: {edge.weight:.2f})"
                )
        return "Retrieved KG evidence (naive mode):\n" + "\n".join(lines)
    except KGQueryError:
        return ""


def run(scenario: Scenario) -> ResearchSynthesis:
    """Single-LLM with LightRAG naive-mode retrieval injected into system prompt."""
    kg_context = _build_kg_context(scenario)

    system_prompt = _BARRIER_AGENT_SYSTEM
    if kg_context:
        system_prompt = system_prompt + "\n\n" + kg_context

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-placeholder"),
    )
    reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
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
        rationale="single-LLM+RAG baseline (no triage step)",
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
    # Slightly higher evidence_tier if KG context was available
    evidence_tier = 0.4 if kg_context else 0.3
    components = ConfidenceComponents(
        evidence_tier=evidence_tier,
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
