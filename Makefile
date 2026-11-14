.PHONY: install lint types arch test web-test check run vendor-tone fmt

PY ?= python

install:
	$(PY) -m pip install -e ".[dev]"

fmt:
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

types:
	$(PY) -m mypy

# Layering guardrail: import-linter contracts + docs/code sync + frontend layering
arch:
	lint-imports
	$(PY) -m pytest tests/architecture -q

test:
	$(PY) -m pytest tests/unit tests/integration -q

web-test:
	node --test web/tests/*.test.mjs

# THE definition of "green". Run before declaring any feature done.
check: lint types arch test web-test

run:
	$(PY) -m earth_jukebox

# Re-vendor Tone.js into web/vendor (needs network; version pinned in web/vendor/VERSION)
vendor-tone:
	sh scripts/vendor_tone.sh
