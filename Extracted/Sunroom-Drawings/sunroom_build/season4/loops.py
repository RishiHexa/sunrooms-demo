"""Stitch LINE/ARC/LWPOLYLINE entities on given layers into closed loops.
Each loop: list of segs ["line",a,b] or ["arc",a,mid,b]; also returns a dense point list."""
import ezdxf, math
def ang(c,p): return math.atan2(p[1]-c[1],p[0]-c[0])
def raw_segments(msp, layers=None):
    raw=[]
    for e in msp:
        if layers and e.dxf.layer not in layers: continue
        t=e.dxftype()
        if t=='LINE':
            a=(e.dxf.start.x,e.dxf.start.y); b=(e.dxf.end.x,e.dxf.end.y)
            if math.dist(a,b)>1e-7: raw.append({'k':'line','a':a,'b':b,'layer':e.dxf.layer})
        elif t=='ARC':
            c=(e.dxf.center.x,e.dxf.center.y); r=e.dxf.radius
            a0=math.radians(e.dxf.start_angle); a1=math.radians(e.dxf.end_angle)
            if a1<=a0: a1+=2*math.pi
            raw.append({'k':'arc','c':c,'r':r,'a0':a0,'a1':a1,
                        'a':(c[0]+r*math.cos(a0),c[1]+r*math.sin(a0)),
                        'b':(c[0]+r*math.cos(a1),c[1]+r*math.sin(a1)),'layer':e.dxf.layer})
        elif t=='LWPOLYLINE':
            pts=list(e.get_points('xyb')); n=len(pts)
            rng=range(n) if e.closed else range(n-1)
            for i in rng:
                x0,y0,bu=pts[i]; x1,y1,_=pts[(i+1)%n]
                if math.hypot(x1-x0,y1-y0)<1e-7: continue
                if abs(bu)<1e-9: raw.append({'k':'line','a':(x0,y0),'b':(x1,y1),'layer':e.dxf.layer})
                else:
                    ch=math.hypot(x1-x0,y1-y0); th=4*math.atan(bu); r=ch/(2*math.sin(abs(th)/2))
                    mx,my=(x0+x1)/2,(y0+y1)/2; d=math.sqrt(max(r*r-(ch/2)**2,0))
                    ux,uy=(x1-x0)/ch,(y1-y0)/ch
                    s=1 if (bu>0)==(abs(th)<math.pi) else -1
                    c=(mx-uy*d*s, my+ux*d*s)
                    a0=ang(c,(x0,y0)); a1=ang(c,(x1,y1))
                    if bu>0:
                        if a1<=a0: a1+=2*math.pi
                        raw.append({'k':'arc','c':c,'r':r,'a0':a0,'a1':a1,'a':(x0,y0),'b':(x1,y1),'layer':e.dxf.layer})
                    else:
                        if a0<=a1: a0+=2*math.pi
                        # store as ccw from end to start, flipped
                        raw.append({'k':'arc','c':c,'r':r,'a0':a1,'a1':a0,'a':(x1,y1),'b':(x0,y0),'layer':e.dxf.layer})
    return raw
def seg_pts(s, flip, step=0.01):
    if s['k']=='line': p=[s['a'],s['b']]
    else:
        n=max(2,int((s['a1']-s['a0'])*s['r']/step)+1)
        p=[(s['c'][0]+s['r']*math.cos(s['a0']+(s['a1']-s['a0'])*i/n), s['c'][1]+s['r']*math.sin(s['a0']+(s['a1']-s['a0'])*i/n)) for i in range(n+1)]
    return p[::-1] if flip else p
def stitch(raw, tol=2e-4):
    from collections import defaultdict
    key=lambda p:(round(p[0]/tol),round(p[1]/tol))
    idx=defaultdict(list)
    for i,s in enumerate(raw):
        for end in ('a','b'):
            k=key(s[end])
            for dx in (-1,0,1):
                for dy in (-1,0,1): idx[(k[0]+dx,k[1]+dy)].append((i,end))
    used=[False]*len(raw); loops=[]; open_chains=[]
    for i in range(len(raw)):
        if used[i]: continue
        used[i]=True; chain=[(i,False)]; cur=raw[i]['b']; start=raw[i]['a']
        while True:
            if math.dist(cur,start)<tol and len(chain)>1: break
            nxt=None
            for j,end in idx[key(cur)]:
                if used[j]: continue
                if math.dist(raw[j][end],cur)<tol: nxt=(j,end=='b'); break
            if nxt is None: break
            used[nxt[0]]=True; chain.append(nxt)
            cur=raw[nxt[0]]['a'] if nxt[1] else raw[nxt[0]]['b']
        if math.dist(cur,start)<tol and len(chain)>1:
            loops.append(chain)
        else: open_chains.append(chain)
    out=[]
    for ch in loops:
        segs=[]; pts=[]
        for j,fl in ch:
            s=raw[j]; a,b=(s['b'],s['a']) if fl else (s['a'],s['b'])
            if s['k']=='line': segs.append(['line',list(a),list(b)])
            else:
                am=(s['a0']+s['a1'])/2; m=(s['c'][0]+s['r']*math.cos(am), s['c'][1]+s['r']*math.sin(am))
                segs.append(['arc',list(a),list(m),list(b)])
            pts.extend(seg_pts(s,fl)[:-1])
        # snap continuity
        for k in range(len(segs)): segs[k][1]=list(segs[k-1][-1])
        A=0.5*sum(pts[k][0]*pts[(k+1)%len(pts)][1]-pts[(k+1)%len(pts)][0]*pts[k][1] for k in range(len(pts)))
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        out.append({'segs':segs,'pts':pts,'area':A,'bb':(min(xs),min(ys),max(xs),max(ys)),'layer':raw[ch[0][0]]['layer']})
    return out, open_chains
def point_in(pt, poly):
    x,y=pt; inside=False; n=len(poly)
    for i in range(n):
        x0,y0=poly[i]; x1,y1=poly[(i+1)%n]
        if (y0>y)!=(y1>y) and x < x0+(y-y0)*(x1-x0)/(y1-y0): inside=not inside
    return inside
def nest(loops):
    """assign depth: outer loops depth 0, holes depth 1, islands-in-holes depth 2..."""
    for L in loops:
        L['parents']=[j for j,M in enumerate(loops) if M is not L and abs(M['area'])>abs(L['area'])
                      and M['bb'][0]<=L['bb'][0]+1e-6 and M['bb'][1]<=L['bb'][1]+1e-6 and M['bb'][2]>=L['bb'][2]-1e-6 and M['bb'][3]>=L['bb'][3]-1e-6
                      and point_in(L['pts'][0],M['pts'])]
        L['depth']=len(L['parents'])
    return loops
