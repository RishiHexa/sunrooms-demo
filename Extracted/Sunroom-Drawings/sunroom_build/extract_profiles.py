"""Extract closed profile loops from die DXF files.
Handles three encodings: closed LWPOLYLINE (with bulges), LINE+ARC wires, ACIS REGION.
Emits JSON: {profile_name: [ [seg,...], ... ]}  where seg is
  ["line", [x,y], [x,y]]  or  ["arc", [x,y], [xm,ym], [x,y]]   (start, mid, end)
"""
import ezdxf, math, json, os, re, collections
from ezdxf.acis import sab

TOL = 1e-6
GEOM_LAYERS = {'0'}
SKIP_LAYERS = {'DIM','DIMENSION','IMP','APROVAL','APPROVAL','TITLE','BORDER','Defpoints'}

# ---------- helpers ----------
def arc_mid(c, r, a0, a1, ccw):
    if ccw:
        if a1 <= a0: a1 += 2*math.pi
    else:
        if a1 >= a0: a1 -= 2*math.pi
    am = (a0 + a1)/2.0
    return [c[0] + r*math.cos(am), c[1] + r*math.sin(am)]

def ang(c, p):
    return math.atan2(p[1]-c[1], p[0]-c[0])

# ---------- 1. ACIS REGION ----------
def _ptrs(e):  return [t.value for t in e.data if t.tag == 12]
def _floats(e):return [t.value for t in e.data if t.tag == 6]
def _vecs(e):  return [t.value for t in e.data if t.tag in (19,20)]

def from_region(region):
    body = sab.parse_sab(region.acis_data)
    ents = body.entities
    loops = [e for e in ents if e.name == 'loop']
    out = []
    for loop in loops:
        start = next(p for p in _ptrs(loop) if getattr(p,'name','') == 'coedge')
        def vpt(v):
            p = next(q for q in _ptrs(v) if getattr(q,'name','') == 'point')
            return _vecs(p)[0]
        segs=[]; ce=start; guard=0
        while True:
            guard += 1
            if guard > 20000: raise RuntimeError('coedge runaway')
            sub  = _ptrs(ce)
            edge = next(p for p in sub if getattr(p,'name','')=='edge')
            nxt  = sub[1]
            sense= [t.value for t in ce.data if t.tag in (10,11)]
            rev  = bool(sense[0]) if sense else False
            esub = _ptrs(edge)
            verts= [p for p in esub if getattr(p,'name','')=='vertex']
            curve= next((p for p in esub if getattr(p,'name','').endswith('-curve')), None)
            a, b = vpt(verts[0])[:2], vpt(verts[-1])[:2]
            if rev: a, b = b, a
            if curve is not None and curve.name == 'ellipse-curve':
                v = _vecs(curve); c = v[0][:2]; normal = v[1]; major = v[2]
                r = math.hypot(major[0], major[1])
                ccw = normal[2] > 0
                if rev: ccw = not ccw
                segs.append(["arc", list(a), arc_mid(c, r, ang(c,a), ang(c,b), ccw), list(b)])
            else:
                segs.append(["line", list(a), list(b)])
            ce = nxt
            if ce is start: break
        out.append(segs)
    return out

# ---------- 2. closed LWPOLYLINE ----------
def from_lwpolyline(pl):
    pts = list(pl.get_points('xyb'))
    n = len(pts); segs=[]
    closed = pl.closed or (n>2 and math.dist(pts[0][:2],pts[-1][:2])<1e-3)
    rng = range(n) if closed else range(n-1)
    for i in rng:
        x0,y0,bulge = pts[i]
        x1,y1,_     = pts[(i+1) % n]
        if abs(bulge) < TOL:
            segs.append(["line",[x0,y0],[x1,y1]])
        else:
            chord = math.hypot(x1-x0, y1-y0)
            if chord < TOL: continue
            theta = 4*math.atan(bulge)              # included angle
            r = chord/(2*math.sin(abs(theta)/2))
            # sagitta method for midpoint
            mx,my = (x0+x1)/2, (y0+y1)/2
            h = bulge*chord/2
            ux,uy = (x1-x0)/chord, (y1-y0)/chord
            segs.append(["arc",[x0,y0],[mx - uy*h, my + ux*h],[x1,y1]])
    return segs

