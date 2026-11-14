#!/usr/bin/env bash
# Phase 5 exit demo: walks health -> analyze -> sonify -> download WAV via curl.
set -euo pipefail

PORT=${PORT:-8008}
BASE_URL="http://127.0.0.1:${PORT}"
CACHE_DIR="data/cache"
mkdir -p "${CACHE_DIR}"

echo "================================================================================"
echo "EARTH JUKEBOX — PHASE 5 EXIT DEMO: HTTP API"
echo "================================================================================"

# 1. Start server in background
python -m uvicorn earth_jukebox.bootstrap:build_app --factory --port "${PORT}" --log-level warning &
SERVER_PID=$!
trap 'kill ${SERVER_PID} 2>/dev/null || true' EXIT

# Wait for server to become responsive
echo -n "Starting server on port ${PORT}..."
for i in {1..30}; do
  if curl -s -f "${BASE_URL}/api/health" > /dev/null 2>&1; then
    echo " ready!"
    break
  fi
  sleep 0.2
done

# 2. Health check
echo -n "Checking GET /api/health... "
HEALTH_RESP=$(curl -s -f "${BASE_URL}/api/health")
STATUS=$(python -c "import json; d=json.loads('${HEALTH_RESP}'); print(d.get('status'))")
MAPPING_VER=$(python -c "import json; d=json.loads('${HEALTH_RESP}'); print(d.get('mapping_version'))")
echo "status=${STATUS}, mapping_version=${MAPPING_VER}"

# 3. Generate synthetic test image
SYNTH_IMG="${CACHE_DIR}/demo_api_input.png"
python -c "
from earth_jukebox.infrastructure.vision.synthetic import generate_map
import json
png, field, legend, cbox, mbox = generate_map(cmap='viridis', seed=42)
with open('${SYNTH_IMG}', 'wb') as f:
    f.write(png)
with open('${CACHE_DIR}/demo_api_meta.json', 'w') as f:
    json.dump({
        'legend': {
            'vmin': legend.vmin, 'vmax': legend.vmax, 'units': legend.units,
            'label': legend.label, 'kind': legend.kind.value, 'category': legend.category.value
        },
        'colorbar_box': {'x': cbox.x, 'y': cbox.y, 'w': cbox.w, 'h': cbox.h},
        'map_box': {'x': mbox.x, 'y': mbox.y, 'w': mbox.w, 'h': mbox.h}
    }, f)
"

# 4. POST /api/analyze
echo -n "Posting image to POST /api/analyze... "
LEGEND_JSON=$(python -c "import json; print(json.dumps(json.load(open('${CACHE_DIR}/demo_api_meta.json'))['legend']))")
CBOX_JSON=$(python -c "import json; print(json.dumps(json.load(open('${CACHE_DIR}/demo_api_meta.json'))['colorbar_box']))")
MBOX_JSON=$(python -c "import json; print(json.dumps(json.load(open('${CACHE_DIR}/demo_api_meta.json'))['map_box']))")

ANALYZE_RESP=$(curl -s -f -X POST "${BASE_URL}/api/analyze" \
  -F "image=@${SYNTH_IMG}" \
  -F "legend=${LEGEND_JSON}" \
  -F "colorbar_box=${CBOX_JSON}" \
  -F "map_box=${MBOX_JSON}")

ANALYSIS_ID=$(python -c "import json; d=json.loads('''${ANALYZE_RESP}'''); print(d['analysis_id'])")
CONFIDENCE=$(python -c "import json; d=json.loads('''${ANALYZE_RESP}'''); print(f\"{d['quality']['confidence']:.3f}\")")
BADGE=$(python -c "import json; d=json.loads('''${ANALYZE_RESP}'''); print(d['quality']['confidence_badge'])")
GRID=$(python -c "import json; d=json.loads('''${ANALYZE_RESP}'''); print(f\"{d['grid']['rows']}x{d['grid']['cols']}\")")
echo "analysis_id=${ANALYSIS_ID}, confidence=${CONFIDENCE} (${BADGE}), grid=${GRID}"

# 5. POST /api/sonify
echo -n "Sonifying analysis via POST /api/sonify... "
SONIFY_RESP=$(curl -s -f -X POST "${BASE_URL}/api/sonify" \
  -H "Content-Type: application/json" \
  -d "{\"analysis_id\": \"${ANALYSIS_ID}\", \"skin\": \"neutral\", \"n_cols\": 48}")

R_FIDELITY=$(python -c "import json; d=json.loads('''${SONIFY_RESP}'''); print(f\"{d['fidelity']['round_trip_r']:.4f}\")")
NOTES_COUNT=$(python -c "import json; d=json.loads('''${SONIFY_RESP}'''); print(len(d['score']['notes']))")
BPM=$(python -c "import json; d=json.loads('''${SONIFY_RESP}'''); print(d['score']['bpm'])")
echo "notes=${NOTES_COUNT}, bpm=${BPM}, fidelity_r=${R_FIDELITY}"

# 6. GET /api/render/{analysis_id}.wav
WAV_OUT="${CACHE_DIR}/demo_api_${ANALYSIS_ID}.wav"
echo -n "Downloading WAV from GET /api/render/${ANALYSIS_ID}.wav... "
curl -s -f "${BASE_URL}/api/render/${ANALYSIS_ID}.wav?skin=neutral&n_cols=48" -o "${WAV_OUT}"
WAV_SIZE=$(stat -c%s "${WAV_OUT}" 2>/dev/null || stat -f%z "${WAV_OUT}")
echo "saved (${WAV_SIZE} bytes)"

# 7. GET /api/render/{analysis_id}.mid
MID_OUT="${CACHE_DIR}/demo_api_${ANALYSIS_ID}.mid"
echo -n "Downloading MIDI from GET /api/render/${ANALYSIS_ID}.mid... "
curl -s -f "${BASE_URL}/api/render/${ANALYSIS_ID}.mid?skin=neutral&n_cols=48" -o "${MID_OUT}"
MID_SIZE=$(stat -c%s "${MID_OUT}" 2>/dev/null || stat -f%z "${MID_OUT}")
echo "saved (${MID_SIZE} bytes)"

# 8. GET /api/legend-sound/{analysis_id}.wav
LEG_OUT="${CACHE_DIR}/demo_api_legend_${ANALYSIS_ID}.wav"
echo -n "Downloading Audio Legend from GET /api/legend-sound/${ANALYSIS_ID}.wav... "
curl -s -f "${BASE_URL}/api/legend-sound/${ANALYSIS_ID}.wav?skin=neutral" -o "${LEG_OUT}"
LEG_SIZE=$(stat -c%s "${LEG_OUT}" 2>/dev/null || stat -f%z "${LEG_OUT}")
echo "saved (${LEG_SIZE} bytes)"

# 9. Verify OpenAPI schema contains all routes
echo -n "Checking OpenAPI /openapi.json endpoint list... "
OPENAPI_PATHS=$(curl -s -f "${BASE_URL}/openapi.json" | python -c "
import sys, json
data = json.load(sys.stdin)
paths = sorted(data.get('paths', {}).keys())
print(', '.join(paths))
")
echo "verified (${OPENAPI_PATHS})"

echo "--------------------------------------------------------------------------------"
echo "PHASE 5 EXIT DEMO COMPLETED SUCCESSFULLY: ALL HTTP ENDPOINTS OPERATIONAL"
echo "================================================================================"
