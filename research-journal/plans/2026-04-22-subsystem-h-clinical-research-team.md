# Subsystem H — AG2 Clinical Research Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an integrated AG2-based clinical research team — a multi-agent system that takes a clinical query, structures it via clinical-intake schemas, retrieves grounded evidence chains from the diet-bioactivity-TCM KG, deliberates across 6 specialist roles, and produces a confidence-calibrated recommendation with auditable provenance. This is the **primary implementation** for the paper's case-study and end-to-end demonstration; it absorbs the original Subsystems B (intake), C (KG retrieval), D (panel), and E (calibration).

**Architecture:** AG2 (`ag2ai/ag2`) `ConversableAgent` + `GroupChat` + `GroupChatManager` over Pydantic-typed structured outputs. Single shared `kg_query` tool registered via `@register_for_execution()` calls LightRAG `/query` (HTTP). Triage agent classifies complexity → conditionally instantiates a subset of roles → 1-round structured rebuttal → moderator synthesis → calibrator emits final `ClinicalVerdict` JSON.

**Tech Stack:** Python 3.10+, AG2 v0.12+ (`pip install ag2`), Pydantic v2, requests, pytest, pytest-asyncio, scikit-optimize (BayesOpt), neo4j-driver (for Cypher provenance verification).

**Pre-requisites:**
- Subsystem A complete (KG ingested into Aura at full scale or prototype scale)
- Aura credentials in `shrine-diet-bioactivity/.env` (see `.env.template`)
- LightRAG `/query` endpoint reachable (FastAPI server on `:9621` or production deployment)
- OpenAI or Anthropic API key in `.env`

