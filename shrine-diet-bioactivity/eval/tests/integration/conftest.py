"""Shared fixtures + env-gating for `eval/tests/integration/` — Phase 3 of
the integration-test coverage uplift plan
(`research-journal/plans/2026-05-08-integration-test-coverage-uplift-plan.md`).

Each test in this directory drives the full `diet_os.run(scenario)` pipeline
against:
  - real OpenRouter (env: OPENROUTER_API_KEY)
  - real MCP gateway (env: MCP_API_KEY; MCP_URL defaults to staged Railway)

Tests carry `pytestmark = [pytest.mark.e2e, pytest.mark.live_llm, pytest.mark.slow]`
so they're excluded by default and run only when those markers are explicitly
selected (nightly CI).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eval.scenario import BenchmarkSet, Scenario  # type: ignore[import-not-found]

# Resolve the benchmark JSON path from this file's location:
#   __file__:  shrine-diet-bioactivity/eval/tests/integration/conftest.py
#   parents[4]: <repo root>
BENCH_PATH = (
    Path(__file__).resolve().parents[4]
    / "research-journal"
    / "shared"
    / "datasets"
    / "dietresearchbench_v1.json"
)


@pytest.fixture(scope="session")
def benchmark() -> BenchmarkSet:
    """Load DietResearchBench v1 once per session."""
    data = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
    return BenchmarkSet.model_validate(data)


@pytest.fixture(scope="session")
def scenario_by_id(benchmark: BenchmarkSet):
    """Return a lookup callable: id -> Scenario."""
    index = {s.id: s for s in benchmark.scenarios}

    def _lookup(scenario_id: str) -> Scenario:
        if scenario_id not in index:
            pytest.fail(
                f"scenario id {scenario_id!r} not found in {BENCH_PATH.name}; "
                f"available ids start with: {sorted(index)[:3]}..."
            )
        return index[scenario_id]

    return _lookup


@pytest.fixture(autouse=True)
def _require_live_env() -> None:
    """Skip every test in this directory unless both live-env credentials
    are present. Combined with the file-level `live_llm` marker, this gives
    two layers of safety against accidental cost incurrence:

      1. Default `-m "not e2e"` (mcp/pyproject.toml addopts) deselects them.
      2. This autouse fixture skips them even if explicitly selected without
         credentials in env.
    """
    missing = [
        var for var in ("OPENROUTER_API_KEY", "MCP_API_KEY") if not os.environ.get(var)
    ]
    if missing:
        pytest.skip(
            f"pipeline e2e requires {', '.join(missing)} — set in env to run"
        )


# Verdict-direction-aware confidence assertion helper lives in
# `_helpers.py` so test files can import it directly without depending on
# pytest's conftest collection mechanics.
