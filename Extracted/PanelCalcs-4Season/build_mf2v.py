"""Parametric 4-Season Sunroom Panel Builder for FreeCAD.

Builds individual panel assemblies directly from the authoritative die DXF files
in 4SeasonDrawings, using pure rigid 3D rotations (no mirrored extrusions) at
true 1:1 scale (1 inch = 25.4 mm for FreeCAD's Building US / Imperial units).

Automatically detects the 0.144" screw chase cavities in horizontal members and
drills coaxial clearance holes (default #10 clearance, 0.201" dia) through the
left and right vertical members.

Usage inside FreeCAD:
    exec(open(r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/panels/build_mf2v.py').read())
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
    """Map die-local 2D point (inches) into 3D world coordinates (inches)."""
    return (
        origin_in[0] + pt_2d[0] * u[0] + pt_2d[1] * v[0],
        origin_in[1] + pt_2d[0] * u[1] + pt_2d[1] * v[1],
        origin_in[2] + pt_2d[0] * u[2] + pt_2d[1] * v[2],
    )


def extrude_profile(profile, origin_in, u, v, length_in, scale=INCH):
    """Place a 2D die profile on plane (origin, u, v) and extrude along w = u x v.

    All positions and length are given in inches and scaled by `scale` (25.4 mm/in).
    `u` maps local +x_die (exterior -> interior).
    `v` maps local +y_die (leg tips -> fin tip, or bottom fin -> top fin).
    Extrusion vector is `length_in * (u x v)` so every member is a true rigid
    orientation of the physical extrusion die (det = +1).
    """
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


def drill_x_holes(solid, yz_centers_in, x_start_in, x_end_in, hole_dia_in, scale=INCH):
    """Drill coaxial cylindrical holes along +X through a vertical member."""
    r = (hole_dia_in / 2.0) * scale
    length = (x_end_in - x_start_in) * scale
    out = solid
    for y_in, z_in in yz_centers_in:
        cyl = Part.makeCylinder(
            r,
            length,
            V(x_start_in * scale, y_in * scale, z_in * scale),
            V(1, 0, 0),
        )
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
    mullion_top_heights_in=(25.125,),
    screw_hole_dia_in=0.201,  # #10 screw clearance (#7 drill = 0.201")
    save_path=None,
    scale=INCH,
):
    """Build a 4-season sunroom panel in FreeCAD.

    World coordinate convention (looking at the panel from EXTERIOR):
      +X : Left -> Right  (X=0 at left vertical outer leg tips)
      +Y : Exterior (Y=0) -> Interior (Y=4.18236")
      +Z : Bottom (Z=0) -> Top (Z=height_in)

    Dimension convention (matching M-F-2v.dxf):
      - `opening_width_in`: body-face to body-face width between left & right verticals
      - `height_in`: overall height from bottom leg tips to top leg tips
      - `mullion_top_heights_in`: height from Z=0 to top flat body face of each T04 mullion
      - `screw_hole_dia_in`: clearance hole dia drilled through verticals coaxial with
        each horizontal member's 0.144" screw chases (set None or 0 to disable)
    """
    profiles = {k: extract_profile(DIE_FILES[k]) for k in ("T02", "T03", "T04")}

    # Exact die flat body thicknesses (from leg tips to flat body face)
    BODY_THICKNESS = {"T02": 1.000, "T03": 1.209}
    T04_TOP_BODY_Y = 1.625  # 0.625 bottom fin + 1.000 body

    left_body = BODY_THICKNESS[left_die]
    right_body = BODY_THICKNESS[right_die]
    x_open_left = left_body
    x_open_right = left_body + opening_width_in
    total_width = x_open_right + right_body

    # 1. Left vertical: u=(0,1,0), v=(1,0,0) => w=(0,0,-1), extrude Z=height -> 0
    left_raw = extrude_profile(
        profiles[left_die],
        origin_in=(0.0, 0.0, height_in),
        u=(0, 1, 0),
        v=(1, 0, 0),
        length_in=height_in,
        scale=scale,
    )

    # 2. Right vertical: u=(0,1,0), v=(-1,0,0) => w=(0,0,+1), extrude Z=0 -> height
    right_raw = extrude_profile(
        profiles[right_die],
        origin_in=(total_width, 0.0, 0.0),
        u=(0, 1, 0),
        v=(-1, 0, 0),
        length_in=height_in,
        scale=scale,
    )

    # Helper to build a horizontal member and record its world (Y, Z) screw chase centers
    horizontal_specs = []
    hole_schedule = []

    def add_horizontal(name, die, origin_in, u, v, length_in):
        shp = extrude_profile(profiles[die], origin_in, u, v, length_in, scale=scale)
        horizontal_specs.append((name, die, shp))
        for cx, cy in profiles[die]["chases"]:
            _, wy, wz = map_profile_pt((cx, cy), origin_in, u, v)
            hole_schedule.append((name, wy, wz))

    # 3. Bottom T02 horizontal
    add_horizontal(
        "Bottom_T02_Male", "T02",
        origin_in=(x_open_left, 0.0, 0.0),
        u=(0, 1, 0), v=(0, 0, 1),
        length_in=opening_width_in,
    )

    # 4. Top T02 horizontal
    add_horizontal(
        "Top_T02_Male", "T02",
        origin_in=(x_open_right, 0.0, height_in),
        u=(0, 1, 0), v=(0, 0, -1),
        length_in=opening_width_in,
    )

    # 5. Horizontal T04 mullion(s)
    for idx, z_top in enumerate(mullion_top_heights_in, start=1):
        z_origin = z_top - T04_TOP_BODY_Y
        suffix = f"_{idx}" if len(mullion_top_heights_in) > 1 else ""
        add_horizontal(
            f"Mullion{suffix}_T04_Horizontal", "T04",
            origin_in=(x_open_left, 0.0, z_origin),
            u=(0, 1, 0), v=(0, 0, 1),
            length_in=opening_width_in,
        )

    # Cope all horizontal members cleanly around the un-drilled vertical solids first
    horizontals = []
    for name, die, shp in horizontal_specs:
        coped = shp.cut(left_raw).cut(right_raw)
        if not coped.isValid():
            coped.fix(1e-6, 1e-6, 1e-6)
        horizontals.append((name, die, coped))

    # Drill coaxial #10 clearance screw holes through left & right vertical webs
    yz_centers = [(wy, wz) for _, wy, wz in hole_schedule]
    if screw_hole_dia_in and screw_hole_dia_in > 0 and yz_centers:
        left_shape = drill_x_holes(
            left_raw, yz_centers,
            x_start_in=-0.25, x_end_in=x_open_left + 0.10,
            hole_dia_in=screw_hole_dia_in, scale=scale,
        )
        right_shape = drill_x_holes(
            right_raw, yz_centers,
            x_start_in=x_open_right - 0.10, x_end_in=total_width + 0.25,
            hole_dia_in=screw_hole_dia_in, scale=scale,
        )
    else:
        left_shape = left_raw
        right_shape = right_raw

    members = [
        ("Left_T02_Male", left_die, left_shape),
        ("Right_T03_Female", right_die, right_shape),
    ] + horizontals

    # Create or replace FreeCAD document
    doc_internal = panel_name.replace("-", "_")
    for existing in list(App.listDocuments()):
        d_ex = App.getDocument(existing)
        if existing == doc_internal or d_ex.Label == panel_name:
            App.closeDocument(existing)

    doc = App.newDocument(doc_internal)
    doc.Label = panel_name

    # Wrap all members in a single App::Part container so the panel can be placed as a unit later
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
    all_bb = members[0][2].BoundBox
    for name, _, shp in members:
        bb = shp.BoundBox
        all_bb.add(bb)
        print(
            f"  {name:24s} valid={shp.isValid()} "
            f"X=[{bb.XMin/scale:7.4f}, {bb.XMax/scale:7.4f}] "
            f"Y=[{bb.YMin/scale:7.4f}, {bb.YMax/scale:7.4f}] "
            f"Z=[{bb.ZMin/scale:7.4f}, {bb.ZMax/scale:7.4f}]"
        )
    print(
        f"  OVERALL BBOX (in): "
        f"W={all_bb.XLength/scale:.4f}\"  D={all_bb.YLength/scale:.4f}\"  H={all_bb.ZLength/scale:.4f}\""
    )

    if screw_hole_dia_in and hole_schedule:
        print(f"  SCREW HOLES (dia={screw_hole_dia_in:.3f}\" / #10 clearance, {len(hole_schedule)} per vertical = {2*len(hole_schedule)} total):")
        for hname, wy, wz in sorted(hole_schedule, key=lambda r: (r[2], r[1])):
            side = "Exterior" if wy < 2.0 else "Interior"
            print(f"    {hname:24s} ({side:8s}): Y={wy:.4f}\"  Z={wz:.4f}\"")

    # Check pairwise interference
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

    # Fast face-alignment contact check
    for hname, _, hshp in members[2:]:
        hb = hshp.BoundBox
        gap_l = hb.XMin - x_open_left * scale
        gap_r = x_open_right * scale - hb.XMax
        print(f"  CONTACT {hname:24s}: left_face_err={gap_l:+.6f} mm, right_face_err={gap_r:+.6f} mm")

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


if __name__ == "__main__" or True:
    build_panel(
        panel_name="M-F-2v",
        left_die="T02",
        right_die="T03",
        opening_width_in=30.0,
        height_in=80.0,
        mullion_top_heights_in=(25.125,),
        screw_hole_dia_in=0.201,
        save_path=os.path.join(OUT_DIR, "M-F-2v.FCStd"),
        scale=INCH,
    )
