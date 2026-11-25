import ezdxf, math, json, re
msp=ezdxf.readfile("/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/SideWall-Description.dxf").modelspace()
M=json.load(open('members.json'))
members=M['members']; texts=M['texts']

segs=[((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)) for e in msp.query('LINE') if e.dxf.layer=='Existing']
TOL=0.6
def key(p): return (round(p[0]/TOL), round(p[1]/TOL))
adj={}
for a,b in segs:
    adj.setdefault(key(a),set()).add(key(b)); adj.setdefault(key(b),set()).add(key(a))
pos={}
for a,b in segs: pos[key(a)]=a; pos[key(b)]=b

# connected components
seen=set(); comps=[]
for n in adj:
    if n in seen: continue
    stack=[n]; comp=set()
    while stack:
        x=stack.pop()
        if x in comp: continue
        comp.add(x); seen.add(x)
        stack.extend(adj[x]-comp)
    comps.append(comp)

def dist(p,q): return math.hypot(p[0]-q[0],p[1]-q[1])
def member_dist(p,m):
    best=1e9
    for e in m['edges']:
        (x1,y1),(x2,y2)=e
        dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
        t=max(0,min(1,((p[0]-x1)*dx+(p[1]-y1)*dy)/L2)) if L2 else 0
        best=min(best, math.hypot(p[0]-(x1+t*dx), p[1]-(y1+t*dy)))
    return best

print(f"{len(segs)} leader segments -> {len(comps)} leader groups\n")
out=[]
for t in texts:
    if not t['parts']: continue
    # component whose nearest node is closest to the text insert
    best=None
    for ci,c in enumerate(comps):
        d=min(dist(t['pos'],pos[n]) for n in c)
        if best is None or d<best[1]: best=(ci,d)
    ci,droot=best; comp=comps[ci]
    root=min(comp, key=lambda n: dist(t['pos'],pos[n]))
    leaves=[n for n in comp if len(adj[n])==1 and n!=root]
    tgts=[]
    for lf in leaves:
        p=pos[lf]
        mm=sorted(((member_dist(p,m),m) for m in members), key=lambda x:x[0])[0]
        tgts.append((mm[1]['id'], mm[1]['kind'], round(mm[0],2), p))
    label='/'.join('AS-'+p for p in t['parts'])
    print(f"{label:22s} root_gap={droot:5.2f}  targets:")
    for tid,kind,d,p in tgts:
        m=next(x for x in members if x['id']==tid)
        print(f"      -> M{tid:02d} {kind}  mid=({m['mid'][0]:7.2f},{m['mid'][1]:7.2f}) len={m['len']:7.2f}  arrow_gap={d:5.2f}")
    out.append({'parts':t['parts'],'text':t['text'],'targets':[{'member':x[0],'kind':x[1],'gap':x[2]} for x in tgts]})
json.dump(out, open('mapping.json','w'), indent=1)
print("\nwrote mapping.json")
