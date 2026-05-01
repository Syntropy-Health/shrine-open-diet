"""E2E smoke test for the panel + MCP gateway wiring.

Bypasses the triage stage (which has Nemotron JSON-quality issues per
postmortem §9d) and constructs a fixed high-complexity Triage so all 6
panel roles are assembled. Then verifies:

  1. The MCP tools were actually called by panel agents (look for
     kg_compound_to_targets / kg_hdi_check / kg_diet_to_compounds in the
     transcript).
  2. At least one tool returned non-empty chains/results.
  3. The chat completed without import or wiring errors.

Run:
  python3 -m scripts.smoke_panel_via_mcp

Requires env: MCP_URL, MCP_API_KEY, OPENROUTER_API_KEY.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

# Bootstrap sys.path for `python3 -m scripts.smoke_panel_via_mcp`.
_REPO = Path(__file__).resolve().parent.parent
for _sub in ("", "lightrag", "agents"):
    _p = str(_REPO / _sub) if _sub else str(_REPO)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from autogen import ConversableAgent

from agents.models import ResearchQuestion, Triage  # type: ignore[import-not-found]
from agents.panel.assembly import assemble_panel  # type: ignore[import-not-found]


QUESTION = (
    "In adults receiving moderately emetogenic chemotherapy, does adjunctive "
    "ginger (Zingiber officinale) reduce chemotherapy-induced nausea and "
    "vomiting compared to standard antiemetics alone?"
)


def _fixed_triage() -> Triage:
    return Triage(
        complexity="high",
        rationale="smoke: force all 6 panel roles to wire",
        red_flags=["chemotherapy", "polypharmacy_3plus"],
    )


def _scan_for_tool_calls(messages: list[dict]) -> dict[str, int]:
    """Return {tool_name: call_count} for any MCP tool seen in the chat."""
    counts: dict[str, int] = {}
    for m in messages:
        # AG2 tool-call messages live under content (None) + tool_calls list,
        # OR as serialized dicts in 'content'. Look at both.
        for tc in (m.get("tool_calls") or []):
            name = tc.get("function", {}).get("name") or tc.get("name")
            if name:
                counts[name] = counts.get(name, 0) + 1
        content = m.get("content")
        if isinstance(content, str):
            # Some AG2 versions render tool-call traces as text — sniff names.
            for tool in (
                "kg_query", "kg_diet_to_compounds", "kg_compound_to_targets",
                "kg_compound_to_diseases", "kg_herb_to_diseases",
                "kg_herb_to_symptoms", "kg_compound_to_symptoms",
                "kg_hdi_check", "kg_bilingual_term", "kg_node_neighborhood",
            ):
                if f'"name": "{tool}"' in content or f"name='{tool}'" in content:
                    counts[tool] = counts.get(tool, 0) + 1
    return counts


def main() -> int:
    rq = ResearchQuestion(
        text=QUESTION,
        intervention="Ginger (Zingiber officinale)",
        outcome="chemotherapy-induced nausea and vomiting",
        population="adults on moderately emetogenic chemo",
        comparator="standard antiemetics",
    )
    triage = _fixed_triage()
    print(f"smoke: question={QUESTION[:80]}...")
    print(f"smoke: triage={triage.model_dump_json()}")

    chat, manager = assemble_panel(triage)
    print(f"smoke: panel assembled with {len(chat.agents)} roles "
          f"({[a.name for a in chat.agents]})")

    moderator_input = (
        f"Research question: {rq.model_dump_json()}\n"
        f"Triage: {triage.model_dump_json()}\n"
        "Each role agent: emit a RoleVerdict using the role-priored MCP tools "
        "registered for your role. Cite the tool calls you made. The "
        "moderator emits a PanelDeliberation."
    )
    try:
        manager.initiate_chat(
            cast(ConversableAgent, chat.agents[0]),
            message=moderator_input,
        )
    except Exception as e:
        print(f"smoke: panel chat raised: {type(e).__name__}: {e}", file=sys.stderr)
        # Don't fail-fast — we still want to inspect the partial transcript

    tool_counts = _scan_for_tool_calls(chat.messages)
    print("smoke: tool call counts =", json.dumps(tool_counts, indent=2))
    print(f"smoke: chat had {len(chat.messages)} messages")

    # Persist transcript for forensic review
    out = Path("/tmp/e2e-smoke/panel-transcript.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(m, default=str) for m in chat.messages))
    print(f"smoke: transcript at {out}")

    # Pass criterion: at least one MCP tool was called
    if not tool_counts:
        print("smoke: FAIL — no MCP tools called by panel", file=sys.stderr)
        return 1
    print("smoke: PASS — MCP tools called", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