# ---------- 3. LINE + ARC wire stitching ----------
def from_wire(entities):
    raw=[]
    for e in entities:
        if e.dxftype()=='LINE':
            s,t = e.dxf.start, e.dxf.end
            raw.append({'a':(s.x,s.y),'b':(t.x,t.y),'kind':'line'})
        elif e.dxftype()=='ARC':
            c=(e.dxf.center.x, e.dxf.center.y); r=e.dxf.radius
            a0=math.radians(e.dxf.start_angle); a1=math.radians(e.dxf.end_angle)
            a=(c[0]+r*math.cos(a0), c[1]+r*math.sin(a0))
            b=(c[0]+r*math.cos(a1), c[1]+r*math.sin(a1))
            raw.append({'a':a,'b':b,'kind':'arc','c':c,'r':r})
        elif e.dxftype()=='CIRCLE':
            c=(e.dxf.center.x,e.dxf.center.y); r=e.dxf.radius
            raw.append({'a':(c[0]+r,c[1]),'b':(c[0]-r,c[1]),'kind':'arc','c':c,'r':r})
            raw.append({'a':(c[0]-r,c[1]),'b':(c[0]+r,c[1]),'kind':'arc','c':c,'r':r})
    used=[False]*len(raw); loops=[]
    tol=1e-4
    def close(p,q): return math.hypot(p[0]-q[0],p[1]-q[1]) < tol
    for i in range(len(raw)):
        if used[i]: continue
        used[i]=True
        chain=[dict(raw[i], flip=False)]
        cur=raw[i]['b']
        while True:
            nxt=None
            for j in range(len(raw)):
                if used[j]: continue
                if close(raw[j]['a'],cur): nxt=(j,False); break
                if close(raw[j]['b'],cur): nxt=(j,True);  break
            if nxt is None: break
            j,fl=nxt; used[j]=True
            seg=dict(raw[j]); seg['flip']=fl
            if fl: seg['a'],seg['b']=seg['b'],seg['a']
            chain.append(seg); cur=seg['b']
            if close(cur, chain[0]['a']): break
        if len(chain)>2 and close(chain[-1]['b'], chain[0]['a']):
            loops.append(chain)
    out=[]
    for chain in loops:
        segs=[]
        for s in chain:
            if s['kind']=='line':
                segs.append(["line",list(s['a']),list(s['b'])])
            else:
                c,r=s['c'],s['r']
                a0,a1=ang(c,s['a']),ang(c,s['b'])
                ccw = not s['flip']
                segs.append(["arc",list(s['a']),arc_mid(c,r,a0,a1,ccw),list(s['b'])])
        out.append(segs)
    return out

# ---------- driver ----------
def clean_loops(loops, tol=1e-6):
    """Drop zero-length segments and snap tiny gaps so OCC never sees a degenerate edge."""
    out=[]
    for lp in loops:
        keep=[]
        for s in lp:
            a,b = s[1], s[-1]
            if math.dist(a,b) < tol:      # zero-length line or arc
                continue
            keep.append(s)
        # re-snap: force each segment's start onto previous segment's end
        for i in range(1,len(keep)):
            keep[i][1] = list(keep[i-1][-1])
        if keep:
            keep[0][1] = list(keep[-1][-1])
        out.append(keep)
    return out

def extract(path):
    doc = ezdxf.readfile(path); msp = doc.modelspace()
    geom = [e for e in msp if e.dxf.layer in GEOM_LAYERS]
    regions = [e for e in geom if e.dxftype()=='REGION']
    if regions:
        loops=[]
        for r in regions: loops.extend(from_region(r))
        return clean_loops(loops), 'region'
    def _pseudo_closed(e):
        if e.closed: return True
        try: pts=list(e.get_points('xy'))
        except Exception: return False
        return len(pts)>2 and math.dist(pts[0],pts[-1]) < 1e-3
    pls = [e for e in geom if e.dxftype() in ('LWPOLYLINE','POLYLINE') and _pseudo_closed(e)]
    if pls:
        return clean_loops([from_lwpolyline(p) for p in pls]), 'polyline'
    wires = [e for e in geom if e.dxftype() in ('LINE','ARC','CIRCLE')]
    if wires:
        return clean_loops(from_wire(wires)), 'wire'
    return [], 'empty'

def loop_bbox(segs):
    xs=[];ys=[]
    for s in segs:
        for p in s[1:]:
            xs.append(p[0]); ys.append(p[1])
    return min(xs),min(ys),max(xs),max(ys)

def loop_area(segs):  # shoelace on endpoints, sign gives orientation
    pts=[s[1] for s in segs]
    a=0.0
    for i in range(len(pts)):
        x0,y0=pts[i]; x1,y1=pts[(i+1)%len(pts)]
        a += x0*y1 - x1*y0
    return a/2.0

def max_gap(segs):
    g=0.0
    for i,s in enumerate(segs):
        nxt=segs[(i+1)%len(segs)]
        g=max(g, math.hypot(s[-1][0]-nxt[1][0], s[-1][1]-nxt[1][1]))
    return g

if __name__ == '__main__':
    D = "/sessions/magical-sleepy-babbage/mnt/Lifestyle/DXF FILES FOR DIES/DXF FILES FOR DIES/"
    NEEDED = ["A62420","A62421","A26948","A26949","A26952","A26950","A33861","A33863","A33864","A45216"]
    files = {}
    for f in os.listdir(D):
        m = re.match(r'A(\d+)', f)
        if m and f.lower().endswith('.dxf'): files[m.group(1)] = f
    result={}
    for num in NEEDED:
        key=num[1:]
        fn = files.get(key)
        loops, mode = extract(D+fn)
        result[num] = {'file': fn, 'mode': mode, 'loops': loops}
        print(f"{num} [{mode:8s}] loops={len(loops)}")
        for i,lp in enumerate(loops):
            x0,y0,x1,y1 = loop_bbox(lp)
            print(f"    loop{i}: segs={len(lp):3d} bbox={x1-x0:7.4f} x {y1-y0:7.4f}  area={loop_area(lp):8.4f}  gap={max_gap(lp):.1e}")
    with open('/sessions/magical-sleepy-babbage/mnt/Lifestyle/sunroom_build/profiles_225.json','w') as fh:
        json.dump(result, fh)
    print("\nwrote profiles_225.json")
