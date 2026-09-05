// =====================================================================
//  Thigh tool pouch  –  parametric OpenSCAD model  (all units mm)
//
//  Worn on a belt, hanging on the outside of the thigh.  Two rows of
//  pockets.  Back row (against the leg), rear -> front:
//      torpedo level | 9/16x11/16 ratchet wrench | 3/8x7/16 ratchet wrench | 11-in-1 driver
//  Front row (outside), front -> rear, rims dropped by front_drop:
//      Milwaukee 6-in-1 strippers | Knipex Cobra 180
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
front_gap     = 6;         // wall between the two front pockets (handles spread above the rim)
wall_out      = 4;         // outside wall
wall_back     = 4.5;       // wall against the leg
floor_t       = 4;         // floor under the deepest pocket
rim_round     = 2;         // chamfer on every pocket rim
base_chamfer  = 3;         // chamfer on the bottom edge
front_drop    = 18;        // front row rims sit this much lower than back row
clear_w       = 4;         // total width clearance added to each tool
clear_t       = 3;         // total thickness clearance added to each tool
blend_r       = 7;         // radius used to blend the pocket cells into one smooth shell
band_h        = 1;         // layer height of the sculpted shell (1 = final, 4 = fast preview)
show_tools    = false;     // draw translucent tool stand-ins (preview only)

$fn = 40;

// ---------------- tool sizes (measured from photos) ------------------
// level: 165 long, 32 wide, ~22 thick   -> pocket 36 x 26, 100 deep
// big wrench: 210 long, 11/16 head ~34 dia, 16 thick -> 38 x 19, 110 deep
// small wrench: 165 long, 7/16 head ~26 dia, 13 thick -> 30 x 16, 100 deep
// driver: shaft + flip socket ~105 long, max 14 dia; handle 28 dia -> bore 20, 100 deep
// strippers: 205 long, 15 thick at pivot; nose 12 wide, handles spread to ~46
//            at 105 up -> 18 thick, tapered 20 -> 50 wide, 105 deep
// cobra: 180 long, 11 thick at joint; nose 14, joint 46 wide at ~55 up
//            -> 14 thick, tapered 22 -> 50 wide, 95 deep

// ---------------- derived --------------------------------------------
R        = thigh_circ_in * 25.4 / (2 * PI);   // leg radius
slot_h   = belt_w + belt_extra_w;
slot_gap = belt_t + belt_extra_t;

// Back-row pockets: [name, width(tangential), thickness(radial), depth, rounding]
back = [
    ["level",       32 + clear_w, 22 + clear_t, 100, 5],
    ["wrench_big",  34 + clear_w, 16 + clear_t, 110, 5],
    ["wrench_small",26 + clear_w, 13 + clear_t, 100, 5],
    ["driver",      20,           20,           100, 10],   // round bore
];
back_rim = [ for (p = back) p[3] ];          // floor at z = 0 for the back row
top_back = max(back_rim);                    // highest rim
z_bottom = -(front_drop + floor_t);          // outer bottom of the whole pouch

// front-row pockets: [name, thickness, depth, profile [[z_from_floor, width], ...]]
front = [
    ["strippers", 15 + clear_t, 105, [[0, 20], [40, 32], [105, 50]]],
    ["cobra",     11 + clear_t,  95, [[0, 22], [50, 50], [95, 50]]],
];
t_back_max_under_front = 20;  // thickest back pocket under the front row (big wrench)

r_ref_b = R + wall_back + 10;                                 // reference radius for back spacing
r_ref_f = R + wall_back + t_back_max_under_front + wall + 8;  // ... for front spacing

function r_back(i)  = R + wall_back + back[i][2] / 2;
function r_front(i) = R + wall_back + t_back_max_under_front + wall + front[i][1] / 2;

