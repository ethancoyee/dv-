// =====================================================================
//  Thigh tool pouch  –  parametric OpenSCAD model  (all units mm)
//
//  Worn on a belt, hanging on the outside of the thigh.  Columns along
//  the leg, rear -> front:
//      [level against the leg, Knipex Cobra in front of it]
//      [9/16x11/16 ratchet wrench, edge-on]
//      [3/8x7/16 ratchet wrench, edge-on]
//      [11-in-1 driver against the leg, Milwaukee 6-in-1 strippers in front of it]
//
//  Level, wrenches and driver open on the upper deck; strippers and Cobra
//  open on a deck front_drop lower.  A sloped deck runs from the driver
//  housing outward down to the strippers.  The outside is one smooth shell.
//
//  Print: standing up, pocket openings toward +Z, no supports needed.
//  Tested for a Bambu Lab P1S bed (256 x 256 x 256).
// =====================================================================

// ---------------- user parameters ------------------------------------
side          = "right";   // "right" or "left" thigh  (left = mirror image)
thigh_circ_in = 22;        // circumference of the leg where the pouch sits (inches)
belt_w        = 38.1;      // 1-1/2" belt
belt_t        = 3.2;       // 1/8" belt
belt_extra_w  = 4;         // slot is belt_w + this
belt_extra_t  = 4;         // slot gap is belt_t + this  (easy to thread)

wall          = 3;         // wall between pockets
wall_out      = 4;         // outside wall
wall_back     = 4.5;       // wall against the leg
floor_t       = 4;         // floor under the deepest pocket
rim_round     = 2;         // chamfer on the outside edge of each deck
mouth_chamfer = 1.5;       // lead-in chamfer on every pocket mouth
base_chamfer  = 3;         // chamfer on the bottom edge
deck_back     = 100;       // height of the upper deck above the level/wrench floor
front_drop    = 18;        // lower deck (strippers, Cobra) sits this much lower
clear_w       = 4;         // total width clearance added to each tool
clear_t       = 3;         // total thickness clearance added to each tool
blend_r       = 40;        // closing radius: fills every groove smaller than ~2x this
band_h        = 1;         // layer height of the sculpted shell (1 = final, 4 = fast preview)
show_tools    = false;     // draw the tools in place (preview only)
pouch_color   = [0.30, 0.34, 0.40];   // preview colour of the pouch (alpha < 1 shows what is inside)

// driver (11-in-1) fit
driver_shaft  = 98;        // yellow collar face to bit tip (from photo)
collar_len    = 25;        // yellow collar + green band, up to where the rubber handle starts (from photo)
driver_handle = 31;        // yellow collar diameter (from photo, ~1.2 in)
handle_in     = collar_len + 1;   // deck top sits 1 mm above the green band, right at the rubber
cb_extra      = 6;         // counterbore is this much deeper than handle_in (shaft bottoms first)
bottom_extra  = 6;         // extra floor under everything so the driver bore fits
driver_ramp   = 48;        // how far the sloped deck runs from the driver housing toward the strippers

$fn = 40;

// ---------------- tool sizes (measured from photos) ------------------
// level: 165 long, 32 wide, ~22 thick        -> pocket 36 x 25
// big wrench: 210 long, 11/16 head ~34 dia, 16 thick -> edge-on 19 wide x 38 deep
// small wrench: 165 long, 7/16 head ~26 dia, 13 thick -> edge-on 16 wide x 30 deep
// driver: shaft + flip socket + bit ~98 long, max 14 dia; collar 31 dia -> bore 20, counterbore 34
// strippers: 205 long, 15 thick at pivot; nose 12 wide, handles ~46 wide at 95 up
// cobra: 180 long, 11 thick at joint; nose 14, joint 46 wide at ~55 up

// ---------------- derived --------------------------------------------
R        = thigh_circ_in * 25.4 / (2 * PI);   // leg radius
slot_h   = belt_w + belt_extra_w;
slot_gap = belt_t + belt_extra_t;

top_hi   = deck_back;                     // upper deck
top_lo   = deck_back - front_drop;        // lower deck
z_bottom = -(front_drop + floor_t + bottom_extra);   // outer bottom of the whole pouch

cb_dia   = driver_handle + 3;
cb_depth = handle_in + cb_extra;
driver_floor = top_hi - handle_in - driver_shaft;    // bore floor so the handle sits handle_in deep

