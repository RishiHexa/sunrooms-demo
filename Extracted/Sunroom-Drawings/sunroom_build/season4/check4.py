"""Verification for the 4-season build. Writes check4_report.txt next to this file."""
import FreeCAD as App, itertools, math
OUT = r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/check4_report.txt'
d = App.getDocument('Sunroom_4Season')
S = {o.Label: o.Shape for o in d.Objects if o.TypeId == 'Part::Feature'}
L = []
p = L.append
xs = [v.X for s in S.values() for v in s.Vertexes]; ys = [v.Y for s in S.values() for v in s.Vertexes]; zs = [v.Z for s in S.values() for v in s.Vertexes]
p('vertex extents X %.5f..%.5f  Y %.5f..%.5f  Z %.5f..%.5f' % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
posts = [s for n, s in S.items() if n.startswith('CORNER CP')]
pv = [v for s in posts for v in s.Vertexes]
p('corner posts X %.5f..%.5f  Y %.5f..%.5f' % (min(v.X for v in pv), max(v.X for v in pv), min(v.Y for v in pv), max(v.Y for v in pv)))
inter = []; touch = []
for a, b in itertools.combinations(S, 2):
    A, B = S[a], S[b]
    bb = A.BoundBox; bb2 = B.BoundBox
    bb.enlarge(0.01)
    if not bb.intersect(bb2):
        continue
    v = A.common(B).Volume
    if v > 1e-6:
        inter.append((v, a, b))
    else:
        dist = A.distToShape(B)[0]
        touch.append((dist, a, b))
inter.sort(reverse=True)
p('\nINTERFERENCE (common volume > 1e-6): %d pairs' % len(inter))
for v, a, b in inter:
    p('  %9.5f  %s  <->  %s' % (v, a, b))
p('\nNEAR PAIRS without interference (distToShape):')
for dist, a, b in sorted(touch):
    p('  %9.5f  %s  <->  %s' % (dist, a, b))
# horizontals must touch both neighbouring verticals
p('\nHORIZONTAL END CONTACT:')
for n, s in S.items():
    if ' T04' not in n:
        continue
    wall = n.split()[0]
    vs = [(m, t) for m, t in S.items() if m.startswith(wall + ' ') and (' T02' in m or ' T03' in m)]
    ds = sorted((s.distToShape(t)[0], m) for m, t in vs)[:2]
    p('  %-24s %s' % (n, '   '.join('%.5f %s' % x for x in ds)))
# left/right symmetry
p('\nLEFT/RIGHT SYMMETRY (mirror about X=108):')
worst = 0
for n, s in S.items():
    if not n.startswith('LEFT'):
        continue
    r = 'RIGHT' + n[4:]
    t = S.get(r)
    if t is None:
        p('  missing ' + r); continue
    a = s.BoundBox; b = t.BoundBox
    e = max(abs(a.XMin - (216 - b.XMax)), abs(a.XMax - (216 - b.XMin)), abs(a.YMin - b.YMin), abs(a.YMax - b.YMax), abs(a.ZMin - b.ZMin), abs(a.ZMax - b.ZMax), abs(s.Volume - t.Volume))
    worst = max(worst, e)
    if e > 1e-6:
        p('  %s vs %s  err %.6f' % (n, r, e))
p('  worst %.7f' % worst)
p('\nSECTION AREA (volume / length) per member:')
for n, s in sorted(S.items()):
    b = s.BoundBox
    p('  %-28s vol %9.4f  bbox %.4f x %.4f x %.4f' % (n, s.Volume, b.XLength, b.YLength, b.ZLength))
open(OUT, 'w').write('\n'.join(L))
print('wrote', OUT)
