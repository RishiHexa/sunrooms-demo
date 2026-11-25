"""Reusable Parametric 4-Season Sunroom Panel Builder for FreeCAD.

Builds individual panel assemblies directly from the authoritative die DXF files
in 4SeasonDrawings, using pure rigid 3D rotations (no mirrored extrusions) at
true 1:1 scale (1 inch = 25.4 mm for FreeCAD's Building US / Imperial units).

Supports both rectangular panels (height_left == height_right) and trapezoidal /
raked panels (height_left != height_right), with automatic bevel top cuts,
raked Top_T02_Male coping, and coaxial #10 clearance screw holes aligned with
each horizontal/raked member's 0.144" screw chase axes.
"""

import math
import os
from collections import defaultdict
import FreeCAD as App
import Part
from FreeCAD import Vector as V

DXF_DIR = r"C:\DaVinci_Works\Lifestyle\Sunroom-Drawings\4SeasonDrawings"
OUT_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\season4\panels"

INCH = 25.4  # FreeCAD internal units are mm (true 1:1 scale for Building US ft-in)

DIE_FILES = {
    "T02": os.path.join(DXF_DIR, "T02GR-Male.dxf"),
    "T03": os.path.join(DXF_DIR, "T03GR-Female.dxf"),
    "T04": os.path.join(DXF_DIR, "T04GR-Horizontal.dxf"),
}

COLORS = {
    "T02": (0.35, 0.55, 0.85),  # Male (steel blue)
    "T03": (0.85, 0.40, 0.40),  # Female (red)
    "T04": (0.95, 0.65, 0.25),  # Horizontal mullion (amber)
}

# Exact die flat-body and fin constants (inches)
BODY_THICKNESS = {"T02": 1.000, "T03": 1.209}
FIN_HEIGHT = 0.625
T04_TOP_BODY_Y = 1.625   # 0.625 bottom fin + 1.000 body
T04_TOP_FIN_Y = 2.250    # 0.625 bottom fin + 1.000 body + 0.625 top fin


# ---------------------------------------------------------------------------
# Pure-Python DXF segment parser, closed-loop stitcher & screw-chase detector
# ---------------------------------------------------------------------------

def _parse_dxf_segments(path, layers=("0",)):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [line.rstrip("\r\n") for line in f]
    pairs = []
    i = 0
    while i + 1 < len(lines):
        try:
            code = int(lines[i].strip())
        except ValueError:
            i += 1
            continue
        pairs.append((code, lines[i + 1]))
        i += 2

    ents = []
    in_ent = False
    cur = None
    i = 0
    while i < len(pairs):
        if pairs[i] == (0, "SECTION") and i + 1 < len(pairs) and pairs[i + 1] == (2, "ENTITIES"):
            in_ent = True
            i += 2
            continue
        if in_ent and pairs[i] == (0, "ENDSEC"):
            if cur:
                ents.append(cur)
            break
        if in_ent:
            c, v = pairs[i]
            if c == 0:
                if cur:
                    ents.append(cur)
                cur = {"type": v.strip(), "pairs": []}
            elif cur is not None:
                cur["pairs"].append((c, v))
        i += 1

    raw = []
    for e in ents:
        d = {}
        for c, v in e["pairs"]:
            d.setdefault(c, []).append(v)
        layer = d.get(8, ["0"])[0].strip()
        if layers and layer not in layers:
            continue
        t = e["type"]
        if t == "LINE":
            a = (float(d[10][0]), float(d[20][0]))
            b = (float(d[11][0]), float(d[21][0]))
            if math.dist(a, b) > 1e-7:
                raw.append({"k": "line", "a": a, "b": b})
        elif t == "ARC":
            c = (float(d[10][0]), float(d[20][0]))
            r = float(d[40][0])
            a0 = math.radians(float(d[50][0]))
            a1 = math.radians(float(d[51][0]))
            if a1 <= a0:
                a1 += 2 * math.pi
            raw.append({
                "k": "arc", "c": c, "r": r, "a0": a0, "a1": a1,
                "a": (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0)),
                "b": (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1)),
            })
    return raw


