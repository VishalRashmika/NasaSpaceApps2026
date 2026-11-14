"""Integration tests for Phase 6 Web MVP static asset delivery."""

from __future__ import annotations

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app


def test_web_mvp_assets_served() -> None:
    client = TestClient(build_app())

    # 1. Shell index.html
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Earth Jukebox" in r.text
    assert 'id="map-canvas"' in r.text
    assert 'id="btn-play"' in r.text
    assert 'id="btn-explore"' in r.text
    assert 'id="toggle-haptics"' in r.text
    assert 'id="explore-live"' in r.text
    assert 'id="fid-legend-r"' in r.text
    assert 'id="tab-gallery"' in r.text

    # 2. CSS stylesheet
    r_css = client.get("/css/app.css")
    assert r_css.status_code == 200
    assert "text/css" in r_css.headers["content-type"]
    assert "--accent" in r_css.text
    assert ".box-explore" in r_css.text

    # 3. Main JS and modules
    r_main = client.get("/js/main.js")
    assert r_main.status_code == 200
    assert "javascript" in r_main.headers["content-type"]

    r_core = client.get("/js/core/schedule.js")
    assert r_core.status_code == 200
    assert "scoreToTriggers" in r_core.text

    r_explore = client.get("/js/ui/explore.js")
    assert r_explore.status_code == 200
    assert "ExploreUI" in r_explore.text

    r_audio = client.get("/js/audio/engine.js")
    assert r_audio.status_code == 200
    assert "AudioEngine" in r_audio.text

    # 4. Vendored Tone.js
    r_tone = client.get("/vendor/Tone.js")
    assert r_tone.status_code == 200
    assert len(r_tone.content) > 100_000
