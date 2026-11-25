"""Reusable Parametric 225-Series Sunroom Panel Builder for FreeCAD.

Builds individual 225 panel assemblies directly from the authoritative die
geometry (A26948 Female Channel, A26949 Male Channel, A26950 Glass Adaptor,
and SliderSash225 profiles) using pure rigid 3D rotations (no mirrored
extrusions) at true 1:1 scale (1 inch = 25.4 mm for FreeCAD's Building US units).

Features:
  - Supports rectangular and trapezoidal/raked 225 panels
  - Horizontal A26948 rails extend into both vertical U-pockets right up
    against the vertical webs with clean flange notches (zero slivers)
  - Automatically detects the 0.144" screw chases on every horizontal rail and
    drills coaxial #10 clearance holes (0.201" dia) through both verticals
  - Optional toggleable ON/OFF groups for:
      * SliderSash225 horizontal slider window (auto-sized to any opening)
      * A26950 mitered glass adaptors around any fixed-glass opening
"""

import json
import math
import os
import FreeCAD as App
import Part
from FreeCAD import Vector as V

V2_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\v2"
PROFILES_JSON = os.path.join(V2_DIR, "profiles_all.json")
SLIDER_MACRO = os.path.join(V2_DIR, "Macro", "SliderSash225_Build.FCMacro")
OUT_DIR = os.path.join(V2_DIR, "panels")

INCH = 25.4  # FreeCAD internal units are mm (true 1:1 scale for Building US ft-in)

COLORS = {
    "A26948": (0.85, 0.40, 0.40),     # 225 Female Channel (red)
    "A26949": (0.35, 0.55, 0.85),     # 225 Male Channel (steel blue)
    "A26948_H": (0.95, 0.65, 0.25),   # Horizontal A26948 rails (amber)
    "A26950": (0.35, 0.72, 0.52),     # A26950 Glass Adaptors (teal green)
    "SLIDER_FRAME": (0.80, 0.80, 0.82),
    "SLIDER_SASH": (0.62, 0.66, 0.72),
    "GLASS": (0.55, 0.75, 0.85),
}

# Exact die constants measured from A26948 / A26949 / A26950 profiles (inches)
DIE_WIDTH = {
    "A26948": 1.1250,  # total face width (0.344 back + 0.093 web + 0.688 pocket)
    "A26949": 1.2620,  # total face width (0.481 male back + 0.093 web + 0.688 pocket)
}
POCKET_DEPTH = 0.6880
WEB_FACE_FROM_BACK = {
    "A26948": 0.4370,  # 1.1250 - 0.6880
    "A26949": 0.5740,  # 1.2620 - 0.6880
}
CHANNEL_DEPTH = 2.2800         # A26948 / A26949 outer rib-to-rib depth
INSERT_DEPTH = 2.2500          # A26950 and SliderSash225 flat-to-flat depth
INSERT_Y_EXT = 0.0150          # (2.280 - 2.250) / 2 -> flush with A26948 flat exterior face
INSERT_Y_INT = 2.2650          # flush with A26948 flat interior face
SLIDER_CLIP_DEPTH = 0.24183    # exact clip-tip to outer shoulder on 150/14F/151/SILL
A26950_CLIP_DEPTH = 0.24119    # exact clip-tip to outer shoulder on A26950


# ---------------------------------------------------------------------------
# Profile loader & automatic 0.144" screw-chase detector
# ---------------------------------------------------------------------------

def _arc_circle(a, m, b):
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0 = math.atan2(ay - uy, ax - ux)
    am = math.atan2(by - uy, bx - ux)
    a1 = math.atan2(cy - uy, cx - ux)
    ccw_1 = (a1 - a0) % (2.0 * math.pi)
    ccw_m = (am - a0) % (2.0 * math.pi)
    sweep = ccw_1 if ccw_m <= ccw_1 else (2.0 * math.pi - ccw_1)
    return ux, uy, r, math.degrees(sweep)


def load_225_profile(die_code, chase_dia_in=0.144, chase_tol_in=0.005):
    all_p = json.load(open(PROFILES_JSON, "r", encoding="utf-8"))
    raw_loops = all_p[die_code]["loops"]

    all_pts = []
    cleaned = []
    for L in raw_loops:
        segs = []
        for s in L:
            if s[0] == "line":
                if math.dist(s[1], s[2]) > 1e-6:
                    segs.append(s)
                    all_pts.extend([s[1], s[2]])
            else:
                if math.dist(s[1], s[3]) > 1e-6 and math.dist(s[1], s[2]) > 1e-6 and math.dist(s[2], s[3]) > 1e-6:
                    segs.append(s)
                    all_pts.extend([s[1], s[2], s[3]])
        cleaned.append(segs)

    x0 = min(p[0] for p in all_pts)
    y0 = min(p[1] for p in all_pts)
    x1 = max(p[0] for p in all_pts)
    y1 = max(p[1] for p in all_pts)

    norm_loops = []
    target_r = chase_dia_in / 2.0
    chases = []
    for segs in cleaned:
        nsegs = [[s[0]] + [[p[0] - x0, p[1] - y0] for p in s[1:]] for s in segs]
        for k in range(len(nsegs)):
            nsegs[k][1] = list(nsegs[k - 1][-1])
        norm_loops.append({"segs": nsegs})
        for s in nsegs:
            if s[0] == "arc":
                info = _arc_circle(s[1], s[2], s[3])
                if info is not None:
                    ux, uy, r, sweep = info
                    if abs(r - target_r) <= chase_tol_in and sweep > 150.0:
                        pt = (ux, uy)
                        if not any(math.dist(pt, existing) < 1e-3 for existing in chases):
                            chases.append(pt)

    chases.sort(key=lambda p: (round(p[0], 4), round(p[1], 4)))
    return {"size": (x1 - x0, y1 - y0), "loops": norm_loops, "chases": chases}


