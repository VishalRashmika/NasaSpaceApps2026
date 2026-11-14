#!/bin/sh
# Vendors Tone.js (pinned) into web/vendor so the app works offline. Requires npm + network.
set -e
VERSION="$(cat web/vendor/VERSION)"
TMP="$(mktemp -d)"
( cd "$TMP" && npm pack "tone@$VERSION" --silent && tar xzf tone-*.tgz )
cp "$TMP/package/build/Tone.js" web/vendor/Tone.js
echo "Vendored Tone.js $VERSION"