// arc positions (mm along r_ref_b) of the back pocket centres
function s_back(i) = wall_out + (i == 0 ? 0 : s_back_end(i - 1) + wall) + back[i][1] / 2;
function s_back_end(i) = s_back(i) + back[i][1] / 2;
back_total = s_back_end(len(back) - 1) + wall_out;            // full arc length of the back row
A_total = back_total / r_ref_b * 180 / PI;                    // total angle of the pouch
function a_back(i) = s_back(i) / r_ref_b * 180 / PI;

// front row: front (outer) edge aligned with the front edge of the back row
function w_top(i) = front[i][3][len(front[i][3]) - 1][1];
// arc length (at r_ref_f) from the front face of the pouch back to each front pocket centre
function s_front(i) = wall_out + (i == 0 ? 0 : s_front(i - 1) - wall_out + w_top(i - 1) / 2 + front_gap) + w_top(i) / 2;
function a_front(i) = A_total - s_front(i) / r_ref_f * 180 / PI;

// front row floors
function z_floor_front(i) = top_back - front_drop - front[i][2];
front_rim = top_back - front_drop;

// belt
belt_center_a = A_total / 2;
tab_t   = 8;
strap_t = 4;
z_s0    = top_back + 4;               // bottom of belt slot
z_s1    = z_s0 + slot_h;              // top of belt slot
z_tab1  = z_s1 + slot_gap + strap_t + 10;  // top of the tab
tab_w   = 84;                          // belt loop width (chord, mm)

echo(str("Leg radius R = ", R, " mm; pouch spans ", A_total, " deg; chord ", 2*(R+45)*sin(A_total/2), " mm"));
echo(str("Overall height ", z_tab1 - z_bottom, " mm"));

// ---------------- helpers --------------------------------------------
module rrect(w, t, g, rr) {
    // rounded rectangle, x = radial thickness t, y = tangential width w, grown by g
    r  = min(rr, min(w, t) / 2 - 0.01);
    offset(r = r + g) square([t - 2 * r, w - 2 * r], center = true);
}
module slice(z, w, t, g, rr) {
    translate([0, 0, z]) linear_extrude(height = 0.02) rrect(w, t, g, rr);
}
// place in the pouch frame: angle a about the leg axis, radius r
module place(a, r) { rotate([0, 0, a]) translate([r, 0, 0]) children(); }

// ---------------- back row -------------------------------------------
module back_cavity(i) {
    w = back[i][1]; t = back[i][2]; d = back[i][3]; rr = back[i][4];
    place(a_back(i), r_back(i))
        hull() { slice(0, w, t, 0, rr); slice(d + 60, w, t, 0, rr); }
}
module back_drain(i) {
    place(a_back(i), r_back(i)) translate([0, 0, z_bottom - 1]) cylinder(d = 6, h = 40);
}

// ---------------- front row ------------------------------------------
module front_cavity(i) {
    t = front[i][1]; d = front[i][2]; prof = front[i][3]; z0 = z_floor_front(i);
    place(a_front(i), r_front(i))
        hull() {
            for (p = prof) slice(z0 + p[0], p[1], t, 0, 5);
            slice(z0 + d + 60, w_top(i), t, 0, 5);
        }
}
module front_drain(i) {
    place(a_front(i), r_front(i)) translate([0, 0, z_bottom - 1]) cylinder(d = 6, h = 40);
}

// ---------------- sculpted outer shell --------------------------------
// The shell is built as a stack of thin layers.  At each height the outline is
// the union of every pocket's outline (grown by the wall) with the notches
// between neighbouring pockets filled in, so the outside reads as one smooth
// body that still follows each tool.
function lerp(a, b, f) = a + (b - a) * f;
function interp(prof, z, i = 0) =
    z <= prof[0][0] ? prof[0][1] :
    i >= len(prof) - 1 ? prof[len(prof) - 1][1] :
    z <= prof[i + 1][0] ? lerp(prof[i][1], prof[i + 1][1], (z - prof[i][0]) / (prof[i + 1][0] - prof[i][0])) :
    interp(prof, z, i + 1);
