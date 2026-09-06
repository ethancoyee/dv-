# Thigh tool pouch (Bambu Lab P1S)

Parametric OpenSCAD model of a belt-hung pouch that wraps the outside of the thigh and holds six tools in two rows.

## Files

| File | What it is |
|------|------------|
| `tool_pouch.scad` | The model. Every dimension is a named parameter at the top of the file. |
| `out/tool_pouch.stl` | Ready to slice, millimetres, right thigh, already in print orientation. |
| `out/tool_pouch.3mf` | Same model as 3MF for Bambu Studio. |
| `previews/*.png` | Renders, and renders with translucent tool stand-ins. |
| `fix_tjunctions.py` | Makes the OpenSCAD export watertight (used by `export.sh`). |
| `export.sh` | Re-renders the STL/3MF from the .scad and cleans the mesh. |

## Layout (right thigh, as worn)

Back row, against the leg, from the back of the thigh toward the front:

1. Torpedo level. Pocket is symmetric, so put the screw end whichever way you asked for.
2. 9/16 x 11/16 ratcheting wrench, big end down.
3. 3/8 x 7/16 ratcheting wrench, big end down.
4. 11-in-1 driver, in its own round housing at the front. The shaft drops into a bore and the yellow collar and green band sink into a 34 mm counterbore, so the deck comes right up to the rubber handle. The shaft bottoms out before the handle can.

Front row, on the outside, rims 18 mm lower than the back row, starting just behind the driver housing and running toward the back:

5. Milwaukee 6-in-1 strippers, nose down.
6. Knipex Cobra, nose down.

Each row is one flat deck with the pocket mouths flush in it, and every mouth has a lead-in chamfer. The grooves between pockets are filled so the outside is one smooth surface with nothing to catch on. The front two pockets still taper to match the pliers, so the outside narrows toward the bottom. The back of the pouch is a concave arc that matches the leg.

## Pocket sizes

| Pocket | Opening (W x T) | Depth | Tool exposed |
|--------|-----------------|-------|--------------|
| Level | 36 x 25 mm | 100 mm | ~65 mm |
| Big wrench | 38 x 19 mm | 100 mm | ~110 mm |
| Small wrench | 30 x 16 mm | 100 mm | ~65 mm |
| Driver | 20 mm bore, 34 mm counterbore 32 mm deep | 124 mm | rubber handle only |
| Strippers | 48 x 18 mm at rim, 20 mm wide at floor | 95 mm | ~110 mm |
| Cobra | 50 x 14 mm at rim, 22 mm wide at floor | 95 mm | ~85 mm |

Each pocket has 4 mm of width clearance and 3 mm of thickness clearance over the measured tool, and a 6 mm drain hole in the floor.

## Belt loop

Sized for a 1-1/2 in wide, 1/8 in thick belt. The slot is 42 mm tall with a 7.2 mm gap so the belt threads easily. The loop is 84 mm wide and sits centred on the pouch. The top bridge is chamfered at 45 degrees so it prints without support. Below the loop, the strap face blends into the back of the pouch through a 36 mm S-shaped ramp (`ramp_h`), so there is no edge against the leg. The top edge of the strap is rounded.

## Overall size

| | |
|---|---|
| Height including belt tab | 195 mm |
| Chord across the outside | ~194 mm |
| Wrap around the leg | ~93 degrees |
| Leg circumference it is curved for | 22 in (parameter `thigh_circ_in`) |

## Printing

- Orientation: as exported, pocket openings up. No supports needed.
- Material: PETG is the best fit for a pouch that gets knocked around. ASA also works. PLA will crack at the belt loop over time.
- Layer height 0.2 mm. 4 walls, 5 top and bottom layers, 20 to 30 percent gyroid infill. The thick floor under the back row is solid in the model and becomes infill in the slicer.
- A brim is optional. The footprint is a curved band, so it stands well on its own.

## Changing things

Open `tool_pouch.scad` and edit the parameter block at the top:

- `side = "left"` mirrors the whole pouch for the other leg.
- `thigh_circ_in` changes the curve of the back.
- `belt_w`, `belt_t` resize the belt slot.
- `front_drop` sets how much lower the front deck sits.
- `driver_shaft` is collar face to bit tip, `collar_len` is the collar plus green band up to the rubber. The deck top lands 1 mm above the green band.
- `blend_r` is the smoothing radius. Lower it (7 or so) to get the scalloped look back.
- The `back` and `front` tables hold each pocket's width, thickness, depth, and taper.
- `band_h = 4` gives a fast preview. Set it back to 1 before exporting.
- `show_tools = true` draws translucent stand-ins for the tools in preview mode.

Export with:

```
openscad -o out/tool_pouch.stl tool_pouch.scad
```
