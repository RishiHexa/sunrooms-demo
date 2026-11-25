"""4-season roof: 4" foam panels (0.025 skins), A64048 back channel at the house, GF50 gutter at the low
end, A66048 fascia up both sloped sides, wood wedge on the level front top channel, 1" stand-in seams.
World as members4.py: X along front 0->216, Y front(outside)=0 -> house=144, Z up."""
import json, math, sys, ezdxf
sys.path.insert(0,'/home/claude/s4')
from loops import *
FW, DP = 216.0, 144.0
TAN = 12.0/144.0; COS = 1/math.sqrt(1+TAN*TAN); SIN = TAN*COS
LIP = 0.6712; CH_D_IN = 4.4082            # front top channel: lip outboard of Y=0, inner edge
OVER_SIDE, OVER_FRONT = 16.0, 24.0
PANEL_W = 46.3125; SKIN = 0.025; PANEL_T = 4.0
SEAM_H, SEAM_T, SEAM_CUT_LO, SEAM_CUT_HI = 1.0, 0.10, 1.0, 3.0
t = (0.0, COS, SIN)            # up the slope, toward the house
n = (0.0, -SIN, COS)           # roof normal, up
# roof underside plane touches the outer edge of the front top-channel drip lip (Y=-LIP, Z=84)
def z_under(y): return 84.0 + TAN*(y + LIP)
def P(y_on_underside, h):      # point on the underside at plan Y, offset h along the normal (x omitted)
    return (0.0, y_on_underside + h*n[1], z_under(y_on_underside) + h*n[2])
def add3(a, b, k=1.0): return tuple(a[i] + k*b[i] for i in range(3))

def profile(k):
    d = ezdxf.readfile(f'roof/{k}.dxf'); L, _ = stitch(raw_segments(d.modelspace(), {'0'}))
    assert len(L) == 1
    return L[0]
def place(loop, f):            # f(px,py) -> world xyz
    segs = [[s[0]] + [list(f(p[0], p[1])) for p in s[1:]] for s in loop['segs']]
    return [{'segs': segs, 'depth': 0}]
def pts(loop): return loop['pts']
def cross(loop, axis, c):
    """coordinates where the profile outline crosses the line (axis=0: x=c -> ys ; axis=1: y=c -> xs)"""
    p = loop['pts']; out = []
    for i in range(len(p)):
        a, b = p[i], p[(i+1) % len(p)]
        if (a[axis] - c)*(b[axis] - c) < 0:
            k = (c - a[axis])/(b[axis] - a[axis]); out.append(a[1-axis] + k*(b[1-axis] - a[1-axis]))
    return sorted(out)

MEM = []
def add(name, part, group, loops, extrude, cuts=None, meta=None):
    MEM.append({'name': name, 'part': part, 'group': group, 'loops': loops, 'extrude': list(extrude),
                'cuts': cuts or [], 'meta': meta or {}})
def quad_x(c, x0):             # 4 corners (y,z) -> closed line loop in plane X=x0
    segs = [['line', [x0, c[i][1], c[i][2]], [x0, c[(i+1) % 4][1], c[(i+1) % 4][2]]] for i in range(4)]
    return [{'segs': segs, 'depth': 0}]
def prism_xy(poly, z0, z1): return {'poly': [[p[0], p[1], z0] for p in poly], 'vec': [0, 0, z1 - z0]}

# ---------------- back channel A64048 ----------------
bc = profile('A64048'); bp = pts(bc)
ys_ = cross(bc, 1, 5.5); x_leg_in = ys_[1]; x_leg2_in = ys_[2]            # leg inner faces at y=5.5
yy_ = cross(bc, 0, 16.5); y_web_out = yy_[-1]; y_web_in = yy_[-2]        # web faces at x=16.5
x_min = min(p[0] for p in bp)
# die +x -> n (ring on top), die +y -> t (web at the house). bottom-leg inner face on the underside plane.
# lowest web corner (x_min, y_web_out) touches the house wall Y=144.
dy = -(x_min - x_leg_in)*n[1]              # Y shift of that corner from the anchor
Oy = DP - dy - 0.0
O = P(Oy, 0.0)
def f_bc(px, py, x=0.0):
    w = add3(add3(O, n, px - x_leg_in), t, py - y_web_out); return (x, w[1], w[2])
X0, X1 = -OVER_SIDE, FW + OVER_SIDE
add('ROOF BackChannel', 'A64048', 'roofalu', place(bc, lambda a, b: f_bc(a, b, X0)), (X1 - X0, 0, 0))
y_stop = min([v for xx in (14.3,14.5,14.7,14.9,15.1,15.3,15.5,15.7) for v in cross(bc,0,xx) if 6.2 < v < y_web_in] + [y_web_in])
top_end = add3(O, t, y_stop - y_web_out)             # panel upper end: against the bosses on the web (else the web)
s_top = top_end[1]                                   # Y of the panel's top end on the underside line
print(f"back channel: slot {x_leg_in:.4f}..{x_leg2_in:.4f} = {x_leg2_in-x_leg_in:.4f}  web out/in {y_web_out:.4f}/{y_web_in:.4f} stop {y_stop:.4f}  panel top end at underside Y={s_top:.4f}")

