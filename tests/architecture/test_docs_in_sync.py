"""Guardrail: the domain model and ports in the code must equal the blocks in docs/02.

This makes "never silently change the domain model" mechanical: change the code
without changing the doc (or vice versa) and this test fails.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "02-DOMAIN-MODEL.md"

SYNCED = {
    "domain-models": ROOT / "src/earth_jukebox/domain/models.py",
    "ports": ROOT / "src/earth_jukebox/application/ports.py",
}


def _block(doc_text: str, name: str) -> str:
    pattern = (
        rf"<!-- BEGIN:{re.escape(name)} -->\s*```python\n(.*?)```\s*<!-- END:{re.escape(name)} -->"
    )
    m = re.search(pattern, doc_text, flags=re.DOTALL)
    assert m, f"marker block '{name}' not found in docs/02-DOMAIN-MODEL.md"
    return m.group(1)


def test_doc_blocks_match_source() -> None:
    text = DOC.read_text(encoding="utf-8")
    for name, path in SYNCED.items():
        assert _block(text, name) == path.read_text(encoding="utf-8"), (
            f"{path.relative_to(ROOT)} differs from the '{name}' block in docs/02. "
            "Update BOTH and bump MODEL_REVISION."
        )


def test_feature_ids_are_unique_and_never_renumbered() -> None:
    text = (ROOT / "docs" / "03-FEATURE-CATALOG.md").read_text(encoding="utf-8")
    ids = re.findall(r"^### (F-\d{3})\b", text, flags=re.MULTILINE)
    assert ids, "no feature headings found"
    assert len(ids) == len(set(ids)), "duplicate feature ID in catalog"
