"""Unit tests for F-033 (Mapping manifest)."""

from __future__ import annotations

import re
from pathlib import Path

from earth_jukebox.application.use_cases.mapping_manifest import describe_mapping
from earth_jukebox.domain.mapping_version import MAPPING_VERSION


def test_f033_ac_mapping_manifest_matches_doc06_table() -> None:
    # AC: contains mapping_version and every row of docs/06 §2 table; test fails if they diverge
    doc06_path = Path("docs/06-SONIFICATION-MAPPING-SPEC.md")
    assert doc06_path.exists()
    content = doc06_path.read_text(encoding="utf-8")

    # Extract table rows: | `key` | Data property | Sound parameter | Rule |
    matches = re.findall(r"^\|\s*`([^`]+)`\s*\|", content, flags=re.MULTILINE)
    assert len(matches) == 10, (
        f"Expected 10 rows in doc 06 §2 table, found {len(matches)}: {matches}"
    )

    expected_keys = set(matches)

    manifest = describe_mapping()
    assert manifest["mapping_version"] == MAPPING_VERSION

    # Check top-level or mappings dict
    mappings = manifest.get("mappings", manifest)
    for key in expected_keys:
        assert key in mappings, f"Manifest missing key '{key}' from doc 06 table"
        entry = mappings[key]
        assert "data_property" in entry
        assert "sound_parameter" in entry
        assert "rule" in entry

    # Verify key list asserted
    assert set(mappings.keys()) >= expected_keys
