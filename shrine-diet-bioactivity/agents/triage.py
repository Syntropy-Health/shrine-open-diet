# shrine-diet-bioactivity/agents/triage.py
"""Triage agent — first stage of the clinical research team.

Absorbs the OPQRST + SOCRATES + NCP/ADIME structured-intake schema
from former Subsystem B, but applies it to a *research question*
(intervention, population, outcome, comparator) rather than a patient's
symptom profile. Emits ResearchQuestion + Triage via response_format."""
from __future__ import annotations

from typing import Callable

from autogen import ConversableAgent

from agents.llm_config import default_llm_config  # type: ignore[import-not-found]
from agents.models import ResearchQuestion, Triage  # type: ignore[import-not-found]


def _extract_json_obj(text: str) -> str:
    """Extract the first balanced JSON object from a possibly-padded LLM reply.

    Free-tier Nemotron sometimes pads structured-output JSON with
    tens of thousands of trailing whitespace/newlines that
    `model_validate_json` rejects. This walker finds the first balanced
    {...} and returns just that slice, ignoring outer chatter.
    """
    s = text.strip()
    start = s.find('{')
    if start == -1:
        return s
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]

TRIAGE_SYSTEM_PROMPT = """\
You are the triage clinician of a clinical research team. Given a
free-form research question about a herbal/dietary intervention, you:

1. Extract a structured ResearchQuestion (intervention, outcome, population,
   comparator if present). Borrow PICO conventions from clinical research.
2. Classify complexity:
   - "low"      = single-intervention, single-outcome, no polypharmacy or pregnancy/organ-failure
   - "moderate" = multi-drug interaction question, or comparison across interventions
   - "high"     = pregnancy / hepatic / renal / pediatric / weak-evidence / safety-critical
3. List red_flags (anticoagulant_therapy, pregnancy, hepatic_impairment,
   renal_impairment, pediatric, polypharmacy_3plus, etc.)
4. If the question is ambiguous, set needs_clarification=true and emit
   up to 3 clarification_questions a researcher would ask back.

Use the OPQRST mnemonic for symptom-mention parsing if the question
references presenting symptoms; use NCP/ADIME conventions for nutritional
context. The intent is research-grade rigor, not patient guidance.
"""


def build_triage_agent() -> Callable[[str], tuple[ResearchQuestion, Triage]]:
    cfg = default_llm_config(response_format=None)  # we run two structured calls explicitly

    rq_agent = ConversableAgent(
        name="ResearchQuestionExtractor",
        system_message=TRIAGE_SYSTEM_PROMPT + "\nFor this turn, emit ONLY a ResearchQuestion JSON.",
        llm_config={**cfg, "response_format": ResearchQuestion},
        human_input_mode="NEVER",
    )
    triage_agent = ConversableAgent(
        name="TriageClassifier",
        system_message=TRIAGE_SYSTEM_PROMPT + "\nFor this turn, emit ONLY a Triage JSON.",
        llm_config={**cfg, "response_format": Triage},
        human_input_mode="NEVER",
    )

    def _reply_text(reply: object) -> str:
        if reply is None:
            raise RuntimeError("triage LLM returned None")
        if isinstance(reply, str):
            return reply
        if isinstance(reply, dict):
            content = reply.get("content")
            if isinstance(content, str):
                return content
        raise RuntimeError(f"triage LLM returned unsupported shape: {type(reply).__name__}")

    def run(question_text: str) -> tuple[ResearchQuestion, Triage]:
        rq_reply = rq_agent.generate_reply(messages=[{"role": "user", "content": question_text}])
        rq = ResearchQuestion.model_validate_json(_extract_json_obj(_reply_text(rq_reply)))
        triage_reply = triage_agent.generate_reply(
            messages=[{"role": "user", "content": f"Question: {question_text}\nResearchQuestion: {rq.model_dump_json()}"}]
        )
        t = Triage.model_validate_json(_extract_json_obj(_reply_text(triage_reply)))
        return rq, t

    return run
