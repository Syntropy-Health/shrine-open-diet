"""MedAgents (Tang et al. ACL 2024) debate-consensus baseline.

Based on: Tang et al., ACL 2024 — MedAgents: Large Language Models as Collaborators
for Zero-shot Medical Reasoning.

Pattern: 3 sequential role agents (Dietitian / Pharmacologist / ClinicalResearchScientist)
each call the LLM independently with role-specific prompts cribbed from agents/panel/.
A 4th moderator call synthesizes a PanelDeliberation from the three role verdicts.

No KG retrieval. No triage. 4 total LLM calls.
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
# Import role prompts from agents/panel/ — these are the deliberation-primitive prior art.
from agents.panel.dietitian import DIETITIAN_PROMPT  # type: ignore[import-not-found]
from agents.panel.pharmacologist import PHARMACOLOGIST_PROMPT  # type: ignore[import-not-found]
from agents.panel.clinical_research_scientist import CRS_PROMPT  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

# Strip KG-specific instructions from each panel prompt for this no-KG baseline.
# We preserve the clinical reasoning framing; only remove references to kg_query tool.
_KG_STRIP_PHRASES = [
    "Use the kg_query tool for any claim that is not already in the panel context.",
    "Use the kg_query tool to verify any mechanism you assert.",
    "- Cite chains by index (cited_chains).",
    "Output a RoleVerdict JSON with role=",
]


def _strip_kg_instructions(prompt: str) -> str:
    """Remove KG-specific tool instructions from panel prompts for the no-KG baseline."""
    lines = prompt.splitlines()
    cleaned = []
    for line in lines:
        if any(phrase in line for phrase in _KG_STRIP_PHRASES):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


# Role-specific output instructions for bare JSON emission
_ROLE_OUTPUT_SUFFIX = """\

Given the research question, emit a JSON object with fields:
  role: your role name (exact string)
  verdict: one of prefer|caution|reject|abstain
  support: list of bullet-point strings
  concerns: list of bullet-point strings
  notes: short qualitative summary
Emit ONLY valid JSON. No markdown fences. No preamble.
"""

_MODERATOR_SYSTEM = """\
You are the moderator of a clinical research team. Given three role verdicts
(Dietitian, Pharmacologist, ClinicalResearchScientist), synthesize a consensus.

Emit a JSON object:
  moderator_summary: 2-3 sentence consensus or majority position
  dissent: list of minority opinions raised (can be empty)
  overall_verdict: one of prefer|caution|reject|abstain

Emit ONLY valid JSON. No markdown fences. No preamble.
"""

# Role definitions: (role_name, base_prompt, role_literal_for_verdict)
_ROLES = [
    ("Dietitian", DIETITIAN_PROMPT, "Dietitian"),
    ("Pharmacologist", PHARMACOLOGIST_PROMPT, "Pharmacologist"),
    ("ClinicalResearchScientist", CRS_PROMPT, "ClinicalResearchScientist"),
]


def _call_role(client: OpenAI, base_prompt: str, role_literal: str, question: str) -> RoleVerdict:
    """Call one role agent; return a RoleVerdict (fallback to abstain on parse failure)."""
    system = _strip_kg_instructions(base_prompt) + _ROLE_OUTPUT_SUFFIX
    reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=500,
        extra_body={"seed": 42},
    )
    raw = reply.choices[0].message.content or "{}"
    obj = _parse_json(raw)
    return RoleVerdict(
        role=role_literal,  # type: ignore[arg-type]
        verdict=_coerce_verdict(obj.get("verdict", "abstain")),
        support=obj.get("support", []),
        concerns=obj.get("concerns", []),
        notes=obj.get("notes", ""),
    )


def run(scenario: Scenario) -> ResearchSynthesis:
    """MedAgents debate-consensus: 3 roles + moderator synthesis."""
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-placeholder"),
    )

    # --- Three sequential role calls ---
    verdicts: list[RoleVerdict] = []
    for _role_name, base_prompt, role_literal in _ROLES:
        v = _call_role(client, base_prompt, role_literal, scenario.research_question)
        verdicts.append(v)

    # --- Moderator synthesis ---
    verdicts_json = json.dumps([v.model_dump() for v in verdicts], indent=2)
    moderator_context = (
        f"Research question: {scenario.research_question}\n\n"
        f"Role verdicts:\n{verdicts_json}"
    )
    mod_reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _MODERATOR_SYSTEM},
            {"role": "user", "content": moderator_context},
        ],
        temperature=0,
        max_tokens=400,
        extra_body={"seed": 42},
    )
    mod_raw = mod_reply.choices[0].message.content or "{}"
    mod_obj = _parse_json(mod_raw)

    panel = PanelDeliberation(
        verdicts=verdicts,
        dissent=mod_obj.get("dissent", []),
        moderator_summary=mod_obj.get("moderator_summary", ""),
    )

    rq = ResearchQuestion(text=scenario.research_question)
    triage = Triage(
        complexity="low",
        rationale="medagents debate-consensus baseline (no triage step)",
        red_flags=[],
    )

    # Derive confidence from the majority verdict
    majority = _majority_verdict(verdicts)
    prefer_fraction = sum(1 for v in verdicts if v.verdict == "prefer") / max(len(verdicts), 1)
    components = ConfidenceComponents(
        evidence_tier=0.35,
        hdi_risk=0.3 if majority in {"reject", "caution"} else 0.0,
        question_fit=prefer_fraction,
    )
    confidence = _simple_confidence(components)

    return ResearchSynthesis(
        question=rq,
        triage=triage,
        candidate_chains=[],
        panel=panel,
        confidence=confidence,
        components=components,
        defer_to_clinician=majority == "reject",
    )


def _majority_verdict(verdicts: list[RoleVerdict]) -> str:
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1
    if not counts:
        return "abstain"
    return max(counts.items(), key=lambda kv: kv[1])[0]


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