def _seg_pts(s, flip, step=0.01):
    if s["k"] == "line":
        p = [s["a"], s["b"]]
    else:
        n = max(2, int((s["a1"] - s["a0"]) * s["r"] / step) + 1)
        p = [
            (
                s["c"][0] + s["r"] * math.cos(s["a0"] + (s["a1"] - s["a0"]) * i / n),
                s["c"][1] + s["r"] * math.sin(s["a0"] + (s["a1"] - s["a0"]) * i / n),
            )
            for i in range(n + 1)
        ]
    return p[::-1] if flip else p


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def extract_profile(path, tol=2e-4, chase_dia_in=0.144, chase_tol_in=0.005):
    raw = _parse_dxf_segments(path, layers=("0",))
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))
    idx = defaultdict(list)
    for i, s in enumerate(raw):
        for end in ("a", "b"):
            k = key(s[end])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    idx[(k[0] + dx, k[1] + dy)].append((i, end))

    used = [False] * len(raw)
    chains = []
    open_chains = []
    for i in range(len(raw)):
        if used[i]:
            continue
        used[i] = True
        chain = [(i, False)]
        cur = raw[i]["b"]
        start = raw[i]["a"]
        while True:
            if math.dist(cur, start) < tol and len(chain) > 1:
                break
            nxt = None
            for j, end in idx[key(cur)]:
                if used[j]:
                    continue
                if math.dist(raw[j][end], cur) < tol:
                    nxt = (j, end == "b")
                    break
            if nxt is None:
                break
            used[nxt[0]] = True
            chain.append(nxt)
            cur = raw[nxt[0]]["a"] if nxt[1] else raw[nxt[0]]["b"]
        if math.dist(cur, start) < tol and len(chain) > 1:
            chains.append(chain)
        else:
            open_chains.append(chain)

    if open_chains:
        raise RuntimeError(f"Profile {path} has {len(open_chains)} open chains")

    loops = []
    for ch in chains:
        segs = []
        pts = []
        for j, fl in ch:
            s = raw[j]
            a, b = (s["b"], s["a"]) if fl else (s["a"], s["b"])
            if s["k"] == "line":
                segs.append(["line", list(a), list(b)])
            else:
                am = (s["a0"] + s["a1"]) / 2.0
                m = (s["c"][0] + s["r"] * math.cos(am), s["c"][1] + s["r"] * math.sin(am))
                segs.append(["arc", list(a), list(m), list(b)])
            pts.extend(_seg_pts(s, fl)[:-1])
        for k in range(len(segs)):
            segs[k][1] = list(segs[k - 1][-1])
        area = 0.5 * sum(
            pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1]
            for k in range(len(pts))
        )
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        loops.append({"segs": segs, "pts": pts, "area": area, "bb": (min(xs), min(ys), max(xs), max(ys))})

    x0 = min(l["bb"][0] for l in loops)
    y0 = min(l["bb"][1] for l in loops)
    x1 = max(l["bb"][2] for l in loops)
    y1 = max(l["bb"][3] for l in loops)

    for L in loops:
        parents = [
            j for j, M in enumerate(loops)
            if M is not L and abs(M["area"]) > abs(L["area"])
            and M["bb"][0] <= L["bb"][0] + 1e-6 and M["bb"][1] <= L["bb"][1] + 1e-6
            and M["bb"][2] >= L["bb"][2] - 1e-6 and M["bb"][3] >= L["bb"][3] - 1e-6
            and _point_in_poly(L["pts"][0], M["pts"])
        ]
        L["depth"] = len(parents)

    norm_loops = [
        {
            "segs": [[s[0]] + [[p[0] - x0, p[1] - y0] for p in s[1:]] for s in L["segs"]],
            "depth": L["depth"],
        }
        for L in loops
    ]

    # Detect C-shaped screw chase cavities (0.144" inner diameter, sweep > 180 deg)
    target_r = chase_dia_in / 2.0
    chases = []
    for s in raw:
        if s["k"] == "arc":
            sweep_deg = math.degrees(s["a1"] - s["a0"])
            if abs(s["r"] - target_r) <= chase_tol_in and sweep_deg > 180.0:
                pt = (s["c"][0] - x0, s["c"][1] - y0)
                if not any(math.dist(pt, existing) < 1e-3 for existing in chases):
                    chases.append(pt)
    chases.sort(key=lambda p: (round(p[0], 4), round(p[1], 4)))

    return {"size": (x1 - x0, y1 - y0), "loops": norm_loops, "chases": chases}