**Pivot note (2026-04-22):** This plan supersedes standalone Subsystems B/C/D/E. The clinical-intake schema (originally B's responsibility) is implemented here as Stage 1 of the AG2 pipeline. The KG retrieval (originally C) is the shared `kg_query` tool. The panel (originally D) is the AG2 `GroupChat`. The calibrator (originally E) is the final agent. Standalone extraction of any of these for production decoupling is future work.

---

## Files created

| Path | Role |
|---|---|
| `shrine-diet-bioactivity/agents/__init__.py` | Package marker |
| `shrine-diet-bioactivity/agents/config.py` | LLM config + AG2 `LLMConfig` builder, model pinning, cache_seed |
| `shrine-diet-bioactivity/agents/schemas.py` | Pydantic models: `StructuredIntake`, `KGResult`, `RoleVerdict`, `TriageResult`, `ClinicalVerdict` |
| `shrine-diet-bioactivity/agents/intake_schema.py` | OPQRST + SOCRATES + NCP/ADIME schema constants + intake-prompt builder |
| `shrine-diet-bioactivity/agents/tools/__init__.py` | Package marker |
| `shrine-diet-bioactivity/agents/tools/kg_query.py` | `kg_query` AG2 tool — HTTP wrapper around LightRAG `/query` |
| `shrine-diet-bioactivity/agents/tools/chain_extractor.py` | Typed `herb→compound→target→symptom` chain extraction from KG response |
| `shrine-diet-bioactivity/agents/tools/cypher_verify.py` | Round-trip provenance verification via direct Cypher |
| `shrine-diet-bioactivity/agents/intake.py` | Stage 1 — Clinical intake agent (OPQRST/SOCRATES/NCP/ADIME) |
| `shrine-diet-bioactivity/agents/panel/__init__.py` | Package marker |
| `shrine-diet-bioactivity/agents/panel/triage.py` | MDAgents-style complexity classifier |
| `shrine-diet-bioactivity/agents/panel/roles/dietitian.py` | Role agent + system prompt |
| `shrine-diet-bioactivity/agents/panel/roles/pharmacologist.py` | Role agent |
| `shrine-diet-bioactivity/agents/panel/roles/tcm_practitioner.py` | Role agent (bilingual CN/EN) |
| `shrine-diet-bioactivity/agents/panel/roles/research_scientist.py` | Clinical research scientist (evidence/methodology) |
| `shrine-diet-bioactivity/agents/panel/roles/safety_reviewer.py` | HDI + contraindication safety agent |
| `shrine-diet-bioactivity/agents/panel/roles/defer_clinician.py` | Scope-limiting / defer-to-human classifier |
| `shrine-diet-bioactivity/agents/panel/group_chat.py` | GroupChat assembler + GroupChatManager moderator |
| `shrine-diet-bioactivity/agents/calibrator.py` | Stage 4 — Bayesian linear fusion (evidence × HDI × context) |
| `shrine-diet-bioactivity/agents/provenance.py` | Final artifact formatter with Cypher round-trip check |
| `shrine-diet-bioactivity/agents/orchestrator.py` | Top-level: query → intake → triage → panel → calibrate → emit |
| `shrine-diet-bioactivity/agents/tests/test_*.py` | Per-module pytest |
| `shrine-diet-bioactivity/agents/requirements.txt` | `ag2`, `pydantic`, `scikit-optimize`, `neo4j` pin |
| `research-journal/shared/case_studies/case_001.md` | First clinical-research case study output |

## Conventions threaded through every task

- **Config-driven:** every script reads from `loadDataSources()` + `loadIngestParams()` + `.env`. No hardcoded URLs, model names, weights, or paths.
- **Modular:** one role per file, one function per concern. Files ≤ 300 lines.
- **Reproducible:** `cache_seed=42` + `temperature=0` + pinned model snapshot (`model="gpt-4o-2026-XX-XX"` or `claude-sonnet-4-6-20251001`) + `extra_body={"seed": 42}`. Document the chosen pin in `agents/config.py`.
- **TDD:** every task is RED → GREEN → REFACTOR → COMMIT.
- **Structured output:** every LLM call uses `response_format=PydanticModel` where AG2 supports it. Plain-string outputs forbidden.

---

## Task H0 — AG2 install + smoke test

**Purpose:** verify AG2 v0.12+ installs cleanly and a trivial 2-agent chat runs end-to-end with the chosen LLM provider.

**Files:**
- Create: `shrine-diet-bioactivity/agents/__init__.py`
- Create: `shrine-diet-bioactivity/agents/requirements.txt`
- Create: `shrine-diet-bioactivity/agents/config.py`
- Create: `shrine-diet-bioactivity/agents/tests/test_smoke.py`

- [ ] **Step 1: write requirements + minimal config**

```text
# shrine-diet-bioactivity/agents/requirements.txt
ag2>=0.12.0
pydantic>=2.0
scikit-optimize>=0.10
neo4j>=5.20
requests>=2.31
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23
```

```python
# shrine-diet-bioactivity/agents/config.py
"""AG2 LLMConfig builder. Pins model snapshots + cache_seed + seed for reproducibility."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Pinned 2026-04-22. Bump deliberately when intentionally changing reasoning behavior.
MODEL_PINS = {
    "openai":    {"model": "gpt-4o-2024-08-06",   "api_type": "openai"},
    "anthropic": {"model": "claude-sonnet-4-6-20251001", "api_type": "anthropic"},
}

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")


def llm_config(provider: str = DEFAULT_PROVIDER) -> dict:
    pin = MODEL_PINS[provider]
    if provider == "openai":
        api_key = os.environ["OPENAI_API_KEY"]
    elif provider == "anthropic":
        api_key = os.environ["ANTHROPIC_API_KEY"]
    else:
        raise ValueError(f"unknown provider {provider!r}")
    return {
        "config_list": [{**pin, "api_key": api_key}],
        "cache_seed": 42,
        "temperature": 0.0,
        "extra_body": {"seed": 42},
    }
```

- [ ] **Step 2: failing smoke test**

```python
# shrine-diet-bioactivity/agents/tests/test_smoke.py
import pytest
from autogen import AssistantAgent, UserProxyAgent

from agents.config import llm_config


@pytest.mark.integration
def test_two_agent_chat_runs():
    cfg = llm_config()
    user = UserProxyAgent(name="user", human_input_mode="NEVER",
                          max_consecutive_auto_reply=1, code_execution_config=False)
    asst = AssistantAgent(name="assistant", llm_config=cfg,
                          system_message="Reply with the word 'pong' only.")
    chat = user.initiate_chat(asst, message="ping", max_turns=1)
    last = chat.chat_history[-1]["content"].lower()
    assert "pong" in last
```

- [ ] **Step 3: run + expect FAIL until deps installed**

```bash
cd shrine-diet-bioactivity && pip install -r agents/requirements.txt && cd .. && cd shrine-diet-bioactivity && python3 -m pytest agents/tests/test_smoke.py -m integration -v
```

- [ ] **Step 4: re-run after deps installed → expect PASS**

- [ ] **Step 5: commit**

```bash
git add shrine-diet-bioactivity/agents/__init__.py shrine-diet-bioactivity/agents/requirements.txt shrine-diet-bioactivity/agents/config.py shrine-diet-bioactivity/agents/tests/test_smoke.py
git commit -m "feat(agents): AG2 install + smoke test with pinned model + cache_seed"
```

---

## Task H1 — Pydantic schemas (intake / KG / verdict)

**Purpose:** lock the data contracts used across all stages. Every LLM call uses one of these as `response_format`.

**Files:**
- Create: `shrine-diet-bioactivity/agents/schemas.py`
- Create: `shrine-diet-bioactivity/agents/intake_schema.py`
- Create: `shrine-diet-bioactivity/agents/tests/test_schemas.py`

- [ ] **Step 1: failing tests**

```python
# shrine-diet-bioactivity/agents/tests/test_schemas.py
import pytest
from pydantic import ValidationError

from agents.schemas import (
    StructuredIntake, SymptomProfile, NutritionContext,
    KGChain, KGResult,
    TriageResult, ComplexityTier,
    RoleVerdict, Verdict,
    ClinicalVerdict, ConfidenceComponents,
)
from agents.intake_schema import build_intake_prompt, INTAKE_SCHEMA_DESCRIPTION


def test_structured_intake_minimum_valid():
    i = StructuredIntake(
        chief_complaint="fatigue",
        symptom_profile=SymptomProfile(severity=5),
        nutrition_context=NutritionContext(),
        medications_current=[],
        red_flags=[],
        needs_clarification=False,
        clarification_questions=[],
    )
    assert i.chief_complaint == "fatigue"


def test_structured_intake_severity_bounds():
    with pytest.raises(ValidationError):
        SymptomProfile(severity=11)
    with pytest.raises(ValidationError):
        SymptomProfile(severity=0)


def test_structured_intake_clarifications_capped_at_3():
    with pytest.raises(ValidationError):
        StructuredIntake(
            chief_complaint="x",
            symptom_profile=SymptomProfile(severity=5),
            nutrition_context=NutritionContext(),
            medications_current=[], red_flags=[],
            needs_clarification=True,
            clarification_questions=["a", "b", "c", "d"],  # 4 — must reject
        )


def test_triage_result_enum():
    t = TriageResult(complexity=ComplexityTier.moderate, rationale="3 meds")
    assert t.complexity is ComplexityTier.moderate


def test_role_verdict_enum():
    v = RoleVerdict(role="dietitian", verdict=Verdict.prefer,
                    support=["high omega-3"], concerns=[])
    assert v.verdict is Verdict.prefer


def test_clinical_verdict_components_in_unit_interval():
    cv = ClinicalVerdict(
        recommendation="Add 1 tbsp ground flaxseed daily",
        confidence=0.72,
        components=ConfidenceComponents(evidence_tier=0.8, hdi_risk=0.05, context_fit=0.88),
        provenance_chain=[KGChain(nodes=["Linum usitatissimum", "ALA", "PPAR-α", "Inflammation"],
                                   edges=["CONTAINS_COMPOUND", "TARGETS_PROTEIN", "ASSOC_WITH_DISEASE"],
                                   source_ids=["duke:flax-001", "cmaup:ALA-PPARA", "ctd:D007249"],
                                   evidence_tiers=["traditional", "experimental", "clinical"])],
        panel_notes={}, dissenting_opinions=[], defer_to_clinician=False,
    )
    assert 0 <= cv.confidence <= 1
    for v in (cv.components.evidence_tier, cv.components.hdi_risk, cv.components.context_fit):
        assert 0 <= v <= 1


def test_intake_schema_description_includes_three_anchors():
    desc = INTAKE_SCHEMA_DESCRIPTION
    assert "OPQRST" in desc and "SOCRATES" in desc and "NCP" in desc


def test_build_intake_prompt_includes_user_query():
    prompt = build_intake_prompt(user_query="I feel exhausted after meals")
    assert "exhausted after meals" in prompt
```

- [ ] **Step 2: run tests → expect FAIL (modules don't exist)**

```bash
cd shrine-diet-bioactivity && python3 -m pytest agents/tests/test_schemas.py -v
```

- [ ] **Step 3: implement schemas**

```python
# shrine-diet-bioactivity/agents/schemas.py
"""Pydantic data contracts for the Diet-OS clinical research team pipeline.

Every LLM-driven stage uses one of these as `response_format`.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, conlist


# =====================================================================
# Stage 1 — Clinical intake (OPQRST + SOCRATES + NCP/ADIME)
# =====================================================================

class SymptomProfile(BaseModel):
    onset: str = ""
    provocation: str = ""
    quality: str = ""
    region: str = ""
    severity: int = Field(ge=1, le=10)
    timing: str = ""
    associated: list[str] = Field(default_factory=list)
    exacerbating: list[str] = Field(default_factory=list)
    relieving: list[str] = Field(default_factory=list)


class NutritionContext(BaseModel):
    """NCP Assessment domain — anthropometric / biochemical / clinical / dietary / behavioral."""
    anthropometric: dict[str, str | float] = Field(default_factory=dict)
    biochemical: dict[str, str | float] = Field(default_factory=dict)
    clinical: dict[str, str | float] = Field(default_factory=dict)
    dietary: dict[str, str | float] = Field(default_factory=dict)
    behavioral: dict[str, str | float] = Field(default_factory=dict)


class StructuredIntake(BaseModel):
    chief_complaint: str
    symptom_profile: SymptomProfile
    nutrition_context: NutritionContext
    medications_current: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: conlist(str, max_length=3) = Field(default_factory=list)


# =====================================================================
# Stage 2 — KG result
# =====================================================================

class KGChain(BaseModel):
    nodes: list[str]
    edges: list[str]
    source_ids: list[str]
    evidence_tiers: list[str] = Field(default_factory=list)
    weights: list[float] = Field(default_factory=list)


class KGResult(BaseModel):
    chains: list[KGChain]
    raw_query: str
    mode: str = "hybrid"


# =====================================================================
# Stage 3 — Panel triage + role verdicts
# =====================================================================

class ComplexityTier(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class TriageResult(BaseModel):
    complexity: ComplexityTier
    rationale: str
    triggers: list[str] = Field(default_factory=list)


class Verdict(str, Enum):
    prefer = "prefer"
    caution = "caution"
    reject = "reject"
    abstain = "abstain"


class RoleVerdict(BaseModel):
    role: str
    verdict: Verdict
    support: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    cited_chains: list[int] = Field(default_factory=list)  # indices into KGResult.chains


# =====================================================================
# Stage 4 — Final artifact
# =====================================================================

class ConfidenceComponents(BaseModel):
    evidence_tier: float = Field(ge=0, le=1)
    hdi_risk: float = Field(ge=0, le=1)
    context_fit: float = Field(ge=0, le=1)


class ClinicalVerdict(BaseModel):
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    components: ConfidenceComponents
    provenance_chain: list[KGChain]
    panel_notes: dict[str, RoleVerdict]
    dissenting_opinions: list[RoleVerdict] = Field(default_factory=list)
    defer_to_clinician: bool = False
```

```python
# shrine-diet-bioactivity/agents/intake_schema.py
"""Clinical-intake schema constants — OPQRST + SOCRATES + NCP/ADIME.

These are the load-bearing reference frameworks the Stage 1 agent
prompt grounds itself in. Changing these strings re-shapes the agent's
elicitation behavior — version them carefully.
"""
from __future__ import annotations

OPQRST = """OPQRST (emergency-medicine triage mnemonic):
  Onset       — when did this start?
  Provocation — what triggers or worsens it?
  Quality     — how would you describe the sensation?
  Region      — where is it located? does it radiate?
  Severity    — 1-10 intensity scale
  Time        — duration, frequency, pattern
"""

SOCRATES = """SOCRATES (UK Resuscitation Council; deeper symptom characterization):
  Site, Onset, Character, Radiation, Associations,
  Time course, Exacerbating factors, Severity
"""

NCP_ADIME = """Nutrition Care Process / ADIME (Academy of Nutrition and Dietetics):
  Assessment domains:
    Anthropometric — weight, height, BMI, waist/hip
    Biochemical    — labs (lipid panel, HbA1c, ferritin, vit D, etc.)
    Clinical       — comorbidities, medications, allergies
    Dietary        — typical intake, restrictions, supplements
    Behavioral     — eating patterns, stress, sleep, activity
"""

INTAKE_SCHEMA_DESCRIPTION = "\n".join([OPQRST, SOCRATES, NCP_ADIME])


def build_intake_prompt(user_query: str) -> str:
    return f"""You are a clinical-intake agent. Transform the user's free-text query
into a structured intake record using the following clinical reference frameworks:

{INTAKE_SCHEMA_DESCRIPTION}

If the query lacks information needed for safe downstream reasoning,
set `needs_clarification=true` and ask up to 3 targeted questions.

Always populate `red_flags` if any of these appear: pregnancy, anticoagulant
therapy, hepatic/renal impairment, pediatric (<18), polypharmacy (>=3 meds),
recent surgery, active malignancy.

User query:
{user_query}
"""
```

- [ ] **Step 4: re-run tests → expect PASS**

- [ ] **Step 5: commit**

```bash
git add shrine-diet-bioactivity/agents/schemas.py shrine-diet-bioactivity/agents/intake_schema.py shrine-diet-bioactivity/agents/tests/test_schemas.py
git commit -m "feat(agents): Pydantic schemas + OPQRST/SOCRATES/NCP intake reference"
```

---

## Task H2 — `kg_query` AG2 tool + chain extractor

**Purpose:** the shared LightRAG-backed tool every panel agent calls. Returns typed `KGChain` lists, not just text.

**Files:**
- Create: `shrine-diet-bioactivity/agents/tools/__init__.py`
- Create: `shrine-diet-bioactivity/agents/tools/kg_query.py`
- Create: `shrine-diet-bioactivity/agents/tools/chain_extractor.py`
- Create: `shrine-diet-bioactivity/agents/tests/test_kg_query.py`

- [ ] **Step 1: failing tests**

```python
# shrine-diet-bioactivity/agents/tests/test_kg_query.py
import pytest
from unittest.mock import patch, MagicMock

from agents.schemas import KGResult, KGChain
from agents.tools.kg_query import kg_query
from agents.tools.chain_extractor import extract_chains_from_response


@patch("agents.tools.kg_query.requests.post")
def test_kg_query_calls_lightrag_query_endpoint(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"response": "Ginger contains 6-gingerol which targets TRPV1...",
                      "context": {"chains": []}},
    )
    result = kg_query("What herbs help with bloating?", mode="hybrid")
    assert isinstance(result, KGResult)
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert "/query" in args[0]


def test_extract_chains_pulls_typed_path():
    fake_subgraph = {
        "edges": [
            {"src": "Zingiber officinale", "tgt": "6-gingerol",
             "rel": "CONTAINS_COMPOUND", "source_id": "duke:gingerol-014", "weight": 0.92},
            {"src": "6-gingerol", "tgt": "TRPV1",
             "rel": "TARGETS_PROTEIN", "source_id": "cmaup:cmp-4421",
             "evidence_tier": "in_vivo"},
            {"src": "TRPV1", "tgt": "Functional dyspepsia",
             "rel": "ASSOC_WITH_DISEASE", "source_id": "ctd:D036961",
             "evidence_tier": "experimental"},
        ],
    }
    chains = extract_chains_from_response(fake_subgraph)
    assert len(chains) == 1
    chain = chains[0]
    assert "Zingiber officinale" in chain.nodes
    assert "Functional dyspepsia" in chain.nodes
    assert "CONTAINS_COMPOUND" in chain.edges
    assert chain.source_ids == ["duke:gingerol-014", "cmaup:cmp-4421", "ctd:D036961"]


def test_kg_query_returns_empty_chains_on_no_hit():
    with patch("agents.tools.kg_query.requests.post") as mp:
        mp.return_value = MagicMock(status_code=200,
                                    json=lambda: {"response": "no relevant context", "context": {"edges": []}})
        result = kg_query("xyz herb", mode="hybrid")
    assert result.chains == []
```

- [ ] **Step 2: run → expect FAIL**

- [ ] **Step 3: implement**

```python
# shrine-diet-bioactivity/agents/tools/kg_query.py
"""AG2 tool — query LightRAG / Neo4j Aura via the FastAPI /query endpoint.

Registered onto every panel agent via `register_for_execution()`. Returns
a typed KGResult so downstream agents and the calibrator can reason
structurally (not just over LLM-rendered text).
"""
from __future__ import annotations

import os

import requests

from agents.schemas import KGResult
from agents.tools.chain_extractor import extract_chains_from_response

LIGHTRAG_BASE = os.environ.get("LIGHTRAG_BASE", "http://localhost:9621")
DEFAULT_TIMEOUT = 60


def kg_query(query: str, mode: str = "hybrid", top_k: int = 20) -> KGResult:
    """Query LightRAG and return typed chains.

    `mode` ∈ {local, global, hybrid, naive, mix}. Hybrid is the paper-recommended default.
    """
    resp = requests.post(
        f"{LIGHTRAG_BASE}/query",
        json={"query": query, "mode": mode, "top_k": top_k},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    chains = extract_chains_from_response(payload.get("context") or {})
    return KGResult(chains=chains, raw_query=query, mode=mode)
```

```python
# shrine-diet-bioactivity/agents/tools/chain_extractor.py
"""Pull typed `Herb→Compound→Target→Symptom` chains from a LightRAG response.

LightRAG's /query returns mixed context (entities + edges + chunks).
We project onto our 5 relationship types and emit chains in canonical
biology order so the panel + calibrator see consistent provenance.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from agents.schemas import KGChain

CANONICAL_ORDER = (
    "TREATS_SYMPTOM",
    "CONTAINS_COMPOUND",
    "TARGETS_PROTEIN",
    "ASSOC_WITH_DISEASE",
    "INTERACTS_WITH",
)


def extract_chains_from_response(context: Mapping) -> list[KGChain]:
    edges = context.get("edges", []) if isinstance(context, dict) else []
    if not edges:
        return []
    # Group edges by source-node, walk each starting point
    out_by_src: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        if not isinstance(e, dict):
            continue
        out_by_src[e.get("src", "")].append(e)

    chains: list[KGChain] = []
    seen_starts: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("src", "")
        if src in seen_starts or not src:
            continue
        # Build one chain by greedy descent
        nodes = [src]
        edge_types: list[str] = []
        source_ids: list[str] = []
        evidence_tiers: list[str] = []
        weights: list[float] = []
        cursor = src
        while True:
            outs = out_by_src.get(cursor, [])
            if not outs:
                break
            chosen = outs[0]
            tgt = chosen.get("tgt", "")
            if not tgt or tgt in nodes:
                break
            nodes.append(tgt)
            edge_types.append(chosen.get("rel", ""))
            source_ids.append(chosen.get("source_id", ""))
            evidence_tiers.append(chosen.get("evidence_tier", ""))
            weights.append(float(chosen.get("weight", 0.0)))
            cursor = tgt
            if len(nodes) >= 5:  # cap traversal depth (DESIGN §2.2 failure-mode mitigation)
                break
        if len(edge_types) >= 1:
            chains.append(KGChain(nodes=nodes, edges=edge_types,
                                   source_ids=source_ids,
                                   evidence_tiers=evidence_tiers,
                                   weights=weights))
            seen_starts.add(src)
    return chains
```

- [ ] **Step 4: re-run tests → PASS**

- [ ] **Step 5: commit**

```bash
git add shrine-diet-bioactivity/agents/tools/ shrine-diet-bioactivity/agents/tests/test_kg_query.py
git commit -m "feat(agents): kg_query AG2 tool + typed chain extractor"
```

---

## Task H3 — Stage 1: Clinical intake agent

**Files:**
- Create: `shrine-diet-bioactivity/agents/intake.py`
- Create: `shrine-diet-bioactivity/agents/tests/test_intake.py`

- [ ] **Step 1: failing tests** — verify intake agent emits a valid `StructuredIntake` for representative queries (with both red-flag and clarification scenarios). Use `unittest.mock` to mock the LLM call and assert prompt structure.

```python
# shrine-diet-bioactivity/agents/tests/test_intake.py
from unittest.mock import patch
import pytest

from agents.intake import run_intake
from agents.schemas import StructuredIntake


@patch("agents.intake._llm_call")
def test_intake_returns_validated_structured_intake(mock_llm):
    mock_llm.return_value = StructuredIntake.model_validate({
        "chief_complaint": "post-prandial bloating",
        "symptom_profile": {"severity": 6, "timing": "30 min after meals"},
        "nutrition_context": {},
        "medications_current": [],
        "red_flags": [],
        "needs_clarification": False,
        "clarification_questions": [],
    })
    result = run_intake("I feel bloated after eating, especially heavy meals.")
    assert isinstance(result, StructuredIntake)
    assert result.chief_complaint == "post-prandial bloating"


@patch("agents.intake._llm_call")
def test_intake_surfaces_red_flags(mock_llm):
    mock_llm.return_value = StructuredIntake.model_validate({
        "chief_complaint": "fatigue",
        "symptom_profile": {"severity": 5},
        "nutrition_context": {},
        "medications_current": ["warfarin", "metoprolol"],
        "red_flags": ["anticoagulant therapy"],
        "needs_clarification": False,
        "clarification_questions": [],
    })
    result = run_intake("I'm tired all the time, on warfarin and metoprolol.")
    assert "anticoagulant therapy" in result.red_flags


@patch("agents.intake._llm_call")
def test_intake_caps_clarifications(mock_llm):
    # If LLM returns >3 questions despite the schema cap, validation should catch it.
    mock_llm.side_effect = [
        StructuredIntake.model_validate({
            "chief_complaint": "x",
            "symptom_profile": {"severity": 5},
            "nutrition_context": {},
            "medications_current": [], "red_flags": [],
            "needs_clarification": True,
            "clarification_questions": ["q1", "q2", "q3"],  # already at cap
        }),
    ]
    out = run_intake("vague query")
    assert len(out.clarification_questions) <= 3
```

- [ ] **Step 2: run → FAIL**

- [ ] **Step 3: implement** — `run_intake(query: str) -> StructuredIntake` calls AG2 `AssistantAgent` with `response_format=StructuredIntake`. The `_llm_call(prompt)` helper is mocked in tests but in production wraps `agent.generate_oai_reply()` or AG2's structured-output API.

```python
# shrine-diet-bioactivity/agents/intake.py
"""Stage 1 — Clinical intake agent."""
from __future__ import annotations

from autogen import AssistantAgent

from agents.config import llm_config
from agents.intake_schema import build_intake_prompt
from agents.schemas import StructuredIntake


def _llm_call(prompt: str) -> StructuredIntake:
    """Wrap AG2 structured-output call. Isolated for test mocking."""
    cfg = {**llm_config(), "response_format": StructuredIntake}
    agent = AssistantAgent(
        name="intake",
        llm_config=cfg,
        system_message="You return ONLY the JSON conforming to StructuredIntake.",
    )
    reply = agent.generate_reply(messages=[{"role": "user", "content": prompt}])
    if isinstance(reply, dict):
        return StructuredIntake.model_validate(reply)
    if isinstance(reply, StructuredIntake):
        return reply
    # AG2 may return string with structured content; defensive parse
    import json
    return StructuredIntake.model_validate(json.loads(reply))


def run_intake(user_query: str) -> StructuredIntake:
    return _llm_call(build_intake_prompt(user_query))
```

- [ ] **Step 4: re-run → PASS**

- [ ] **Step 5: commit** — `feat(agents): Stage 1 clinical intake agent (OPQRST/SOCRATES/NCP)`

---

## Task H4 — Stage 3a: Triage classifier (MDAgents-style)

**Files:** `agents/panel/__init__.py`, `agents/panel/triage.py`, `agents/tests/test_triage.py`

- [ ] **Step 1–5:** RED → GREEN → REFACTOR → COMMIT.

`run_triage(intake: StructuredIntake) -> TriageResult` returns `low`, `moderate`, or `high`. Triggers from intake's `red_flags` and `medications_current` count drive the rule-based fallback; LLM call confirms (response_format=TriageResult).

Test that:
- `len(red_flags) > 0` → at least `moderate`
- `len(medications_current) >= 3` (polypharmacy) → at least `moderate`
- Pregnancy / hepatic / renal red flags → `high`
- Otherwise → `low`

```python
# shrine-diet-bioactivity/agents/panel/triage.py
from __future__ import annotations

from agents.schemas import StructuredIntake, TriageResult, ComplexityTier

HIGH_RED_FLAGS = {"pregnancy", "hepatic impairment", "renal impairment",
                  "active malignancy", "pediatric"}


def run_triage(intake: StructuredIntake) -> TriageResult:
    flags = {f.lower() for f in intake.red_flags}
    n_meds = len(intake.medications_current)
    triggers: list[str] = []
    if flags & HIGH_RED_FLAGS:
        triggers.append("high-severity red flag")
        return TriageResult(complexity=ComplexityTier.high,
                            rationale="; ".join(triggers), triggers=triggers)
    if intake.red_flags:
        triggers.append("non-empty red_flags")
    if n_meds >= 3:
        triggers.append(f"polypharmacy ({n_meds} meds)")
    if triggers:
        return TriageResult(complexity=ComplexityTier.moderate,
                            rationale="; ".join(triggers), triggers=triggers)
    return TriageResult(complexity=ComplexityTier.low,
                        rationale="no escalation triggers", triggers=[])
```

Tests:
```python
from agents.schemas import StructuredIntake, SymptomProfile, NutritionContext, ComplexityTier
from agents.panel.triage import run_triage


def _intake(red_flags=None, meds=None):
    return StructuredIntake(
        chief_complaint="x",
        symptom_profile=SymptomProfile(severity=5),
        nutrition_context=NutritionContext(),
        medications_current=meds or [],
        red_flags=red_flags or [],
        needs_clarification=False, clarification_questions=[],
    )


def test_triage_low_when_no_signals():
    assert run_triage(_intake()).complexity is ComplexityTier.low


def test_triage_moderate_with_polypharmacy():
    assert run_triage(_intake(meds=["a", "b", "c"])).complexity is ComplexityTier.moderate


def test_triage_high_for_pregnancy():
    assert run_triage(_intake(red_flags=["pregnancy"])).complexity is ComplexityTier.high
```

Commit: `feat(agents): MDAgents-style complexity triage`

---

## Task H5 — Stage 3b: Six role agents (one per file)

For each role: `agents/panel/roles/<role>.py` exporting `make_<role>(llm_cfg) -> ConversableAgent` with a role-specific `system_message`. Each agent registers `kg_query` as an executable tool and emits `RoleVerdict` via `response_format`.

Roles (one task each, identical structure):
- **H5.1** Dietitian — `prefer/caution/reject` based on nutrition adequacy + dietary pattern fit
- **H5.2** Pharmacologist — mechanism plausibility + PK/PD considerations
- **H5.3** TCM Practitioner — bilingual CN/EN, classical formula context, syndrome pattern (辨證); cites SymMap + HERB 2.0 chains
- **H5.4** Clinical Research Scientist — GRADE/Cochrane evidence quality lens; writes dissenting-minority report when mechanism is plausible but evidence weak
- **H5.5** Safety Reviewer — HDI lookup via `INTERACTS_WITH` edges (HDI-Safe 50); contraindications via `CONTRAINDICATES`
- **H5.6** Defer-to-Clinician — scope-limiting agent; emits `defer=True` for queries outside dietary/herbal scope

For each role, write the system prompt to:
1. Anchor the role's clinical perspective (reference frameworks)
2. Require it to call `kg_query` ≥ 1 time before forming a verdict
3. Require it to cite at least one chain index in `cited_chains`
4. Require it to emit `RoleVerdict` JSON only — no narrative

Tests for each role: mock `kg_query`, verify the agent emits a valid `RoleVerdict` and that the `verdict` enum is one of the four allowed values.

Commit per role: `feat(agents): <role> panel agent + KG-grounded verdict prompt`

---

## Task H6 — Stage 3c: GroupChat assembler + moderator

**Files:** `agents/panel/group_chat.py`, `agents/tests/test_group_chat.py`

`build_panel(triage: TriageResult, intake, kg_result, llm_cfg) -> GroupChat` that:
- For `low`: returns a 1-agent "GroupChat" (just Dietitian) — degenerate case for cost reasons
- For `moderate`: 3-way GroupChat (Dietitian + Pharmacologist + TCM Practitioner)
- For `high`: 6-way GroupChat (+ Clinical Research Scientist + Safety Reviewer + Defer-to-Clinician)

`speaker_selection_method="round_robin"`, `max_round=2` (verdict + rebuttal). `GroupChatManager` system prompt instructs it to synthesize role verdicts into a final ranking, surface dissent, and emit `"CONSENSUS:"` to terminate.

Termination via `is_termination_msg=lambda m: "CONSENSUS:" in m.get("content", "")`.

Tests: assert that for each complexity tier, the panel includes the right roles. Mock all role agents to return canned `RoleVerdict`s and verify the moderator synthesizes them.

Commit: `feat(agents): adaptive GroupChat assembler + moderator (MDAgents-style)`

---

## Task H7 — Stage 4: Calibrator + provenance formatter

**Files:** `agents/calibrator.py`, `agents/provenance.py`, `agents/tests/test_calibrator.py`

`calibrate(chains, intake, panel_critique) -> ClinicalVerdict` computes:
- `evidence_tier` ← max over chains' max evidence-tier weight (from `ingest_params.yaml`'s `evidence_tier_weights`)
- `hdi_risk` ← max severity from any `INTERACTS_WITH` edge incident to the chain's compounds vs. `intake.medications_current`. Lookup via direct Cypher (or via SQLite) using the HDI-Safe 50 ingest.
- `context_fit` ← 1 minus the count of `CONTRAINDICATES` matches against `intake.red_flags + nutrition_context.clinical`

Bayesian linear fusion (logit scale) with weights stored at `config/calibrator_weights.json`. Initial weights are equal (`β₁=β₂=β₃=1/3`); BayesOpt tuning is deferred to Subsystem F.

Tests:
- Property: `confidence` is non-decreasing in `evidence_tier`, non-increasing in `hdi_risk`, non-decreasing in `context_fit`
- Property: `confidence ∈ [0,1]` for all valid inputs
- HDI hit triggers measurable confidence drop (cite a known HDI-Safe 50 entry — e.g., St. John's Wort + sertraline)
- Provenance formatter: every chain's `source_ids` round-trip through Cypher (mock the driver)

Commit: `feat(agents): Bayesian linear calibrator + provenance Cypher round-trip`

---

## Task H8 — Top-level orchestrator + CLI

**Files:** `agents/orchestrator.py`, `agents/__main__.py`, `agents/tests/test_orchestrator.py`

`run(query: str) -> ClinicalVerdict` glues the stages:

```python
def run(query: str) -> ClinicalVerdict:
    intake = run_intake(query)
    if intake.needs_clarification:
        # In real use, this would surface to the caller; for case-study mode,
        # log + auto-decline rather than blocking.
        ...
    triage = run_triage(intake)
    kg_result = kg_query(_keyword_join(intake), mode="hybrid")
    panel_history = run_group_chat(intake, kg_result, triage)
    return calibrate_and_format(intake, kg_result, panel_history)
```

CLI: `python -m agents "I have post-prandial bloating, on no medications."` writes a `ClinicalVerdict` JSON to stdout.

End-to-end test (slow, integration-marked): a single query producing a non-empty `ClinicalVerdict` with provenance chains. Pin the LLM seed; expected output is fuzzy-asserted (recommendation contains at least one term from a small whitelist of plausible answers).

Commit: `feat(agents): top-level orchestrator + CLI entry`

---

## Task H9 — First case study (clinical research focus)

**Files:** `research-journal/shared/case_studies/case_001.md`, `research-journal/shared/case_studies/case_001_input.json`, `research-journal/shared/case_studies/case_001_output.json`

Run the orchestrator against a curated **clinical research** scenario — e.g., "researcher panel evaluating whether ashwagandha (Withania somnifera) is appropriate as adjunctive therapy for cortisol-driven sleep disturbance in a patient on bupropion + atorvastatin." This exercises:
- HDI lookup (ashwagandha + bupropion lacks strong evidence; ashwagandha + atorvastatin no known interaction — should surface as `caution` not `reject`)
- TCM agent (ashwagandha is *not* TCM — TCM agent should defer to Pharmacologist)
- Clinical Research Scientist (RCT evidence for ashwagandha + sleep is moderate-quality; should write a dissenting note)
- Safety Reviewer (citing HDI-Safe 50 entries if applicable)
- Provenance chain (`Withania somnifera → withanolides → cortisol/HPA axis → sleep`)

Persist input + output JSON. Write a short markdown case study (`case_001.md`) explaining the scenario, expected behavior, observed behavior, and any disagreements with the panel's verdict.

Commit: `docs(case-study): case_001 clinical research panel — ashwagandha sleep adjunct`

---

## Task H10 — Reproducibility wrapper + AG2 deterministic settings audit

**Files:** `agents/tests/test_reproducibility.py`

Run the orchestrator twice with `cache_seed=42` and assert byte-identical `ClinicalVerdict.model_dump_json()`. If they diverge:
- AG2 `cache_seed` is local file cache, not OpenAI `seed` — confirm both are pinned.
- Token/whitespace drift in panel debate strings is allowed if it doesn't affect the structured `RoleVerdict`. Use a `_normalize_for_compare` helper that strips panel-narrative free-text and compares only the typed fields.

Commit: `test(agents): reproducibility — twice-run orchestrator yields identical verdict`

---

## Completion checklist

- [ ] AG2 installed; smoke test green
- [ ] Pydantic schemas + intake-schema constants committed; tests green
- [ ] `kg_query` tool + chain extractor committed; tests green
- [ ] Stage 1 intake agent committed; OPQRST/SOCRATES/NCP-grounded
- [ ] Triage classifier committed; rule-based, deterministic
- [ ] All 6 role agents committed; each calls `kg_query` and emits `RoleVerdict`
- [ ] GroupChat assembler + moderator; round_robin, max_round=2
- [ ] Calibrator (Bayesian linear, equal-weight default) + provenance verify
- [ ] Orchestrator + CLI
- [ ] Case study case_001 produced and committed
- [ ] Reproducibility test green
- [ ] Coverage on `agents/` ≥ 80% (`pytest --cov=shrine-diet-bioactivity/agents --cov-report=term-missing`)

When done: write Subsystem F (DietBench-Clinical eval harness) plan, then Subsystem G (manuscript).

---

## Cost + latency caveats from AG2 research

1. **Avoid `speaker_selection_method="auto"`** — fires LLM call per turn for routing. Use `"round_robin"`. ~12× cost saving in 6-role × 2-round panel.
2. **`cache_seed=42` is local file cache, not OpenAI `seed`** — pass both. Done in `agents/config.py`.
3. **`response_format` on Anthropic strict mode** — has subtle constraints around tool calling. If `kg_query` tool call inside a structured-output agent breaks, switch that agent to OpenAI for the demo (configurable per-role via `llm_config(provider="openai")`).
4. **GroupChat token blow-up** — moderator sees full chat history. For the 6-role × 2-round case, expect 6k–12k tokens per case. Budget at ~$0.10–$0.30 per case study with GPT-4o-2024-08-06; cheaper with Haiku.
5. **Pinned model snapshot drift** — when the pinned snapshot is deprecated by the provider, bump deliberately and re-run reproducibility test; the case study output JSON should be regenerated and version-tagged.
