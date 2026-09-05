#!/usr/bin/env bash
# Render the pouch and make the mesh watertight (OpenSCAD 2021 leaves T-junctions between shell layers).
set -e
cd "$(dirname "$0")"
mkdir -p out
openscad -o out/tool_pouch_raw.stl tool_pouch.scad
python3 fix_tjunctions.py out/tool_pouch_raw.stl out/tool_pouch.stl out/tool_pouch.3mf
rm -f out/tool_pouch_raw.stl
