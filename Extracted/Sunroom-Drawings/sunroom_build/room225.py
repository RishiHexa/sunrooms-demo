import ezdxf, math, json, re, collections
P="/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/225-Room-Description.dxf"
msp=ezdxf.readfile(P).modelspace()

lines=[((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)) for e in msp.query('LINE')]
def ori(a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    if abs(dx)<0.4: return 'V'
    if abs(dy)<0.4: return 'H'
    return 'S'
LONG=8.0
struct=[(a,b) for a,b in lines if math.dist(a,b)>=LONG]
leaders=[(a,b) for a,b in lines if math.dist(a,b)<LONG]
# long sloped lines that are the raked top are structural; short sloped are leaders
# reclassify: sloped & long & spans a wall => structural (already by LONG)
extra_leaders=[(a,b) for a,b in struct if ori(a,b)=='S' and math.dist(a,b)<40]
struct=[s for s in struct if s not in extra_leaders]
leaders+=extra_leaders

def wall_of(x): return 'LEFT' if x < 100 else 'FRONT'

# cluster structural lines into members
used=[False]*len(struct); members=[]
for i,(a,b) in enumerate(struct):
    if used[i]: continue
    o=ori(a,b); grp=[(a,b)]; used[i]=True
    for j,(c,d) in enumerate(struct):
        if used[j] or ori(c,d)!=o: continue
        if o=='V' and abs(c[0]-a[0])<3.0 and abs(((c[1]+d[1])/2)-((a[1]+b[1])/2))<12: grp.append((c,d)); used[j]=True
        elif o=='H' and abs(c[1]-a[1])<3.0 and abs(((c[0]+d[0])/2)-((a[0]+b[0])/2))<12: grp.append((c,d)); used[j]=True
    xs=[p[0] for e in grp for p in e]; ys=[p[1] for e in grp for p in e]
    mid=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)
    if o=='V':   thick=round(max(xs)-min(xs),3); ln=round(max(ys)-min(ys),2)
    elif o=='H': thick=round(max(ys)-min(ys),3); ln=round(max(xs)-min(xs),2)
    else:        thick=None; ln=round(max(math.dist(*e) for e in grp),2)
    members.append({'kind':o,'edges':grp,'mid':mid,'len':ln,'thick':thick,'wall':wall_of(mid[0])})
members.sort(key=lambda m:(m['wall']!='LEFT', m['kind'], m['mid'][0], m['mid'][1]))
for i,m in enumerate(members): m['id']=i

callouts=[]
for e in msp.query('MTEXT'):
    t=re.sub(r'\{[^}]*\}','',e.text)
    t=re.sub(r'\\\\[A-Za-z][^;]*;','',t).replace('\\P',' | ')
    t=re.sub(r'\\[A-Za-z][^;]*;','',t).strip()
    parts=re.findall(r'\bA(\d{4,6})\b', t)
    if parts: callouts.append({'pos':(e.dxf.insert.x,e.dxf.insert.y),'text':t,'parts':parts})

def seg_dist(p,e):
    (x1,y1),(x2,y2)=e; dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-x1)*dx+(p[1]-y1)*dy)/L2)) if L2 else 0
    return math.hypot(p[0]-(x1+t*dx), p[1]-(y1+t*dy))
def mdist(p,m): return min(seg_dist(p,e) for e in m['edges'])

print(f"structural={len(struct)}  leaders={len(leaders)}  members={len(members)}\n")
print("=== MEMBERS ===")
for m in members:
    th=f"{m['thick']:.3f}" if m['thick'] is not None else "-"
    print(f"  M{m['id']:02d} {m['wall']:5s} {m['kind']} mid=({m['mid'][0]:8.2f},{m['mid'][1]:7.2f}) len={m['len']:7.2f} t={th} edges={len(m['edges'])}")

print("\n=== CALLOUT -> MEMBER (via nearest leader arrow) ===")
mapping=[]
for co in callouts:
    ld=sorted(leaders, key=lambda e: min(math.dist(co['pos'],e[0]),math.dist(co['pos'],e[1])))
    tip=None
    if ld:
        e=ld[0]
        tip = e[1] if math.dist(co['pos'],e[0])<math.dist(co['pos'],e[1]) else e[0]
    src = tip if tip else co['pos']
    best=sorted(((mdist(src,m),m) for m in members), key=lambda x:x[0])[0]
    mapping.append({'parts':co['parts'],'text':co['text'],'member':best[1]['id'],'gap':round(best[0],2)})
    print(f"  {co['text'][:38]:38s} -> M{best[1]['id']:02d} {best[1]['wall']:5s} {best[1]['kind']} gap={best[0]:6.2f}")

json.dump({'members':members,'callouts':callouts,'leaders':leaders,'mapping':mapping},
          open('room225.json','w'), indent=1, default=list)
print("\nwrote room225.json")
