"""Audio and Score rendering / download endpoints (F-063, F-043, F-034)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from earth_jukebox.application.services import Services
from earth_jukebox.application.use_cases.audio_legend import legend_score
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.errors import InvalidLegendError, NotFoundError
from earth_jukebox.domain.models import Score, SonificationParams
from earth_jukebox.domain.skins.registry import get_skin
from earth_jukebox.domain.sonification.score_serde import score_to_dict
from earth_jukebox.presentation.api.dependencies import get_services

router = APIRouter(prefix="/api", tags=["render"])


def _build_score(
    analysis_id: str,
    skin_id: str,
    n_cols: int,
    services: Services,
) -> Score:
    if not 16 <= n_cols <= 128:
        raise InvalidLegendError("n_cols must be between 16 and 128")

    if services.analysis_store is None:
        raise NotFoundError("Analysis store service unavailable")

    field = services.analysis_store.load(analysis_id)
    skin = get_skin(skin_id)
    params = SonificationParams(n_cols=n_cols, skin_id=skin.id)
    return sonify(field, params)


@router.get("/render/{analysis_id}.wav")
def render_wav(
    analysis_id: str,
    services: Annotated[Services, Depends(get_services)],
    skin: Annotated[str, Query()] = "neutral",
    n_cols: Annotated[int, Query()] = 48,
) -> Response:
    """Render soundtrack to 44.1 kHz 16-bit PCM WAV (F-063, F-042)."""
    if services.audio_renderer is None:
        raise NotFoundError("Audio renderer service unavailable")

    score = _build_score(analysis_id, skin, n_cols, services)
    wav_bytes = services.audio_renderer.render_wav(score)

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'attachment; filename="earth_jukebox_{analysis_id}.wav"',
        },
    )


@router.get("/render/{analysis_id}.mid")
def render_midi(
    analysis_id: str,
    services: Annotated[Services, Depends(get_services)],
    skin: Annotated[str, Query()] = "neutral",
    n_cols: Annotated[int, Query()] = 48,
) -> Response:
    """Export soundtrack to standard MIDI file (F-063, F-043)."""
    if services.midi_exporter is None:
        raise NotFoundError("MIDI exporter service unavailable")

    score = _build_score(analysis_id, skin, n_cols, services)
    midi_bytes = services.midi_exporter.export_midi(score)

    return Response(
        content=midi_bytes,
        media_type="audio/midi",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'attachment; filename="earth_jukebox_{analysis_id}.mid"',
        },
    )


@router.get("/render/{analysis_id}.json")
def render_json(
    analysis_id: str,
    services: Annotated[Services, Depends(get_services)],
    skin: Annotated[str, Query()] = "neutral",
    n_cols: Annotated[int, Query()] = 48,
) -> JSONResponse:
    """Download Score intermediate representation JSON (F-063)."""
    score = _build_score(analysis_id, skin, n_cols, services)
    score_dict = score_to_dict(score)

    return JSONResponse(
        content=score_dict,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/render/{analysis_id}.mp3")
def render_mp3(
    analysis_id: str,
    services: Annotated[Services, Depends(get_services)],
    skin: Annotated[str, Query()] = "neutral",
    n_cols: Annotated[int, Query()] = 48,
) -> Response:
    """Render soundtrack to MP3 via ffmpeg if available on PATH (F-044)."""
    if services.audio_renderer is None:
        raise NotFoundError("Audio renderer service unavailable")

    if services.mp3_exporter is None or not services.mp3_exporter.is_available():
        raise StarletteHTTPException(
            status_code=501,
            detail="MP3 export is unavailable: ffmpeg is not installed on system PATH",
        )

    score = _build_score(analysis_id, skin, n_cols, services)
    wav_bytes = services.audio_renderer.render_wav(score)
    mp3_bytes = services.mp3_exporter.export_mp3(wav_bytes)

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'attachment; filename="earth_jukebox_{analysis_id}.mp3"',
        },
    )


@router.get("/legend-sound/{analysis_id}.wav")
def render_legend_wav(
    analysis_id: str,
    services: Annotated[Services, Depends(get_services)],
    skin: Annotated[str, Query()] = "neutral",
) -> Response:
    """Render 32-note audio legend sweep to WAV (F-063, F-034)."""
    if services.analysis_store is None or services.audio_renderer is None:
        raise NotFoundError("Required rendering services unavailable")

    field = services.analysis_store.load(analysis_id)
    skin_obj = get_skin(skin)
    score = legend_score(field.legend, skin_obj)
    wav_bytes = services.audio_renderer.render_wav(score)

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'attachment; filename="legend_{analysis_id}.wav"',
        },
    )
