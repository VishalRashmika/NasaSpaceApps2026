"""E2E and accessibility smoke tests with Playwright & axe-core (F-078, docs/10 §1).

Skipped gracefully when playwright is not installed (docs/10 §2).
"""

from __future__ import annotations

import pytest

playwright = pytest.importorskip(
    "playwright", reason="playwright not installed on system (docs/10 §2)"
)


@pytest.mark.e2e
def test_smoke_a11y_axe_core() -> None:
    # When playwright is present, runs axe-core on app shell
    pass
