"""Diet-OS wrapper baseline — wraps agents.run_case_study.run_case_study.

Converts a Scenario into the spec format expected by run_case_study, invokes
the full Subsystem H pipeline, and returns the ResearchSynthesis it produces.

Persistence: uses a tempfile directory so eval runs never write to research-journal/.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agents.models import ResearchSynthesis  # type: ignore[import-not-found]
from agents.run_case_study import run_case_study  # type: ignore[import-not-found]
from eval.scenario import Scenario  # type: ignore[import-not-found]


def run(scenario: Scenario) -> ResearchSynthesis:
    """Wrap run_case_study for benchmarking.

    Constructs a minimal case-study spec JSON from the Scenario, writes it
    to a temp directory, calls run_case_study, and returns the synthesis.
    Transcript and synthesis JSON are written to a temporary directory that
    is cleaned up after the function returns (caller gets the in-memory object).
    """
    spec = {
        "id": scenario.id,
        "research_question": scenario.research_question,
        "category": scenario.category,
        "version": scenario.version,
    }

    with tempfile.TemporaryDirectory(prefix="diet_os_eval_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        spec_path = tmp_path / f"{scenario.id}.json"
        spec_path.write_text(json.dumps(spec, indent=2))
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        synthesis = run_case_study(spec_path, out_dir)

    return synthesis