# ---------------------------------------------------------------------------
# 3D Solid Helpers (right-handed basis u x v = w, no mirroring)
# ---------------------------------------------------------------------------

def map_profile_pt(pt_2d, origin_in, u, v):
    return (
        origin_in[0] + pt_2d[0] * u[0] + pt_2d[1] * v[0],
        origin_in[1] + pt_2d[0] * u[1] + pt_2d[1] * v[1],
        origin_in[2] + pt_2d[0] * u[2] + pt_2d[1] * v[2],
    )


def extrude_profile(profile, origin_in, u, v, length_in, scale=INCH):
    u_vec = V(*u)
    v_vec = V(*v)
    w_vec = u_vec.cross(v_vec)
    assert abs(w_vec.Length - 1.0) < 1e-9, f"u={u}, v={v} must be orthonormal"

    orig = V(*origin_in) * scale

    def map_pt(p):
        return orig + u_vec * (p[0] * scale) + v_vec * (p[1] * scale)

    wires = []
    for L in profile["loops"]:
        edges = []
        for s in L["segs"]:
            if s[0] == "line":
                a, b = map_pt(s[1]), map_pt(s[2])
                if (a - b).Length > 1e-5:
                    edges.append(Part.LineSegment(a, b).toShape())
            else:
                a, m, b = map_pt(s[1]), map_pt(s[2]), map_pt(s[3])
                if (a - b).Length > 1e-5 and (a - m).Length > 1e-5 and (m - b).Length > 1e-5:
                    edges.append(Part.Arc(a, m, b).toShape())
        w = Part.Wire(edges)
        if not w.isClosed():
            w.fixWire(None, 1e-4)
        wires.append(w)

    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    if not face.isValid():
        face.fix(1e-6, 1e-6, 1e-6)
    solid = face.extrude(w_vec * (length_in * scale))
    if not solid.isValid():
        solid.fix(1e-6, 1e-6, 1e-6)
    return solid


def make_xz_prism(xz_pts_in, y_lo_in=-2.0, y_hi_in=6.0, scale=INCH):
    pts = [V(x * scale, y_lo_in * scale, z * scale) for x, z in xz_pts_in]
    wire = Part.makePolygon(pts + [pts[0]])
    return Part.Face(wire).extrude(V(0, (y_hi_in - y_lo_in) * scale, 0))


def drill_coaxial_holes(solid, hole_rays, hole_dia_in, back_in=1.5, fwd_in=0.20, scale=INCH):
    r = (hole_dia_in / 2.0) * scale
    total_len = (back_in + fwd_in) * scale
    out = solid
    for anchor_in, dir_vec in hole_rays:
        d = V(*dir_vec)
        d.normalize()
        start = V(*anchor_in) * scale - d * (back_in * scale)
        cyl = Part.makeCylinder(r, total_len, start, d)
        out = out.cut(cyl)
    if not out.isValid():
        out.fix(1e-6, 1e-6, 1e-6)
    return out


# ---------------------------------------------------------------------------
# Modular Additions: A26950 Glass Adaptors & SliderSash225 Window Assembly
# ---------------------------------------------------------------------------

