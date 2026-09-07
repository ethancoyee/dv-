# Thigh tool pouch (Bambu Lab P1S)

Parametric OpenSCAD model of a belt-hung pouch that wraps the outside of the thigh and holds six tools in two rows.

## Files

| File | What it is |
|------|------------|
| `tool_pouch.scad` | The model. Every dimension is a named parameter at the top of the file. |
| `out/tool_pouch.stl` | Ready to slice, millimetres, right thigh, already in print orientation. |
| `out/tool_pouch.3mf` | Same model as 3MF for Bambu Studio. |
| `out/tool_pouch_blender.stl` | Same model moved to the origin, for editing in Blender. |
| `previews/*.png` | Renders, and renders with translucent tool stand-ins. |
| `fix_tjunctions.py` | Makes the OpenSCAD export watertight (used by `export.sh`). |
| `export.sh` | Re-renders the STL/3MF from the .scad and cleans the mesh. |

## Layout (right thigh, as worn)

Five columns along the leg, from the back of the thigh toward the front:

1. Torpedo level against the leg, with the Knipex Cobra in front of it. Pocket is symmetric, so put the screw end whichever way you asked for.
2. 9/16 x 11/16 ratcheting wrench, edge-on (flat face across the leg), big end down.
3. 3/8 x 7/16 ratcheting wrench, edge-on, big end down.
4. 11-in-1 driver against the leg in a round housing, with the Milwaukee 6-in-1 strippers in front of it.

Level, wrenches, and driver open on the upper deck. Strippers and Cobra open on a deck 18 mm lower. A sloped deck runs from the driver housing outward down to the strippers so the housing doesn't stand up abruptly.

The driver is held at three points: the bit tip in an 8.5 mm pilot hole, the 5/8 in flip socket in a snug 18 mm bore, and the 1-1/16 in yellow collar in a 30 mm counterbore. The socket's shoulder rests on the 45-degree step above the pilot, so the bit tip carries no weight, and the deck comes right up to the rubber handle with the collar and green band inside.

Every pocket mouth has a lead-in chamfer. The grooves between pockets are filled so the outside is one smooth surface with nothing to catch on. The two pliers pockets still taper to match the tools. The back of the pouch is a concave arc that matches the leg.

## Pocket sizes

| Pocket | Opening (W x T) | Depth | Tool exposed |
|--------|-----------------|-------|--------------|
| Level | 36 x 25 mm | 100 mm | ~65 mm |
| Big wrench, edge-on | 19 x 38 mm | 100 mm | ~110 mm |
| Small wrench, edge-on | 16 x 30 mm | 100 mm | ~65 mm |
| Driver | 8.5 mm pilot, 18 mm bore, 30 mm counterbore 33 mm deep | 127 mm | rubber handle only |
| Strippers | 48 x 18 mm at rim, 20 mm wide at floor | 95 mm | ~110 mm |
| Cobra | 50 x 14 mm at rim, 22 mm wide at floor | 95 mm | ~85 mm |

Each pocket has 4 mm of width clearance and 3 mm of thickness clearance over the measured tool. Every mouth has a 2 mm 45-degree lead-in chamfer, and the driver's counterbore floor funnels at 45 degrees into the shaft bore so the flip socket self-centres. Drain holes are 4 mm (3 mm under the driver), smaller than a 1/4 in hex bit. Walls between pockets are 5 mm, which leaves a 1 mm flat between the two chamfers on top of each divider.

## Belt loop

Sized for a 1-1/2 in wide, 1/8 in thick belt with room to spare: the slot is 44 mm (1-3/4 in) tall with a 7.2 mm (9/32 in) gap. The four vertical edges of the strap and the slot floor at each end have 2 mm 45-degree chamfers so the belt feeds in without catching. The loop is 84 mm wide and sits centred on the pouch. The top bridge is chamfered at 45 degrees so it prints without support. Below the loop, the strap face blends into the back of the pouch through a 36 mm S-shaped ramp (`ramp_h`), so there is no edge against the leg. The top edge of the strap is rounded.

## Overall size

| | |
|---|---|
| Height including belt tab | 199 mm |
| Chord across the outside | ~176 mm |
| Wrap around the leg | ~68 degrees |
| Thickest point off the leg | ~60 mm at the strippers, ~50 mm at the Cobra |
| Leg circumference it is curved for | 24 in (parameter `thigh_circ_in`) |

## Printing

- Orientation: as exported, pocket openings up. No supports needed.
- Material: PETG is the best fit for a pouch that gets knocked around. ASA also works. PLA will crack at the belt loop over time.
- Layer height 0.2 mm. 4 walls, 5 top and bottom layers, 20 to 30 percent gyroid infill. The thick floor under the back row is solid in the model and becomes infill in the slicer.
- A brim is optional. The footprint is a curved band, so it stands well on its own.

## Changing things

Open `tool_pouch.scad` and edit the parameter block at the top:

- `side = "left"` mirrors the whole pouch for the other leg.
- `thigh_circ_in` changes the curve of the back.
- `belt_w`, `belt_t` are the belt; `belt_extra_w`, `belt_extra_t` are the slack added to the slot; `belt_chamfer` is the entry chamfer.
- `front_drop` sets how much lower the front deck sits.
- `driver_shaft` is collar face to bit tip, `collar_len` is the collar plus green band up to the rubber, `socket_d` and `bit_len` size the snug bore and pilot. The deck top lands about 1 mm above the green band.
- `blend_r` is the smoothing radius. Lower it (7 or so) to get the scalloped look back.
- The `cells` table holds each pocket: which column it is in, how far off the leg it sits, width, thickness, deck, floor, and taper. Column spacing is computed from the pockets, so changing a size moves everything else to keep 3 mm walls.
- `driver_ramp` sets how far the sloped deck runs from the driver housing toward the strippers.
- `band_h = 4` gives a fast preview. Set it back to 1 before exporting.
- `show_tools = true` draws translucent stand-ins for the tools in preview mode.

Export with:

```
openscad -o out/tool_pouch.stl tool_pouch.scad
```