# ---------------------------------------------------------------------------
# 3D Solid Builder (right-handed basis u x v = w, no mirroring)
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
                if (a - b).Length > 1e-6:
                    edges.append(Part.LineSegment(a, b).toShape())
            else:
                edges.append(Part.Arc(map_pt(s[1]), map_pt(s[2]), map_pt(s[3])).toShape())
        w = Part.Wire(edges)
        if not w.isClosed():
            w.fixWire(None, 1e-5)
        wires.append(w)

    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    if not face.isValid():
        face.fix(1e-6, 1e-6, 1e-6)
    solid = face.extrude(w_vec * (length_in * scale))
    if not solid.isValid():
        solid.fix(1e-6, 1e-6, 1e-6)
    return solid


def make_xz_prism(xz_pts_in, y_lo_in=-2.0, y_hi_in=8.0, scale=INCH):
    """Build a cutting prism from a 2D polygon in XZ extruded along +Y."""
    pts = [V(x * scale, y_lo_in * scale, z * scale) for x, z in xz_pts_in]
    wire = Part.makePolygon(pts + [pts[0]])
    return Part.Face(wire).extrude(V(0, (y_hi_in - y_lo_in) * scale, 0))


def drill_coaxial_holes(solid, hole_rays, hole_dia_in, back_in=2.0, fwd_in=0.25, scale=INCH):
    """Drill coaxial cylindrical holes along each ray (anchor_in, dir_unit).

    Each ray is `(anchor_pt_in, dir_vec)` where `anchor_pt_in` is the exact point
    where the horizontal chase axis meets the vertical body face and `dir_vec` is
    the unit vector pointing from outside the vertical INTO the chase.
    """
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