// Cells.  Every cell: [name, column, behind, width (tangential), thickness (radial),
//                       deck, floor, rounding, profile-or-0, counterbore dia, counterbore depth]
//   column  : cells in the same column share a centre angle (one in front of the other)
//   behind  : radial distance from the back wall to the cell (what sits between it and the leg)
//   profile : [[z_from_floor, width], ...] for tapered pockets (width then = width at the rim)
cells = [
    ["level",        0, 0,               32 + clear_w, 22 + clear_t, top_hi, 0,                  5, 0, 0, 0],
    ["cobra",        0, 22 + clear_t + wall, 50,        11 + clear_t, top_lo, top_lo - 95,        5, [[0, 22], [50, 50], [95, 50]], 0, 0],
    ["wrench_big",   1, 0,               16 + clear_t, 34 + clear_w, top_hi, 0,                  5, 0, 0, 0],   // edge-on
    ["wrench_small", 2, 0,               13 + clear_t, 26 + clear_w, top_hi, 0,                  5, 0, 0, 0],   // edge-on
    ["strippers",    3, cb_dia + wall,   48,           15 + clear_t, top_lo, top_lo - 95,        5, [[0, 20], [40, 32], [95, 48]], 0, 0],   // in front of the driver
    ["driver",       3, 0,               cb_dia,       cb_dia,       top_hi, driver_floor,       cb_dia / 2, 0, cb_dia, cb_depth],
];
n_cells = len(cells);
function c_name(i) = cells[i][0];
function c_col(i)  = cells[i][1];
function c_w(i)    = cells[i][3];
function c_t(i)    = cells[i][4];
function c_deck(i) = cells[i][5];
function c_z0(i)   = cells[i][6];
function c_rr(i)   = cells[i][7];
function c_prof(i) = cells[i][8];
function c_cbd(i)  = cells[i][9];
function c_cbh(i)  = cells[i][10];
function c_r(i)    = R + wall_back + cells[i][2] + c_t(i) / 2;      // radial centre
function is_bore(i)  = c_cbd(i) > 0;
function is_taper(i) = c_prof(i) != 0;
bore_w = 20;                                                        // driver shaft bore

// Column angles.  Pocket sides are parallel (not radial), so two neighbours are
// closest at the innermost radius they share.  Space each pair so the wall there
// is at least `wall`.
n_cols = 4;
function r_in(i)  = c_r(i) - c_t(i) / 2;
function r_out(i) = c_r(i) + c_t(i) / 2;
// (rounded corners of radius rr pull the pinch point out by rr)
function pair_delta(i, j) = (c_w(i) / 2 + c_w(j) / 2 + wall) / max(r_in(i) + c_rr(i), r_in(j) + c_rr(j)) * 180 / PI;
function col_delta(k) = max([ for (i = [0 : n_cells - 1], j = [0 : n_cells - 1])
                              if (c_col(i) == k - 1 && c_col(j) == k) pair_delta(i, j) ]);
function col_edge(k)  = max([ for (i = [0 : n_cells - 1]) if (c_col(i) == k) (c_w(i) / 2 + wall_out) / (r_in(i) + c_rr(i)) * 180 / PI ]);
function col_a(k)     = (k == 0 ? col_edge(0) : col_a(k - 1) + col_delta(k));
A_total = col_a(n_cols - 1) + col_edge(n_cols - 1);
function c_a(i) = col_a(c_col(i));

i_drv = 5; i_str = 4;                                               // indices used by the deck ramp

// belt
belt_center_a = A_total / 2;
tab_t   = 8;
strap_t = 4;
z_s0    = top_hi + 4;                      // bottom of belt slot
z_s1    = z_s0 + slot_h;                   // top of belt slot
z_tab1  = z_s1 + slot_gap + strap_t + 10;  // top of the tab
tab_w   = 84;                              // belt loop width (chord, mm)
ramp_h  = 36;                              // height of the rounded ramp under the belt loop
ramp_steps = 16;

echo(str("Leg radius R = ", R, " mm; pouch spans ", A_total, " deg; chord ", 2*(R+45)*sin(A_total/2), " mm"));
echo(str("Overall height ", z_tab1 - z_bottom, " mm; driver bore floor at z = ", driver_floor,
         " (outer bottom at ", z_bottom, ")"));
