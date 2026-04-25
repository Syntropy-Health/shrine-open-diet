"""Mirrors agents/conftest.py — adds project-local lightrag/ + agents/ to sys.path
so eval modules can `from agents.* import ...` and `from config_loader import ...`
without a project-level pyrightconfig or pip install."""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_SUBPATH = _HERE.parent  # shrine-diet-bioactivity/ (the inner project root)

# Put the project root first so `import eval` resolves to our package, not the builtin
if str(_REPO_SUBPATH) not in sys.path:
    sys.path.insert(0, str(_REPO_SUBPATH))

for sub in ("lightrag", "agents"):
    p = _REPO_SUBPATH / sub
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