def add_glass_adaptors(
    doc,
    parent_part,
    x_left_in,
    x_right_in,
    z_bot_in,
    z_top_left_in,
    z_top_right_in=None,
    group_name="Top_Glass_Adaptors",
    prefix="Top",
    sides=("bottom", "top", "left", "right"),
    scale=INCH,
):
    """Add angle-bisector mitered A26950 glass adaptors around a rectangular or trapezoidal opening.

    Placed in a dedicated App::DocumentObjectGroup so the user can toggle the
    entire set ON/OFF with one click / Spacebar in the FreeCAD Model Tree.
    """
    if z_top_right_in is None:
        z_top_right_in = z_top_left_in

    prof = load_225_profile("A26950")
    clip = A26950_CLIP_DEPTH
    pad = 2.0  # over-extrude past corners before angle-bisector miter trim
    min_edge = min(x_right_in - x_left_in, z_top_left_in - z_bot_in, z_top_right_in - z_bot_in)
    M = min(2.5, max(1.05, 0.45 * min_edge))  # covers clip (0.241") & fin (0.562") without crossing short edges

    dx = x_right_in - x_left_in
    dz_top = z_top_right_in - z_top_left_in
    top_len = math.hypot(dx, dz_top)
    cos_t = dx / top_len
    sin_t = dz_top / top_len

    # Unit inward normals of the 4 opening sides in XZ
    n_B = (0.0, 1.0)
    n_L = (1.0, 0.0)
    n_R = (-1.0, 0.0)
    n_T = (sin_t, -cos_t)

    def unit_sum(a, b):
        sx, sz = a[0] + b[0], a[1] + b[1]
        L = math.hypot(sx, sz)
        return (sx / L, sz / L)

    # Exact angle bisectors pointing inward from the 4 opening shoulder corners
    P_bl = (x_left_in, z_bot_in)
    P_br = (x_right_in, z_bot_in)
    P_tl = (x_left_in, z_top_left_in)
    P_tr = (x_right_in, z_top_right_in)

    b_bl = unit_sum(n_L, n_B)
    b_br = unit_sum(n_R, n_B)
    b_tl = unit_sum(n_L, n_T)
    b_tr = unit_sum(n_R, n_T)

    def miter_quad(A, bA, B, bB):
        return [
            (A[0] - M * bA[0], A[1] - M * bA[1]),
            (B[0] - M * bB[0], B[1] - M * bB[1]),
            (B[0] + M * bB[0], B[1] + M * bB[1]),
            (A[0] + M * bA[0], A[1] + M * bA[1]),
        ]

    miter_polys = {
        "bottom": miter_quad(P_bl, b_bl, P_br, b_br),
        "top":    miter_quad(P_tl, b_tl, P_tr, b_tr),
        "left":   miter_quad(P_bl, b_bl, P_tl, b_tl),
        "right":  miter_quad(P_br, b_br, P_tr, b_tr),
    }

    # Top adaptor origin shifted outward along -n_T by `clip` and backward along -(cos_t, sin_t) by `pad`
    top_x0 = P_tl[0] - clip * n_T[0] - pad * cos_t
    top_z0 = P_tl[1] - clip * n_T[1] - pad * sin_t

    # u = (0, -1, 0) from Y=2.265" -> Y=0.015" puts the serrated glass-stop fin on EXTERIOR (Y=0.515..0.602")
    # Every side uses a right-handed basis u x v = w (pure rigid 3D rotation, zero mirroring).
    side_specs = {
        "bottom": (
            f"{prefix}_A26950_Bottom",
            (x_right_in + pad, INSERT_Y_INT, z_bot_in - clip),
            (0, -1, 0), (0, 0, 1),
            dx + 2.0 * pad,
        ),
        "top": (
            f"{prefix}_A26950_Top",
            (top_x0, INSERT_Y_INT, top_z0),
            (0, -1, 0), (sin_t, 0.0, -cos_t),
            top_len + 2.0 * pad,
        ),
        "left": (
            f"{prefix}_A26950_Left",
            (x_left_in - clip, INSERT_Y_INT, z_bot_in - pad),
            (0, -1, 0), (1, 0, 0),
            (z_top_left_in - z_bot_in) + 2.0 * pad,
        ),
        "right": (
            f"{prefix}_A26950_Right",
            (x_right_in + clip, INSERT_Y_INT, z_top_right_in + pad),
            (0, -1, 0), (-1, 0, 0),
            (z_top_right_in - z_bot_in) + 2.0 * pad,
        ),
    }

    grp = doc.addObject("App::DocumentObjectGroup", group_name)
    grp.Label = group_name
    parent_part.addObject(grp)

    shapes = []
    for side in sides:
        name, origin_in, u, v, length_in = side_specs[side]
        raw = extrude_profile(prof, origin_in, u, v, length_in, scale=scale)
        mitered = raw.common(make_xz_prism(miter_polys[side], y_lo_in=-1.0, y_hi_in=4.0, scale=scale))
        if not mitered.isValid():
            mitered.fix(1e-6, 1e-6, 1e-6)
        obj = doc.addObject("Part::Feature", name)
        obj.Label = name
        obj.Shape = mitered.removeSplitter() if mitered.isValid() else mitered
        grp.addObject(obj)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = COLORS["A26950"]
        shapes.append((name, obj.Shape))

    inter = []
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            vol = shapes[i][1].common(shapes[j][1]).Volume
            if vol > 1e-3:
                inter.append((shapes[i][0], shapes[j][0], vol))
    print(f"  [{group_name}] {len(shapes)} A26950 pieces added (mitered), internal interference pairs: {len(inter)}")
    for name, shp in shapes:
        bb = shp.BoundBox
        print(
            f"    {name:24s} valid={shp.isValid()} "
            f"X=[{bb.XMin/scale:7.4f}, {bb.XMax/scale:7.4f}] "
            f"Y=[{bb.YMin/scale:7.4f}, {bb.YMax/scale:7.4f}] "
            f"Z=[{bb.ZMin/scale:7.4f}, {bb.ZMax/scale:7.4f}]"
        )
    return grp, shapes


