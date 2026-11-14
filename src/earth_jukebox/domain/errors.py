"""Domain errors. The presentation layer maps these to HTTP problem responses."""

from __future__ import annotations


class JukeboxError(Exception):
    """Base class. `code` is a stable machine-readable string used by the API."""

    code = "jukebox_error"


class InvalidImageError(JukeboxError):
    code = "invalid_image"


class InvalidLegendError(JukeboxError):
    code = "invalid_legend"


class RecoveryError(JukeboxError):
    code = "recovery_failed"


class NotFoundError(JukeboxError):
    code = "not_found"