// wall growth at height z for a cell whose rim is at `rim` (rim + base chamfers)
function grow_at(z, rim) =
    min(wall_out - max(0, z - (rim - rim_round)),
        wall_out - base_chamfer + (z - z_bottom));

module place2d(a, r) { rotate(a) translate([r, 0]) children(); }

module footprint(z) {
    offset(r = -blend_r) offset(r = blend_r) union() {
        for (i = [0 : len(back) - 1]) {
            rim = back[i][3];
            if (z < rim)
                place2d(a_back(i), r_back(i))
                    rrect(back[i][1], back[i][2], grow_at(z, rim), back[i][4]);
        }
        for (i = [0 : len(front) - 1]) {
            z0 = z_floor_front(i); d = front[i][2]; rim = z0 + d;
            if (z < rim)
                place2d(a_front(i), r_front(i))
                    rrect(interp(front[i][3], max(0, z - z0)), front[i][1], grow_at(z, rim), 5);
        }
    }
}
module shell() {
    for (z = [z_bottom : band_h : top_back - band_h / 2])
        translate([0, 0, z]) linear_extrude(height = band_h + 0.02) footprint(z + band_h / 2);
}

// ---------------- belt loop ------------------------------------------
module belt_loop() {
    g = slot_gap; st = strap_t; tt = tab_t;
    z_lo = top_back - 14;                       // where the tab grows out of the body
    z_strap0 = z_s0 - 6;
    outer = [[R, z_lo], [R + tt, z_lo], [R + tt, z_tab1], [R - g - st, z_tab1],
             [R - g - st, z_strap0], [R, z_strap0 - (g + st)]];
    hole  = [[R - g, z_s0], [R, z_s0], [R, z_s1], [R - g, z_s1 + g]];
    rotate([0, 0, belt_center_a])
    intersection() {
        rotate([0, 0, -50]) rotate_extrude(angle = 100)
            polygon(concat(outer, hole), [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9]]);
        // round the corners of the tab (seen from the side)
        rotate([90, 0, 90]) linear_extrude(height = 600, center = true)
            translate([0, (z_lo + z_tab1) / 2])
                offset(r = 14) offset(delta = -14) square([tab_w, z_tab1 - z_lo], center = true);
    }
}

// ---------------- tool stand-ins for preview ---------------------------
module tool_ghosts() {
    color([0.85, 0.35, 0.1, 0.55]) {
        place(a_back(0), r_back(0)) linear_extrude(165) square([22, 32], center = true);          // level
        place(a_back(1), r_back(1)) linear_extrude(210) square([16, 34], center = true);          // big wrench
        place(a_back(2), r_back(2)) linear_extrude(165) square([13, 26], center = true);          // small wrench
        place(a_back(3), r_back(3)) { cylinder(d = 14, h = 105); translate([0, 0, 105]) cylinder(d = 28, h = 100); } // driver
        place(a_front(0), r_front(0)) hull() for (p = [[0, 12], [75, 30], [205, 60]])
            translate([0, 0, z_floor_front(0) + p[0]]) linear_extrude(0.1) square([15, p[1]], center = true); // strippers
        place(a_front(1), r_front(1)) hull() for (p = [[0, 14], [55, 46], [180, 55]])
            translate([0, 0, z_floor_front(1) + p[0]]) linear_extrude(0.1) square([11, p[1]], center = true); // cobra
    }
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
        for (i = [0 : len(back) - 1])  { back_cavity(i);  back_drain(i);  }
        for (i = [0 : len(front) - 1]) { front_cavity(i); front_drain(i); }
    }
}

// centre the pouch on +X, front of the thigh toward +Y for the right leg
module oriented() {
    rotate([0, 0, -belt_center_a]) { pouch(); if (show_tools) tool_ghosts(); }
}

if (side == "left") mirror([0, 1, 0]) oriented(); else oriented();
