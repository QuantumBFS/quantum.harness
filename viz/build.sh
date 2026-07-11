#!/bin/sh
# Developer-only build: bundles viz/src → viz/dist/lattix.min.js (committed),
# runs the unit tests, and regenerates the example scenes + preview page.
set -e
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
npx esbuild src/main.js --bundle --minify --format=iife \
  --global-name=Lattix --outfile=dist/lattix.min.js
node --test test.js
python3 examples/generate.py
wc -c dist/lattix.min.js