def build_panel(
    panel_name="M-F-2v",
    left_die="T02",
    right_die="T03",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=None,
    mullion_top_heights_in=(25.125,),
    include_bottom=True,
    screw_hole_dia_in=0.201,
    save_path=None,
    scale=INCH,
):
    """Build a 4-season sunroom panel (rectangular or trapezoidal) in FreeCAD.

    World coordinate convention (looking at the panel from EXTERIOR):
      +X : Left -> Right  (X=0 at left vertical outer leg tips)
      +Y : Exterior (Y=0) -> Interior (Y=4.18236")
      +Z : Bottom (Z=0) -> Top (Z=height_in at X=0, height_right_in at X=total_width)
    """
    if height_right_in is None:
        height_right_in = height_in

    profiles = {k: extract_profile(DIE_FILES[k]) for k in ("T02", "T03", "T04")}

    left_body = BODY_THICKNESS[left_die]
    right_body = BODY_THICKNESS[right_die]
    x_open_left = left_body
    x_open_right = left_body + opening_width_in
    total_width = x_open_right + right_body

    # Top rake geometry: straight line from (0, height_in) to (total_width, height_right_in)
    tan_rake = (height_right_in - height_in) / total_width
    cos_rake = 1.0 / math.sqrt(1.0 + tan_rake * tan_rake)
    sin_rake = tan_rake * cos_rake
    is_raked = abs(height_right_in - height_in) > 1e-7

    def z_top_at(x):
        return height_in + tan_rake * x

    max_h = max(height_in, height_right_in)

    # Top bevel cutting prism (removes everything above Z = z_top_at(X))
    if is_raked:
        x_a, x_b = -5.0, total_width + 5.0
        z_ceil = max_h + 15.0
        rake_top_cut = make_xz_prism(
            [(x_a, z_top_at(x_a)), (x_b, z_top_at(x_b)), (x_b, z_ceil), (x_a, z_ceil)],
            scale=scale,
        )
    else:
        rake_top_cut = None

    # 1. Left vertical
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

    # 2. Right vertical
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

    horizontal_specs = []
    left_hole_rays = []
    right_hole_rays = []
    hole_report = []

    def add_span_member(name, die, origin_in, u, v, length_in, end_cuts=None):
        shp = extrude_profile(profiles[die], origin_in, u, v, length_in, scale=scale)
        if end_cuts:
            for c in end_cuts:
                shp = shp.cut(c)
            if not shp.isValid():
                shp.fix(1e-6, 1e-6, 1e-6)
        horizontal_specs.append((name, die, shp))

        # Extrusion axis unit vector w = u x v; ensure axis points left->right (+X)
        w = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        axis_lr = w if w[0] > 0 else (-w[0], -w[1], -w[2])
        axis_rl = (-axis_lr[0], -axis_lr[1], -axis_lr[2])

        for cx, cy in profiles[die]["chases"]:
            px, py, pz = map_profile_pt((cx, cy), origin_in, u, v)
            # Intersect chase line P + t * axis_lr with X = x_open_left and X = x_open_right
            t_l = (x_open_left - px) / axis_lr[0]
            t_r = (x_open_right - px) / axis_lr[0]
            pt_l = (x_open_left, py + t_l * axis_lr[1], pz + t_l * axis_lr[2])
            pt_r = (x_open_right, py + t_r * axis_lr[1], pz + t_r * axis_lr[2])
            left_hole_rays.append((pt_l, axis_lr))
            right_hole_rays.append((pt_r, axis_rl))
            hole_report.append((name, py, pt_l[2], pt_r[2], math.degrees(math.atan2(axis_lr[2], axis_lr[0]))))

    # 3. Bottom T02 horizontal (optional; omitted on door frames)
    if include_bottom:
        add_span_member(
            "Bottom_T02_Male", "T02",
            origin_in=(x_open_left, 0.0, 0.0),
            u=(0, 1, 0), v=(0, 0, 1),
            length_in=opening_width_in,
        )

    # 4. Top T02 member (level or raked along roof slope)
    if not is_raked:
        add_span_member(
            "Top_T02_Male", "T02",
            origin_in=(x_open_right, 0.0, height_in),
            u=(0, 1, 0), v=(0, 0, -1),
            length_in=opening_width_in,
        )
    else:
        # Extrude generously past X=x_open_left and X=x_open_right, then trim vertically at both body faces
        pad = 3.0
        x_start = x_open_right + pad
        x_end = x_open_left - pad
        raked_len = (x_start - x_end) / cos_rake
        cut_left = make_xz_prism(
            [(x_open_left - 20.0, -5.0), (x_open_left, -5.0), (x_open_left, max_h + 20.0), (x_open_left - 20.0, max_h + 20.0)],
            scale=scale,
        )
        cut_right = make_xz_prism(
            [(x_open_right, -5.0), (x_open_right + 20.0, -5.0), (x_open_right + 20.0, max_h + 20.0), (x_open_right, max_h + 20.0)],
            scale=scale,
        )
        add_span_member(
            "Top_T02_Male", "T02",
            origin_in=(x_start, 0.0, z_top_at(x_start)),
            u=(0, 1, 0),
            v=(sin_rake, 0.0, -cos_rake),
            length_in=raked_len,
            end_cuts=[cut_left, cut_right],
        )

    # 5. Horizontal T04 mullion(s), sorted bottom-to-top
    sorted_mullions = sorted(mullion_top_heights_in)
    for idx, z_top in enumerate(sorted_mullions, start=1):
        z_origin = z_top - T04_TOP_BODY_Y
        suffix = f"_{idx}" if len(sorted_mullions) > 1 else ""
        add_span_member(
            f"Mullion{suffix}_T04_Horizontal", "T04",
            origin_in=(x_open_left, 0.0, z_origin),
            u=(0, 1, 0), v=(0, 0, 1),
            length_in=opening_width_in,
        )

    # Cope all horizontal/raked members cleanly around un-drilled vertical solids
    horizontals = []
    for name, die, shp in horizontal_specs:
        coped = shp.cut(left_raw).cut(right_raw)
        if not coped.isValid():
            coped.fix(1e-6, 1e-6, 1e-6)
        horizontals.append((name, die, coped))

    # Drill coaxial #10 clearance screw holes through left & right vertical webs
    if screw_hole_dia_in and screw_hole_dia_in > 0 and left_hole_rays:
        left_shape = drill_coaxial_holes(
            left_raw, left_hole_rays,
            hole_dia_in=screw_hole_dia_in, back_in=2.0, fwd_in=0.15, scale=scale,
        )
        right_shape = drill_coaxial_holes(
            right_raw, right_hole_rays,
            hole_dia_in=screw_hole_dia_in, back_in=2.0, fwd_in=0.15, scale=scale,
        )
    else:
        left_shape = left_raw
        right_shape = right_raw

    left_label = f"Left_{left_die}_{'Male' if left_die == 'T02' else 'Female'}"
    right_label = f"Right_{right_die}_{'Male' if right_die == 'T02' else 'Female'}"
    members = [
        (left_label, left_die, left_shape),
        (right_label, right_die, right_shape),
    ] + horizontals

    # Create or replace FreeCAD document with the same name/label
    doc_internal = panel_name.replace("-", "_")
    for existing in list(App.listDocuments()):
        d_ex = App.getDocument(existing)
        if existing == doc_internal or d_ex.Label == panel_name:
            App.closeDocument(existing)

    doc = App.newDocument(doc_internal)
    doc.Label = panel_name

    part_grp = doc.addObject("App::Part", doc_internal)
    part_grp.Label = panel_name

    for name, die, shp in members:
        obj = doc.addObject("Part::Feature", name)
        obj.Label = name
        obj.Shape = shp
        part_grp.addObject(obj)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = COLORS[die]

    doc.recompute()

    # Verification report
    print(f"=== Panel {panel_name} Verification (units: inches, scale={scale} mm/in) ===")
    if is_raked:
        print(
            f"  RAKE: H_left={height_in:.4f}\" (at X=0) -> H_right={height_right_in:.4f}\" "
            f"(at X={total_width:.4f}\"), slope={tan_rake:.6f} ({math.degrees(math.atan(tan_rake)):.3f} deg)"
        )
    all_bb = members[0][2].BoundBox
    for name, _, shp in members:
        bb = shp.BoundBox
        all_bb.add(bb)
        print(
            f"  {name:26s} valid={shp.isValid()} "
            f"X=[{bb.XMin/scale:7.4f}, {bb.XMax/scale:7.4f}] "
            f"Y=[{bb.YMin/scale:7.4f}, {bb.YMax/scale:7.4f}] "
            f"Z=[{bb.ZMin/scale:7.4f}, {bb.ZMax/scale:7.4f}]"
        )
    print(
        f"  OVERALL BBOX (in): "
        f"W={all_bb.XLength/scale:.4f}\"  D={all_bb.YLength/scale:.4f}\"  H={all_bb.ZLength/scale:.4f}\""
    )

    if screw_hole_dia_in and hole_report:
        print(f"  SCREW HOLES (dia={screw_hole_dia_in:.3f}\" / #10 clearance, {len(hole_report)} per vertical = {2*len(hole_report)} total):")
        for hname, wy, zl, zr, ang in sorted(hole_report, key=lambda r: (r[2], r[1])):
            side = "Exterior" if wy < 2.0 else "Interior"
            print(f"    {hname:26s} ({side:8s}): Y={wy:.4f}\"  Z_left={zl:.4f}\"  Z_right={zr:.4f}\"  angle={ang:+.3f} deg")

    interferences = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            n1, _, s1 = members[i]
            n2, _, s2 = members[j]
            vol = s1.common(s2).Volume
            if vol > 1e-4:
                interferences.append((n1, n2, vol))
    print(f"  INTERFERENCE PAIRS (vol > 1e-4 mm^3): {len(interferences)}")
    for pair in interferences:
        print("   ", pair)

    for hname, _, hshp in members[2:]:
        hb = hshp.BoundBox
        gap_l = hb.XMin - x_open_left * scale
        gap_r = x_open_right * scale - hb.XMax
        print(f"  CONTACT {hname:26s}: left_face_err={gap_l:+.6f} mm, right_face_err={gap_r:+.6f} mm")

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