assert(driver_floor >= z_bottom + 3, "driver bore goes through the bottom: shorten driver_shaft or raise deck_back");

// ---------------- helpers --------------------------------------------
module rrect(w, t, g, rr) {
    // rounded rectangle, x = radial thickness t, y = tangential width w, grown by g
    r  = min(rr, min(w, t) / 2 - 0.01);
    offset(r = r + g) square([t - 2 * r, w - 2 * r], center = true);
}
module slice(z, w, t, g, rr) {
    translate([0, 0, z]) linear_extrude(height = 0.02) rrect(w, t, g, rr);
}
module place(a, r) { rotate([0, 0, a]) translate([r, 0, 0]) children(); }
module place2d(a, r) { rotate(a) translate([r, 0]) children(); }
module at_cell(i) { place(c_a(i), c_r(i)) children(); }
module at_cell2d(i) { place2d(c_a(i), c_r(i)) children(); }

// straight pocket with a lead-in chamfer at the mouth
module straight_cavity(w, t, z0, rim, rr) {
    hull() {
        slice(z0, w, t, 0, rr);
        slice(rim - mouth_chamfer, w, t, 0, rr);
        slice(rim, w, t, mouth_chamfer, rr);
        slice(rim + 60, w, t, mouth_chamfer, rr);
    }
}

function lerp(a, b, f) = a + (b - a) * f;
function interp(prof, z, i = 0) =
    z <= prof[0][0] ? prof[0][1] :
    i >= len(prof) - 1 ? prof[len(prof) - 1][1] :
    z <= prof[i + 1][0] ? lerp(prof[i][1], prof[i + 1][1], (z - prof[i][0]) / (prof[i + 1][0] - prof[i][0])) :
    interp(prof, z, i + 1);

// ---------------- cavities -------------------------------------------
module cavity(i) {
    w = c_w(i); t = c_t(i); rim = c_deck(i); z0 = c_z0(i); rr = c_rr(i);
    at_cell(i) {
        if (is_bore(i)) {
            hull() { slice(z0, bore_w, bore_w, 0, bore_w / 2); slice(rim, bore_w, bore_w, 0, bore_w / 2); }
            straight_cavity(c_cbd(i), c_cbd(i), rim - c_cbh(i), rim, c_cbd(i) / 2);
        } else if (is_taper(i)) {
            prof = c_prof(i);
            hull() {
                for (p = prof) if (z0 + p[0] <= rim - mouth_chamfer) slice(z0 + p[0], p[1], t, 0, rr);
                slice(rim - mouth_chamfer, w, t, 0, rr);
                slice(rim, w, t, mouth_chamfer, rr);
                slice(rim + 60, w, t, mouth_chamfer, rr);
            }
        } else {
            straight_cavity(w, t, z0, rim, rr);
        }
    }
}
module drain(i) {
    at_cell(i) translate([0, 0, z_bottom - 1]) cylinder(d = 6, h = c_z0(i) - z_bottom + 3);
}

// ---------------- sculpted outer shell --------------------------------
// The shell is a stack of thin layers.  At each height the outline is the
// union of every cell's outline (grown by the wall), plus the sloped deck
// from the driver housing, then closed with a large radius so grooves
// between cells are filled and the outside reads as one smooth surface.
function grow_at(z, rim) =
    min(wall_out - max(0, z - (rim - rim_round)),
        wall_out - base_chamfer + (z - z_bottom));

module cell_outline(i, z) {
    rim = c_deck(i); z0 = c_z0(i); g = grow_at(z, rim);
    if (z < rim) at_cell2d(i) {
        if (is_bore(i)) {
            in_cb = z > rim - c_cbh(i) - 2;
            if (in_cb) rrect(c_cbd(i), c_cbd(i), g, c_cbd(i) / 2);
            else       rrect(bore_w, bore_w, g, bore_w / 2);
        } else if (is_taper(i)) {
            rrect(interp(c_prof(i), max(0, z - z0)), c_t(i), g, c_rr(i));
        } else {
            rrect(c_w(i), c_t(i), g, c_rr(i));
        }
    }
}
// sloped deck: between the lower and upper deck heights, material spreads from the
// driver housing toward the strippers, further the lower you go
module driver_ramp_outline(z) {
    if (z > top_lo - 0.01 && z < top_hi) {
        f = (top_hi - z) / (top_hi - top_lo);            // 0 at the upper deck, 1 at the lower deck
        d = driver_ramp * f;
        intersection() {
            hull() { cell_outline(i_drv, z); cell_outline(i_str, top_lo - 1); }
            offset(r = d) at_cell2d(i_drv) rrect(c_cbd(i_drv), c_cbd(i_drv), grow_at(z, top_hi), c_cbd(i_drv) / 2);
        }
    }
}
module footprint(z) {
    offset(r = -blend_r) offset(r = blend_r) union() {
        for (i = [0 : n_cells - 1]) cell_outline(i, z);
        driver_ramp_outline(z);
    }
}
module shell() {
    for (z = [z_bottom : band_h : top_hi - band_h / 2])
        translate([0, 0, z]) linear_extrude(height = band_h + 0.02) footprint(z + band_h / 2);
}