# ---------------- panels ----------------
y_lo = -OVER_FRONT                                   # panel lower end: underside corner 24" in front of the wall
L_under = (s_top - y_lo)/COS
def corners(h0, h1):
    a = P(y_lo, h0); b = P(y_lo, h1); c = add3(b, t, L_under); d = add3(a, t, L_under)
    return [a, b, c, d]
widths = []; x = X0
while X1 - x > 1e-6:
    w = min(PANEL_W, X1 - x); widths.append((x, w)); x += w
print("panels:", [round(w, 4) for _, w in widths], " roof width", X1 - X0)
for i, (x, w) in enumerate(widths, 1):
    add(f'ROOF P{i} SkinBottom', 'skin', 'roofskin', quad_x(corners(0, SKIN), x), (w, 0, 0))
    add(f'ROOF P{i} Foam', 'foam', 'rooffoam', quad_x(corners(SKIN, PANEL_T - SKIN), x), (w, 0, 0))
    add(f'ROOF P{i} SkinTop', 'skin', 'roofskin', quad_x(corners(PANEL_T - SKIN, PANEL_T), x), (w, 0, 0))
# stand-in standing seams: interior joints only, 1" high, cut back 1" at the gutter and 3" at the house
for i, (x, w) in enumerate(widths[1:], 1):
    a = add3(P(y_lo, PANEL_T), t, SEAM_CUT_LO); b = add3(a, n, SEAM_H)
    L = L_under - SEAM_CUT_LO - SEAM_CUT_HI
    c = add3(b, t, L); d = add3(a, t, L)
    add(f'ROOF Seam{i}', 'seam', 'roofalu', quad_x([a, b, c, d], x - SEAM_T/2), (SEAM_T, 0, 0))

# ---------------- gutter GF50 (low end) ----------------
gu = profile('GF50'); gp = pts(gu)
x_wall = cross(gu, 1, 34.25)[-1]                                          # panel-side wall outer face
y_flange = cross(gu, 0, 73.2)[0]                                          # top flange underside
gx_min = min(p[0] for p in gp)
end_top = P(y_lo, PANEL_T)                                                # panel end, top corner
def f_gu(px, py, x=0.0):
    w = add3(add3(end_top, t, px - x_wall), n, py - y_flange); return (x, w[1], w[2])
add('ROOF Gutter', 'GF50', 'roofalu', place(gu, lambda a, b: f_gu(a, b, X0)), (X1 - X0, 0, 0))
g_out = f_gu(gx_min, y_flange)                                            # outer face point (for fascia length)
print(f"gutter: wall {x_wall:.4f} flange underside {y_flange:.4f}; floor below panel underside by {(y_flange - PANEL_T) - cross(gu,0,70.5)[0]:+.4f}")

# ---------------- fascia A66048 (both sloped sides) ----------------
fa = profile('A66048'); fp = pts(fa)
f_flange = cross(fa, 0, 13.3)[0]                                              # long flange underside
f_web_in = max(cross(fa, 1, yy)[-1] for yy in (4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5))   # inner-most face (hook tips) the panel edge bears on
s_from = (gx_min - x_wall)                                                     # start at gutter outer face (along t)
s_len = (DP + 10 - y_lo)/COS
base = add3(P(y_lo, PANEL_T), t, s_from)
HOUSE = prism_xy([[-40, DP], [FW + 40, DP], [FW + 40, DP + 40], [-40, DP + 40]], 0, 200)
for side, xe, sgn in (('L', X0, 1), ('R', X1, -1)):
    def f_fa(px, py, xe=xe, sgn=sgn):
        w = add3(base, n, py - f_flange); return (xe + sgn*(px - f_web_in), w[1], w[2])
    loops = place(fa, f_fa)
    # profile lies in the plane perpendicular to t: rebuild with the t-offset in Y/Z already (base), extrude along t
    add(f'ROOF Fascia{side}', 'A66048', 'roofalu', loops, tuple(c*s_len for c in t), cuts=[HOUSE])

# ---------------- wood wedge on the level front top channel ----------------
c = [(0, 0.0, 84.0), (0, CH_D_IN, 84.0), (0, CH_D_IN, z_under(CH_D_IN)), (0, 0.0, z_under(0.0))]
add('ROOF Wedge', 'wedge', 'wood', quad_x(c, 0.0), (FW, 0, 0))
print(f"wedge: {z_under(0)-84:.4f} at Y=0 -> {z_under(CH_D_IN)-84:.4f} at Y={CH_D_IN}")
print(f"roof underside: Z {z_under(y_lo):.4f} at front end (Y={y_lo}), {z_under(DP):.4f} at house")
json.dump({'members': MEM}, open('roof4.json', 'w'))
print(len(MEM), 'roof members')
