"""Guardrail: browser code follows the same dependency rule as the backend.

web/js/core   -> imports NOTHING outside core; no DOM/Web Audio/network globals.
web/js/audio  -> may import core only.
web/js/api    -> may import core only.
web/js/ui     -> may import core, audio, api.
web/js/main.js is the frontend composition root (may import everything).
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[2] / "web" / "js"
IMPORT_RE = re.compile(
    r"""(?:import|export)\s[^'"]*?from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]"""
)
FORBIDDEN_IN_CORE = re.compile(
    r"\b(document|window|navigator|fetch|AudioContext|localStorage|XMLHttpRequest|Tone)\b"
)
ALLOWED = {
    "core": {"core"},
    "audio": {"core", "audio"},
    "api": {"core", "api"},
    "ui": {"core", "audio", "api", "ui"},
}


def _layer_of(path: Path) -> str | None:
    rel = path.relative_to(JS)
    return rel.parts[0] if len(rel.parts) > 1 else None  # None => main.js (root)


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", src)


def test_frontend_dependency_rule() -> None:
    violations: list[str] = []
    for f in JS.rglob("*.js"):
        layer = _layer_of(f)
        if layer is None:
            continue
        src = _strip_comments(f.read_text(encoding="utf-8"))
        for m in IMPORT_RE.finditer(src):
            spec = m.group(1) or m.group(2)
            if not spec.startswith("."):
                violations.append(f"{f.relative_to(JS)}: bare/external import '{spec}'")
                continue
            target = (f.parent / spec).resolve()
            try:
                tl = target.relative_to(JS.resolve()).parts[0]
            except ValueError:
                violations.append(f"{f.relative_to(JS)}: import escapes web/js: {spec}")
                continue
            if tl not in ALLOWED[layer]:
                violations.append(f"{f.relative_to(JS)} ({layer}) must not import {tl}: {spec}")
        if layer == "core":
            hit = FORBIDDEN_IN_CORE.search(src)
            if hit:
                violations.append(
                    f"{f.relative_to(JS)}: core uses forbidden global '{hit.group(0)}'"
                )
    assert not violations, "\n".join(violations)