// ---------------- belt loop ------------------------------------------
module belt_loop() {
    g = slot_gap; st = strap_t; tt = tab_t; rr = 3;
    z_strap0 = z_s0 - 6;                                  // bottom of the flat strap face
    z_ramp1  = z_strap0 - ramp_h;                         // where the ramp meets the pouch back
    z_lo     = min(top_hi - 14, z_ramp1 - 6);             // where the tab grows out of the body
    // S-shaped ramp: vertical at both ends, so there is no edge against the leg
    ramp = [ for (i = [0 : ramp_steps]) let (t = i / ramp_steps)
             [R - (g + st) * (1 + cos(180 * t)) / 2, z_strap0 - ramp_h * t] ];
    // rounded top corners (quarter circles)
    top_out = [ for (i = [0 : 6]) let (a = 90 * i / 6) [R + tt - rr + rr * cos(a), z_tab1 - rr + rr * sin(a)] ];
    top_in  = [ for (i = [0 : 6]) let (a = 90 + 90 * i / 6) [R - g - st + rr + rr * cos(a), z_tab1 - rr + rr * sin(a)] ];
    outer = concat([[R, z_lo], [R + tt, z_lo]], top_out, top_in, [[R - g - st, z_strap0]], ramp);
    hole  = [[R - g, z_s0], [R, z_s0], [R, z_s1], [R - g, z_s1 + g]];
    n = len(outer);
    rotate([0, 0, belt_center_a])
    intersection() {
        rotate([0, 0, -50]) rotate_extrude(angle = 100)
            polygon(concat(outer, hole), [[for (i = [0 : n - 1]) i], [n, n + 1, n + 2, n + 3]]);
        // round the corners of the tab (seen from the side)
        rotate([90, 0, 90]) linear_extrude(height = 600, center = true)
            translate([0, (z_lo + z_tab1) / 2])
                offset(r = 14) offset(delta = -14) square([tab_w, z_tab1 - z_lo], center = true);
    }
}

// ---------------- tool models for preview -------------------------------
// Recognisable stand-ins at real size (preview only, never exported).
// Local frame of each cell: x = radial (thickness), y = tangential (width), z = up.
C_chrome = [0.80, 0.81, 0.84]; C_red = [0.82, 0.16, 0.10]; C_black = [0.13, 0.13, 0.14];
C_orange = [0.95, 0.52, 0.08]; C_brass = [0.78, 0.64, 0.22]; C_tape = [0.08, 0.42, 0.30];
C_yellow = [0.92, 0.82, 0.25]; C_green = [0.10, 0.36, 0.30]; C_vial = [0.75, 0.92, 0.35];

module box(x, y, z0, z1) { translate([0, 0, z0]) linear_extrude(z1 - z0) square([x, y], center = true); }
module taper(x0, y0, z0, x1, y1, z1) {
    hull() { box(x0, y0, z0, z0 + 0.1); box(x1, y1, z1 - 0.1, z1); }
}
module xcyl(d, l, z, y = 0) { translate([0, y, z]) rotate([0, 90, 0]) cylinder(d = d, h = l, center = true); }