def add_slider_window(
    doc,
    parent_part,
    x_left_in,
    x_right_in,
    z_bot_in,
    z_top_in,
    group_name="Slider_Window",
    scale=INCH,
):
    """Build SliderSash225 sized to snap cleanly into the given opening and add as a toggleable group.

    Uses the exact die profiles and build logic from v2/Macro/SliderSash225_Build.FCMacro,
    rotated 180 deg about Z (pure rigid rotation, no mirroring) so Exterior sits at Y=0.015"
    and Interior at Y=2.265", scaled by 25.4 mm/in to match the 1:1 225 panel.
    """
    src = open(SLIDER_MACRO, "r", encoding="utf-8").read()
    p_line = [l for l in src.splitlines() if l.startswith("P = json.loads")][0]
    P = json.loads(p_line.split("r'''")[1].split("'''")[0])

    clip = SLIDER_CLIP_DEPTH
    W = (x_right_in - x_left_in) + 2.0 * clip   # frame outside width over jamb clips
    H = (z_top_in - z_bot_in) + 2.0 * clip      # frame outside height over head/sill clips
    GLASS_T = 0.125
    GLASS_BITE_CLR = 0.06
    MITRE_D = 2.0

    def face(key):
        es = []
        for e in P[key]:
            if e[0] == "L":
                es.append(Part.LineSegment(V(*e[1], 0), V(*e[2], 0)).toShape())
            else:
                es.append(Part.Arc(V(*e[1], 0), V(*e[2], 0), V(*e[3], 0)).toShape())
        w = Part.Wire(es)
        assert w.isClosed(), key
        f = Part.Face(w)
        if not f.isValid():
            f.fix(1e-7, 1e-7, 1e-7)
        assert f.isValid(), key
        return f

    F = {k: face(k) for k in P}
    bb = {k: f.optimalBoundingBox() for k, f in F.items()}

    def hmember(key, dx, dy, z0, z1):
        f = F[key].copy()
        f.translate(V(dx, dy, z0))
        return f.extrude(V(0, 0, z1 - z0))

    ROT = App.Matrix(0, 0, -1, 0,  -1, 0, 0, 0,  0, 1, 0, 0,  0, 0, 0, 1)

    def vmember(key, ycoef, zoff, x0, x1):
        f = F[key].copy()
        f.transformShape(ROT)
        f.translate(V(x0, ycoef, zoff))
        return f.extrude(V(x1 - x0, 0, 0))

    X0 = bb["150"].XMin
    Y150 = bb["150"].YMax - 2.25
    Y14F = bb["14F"].YMax - 2.25
    YG_EXT = 50.5585 - Y150
    YG_INT = 49.9295 - Y150
    RAIL_PC = {"3E": 46.9808, "3D": 47.0033}
    YH = bb["151"].XMin + 2.25
    YS = bb["SILL"].XMin + 2.25

    ext_l = bb["3C"].XMin - X0
    int_r = W - (bb["14F"].XMax - bb["3B"].XMax)
    d = ((int_r - (bb["3A"].XMin - X0)) - (bb["39"].XMax - X0 - ext_l)) / 2.0
    ext_r = bb["39"].XMax - X0 + d
    int_l = bb["3A"].XMin - X0 + d

    ZH = H - bb["151"].YMax
    ZS = -bb["SILL"].YMin
    sash_top = bb["3E"].YMax + ZH
    sash_bot = bb["3D"].YMin + ZS

    def keep_prism(poly_xz):
        w = Part.makePolygon([V(x, -1, z) for x, z in poly_xz] + [V(poly_xz[0][0], -1, poly_xz[0][1])])
        return Part.Face(w).extrude(V(0, 5, 0))

    def mitre(shape, side, xl, xr, zb, zt):
        D = MITRE_D
        poly = {
            "top":    [(xl, zt), (xr, zt), (xr - D, zt - D), (xl + D, zt - D)],
            "bottom": [(xl, zb), (xl + D, zb + D), (xr - D, zb + D), (xr, zb)],
            "left":   [(xl, zb), (xl, zt), (xl + D, zt - D), (xl + D, zb + D)],
            "right":  [(xr, zb), (xr - D, zb + D), (xr - D, zt - D), (xr, zt)],
        }[side]
        return shape.common(keep_prism(poly))

    def main_solid(shp):
        sol = sorted(shp.Solids, key=lambda s: s.Volume)
        return sol[-1]

    def build_sash(name, stile_l, stile_r, xl, xr, yg, dl, dr):
        return {
            name + "_StileL":  mitre(hmember(stile_l, dl, -Y150, sash_bot - 0.1, sash_top + 0.1), "left", xl, xr, sash_bot, sash_top),
            name + "_StileR":  mitre(hmember(stile_r, dr, -Y150, sash_bot - 0.1, sash_top + 0.1), "right", xl, xr, sash_bot, sash_top),
            name + "_RailTop": mitre(vmember("3E", RAIL_PC["3E"] + yg, ZH, xl - 0.1, xr + 0.1), "top", xl, xr, sash_bot, sash_top),
            name + "_RailBot": mitre(vmember("3D", RAIL_PC["3D"] + yg, ZS, xl - 0.1, xr + 0.1), "bottom", xl, xr, sash_bot, sash_top),
        }

    # Head & sill span the clear opening width between the vertical leg tips (clip .. W - clip),
    # so their top/bottom snap clips seat into the horizontal rails while their ends stop dead-flush
    # against Left_A26948 / Right_A26949 without protruding through the vertical exterior/interior faces.
    head = vmember("151", YH, ZH, clip, W - clip)
    sill = vmember("SILL", YS, ZS, clip, W - clip)
    jz0 = 46.7496 + ZS
    jz1 = 53.0385 + ZH
    jamb_l = main_solid(hmember("150", -X0, -Y150, jz0, jz1).cut(head).cut(sill))
    jamb_r = main_solid(hmember("14F", W - bb["14F"].XMax, -Y14F, jz0, jz1).cut(head).cut(sill))

    ext = build_sash("Ext", "3C", "39", ext_l, ext_r, YG_EXT, -X0, -X0 + d)
    inn = build_sash("Int", "3A", "3B", int_l, int_r, YG_INT, -X0 + d, W - bb["14F"].XMax)

    CLR = 1.0 / 32.0
    hd = head.copy()
    hd.translate(V(0, 0, -CLR))
    sl = sill.copy()
    sl.translate(V(0, 0, CLR))
    ext["Ext_StileR"] = main_solid(ext["Ext_StileR"].cut(hd).cut(sl))
    inn["Int_StileL"] = main_solid(inn["Int_StileL"].cut(hd).cut(sl))

    def make_glass(xl, xr, yg):
        zt = 52.183 - GLASS_BITE_CLR + ZH
        zb = 47.5723 + GLASS_BITE_CLR + ZS
        return Part.makeBox(xr - xl, GLASS_T, zt - zb, V(xl, yg - GLASS_T / 2.0, zb))

    g_ext = make_glass(39.2637 + GLASS_BITE_CLR - X0, 41.4698 - GLASS_BITE_CLR - X0 + d, YG_EXT)
    g_int = make_glass(41.7932 + GLASS_BITE_CLR - X0 + d, 43.9800 - GLASS_BITE_CLR + W - bb["14F"].XMax, YG_INT)

    # Compute exact interior sash slide travel (in inches, before world transform)
    movers = [inn[k] for k in inn]
    fixed = [head, sill, jamb_l, jamb_r] + [ext[k] for k in ext]

    def clash(t):
        for m in movers:
            mm = m.copy()
            mm.translate(V(-t, 0, 0))
            for f in fixed:
                if mm.BoundBox.intersect(f.BoundBox) and mm.common(f).Volume > 1e-6:
                    return True
        return False

    assert not clash(0.0), "Slider interior sash clashes when closed"
    lo, hi = 0.0, int_r - int_l
    if not clash(hi):
        lo = hi
    while hi - lo > 1e-3:
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if not clash(mid) else (lo, mid)
    travel_in = round(lo - 0.125, 3)

    # Transform from SliderSash225 local inches (Y=2.25 exterior, Y=0 interior) into
    # 225-Solid-Window-Fix world mm (Y=0.015" exterior, Y=2.265" interior):
    # Pure 180-deg rotation about Z + translate + uniform scale(25.4).
    # (x_s, y_s, z_s) -> (x_left - clip + W - x_s, INSERT_Y_INT - y_s, z_bot - clip + z_s) * scale
    x_origin_in = x_left_in - clip
    z_origin_in = z_bot_in - clip
    tx = (x_origin_in + W) * scale
    ty = INSERT_Y_INT * scale
    tz = z_origin_in * scale
    xfm = App.Matrix(
        -scale, 0, 0, tx,
        0, -scale, 0, ty,
        0, 0, scale, tz,
        0, 0, 0, 1,
    )

    def to_world(shp):
        s = shp.transformGeometry(xfm)
        if s.isValid():
            s = s.removeSplitter()
        return s

    g_slider = doc.addObject("App::DocumentObjectGroup", group_name)
    g_slider.Label = group_name
    parent_part.addObject(g_slider)

    g_frame = doc.addObject("App::DocumentObjectGroup", "Slider_Frame")
    g_frame.Label = "Slider_Frame"
    g_slider.addObject(g_frame)

    g_ext_part = doc.addObject("App::Part", "ExteriorSash")
    g_ext_part.Label = "ExteriorSash"
    g_slider.addObject(g_ext_part)

    g_int_part = doc.addObject("App::Part", "InteriorSash")
    g_int_part.Label = "InteriorSash"
    g_slider.addObject(g_int_part)
    g_int_part.addProperty("App::PropertyFloat", "Travel_in", "Slider", "Opening travel in inches (+X direction)")
    g_int_part.Travel_in = travel_in

    def add_obj(name, shp, col, grp, transp=0):
        o = doc.addObject("Part::Feature", name)
        o.Label = name
        o.Shape = to_world(shp)
        grp.addObject(o)
        if App.GuiUp:
            o.ViewObject.ShapeColor = col
            o.ViewObject.Transparency = transp
        return o

    # Note: after 180-deg Z rotation, Slider local JambLeft (x=0) lands on world RIGHT (+X)
    # and local JambRight (x=W) lands on world LEFT (x_left). Name them by world position!
    o_head = add_obj("Slider_Head", head, COLORS["SLIDER_FRAME"], g_frame)
    o_sill = add_obj("Slider_Sill", sill, COLORS["SLIDER_FRAME"], g_frame)
    o_jl = add_obj("Slider_JambLeft", jamb_r, COLORS["SLIDER_FRAME"], g_frame)
    o_jr = add_obj("Slider_JambRight", jamb_l, COLORS["SLIDER_FRAME"], g_frame)

    for k, s in ext.items():
        add_obj(k, s, COLORS["SLIDER_SASH"], g_ext_part)
    add_obj("Ext_Glass", g_ext, COLORS["GLASS"], g_ext_part, 70)

    for k, s in inn.items():
        add_obj(k, s, COLORS["SLIDER_SASH"], g_int_part)
    add_obj("Int_Glass", g_int, COLORS["GLASS"], g_int_part, 70)

    overall_bb = o_head.Shape.BoundBox
    for o in (o_sill, o_jl, o_jr):
        overall_bb.add(o.Shape.BoundBox)
    print(
        f"  [{group_name}] SliderSash225 sized to W={W:.4f}\" x H={H:.4f}\" (over clips), "
        f"world X=[{overall_bb.XMin/scale:.4f}, {overall_bb.XMax/scale:.4f}] "
        f"Y=[{overall_bb.YMin/scale:.4f}, {overall_bb.YMax/scale:.4f}] "
        f"Z=[{overall_bb.ZMin/scale:.4f}, {overall_bb.ZMax/scale:.4f}], "
        f"sash travel={travel_in:.3f}\""
    )
    return g_slider


