// API client: the only place in the frontend that calls fetch().

async function _handleResponse(res) {
  if (!res.ok) {
    let detail = `Request failed: ${res.status} ${res.statusText}`;
    let code = "http_error";
    let problem = null;
    try {
      problem = await res.json();
      if (problem && problem.detail) {
        detail = problem.detail;
      }
      if (problem && problem.code) {
        code = problem.code;
      }
    } catch {
      // Not JSON problem response
    }
    const err = new Error(detail);
    err.status = res.status;
    err.code = code;
    err.problem = problem;
    throw err;
  }
  return res.json();
}

export async function getHealth() {
  const r = await fetch("/api/health");
  return _handleResponse(r);
}

export async function getMapping() {
  const r = await fetch("/api/mapping");
  return _handleResponse(r);
}

export async function getSkins() {
  const r = await fetch("/api/skins");
  return _handleResponse(r);
}

export async function getColormaps() {
  const r = await fetch("/api/colormaps");
  return _handleResponse(r);
}

export async function getSamples() {
  const r = await fetch("/api/samples");
  return _handleResponse(r);
}

export async function getSample(id) {
  const r = await fetch(`/api/samples/${encodeURIComponent(id)}`);
  return _handleResponse(r);
}

export function getSampleImageUrl(id) {
  return `/api/samples/${encodeURIComponent(id)}/image`;
}

export async function analyzeSample(id, signal) {
  const r = await fetch(`/api/samples/${encodeURIComponent(id)}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
    signal,
  });
  return _handleResponse(r);
}

export async function detectColorbar(imageBlob, signal) {
  const fd = new FormData();
  fd.append("image", imageBlob);
  const r = await fetch("/api/detect-colorbar", {
    method: "POST",
    body: fd,
    signal,
  });
  return _handleResponse(r);
}

export async function analyzeImage(
  { imageBlob, legend, colorbarBox, mapBox, preset, extent, categoryId },
  signal
) {
  const fd = new FormData();
  fd.append("image", imageBlob);
  fd.append("legend", JSON.stringify(legend));

  if (categoryId) {
    fd.append("category_id", categoryId);
  }
  if (colorbarBox) {
    fd.append("colorbar_box", JSON.stringify(colorbarBox));
  }
  if (mapBox) {
    fd.append("map_box", JSON.stringify(mapBox));
  }
  if (preset) {
    fd.append("preset", preset);
  }
  if (extent) {
    fd.append("extent", JSON.stringify(extent));
  }

  const r = await fetch("/api/analyze", {
    method: "POST",
    body: fd,
    signal,
  });
  return _handleResponse(r);
}

export async function sonify({ analysisId, skin = "neutral", nCols = 48 }, signal) {
  const r = await fetch("/api/sonify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysis_id: analysisId,
      skin,
      n_cols: nCols,
    }),
    signal,
  });
  return _handleResponse(r);
}

export function getRenderUrl(analysisId, ext = "wav", skin = "neutral", nCols = 48) {
  return `/api/render/${encodeURIComponent(analysisId)}.${ext}?skin=${encodeURIComponent(skin)}&n_cols=${encodeURIComponent(nCols)}`;
}

export function getLegendSoundUrl(analysisId, skin = "neutral") {
  return `/api/legend-sound/${encodeURIComponent(analysisId)}.wav?skin=${encodeURIComponent(skin)}`;
}

export async function getCategories(signal) {
  const r = await fetch("/api/categories", { signal });
  return _handleResponse(r);
}

export async function getCategory(id, signal) {
  const r = await fetch(`/api/categories/${encodeURIComponent(id)}`, { signal });
  return _handleResponse(r);
}

export function getCategoryLegendUrl(id) {
  return `/api/categories/${encodeURIComponent(id)}/legend`;
}

export function getCategoryImageUrl(id, filename) {
  return `/api/categories/${encodeURIComponent(id)}/images/${encodeURIComponent(filename)}`;
}

export async function fetchCategoryImageBlob(id, filename, signal) {
  const url = getCategoryImageUrl(id, filename);
  const r = await fetch(url, { signal });
  if (!r.ok) {
    throw new Error(`Failed to fetch image: ${r.status}`);
  }
  return r.blob();
}

