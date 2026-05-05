"""MDAgents (Kim et al. NeurIPS 2024) adaptive panel baseline.

Based on: Kim et al., NeurIPS 2024 — MDAgents: An Adaptive Collaboration of LLMs
for Medical Decision-Making.

Pattern:
  Step 1 — Complexity classification: single LLM call to classify question as
            low / moderate / high.
  Step 2 — Route to adaptive panel:
            low      → 1 role agent  (Dietitian)
            moderate → 3 role agents (Dietitian, Pharmacologist, TCMPractitioner)
            high     → 6 role agents (all 6 from agents/panel/)
  Step 3 — Moderator synthesis.

SAME role prompts as Subsystem H's panel modules (imported from agents.panel).
Difference vs Diet-OS: no KG retrieval, no Diet-OS-specific wrapping.
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
# Use the same role prompts as Subsystem H
from agents.panel.dietitian import DIETITIAN_PROMPT  # type: ignore[import-not-found]
from agents.panel.pharmacologist import PHARMACOLOGIST_PROMPT  # type: ignore[import-not-found]
from agents.panel.tcm_practitioner import TCM_PROMPT  # type: ignore[import-not-found]
from agents.panel.clinical_research_scientist import CRS_PROMPT  # type: ignore[import-not-found]
from agents.panel.safety_reviewer import SAFETY_PROMPT  # type: ignore[import-not-found]
from agents.panel.defer_to_clinician import DEFER_PROMPT  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]

_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

_COMPLEXITY_SYSTEM = """\
You are a clinical complexity classifier. Given a research question about a
herbal or dietary intervention, classify the complexity as one of:
  low      — single-intervention, single-outcome, no polypharmacy
  moderate — multi-drug interaction question, comparison across interventions
  high     — pregnancy/hepatic/renal/pediatric/weak-evidence/safety-critical

Emit a JSON object: {"complexity": "<low|moderate|high>"}
Emit ONLY valid JSON. No markdown fences. No preamble.
"""

_MODERATOR_SYSTEM = """\
You are the moderator of an adaptive clinical research panel. Given role verdicts,
synthesize a consensus PanelDeliberation.

Emit a JSON object:
  moderator_summary: 2-3 sentence consensus
  dissent: list of minority opinions (can be empty)
  overall_verdict: one of prefer|caution|reject|abstain

Emit ONLY valid JSON. No markdown fences. No preamble.
"""

# Strip KG tool-call lines from prompts (this is the no-KG variant)
_KG_STRIP_PHRASES = [
    "Use the kg_query tool",
    "- Cite chains by index (cited_chains).",
    "Output a RoleVerdict JSON with role=",
    "use kg_query",
]

_ROLE_OUTPUT_SUFFIX = """\

Given the research question, emit a JSON object:
  role: your exact role name
  verdict: one of prefer|caution|reject|abstain
  support: list of bullet-point strings
  concerns: list of bullet-point strings
  notes: short qualitative summary
Emit ONLY valid JSON. No markdown fences. No preamble.
"""

# Role definitions ordered as in assembly.py
# (role_display_name, base_prompt, role_literal_for_verdict)
_ALL_ROLES = [
    ("Dietitian", DIETITIAN_PROMPT, "Dietitian"),
    ("Pharmacologist", PHARMACOLOGIST_PROMPT, "Pharmacologist"),
    ("TCMPractitioner", TCM_PROMPT, "TCMPractitioner"),
    ("ClinicalResearchScientist", CRS_PROMPT, "ClinicalResearchScientist"),
    ("SafetyReviewer", SAFETY_PROMPT, "SafetyReviewer"),
    ("DeferToClinician", DEFER_PROMPT, "DeferToClinician"),
]

_COMPLEXITY_TO_N_ROLES = {
    "low": 1,
    "moderate": 3,
    "high": 6,
}


def _strip_kg_instructions(prompt: str) -> str:
    lines = prompt.splitlines()
    return "\n".join(
        line for line in lines
        if not any(phrase.lower() in line.lower() for phrase in _KG_STRIP_PHRASES)
    )


def _classify_complexity(client: OpenAI, question: str) -> str:
    """Single call to classify question complexity. Falls back to 'moderate' on failure."""
    reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _COMPLEXITY_SYSTEM},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=50,
        extra_body={"seed": 42},
    )
    raw = reply.choices[0].message.content or "{}"
    obj = _parse_json(raw)
    complexity = obj.get("complexity", "moderate")
    if complexity not in _COMPLEXITY_TO_N_ROLES:
        complexity = "moderate"
    return complexity


def _call_role(client: OpenAI, base_prompt: str, role_literal: str, question: str) -> RoleVerdict:
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
    """MDAgents adaptive panel: classify → route to N agents → moderate."""
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", "test-placeholder"),
    )

    # --- Step 1: Classify complexity ---
    complexity = _classify_complexity(client, scenario.research_question)
    n_roles = _COMPLEXITY_TO_N_ROLES[complexity]
    active_roles = _ALL_ROLES[:n_roles]

    # --- Step 2: Call each role agent sequentially ---
    verdicts: list[RoleVerdict] = []
    for _display, base_prompt, role_literal in active_roles:
        v = _call_role(client, base_prompt, role_literal, scenario.research_question)
        verdicts.append(v)

    # --- Step 3: Moderator synthesis ---
    verdicts_json = json.dumps([v.model_dump() for v in verdicts], indent=2)
    mod_context = (
        f"Research question: {scenario.research_question}\n\n"
        f"Complexity: {complexity}\n\n"
        f"Role verdicts:\n{verdicts_json}"
    )
    mod_reply = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _MODERATOR_SYSTEM},
            {"role": "user", "content": mod_context},
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
        complexity=complexity,  # type: ignore[arg-type]
        rationale=f"mdagents adaptive panel classified as {complexity}",
        red_flags=[],
    )

    majority = _majority_verdict(verdicts)
    prefer_fraction = sum(1 for v in verdicts if v.verdict == "prefer") / max(len(verdicts), 1)
    safety_reject = any(v.role == "SafetyReviewer" and v.verdict == "reject" for v in verdicts)
    defer_flag = any(v.role == "DeferToClinician" and v.verdict in {"caution", "reject"} for v in verdicts)

    components = ConfidenceComponents(
        evidence_tier=0.35,
        hdi_risk=1.0 if safety_reject else (0.5 if majority == "caution" else 0.0),
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
        defer_to_clinician=safety_reject or defer_flag,
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