# ---------------------------------------------------------------------------
# Main 225 Panel Builder
# ---------------------------------------------------------------------------

def build_225_panel(
    panel_name="225-Solid-Window-Fix",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=None,
    rails=(),
    screw_hole_dia_in=0.201,
    slider_opening_z=None,
    glass_adaptor_opening_z=None,
    glass_adaptor_sides=("bottom", "top", "left", "right"),
    glass_adaptor_openings=None,
    save_path=None,
    scale=INCH,
):
    """Build a 225-series sunroom panel in FreeCAD with optional toggleable Slider & A26950 layers."""
    if height_right_in is None:
        height_right_in = height_in

    profiles = {k: load_225_profile(k) for k in set([left_die, right_die, "A26948"])}

    left_w = DIE_WIDTH[left_die]
    right_w = DIE_WIDTH[right_die]
    x_open_left = left_w
    x_open_right = left_w + opening_width_in
    total_width = x_open_right + right_w

    x_web_left = WEB_FACE_FROM_BACK[left_die]
    x_web_right = total_width - WEB_FACE_FROM_BACK[right_die]
    coped_span_in = x_web_right - x_web_left

    tan_rake = (height_right_in - height_in) / total_width
    cos_rake = 1.0 / math.sqrt(1.0 + tan_rake * tan_rake)
    sin_rake = tan_rake * cos_rake
    is_raked = abs(height_right_in - height_in) > 1e-7

    def z_top_at(x):
        return height_in + tan_rake * x

    max_h = max(height_in, height_right_in)
    if is_raked:
        x_a, x_b = -5.0, total_width + 5.0
        z_ceil = max_h + 15.0
        rake_top_cut = make_xz_prism(
            [(x_a, z_top_at(x_a)), (x_b, z_top_at(x_b)), (x_b, z_ceil), (x_a, z_ceil)],
            scale=scale,
        )
    else:
        rake_top_cut = None

    left_ext_h = (max_h + 5.0) if is_raked else height_in
    left_raw = extrude_profile(
        profiles[left_die],
        origin_in=(0.0, 0.0, left_ext_h),
        u=(0, 1, 0),
        v=(1, 0, 0),
        length_in=left_ext_h,
        scale=scale,
    )
    if rake_top_cut is not None:
        left_raw = left_raw.cut(rake_top_cut)
        if not left_raw.isValid():
            left_raw.fix(1e-6, 1e-6, 1e-6)

    right_ext_h = (max_h + 5.0) if is_raked else height_in
    right_raw = extrude_profile(
        profiles[right_die],
        origin_in=(total_width, 0.0, 0.0),
        u=(0, 1, 0),
        v=(-1, 0, 0),
        length_in=right_ext_h,
        scale=scale,
    )
    if rake_top_cut is not None:
        right_raw = right_raw.cut(rake_top_cut)
        if not right_raw.isValid():
            right_raw.fix(1e-6, 1e-6, 1e-6)

    rail_specs = []
    left_hole_rays = []
    right_hole_rays = []
    hole_report = []

    rail_h = DIE_WIDTH["A26948"]

    for r in rails:
        rname = r["name"]
        pocket_dir = r["pocket_dir"].lower()
        raked_top = r.get("raked_top", False) and is_raked

        if not raked_top:
            zb = r["z_bottom"]
            if pocket_dir == "up":
                origin_in = (x_web_left, 0.0, zb)
                u, v = (0, 1, 0), (0, 0, 1)
                shp = extrude_profile(profiles["A26948"], origin_in, u, v, coped_span_in, scale=scale)
            elif pocket_dir == "down":
                origin_in = (x_web_right, 0.0, zb + rail_h)
                u, v = (0, 1, 0), (0, 0, -1)
                shp = extrude_profile(profiles["A26948"], origin_in, u, v, coped_span_in, scale=scale)
            else:
                raise ValueError(f"Unknown pocket_dir: {pocket_dir}")
        else:
            pad = 3.0
            x_start = x_web_right + pad
            x_end = x_web_left - pad
            raked_len = (x_start - x_end) / cos_rake
            origin_in = (x_start, 0.0, z_top_at(x_start))
            u, v = (0, 1, 0), (sin_rake, 0.0, -cos_rake)
            shp = extrude_profile(profiles["A26948"], origin_in, u, v, raked_len, scale=scale)
            cut_l = make_xz_prism(
                [(x_web_left - 20.0, -5.0), (x_web_left, -5.0), (x_web_left, max_h + 20.0), (x_web_left - 20.0, max_h + 20.0)],
                scale=scale,
            )
            cut_r = make_xz_prism(
                [(x_web_right, -5.0), (x_web_right + 20.0, -5.0), (x_web_right + 20.0, max_h + 20.0), (x_web_right, max_h + 20.0)],
                scale=scale,
            )
            shp = shp.cut(cut_l).cut(cut_r)
            if not shp.isValid():
                shp.fix(1e-6, 1e-6, 1e-6)

        rail_specs.append((rname, shp))

        w = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        axis_lr = w if w[0] > 0 else (-w[0], -w[1], -w[2])
        axis_rl = (-axis_lr[0], -axis_lr[1], -axis_lr[2])

        for cx, cy in profiles["A26948"]["chases"]:
            px, py, pz = map_profile_pt((cx, cy), origin_in, u, v)
            t_l = (x_web_left - px) / axis_lr[0]
            t_r = (x_web_right - px) / axis_lr[0]
            pt_l = (x_web_left, py + t_l * axis_lr[1], pz + t_l * axis_lr[2])
            pt_r = (x_web_right, py + t_r * axis_lr[1], pz + t_r * axis_lr[2])
            left_hole_rays.append((pt_l, axis_lr))
            right_hole_rays.append((pt_r, axis_rl))
            hole_report.append((rname, py, pt_l[2], pt_r[2], math.degrees(math.atan2(axis_lr[2], axis_lr[0]))))

    # Clean flange-notch boxes
    FLANGE_INNER_Y_LO = 0.120
    FLANGE_INNER_Y_HI = 2.160
    z_lo_box = -5.0 * scale
    z_hi_box = (max_h + 15.0) * scale
    flange_notches = [
        Part.makeBox((x_open_left + 5.0) * scale, (FLANGE_INNER_Y_LO + 1.0) * scale, z_hi_box - z_lo_box,
                     V(-5.0 * scale, -1.0 * scale, z_lo_box)),
        Part.makeBox((x_open_left + 5.0) * scale, (3.28 - FLANGE_INNER_Y_HI) * scale, z_hi_box - z_lo_box,
                     V(-5.0 * scale, FLANGE_INNER_Y_HI * scale, z_lo_box)),
        Part.makeBox((total_width - x_open_right + 5.0) * scale, (FLANGE_INNER_Y_LO + 1.0) * scale, z_hi_box - z_lo_box,
                     V(x_open_right * scale, -1.0 * scale, z_lo_box)),
        Part.makeBox((total_width - x_open_right + 5.0) * scale, (3.28 - FLANGE_INNER_Y_HI) * scale, z_hi_box - z_lo_box,
                     V(x_open_right * scale, FLANGE_INNER_Y_HI * scale, z_lo_box)),
    ]

    coped_rails = []
    for rname, shp in rail_specs:
        coped = shp
        for fn in flange_notches:
            coped = coped.cut(fn)
        coped = coped.cut(left_raw).cut(right_raw)
        if not coped.isValid():
            coped.fix(1e-6, 1e-6, 1e-6)
        coped_rails.append((rname, "A26948_H", coped))

    if screw_hole_dia_in and screw_hole_dia_in > 0 and left_hole_rays:
        left_shape = drill_coaxial_holes(
            left_raw, left_hole_rays,
            hole_dia_in=screw_hole_dia_in, back_in=1.5, fwd_in=0.10, scale=scale,
        )
        right_shape = drill_coaxial_holes(
            right_raw, right_hole_rays,
            hole_dia_in=screw_hole_dia_in, back_in=1.5, fwd_in=0.10, scale=scale,
        )
    else:
        left_shape = left_raw
        right_shape = right_raw

    left_label = f"Left_{left_die}_{'Female' if left_die == 'A26948' else 'Male'}"
    right_label = f"Right_{right_die}_{'Female' if right_die == 'A26948' else 'Male'}"
    members = [
        (left_label, left_die, left_shape),
        (right_label, right_die, right_shape),
    ] + coped_rails

    doc_internal = panel_name.replace("-", "_")
    if doc_internal[0].isdigit():
        doc_internal = "P_" + doc_internal
    for existing in list(App.listDocuments()):
        d_ex = App.getDocument(existing)
        if existing == doc_internal or d_ex.Label == panel_name:
            App.closeDocument(existing)

    doc = App.newDocument(doc_internal)
    doc.Label = panel_name

    part_grp = doc.addObject("App::Part", doc_internal)
    part_grp.Label = panel_name

    # Put the structural channel frame in its own toggleable group
    frame_grp = doc.addObject("App::DocumentObjectGroup", "Panel_Frame")
    frame_grp.Label = "Panel_Frame"
    part_grp.addObject(frame_grp)

    for name, color_key, shp in members:
        obj = doc.addObject("Part::Feature", name)
        obj.Label = name
        obj.Shape = shp
        frame_grp.addObject(obj)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = COLORS[color_key]

    print(f"=== 225 Panel {panel_name} Verification (units: inches, scale={scale} mm/in) ===")
    all_bb = members[0][2].BoundBox
    for name, _, shp in members:
        bb = shp.BoundBox
        all_bb.add(bb)
        print(
            f"  {name:28s} valid={shp.isValid()} "
            f"X=[{bb.XMin/scale:7.4f}, {bb.XMax/scale:7.4f}] "
            f"Y=[{bb.YMin/scale:7.4f}, {bb.YMax/scale:7.4f}] "
            f"Z=[{bb.ZMin/scale:7.4f}, {bb.ZMax/scale:7.4f}]"
        )
    print(
        f"  OVERALL FRAME BBOX (in): "
        f"W={all_bb.XLength/scale:.4f}\"  D={all_bb.YLength/scale:.4f}\"  H={all_bb.ZLength/scale:.4f}\""
    )

    interferences = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            n1, _, s1 = members[i]
            n2, _, s2 = members[j]
            vol = s1.common(s2).Volume
            if vol > 1e-4:
                interferences.append((n1, n2, vol))
    print(f"  FRAME INTERFERENCE PAIRS (vol > 1e-4 mm^3): {len(interferences)}")

    # Optional toggleable Layer 2: SliderSash225 in middle opening
    if slider_opening_z is not None:
        add_slider_window(
            doc, part_grp,
            x_open_left, x_open_right,
            slider_opening_z[0], slider_opening_z[1],
            group_name="Slider_Window",
            scale=scale,
        )

    # Optional toggleable A26950 Glass Adaptor layers (single or multiple fixed openings)
    adp_list = list(glass_adaptor_openings) if glass_adaptor_openings else []
    if glass_adaptor_opening_z is not None:
        adp_list.append({
            "group_name": "Top_Glass_Adaptors",
            "prefix": "Top",
            "z": glass_adaptor_opening_z,
            "sides": glass_adaptor_sides,
        })

    for spec in adp_list:
        z_spec = spec["z"]
        z_adp_bot = z_spec[0]
        if z_spec[1] == "raked_top":
            z_adp_tl = z_top_at(x_open_left) - rail_h / cos_rake
            z_adp_tr = z_top_at(x_open_right) - rail_h / cos_rake
        elif len(z_spec) == 3:
            z_adp_tl, z_adp_tr = z_spec[1], z_spec[2]
        else:
            z_adp_tl = z_adp_tr = z_spec[1]
        add_glass_adaptors(
            doc, part_grp,
            x_open_left, x_open_right,
            z_adp_bot, z_adp_tl, z_adp_tr,
            group_name=spec.get("group_name", "Top_Glass_Adaptors"),
            prefix=spec.get("prefix", "Top"),
            sides=spec.get("sides", ("bottom", "top", "left", "right")),
            scale=scale,
        )

    doc.recompute()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        doc.saveAs(save_path)
        print(f"Saved: {save_path}")

    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.ActiveDocument = Gui.getDocument(doc.Name)
        Gui.ActiveDocument.ActiveView.viewIsometric()
        Gui.SendMsgToActiveView("ViewFit")

    return doc
