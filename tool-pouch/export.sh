#!/usr/bin/env bash
# Render the pouch and clean the mesh (OpenSCAD 2021 leaves T-junctions between the shell layers).
set -e
cd "$(dirname "$0")"
mkdir -p out
openscad -o out/tool_pouch_raw.stl tool_pouch.scad
python3 - <<'PY'
import trimesh, pymeshfix
m = trimesh.load('out/tool_pouch_raw.stl', process=True)
mf = pymeshfix.MeshFix(m.vertices, m.faces)
mf.repair(joincomp=True, remove_smallest_components=True)
r = trimesh.Trimesh(mf.points, mf.faces, process=True)
assert r.is_watertight
r.export('out/tool_pouch.stl'); r.export('out/tool_pouch.3mf')
print('ok', len(r.faces), 'faces', round(r.volume/1000, 1), 'cm3')
PY
