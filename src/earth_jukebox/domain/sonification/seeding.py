"""F-031: Deterministic seeding & ornaments.

Per docs/06 §11:
seed = int(sha256(f"{source_hash}|{canonical_params_json}|{MAPPING_VERSION}").hexdigest()[:8], 16)
rng  = numpy.random.default_rng(seed)
canonical_params_json = SonificationParams as JSON with sorted keys.
If params.seed is not None it overrides.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.models import SonificationParams


def canonicalize_params(params: SonificationParams) -> str:
    """Return canonical JSON representation of SonificationParams with sorted keys."""
    data = {
        "n_bands": params.n_bands,
        "n_cols": params.n_cols,
        "seed": params.seed,
        "skin_id": params.skin_id,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_seed(source_hash: str, params: SonificationParams) -> int:
    """Compute deterministic integer seed for RNG."""
    if params.seed is not None:
        return params.seed

    params_json = canonicalize_params(params)
    key = f"{source_hash}|{params_json}|{MAPPING_VERSION}"
    hex_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(hex_digest[:8], 16)


def get_rng(seed: int) -> np.random.Generator:
    """Get seeded numpy Generator."""
    return np.random.default_rng(seed)