module m_level() {                          // orange billet torpedo level, 165 x 32 x 22
    color(C_orange) difference() {
        box(22, 32, 0, 165);
        for (z = [28, 68, 108, 148]) xcyl(16, 30, z);
        xcyl(6, 30, 8);                     // hanging hole
    }
    color(C_vial) for (z = [28, 68, 108, 148]) translate([0, 0, z]) rotate([90, 0, 0]) cylinder(d = 7, h = 22, center = true);
    color(C_brass) { translate([0, 14, 155]) rotate([-90, 0, 0]) cylinder(d = 8, h = 7);   // pitch knob
                     translate([0, 0, 163]) cylinder(d = 5, h = 6); }                       // screw
}
module m_wrench(L, d0, t0, d1, t1) {        // ratcheting box wrench, big end (d0) down, flat in x
    color(C_chrome) {
        box(6, 12, d0 / 2, L - d1 / 2);
        difference() { xcyl(d0, t0, d0 / 2); xcyl(d0 * 0.55, t0 + 2, d0 / 2); }
        difference() { xcyl(d1, t1, L - d1 / 2); xcyl(d1 * 0.55, t1 + 2, L - d1 / 2); }
    }
    color(C_tape) box(8, 14, L * 0.5, L * 0.5 + 12);
}
module m_driver() {                          // Klein 11-in-1 with 3/8 flip socket
    color(C_black) { cylinder(d = 6.35, h = 26, $fn = 6);                      // bit
                     translate([0, 0, 24]) cylinder(d = 14, h = 40);            // flip socket
                     translate([0, 0, 64]) cylinder(d = 8, h = 34); }           // shaft
    color(C_yellow) translate([0, 0, driver_shaft]) cylinder(d = driver_handle, h = 11);                 // collar
    color(C_green)  translate([0, 0, driver_shaft + 11]) cylinder(d = driver_handle - 5, h = collar_len - 11); // green band
    color(C_black)  translate([0, 0, driver_shaft + collar_len]) cylinder(d = driver_handle + 1, h = 90);  // rubber handle
}
module m_strippers() {                       // Milwaukee 6-in-1, nose down, 205 long
    color(C_black) { taper(6, 8, 0, 9, 22, 60); box(10, 32, 60, 95); }
    color(C_chrome) { xcyl(22, 11, 78); translate([0, 0, 90]) box(8, 6, 88, 96); }
    for (sgn = [-1, 1]) color(C_red)
        hull() { translate([0, sgn * 11, 95]) box(14, 12, 0, 0.1); translate([0, sgn * 24, 205]) box(14, 13, -0.1, 0); }
    color(C_tape) hull() { translate([0, 14, 150]) box(15, 14, 0, 0.1); translate([0, 15.5, 164]) box(15, 14, 0, 0.1); }
}
module m_cobra() {                            // Knipex Cobra 180, nose down
    color(C_chrome) { taper(8, 12, 0, 11, 40, 42); box(11, 46, 42, 72);
                      translate([6, 8, 60]) rotate([0, 90, 0]) cylinder(d = 7, h = 3); }   // push button
    for (sgn = [-1, 1]) color(C_red)
        hull() { translate([0, sgn * 10, 72]) box(10, 11, 0, 0.1); translate([0, sgn * 27, 180]) box(10, 10, -0.1, 0); }
    color(C_tape) hull() { translate([0, -13, 105]) box(11, 12, 0, 0.1); translate([0, -14.5, 117]) box(11, 12, 0, 0.1); }
}

module tool_models() {
    at_cell(0) m_level();
    at_cell(1) translate([0, 0, c_z0(1)]) m_cobra();
    at_cell(2) rotate([0, 0, 90]) m_wrench(210, 34, 16, 30, 14);     // edge-on
    at_cell(3) rotate([0, 0, 90]) m_wrench(165, 26, 13, 22, 11);     // edge-on
    at_cell(4) translate([0, 0, c_z0(4)]) m_strippers();
    at_cell(5) translate([0, 0, driver_floor]) m_driver();
}

// ---------------- assembly -------------------------------------------
module pouch() {
    difference() {
        union() {
            difference() {
                shell();
                // concave back that wraps the leg
                translate([0, 0, z_bottom - 5]) cylinder(r = R, h = 400, $fn = 180);
            }
            belt_loop();
        }
        for (i = [0 : n_cells - 1]) { cavity(i); drain(i); }
    }
}

// centre the pouch on +X, front of the thigh toward +Y for the right leg
module oriented() {
    rotate([0, 0, -belt_center_a]) { color(pouch_color) pouch(); if (show_tools) tool_models(); }
}

if (side == "left") mirror([0, 1, 0]) oriented(); else oriented();
