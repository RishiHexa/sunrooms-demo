"""Identify every profile instance in 225-Assembly.dxf and solve its orientation
(rotation + mirror) relative to the die drawing."""
import ezdxf, math, json, re, collections
doc=ezdxf.readfile("225-Assembly.dxf"); msp=doc.modelspace()
P=json.load(open('profiles_all.json'))

# ---------- die profile point sets (outer loop only) ----------
def die_pts(n):
    lps=P[n]['loops']
    lp=max(lps,key=lambda L: abs(sum(L[i][1][0]*L[(i+1)%len(L)][1][1]-L[(i+1)%len(L)][1][0]*L[i][1][1] for i in range(len(L)))))
    out=[]
    for s in lp:
        out.append(tuple(s[1]))
        if s[0]=='arc': out.append(tuple(s[2]))
    return out
DIE={k:die_pts(k) for k in P}

# ---------- instances ----------
def close(a,b,t=1e-4): return math.hypot(a[0]-b[0],a[1]-b[1])<t
insts=[]
for e in msp.query('LWPOLYLINE'):
    if e.dxf.layer!='0': continue
    pts=[(p[0],p[1]) for p in e.get_points('xy')]
    if len(pts)>=4: insts.append(pts)
# stitch LINE+ARC
raw=[]
for e in msp.query('LINE'):
    if e.dxf.layer!='0': continue
    raw.append(((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y),None))
for e in msp.query('ARC'):
    if e.dxf.layer!='0': continue
    c=(e.dxf.center.x,e.dxf.center.y); r=e.dxf.radius
    a0=math.radians(e.dxf.start_angle); a1=math.radians(e.dxf.end_angle)
    if a1<a0: a1+=2*math.pi
    pts=[(c[0]+r*math.cos(a0+(a1-a0)*t/6), c[1]+r*math.sin(a0+(a1-a0)*t/6)) for t in range(7)]
    raw.append((pts[0],pts[-1],pts))
used=[False]*len(raw)
for i in range(len(raw)):
    if used[i]: continue
    used[i]=True; chain=[raw[i]]; cur=raw[i][1]; pts=[raw[i][0]]+ (raw[i][2][1:] if raw[i][2] else [raw[i][1]])
    while True:
        nxt=None
        for j in range(len(raw)):
            if used[j]: continue
            if close(raw[j][0],cur): nxt=(j,False); break
            if close(raw[j][1],cur): nxt=(j,True); break
        if nxt is None: break
        j,fl=nxt; used[j]=True
        seg=raw[j]; sp=seg[2][:] if seg[2] else [seg[0],seg[1]]
        if fl: sp=sp[::-1]
        pts.extend(sp[1:]); cur=sp[-1]
        if close(cur,pts[0]): break
    if len(pts)>=5 and close(pts[-1],pts[0]): insts.append(pts[:-1])

# ---------- labels ----------
labels=[]
for e in msp.query('MTEXT TEXT'):
    t=e.text if e.dxftype()=='MTEXT' else e.dxf.text
    t=re.sub(r'\{[^}]*\}','',t); t=re.sub(r'\\\\?[A-Za-z][^;]*;','',t).replace('\\P',' ').strip()
    if t: labels.append({'x':e.dxf.insert.x,'y':e.dxf.insert.y,'text':t,
                         'kind':'H' if 'horizontal' in t.lower() else 'V'})

# ---------- orientation solve ----------
TF={'0':lambda p:(p[0],p[1]), '90':lambda p:(-p[1],p[0]), '180':lambda p:(-p[0],-p[1]), '270':lambda p:(p[1],-p[0])}
def norm(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    mnx,mny=min(xs),min(ys)
    return [(p[0]-mnx,p[1]-mny) for p in pts]
def hd(A,B):
    "mean nearest-neighbour distance A->B (sampled)"
    if not A or not B: return 9e9
    step=max(1,len(A)//40); tot=0; n=0
    for a in A[::step]:
        tot+=min((a[0]-b[0])**2+(a[1]-b[1])**2 for b in B)**0.5; n+=1
    return tot/n
def solve(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    w,h=max(xs)-min(xs),max(ys)-min(ys)
    best=None
    for name,src in DIE.items():
        dx=[p[0] for p in src]; dy=[p[1] for p in src]
        dw,dh=max(dx)-min(dx),max(dy)-min(dy)
        for rot in TF:
            for mir in (False,True):
                t=[TF[rot]((-p[0] if mir else p[0], p[1])) for p in src]
                tx=[p[0] for p in t]; ty=[p[1] for p in t]
                if abs((max(tx)-min(tx))-w)>0.03 or abs((max(ty)-min(ty))-h)>0.03: continue
                d=hd(norm(pts),norm(t))
                if best is None or d<best[0]: best=(d,name,rot,mir)
    return best

print(f"{len(insts)} closed instances found\n")
res=[]
for pts in insts:
    b=solve(pts)
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2
    lb=min(labels,key=lambda L: math.hypot(cx-L['x'],cy-L['y']))
    res.append({'part':b[1] if b else None,'err':round(b[0],4) if b else None,
                'rot':b[2] if b else None,'mirror':b[3] if b else None,
                'cx':round(cx,4),'cy':round(cy,4),'x0':round(min(xs),4),'y0':round(min(ys),4),
                'x1':round(max(xs),4),'y1':round(max(ys),4),
                'section':lb['text'],'kind':lb['kind']})
good=[r for r in res if r['part'] and r['err']<0.02]
print(f"confidently identified: {len(good)}/{len(res)}")
c=collections.Counter(r['part'] for r in good)
print("part counts:", dict(sorted(c.items())))
print("\norientation used per part (rot, mirrored):")
o=collections.defaultdict(collections.Counter)
for r in good: o[r['part']][(r['rot'],r['mirror'])]+=1
for k in sorted(o): print(f"   {k:8s} " + "  ".join(f"{rot}{'M' if mir else ''}x{n}" for (rot,mir),n in o[k].most_common()))
json.dump(res, open('instances.json','w'), indent=1)
print("\nwrote instances.json")
