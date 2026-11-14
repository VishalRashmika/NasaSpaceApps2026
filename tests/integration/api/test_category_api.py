"""Integration tests for category endpoints (F-107)."""

from __future__ import annotations

import urllib.parse

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app


def test_list_categories_endpoint() -> None:
    client = TestClient(build_app())
    res = client.get("/api/categories")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 6

    # Verify each category structure
    for cat in data:
        assert "id" in cat
        assert "title" in cat
        assert "description" in cat
        assert "has_legend" in cat
        assert "images" in cat
        assert "image_count" in cat
        assert cat["image_count"] == len(cat["images"])

        if cat["has_legend"]:
            assert cat["legend_url"] is not None
            assert cat["legend_url"].startswith("/api/categories/")
        else:
            assert cat["legend_url"] is None


def test_get_category_detail_endpoint() -> None:
    client = TestClient(build_app())
    encoded_id = urllib.parse.quote("Near-Surface-Temperature")
    res = client.get(f"/api/categories/{encoded_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == "Near-Surface-Temperature"
    assert "Temperature" in detail["title"]
    assert detail["has_legend"] is True
    assert detail["legend_url"] is not None
    assert detail["image_count"] >= 1
    assert "info_markdown" in detail
    assert len(detail["info_markdown"]) > 0


def test_get_category_legend_endpoint() -> None:
    client = TestClient(build_app())
    # Category with legend
    res = client.get("/api/categories/Near-Surface-Temperature/legend")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/")
    assert len(res.content) > 0

    # Category without legend returns 404
    res_no_legend = client.get("/api/categories/Hubble+IOTD/legend")
    assert res_no_legend.status_code == 404


def test_get_category_image_endpoint() -> None:
    client = TestClient(build_app())
    # Fetch categories first
    res = client.get("/api/categories")
    assert res.status_code == 200
    hubble_cat = next(c for c in res.json() if c["id"] == "Hubble+IOTD")
    assert len(hubble_cat["images"]) > 0

    first_image = hubble_cat["images"][0]["filename"]
    encoded_cat = urllib.parse.quote("Hubble+IOTD")
    encoded_img = urllib.parse.quote(first_image)

    img_res = client.get(f"/api/categories/{encoded_cat}/images/{encoded_img}")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"].startswith("image/")
    assert len(img_res.content) > 0

    # Traversal or invalid returns 404
    bad_res = client.get(f"/api/categories/{encoded_cat}/images/../../etc/passwd")
    assert bad_res.status_code in (404, 422)


def test_category_predefined_config_and_sound_mappings_endpoint() -> None:
    """F-108 AC1, AC3: Verify API returns predefined_config and sound_mappings."""
    client = TestClient(build_app())
    res = client.get("/api/categories")
    assert res.status_code == 200
    categories = res.json()

    for cat in categories:
        assert "predefined_config" in cat
        assert cat["predefined_config"] is not None
        cfg = cat["predefined_config"]
        assert "label" in cfg and len(cfg["label"]) > 0
        assert "units" in cfg
        assert "vmin" in cfg and "vmax" in cfg
        assert cfg["vmin"] < cfg["vmax"]
        assert "kind" in cfg
        assert "instrument_family" in cfg
        assert "sonification_technique" in cat and len(cat["sonification_technique"]) > 0
        assert "sound_mappings" in cat
        assert len(cat["sound_mappings"]) >= 4

    # Detailed view check
    encoded_id = urllib.parse.quote("Near-Surface-Temperature")
    detail_res = client.get(f"/api/categories/{encoded_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert (
        detail["predefined_config"]["label"] == "Near-Surface-Temperature (T2M)"
        or "Temperature" in detail["predefined_config"]["label"]
    )
    assert detail["predefined_config"]["vmin"] == -40.0
    assert detail["predefined_config"]["vmax"] == 40.0
    assert detail["predefined_config"]["instrument_family"] == "strings"
    assert "Thermal" in detail["sonification_technique"]


def test_all_categories_predefined_sonification_flow() -> None:
    """F-108 AC5: Verify predefined configuration from all categories drives analyze and sonify."""
    import io
    import json

    client = TestClient(build_app())
    res = client.get("/api/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 6

    for cat in categories:
        cfg = cat["predefined_config"]
        assert cfg is not None

        # Build legend JSON from predefined config
        legend_json = json.dumps(
            {
                "label": cfg["label"],
                "units": cfg["units"],
                "vmin": cfg["vmin"],
                "vmax": cfg["vmax"],
                "kind": cfg["kind"],
                "category": cfg["category"],
                "scale": cfg.get("scale", "linear"),
                "orientation": cfg.get("orientation", "horizontal"),
                "center": cfg.get("center"),
                "low_at_start": cfg.get("low_at_start", True),
            }
        )

        # Fetch first example image from category
        assert len(cat["images"]) > 0
        img_info = cat["images"][0]
        img_res = client.get(img_info["url"])
        assert img_res.status_code == 200

        # Submit to /api/analyze with predefined metadata and category_id
        files = {
            "image": (img_info["filename"], io.BytesIO(img_res.content), "image/jpeg"),
        }
        data = {
            "legend": legend_json,
            "category_id": cat["id"],
        }
        analyze_res = client.post("/api/analyze", data=data, files=files)
        assert analyze_res.status_code == 200, f"Analyze failed for {cat['id']}: {analyze_res.text}"
        analysis_data = analyze_res.json()
        assert "analysis_id" in analysis_data
        analysis_id = analysis_data["analysis_id"]

        # If category has legend, verify recovery mode used category preset LUT
        if cat["has_legend"]:
            assert analysis_data["quality"]["recovery_mode"] == "preset"
            assert analysis_data["quality"]["confidence"] > 0.10
        else:
            assert analysis_data["quality"]["recovery_mode"] == "luminance_fallback"

        # Submit to /api/sonify
        sonify_res = client.post(
            "/api/sonify", json={"analysis_id": analysis_id, "skin": "neutral"}
        )
        assert sonify_res.status_code == 200, f"Sonify failed for {cat['id']}: {sonify_res.text}"
        score = sonify_res.json()["score"]
        assert score["legend"]["category"] == cfg["category"]
        # Verify instrument matches the category's expected voice
        voices = score["voices"]
        band_voices = [v for v in voices if v["id"].startswith("band")]
        assert len(band_voices) > 0
        assert band_voices[0]["instrument"] == cfg["instrument_family"]


def test_custom_user_image_with_predefined_category_config() -> None:
    """F-108 AC5: Verify custom image analyzed with predefined category metadata."""
    import io
    import json

    from PIL import Image

    client = TestClient(build_app())

    # Create a custom synthetic user image
    custom_img = Image.new("RGB", (300, 200), color=(100, 150, 200))
    buf = io.BytesIO()
    custom_img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    # User chose Near-Surface-Temperature category, so predefined config is used
    res = client.get("/api/categories")
    assert res.status_code == 200
    temp_cat = next(c for c in res.json() if "temp" in c["id"].lower())
    cfg = temp_cat["predefined_config"]

    legend_json = json.dumps(
        {
            "label": cfg["label"],
            "units": cfg["units"],
            "vmin": cfg["vmin"],
            "vmax": cfg["vmax"],
            "kind": cfg["kind"],
            "category": cfg["category"],
            "center": cfg["center"],
        }
    )

    files = {
        "image": ("user_custom_map.png", io.BytesIO(raw_bytes), "image/png"),
    }
    data = {
        "legend": legend_json,
    }
    analyze_res = client.post("/api/analyze", data=data, files=files)
    assert analyze_res.status_code == 200
    analysis_id = analyze_res.json()["analysis_id"]

    sonify_res = client.post("/api/sonify", json={"analysis_id": analysis_id, "skin": "neutral"})
    assert sonify_res.status_code == 200
    score = sonify_res.json()["score"]
    assert score["legend"]["category"] == "temperature"
    assert score["voices"][0]["instrument"] == "strings"


def test_all_categories_custom_user_image_flow() -> None:
    """F-108 AC5: Verify custom user image works for every dataset category."""
    import io
    import json

    from PIL import Image

    client = TestClient(build_app())

    # Create synthetic user-uploaded map
    custom_img = Image.new("RGB", (250, 150), color=(110, 90, 180))
    buf = io.BytesIO()
    custom_img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    res = client.get("/api/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 6

    for cat in categories:
        cfg = cat["predefined_config"]
        assert cfg is not None

        legend_json = json.dumps(
            {
                "label": cfg["label"],
                "units": cfg["units"],
                "vmin": cfg["vmin"],
                "vmax": cfg["vmax"],
                "kind": cfg["kind"],
                "category": cfg["category"],
                "scale": cfg.get("scale", "linear"),
                "orientation": cfg.get("orientation", "horizontal"),
                "center": cfg.get("center"),
                "low_at_start": cfg.get("low_at_start", True),
            }
        )

        files = {
            "image": (f"user_{cat['id']}.png", io.BytesIO(raw_bytes), "image/png"),
        }
        data = {
            "legend": legend_json,
        }
        analyze_res = client.post("/api/analyze", data=data, files=files)
        assert analyze_res.status_code == 200, f"Analyze failed for custom image {cat['id']}"
        analysis_id = analyze_res.json()["analysis_id"]

        sonify_res = client.post(
            "/api/sonify", json={"analysis_id": analysis_id, "skin": "neutral"}
        )
        assert sonify_res.status_code == 200, f"Sonify failed for custom image {cat['id']}"
        score = sonify_res.json()["score"]
        assert score["legend"]["category"] == cfg["category"]
        assert score["voices"][0]["instrument"] == cfg["instrument_family"]
        assert len(score["notes"]) > 0


def test_category_legend_preset_inversion_accuracy() -> None:
    """F-108: Category legend inversion achieves high confidence and scalar range."""
    import io
    import json

    client = TestClient(build_app())

    # 1. Temperature
    temp_url = (
        "/api/categories/Near-Surface-Temperature/images/"
        "MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg"
    )
    temp_img_res = client.get(temp_url)
    assert temp_img_res.status_code == 200
    temp_legend = json.dumps(
        {
            "label": "Near-Surface Temperature (T2M)",
            "units": "°C",
            "vmin": -40.0,
            "vmax": 40.0,
            "kind": "diverging",
            "category": "temperature",
            "center": 0.0,
            "scale": "linear",
        }
    )
    files = {"image": ("temp.jpg", io.BytesIO(temp_img_res.content), "image/jpeg")}
    data = {"legend": temp_legend, "category_id": "Near-Surface-Temperature"}
    res = client.post("/api/analyze", data=data, files=files)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["quality"]["recovery_mode"] == "preset"
    assert res_data["quality"]["confidence"] >= 0.80
    assert res_data["quality"]["mean_delta_e"] < 2.5
    grid = res_data["grid"]
    assert grid["min"] >= -40.0
    assert grid["max"] <= 40.0

    # 2. Wind Speed
    wind_url = (
        "/api/categories/Near-Surface-Wind-Speed/images/"
        "MC02_stage3_GMAO_near_surface_wind_2048x1024_en.00001_print.jpg"
    )
    wind_img_res = client.get(wind_url)
    assert wind_img_res.status_code == 200
    wind_legend = json.dumps(
        {
            "label": "Near-Surface Wind Speed",
            "units": "m/s",
            "vmin": 0.0,
            "vmax": 40.0,
            "kind": "sequential",
            "category": "ocean",
            "scale": "linear",
        }
    )
    files = {"image": ("wind.jpg", io.BytesIO(wind_img_res.content), "image/jpeg")}
    data = {"legend": wind_legend, "category_id": "Near-Surface-Wind-Speed"}
    res = client.post("/api/analyze", data=data, files=files)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["quality"]["recovery_mode"] == "preset"
    assert res_data["grid"]["min"] >= 0.0
    assert res_data["grid"]["max"] <= 40.0

    # 3. Lightning without legend uses fallback without error
    light_res = client.get("/api/categories/lightningEvents")
    assert light_res.status_code == 200
    light_cat = light_res.json()
    first_light_img = light_cat["images"][0]["url"]
    light_img_bytes = client.get(first_light_img).content
    light_legend = json.dumps(
        {
            "label": "Lightning Events",
            "units": "flashes/area",
            "vmin": 0.0,
            "vmax": 1.0,
            "kind": "sequential",
            "category": "precipitation",
        }
    )
    files = {"image": ("light.jpg", io.BytesIO(light_img_bytes), "image/jpeg")}
    data = {"legend": light_legend, "category_id": "lightningEvents"}
    res = client.post("/api/analyze", data=data, files=files)
    assert res.status_code == 200
    assert res.json()["quality"]["recovery_mode"] == "luminance_fallback"
