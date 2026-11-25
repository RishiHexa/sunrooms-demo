"""Segment 225-Assembly.dxf into its labelled cross sections and identify each part instance."""
import ezdxf, math, json, re, collections
A="225-Assembly.dxf"
doc=ezdxf.readfile(A); msp=doc.modelspace()

# ---- labels ----
labels=[]
for e in msp.query('MTEXT TEXT'):
    t=e.text if e.dxftype()=='MTEXT' else e.dxf.text
    t=re.sub(r'\{[^}]*\}','',t); t=re.sub(r'\\\\?[A-Za-z][^;]*;','',t).replace('\\P',' ').strip()
    if t: labels.append({'x':e.dxf.insert.x,'y':e.dxf.insert.y,'text':t,
                         'kind':'H' if t.lower().startswith('horizontal') else 'V'})

# ---- instances: closed loops from lwpolylines + stitched line/arc ----
def poly_pts(e):
    return [(p[0],p[1]) for p in e.get_points('xy')]
inst=[]
for e in msp.query('LWPOLYLINE'):
    if e.dxf.layer!='0': continue
    pts=poly_pts(e)
    if len(pts)<4: continue
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    a=0.0
    for i in range(len(pts)):
        x0,y0=pts[i]; x1,y1=pts[(i+1)%len(pts)]
        a+=x0*y1-x1*y0
    inst.append({'pts':pts,'w':max(xs)-min(xs),'h':max(ys)-min(ys),'area':abs(a)/2,
                 'x0':min(xs),'y0':min(ys),'x1':max(xs),'y1':max(ys),
                 'cx':(min(xs)+max(xs))/2,'cy':(min(ys)+max(ys))/2})

# ---- die profiles ----
P=json.load(open('../profiles_225.json'))
def die_info(n):
    xs=[];ys=[]; 
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)
DIE={k:die_info(k) for k in P}
EXTRA={'A7116':(1.000,1.000)}     # 1x1 patio door tubing (not yet extracted)

def match(i):
    best=None
    for k,(a,b) in list(DIE.items())+list(EXTRA.items()):
        for (ww,hh) in ((a,b),(b,a)):
            d=abs(ww-i['w'])+abs(hh-i['h'])
            if d<0.045 and (best is None or d<best[1]):
                best=(k,d,'rot90' if (ww,hh)==(b,a) else 'upright')
    return best

# ---- assign each instance to nearest label ----
for i in inst:
    m=match(i)
    i['part']=m[0] if m else None
    i['fit']=round(m[1],4) if m else None
    i['pose']=m[2] if m else None
    lb=min(labels,key=lambda L: math.hypot(i['cx']-L['x'], i['cy']-L['y']))
    i['section']=lb['text']; i['kind']=lb['kind']
    i['dist']=round(math.hypot(i['cx']-lb['x'], i['cy']-lb['y']),2)

by=collections.defaultdict(list)
for i in inst: by[i['section']].append(i)
print(f"{len(inst)} instances, {len(labels)} sections\n")
for L in labels:
    g=by.get(L['text'],[])
    named=[x for x in g if x['part']]
    c=collections.Counter(x['part'] for x in named)
    unk=len(g)-len(named)
    print(f"[{L['kind']}] {L['text']}")
    print(f"     {len(g):2d} instances  |  " + ", ".join(f"{k}x{v}" for k,v in sorted(c.items())) + (f"  | unmatched {unk}" if unk else ""))
json.dump([{k:v for k,v in i.items() if k!='pts'} for i in inst], open('instances.json','w'), indent=1)
print("\nwrote instances.json")
