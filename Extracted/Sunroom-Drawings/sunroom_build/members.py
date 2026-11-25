import ezdxf, math, json, re, collections
P="/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/SideWall-Description.dxf"
msp=ezdxf.readfile(P).modelspace()
lines=[]
for e in msp.query('LINE'):
    if e.dxf.layer!='Walls': continue
    s,t=e.dxf.start,e.dxf.end
    lines.append(((s.x,s.y),(t.x,t.y)))

# group parallel line pairs into members (each member drawn as 2 edges)
def ori(l):
    dx,dy=l[1][0]-l[0][0], l[1][1]-l[0][1]
    if abs(dx)<0.5: return 'V'
    if abs(dy)<0.5: return 'H'
    return 'S'   # sloped
def mid(l): return ((l[0][0]+l[1][0])/2,(l[0][1]+l[1][1])/2)
def length(l): return math.dist(l[0],l[1])

used=[False]*len(lines); members=[]
for i,a in enumerate(lines):
    if used[i]: continue
    best=None
    for j,b in enumerate(lines):
        if i==j or used[j]: continue
        if ori(a)!=ori(b): continue
        if abs(length(a)-length(b))>1.0: continue
        d=math.dist(mid(a),mid(b))
        if d<5.0 and (best is None or d<best[1]): best=(j,d)
    if best:
        j,d=best; used[i]=used[j]=True
        members.append({'kind':ori(a),'edges':[a,lines[j]],'thick':round(d,3),
                        'mid':((mid(a)[0]+mid(lines[j])[0])/2,(mid(a)[1]+mid(lines[j])[1])/2),
                        'len':round((length(a)+length(lines[j]))/2,3)})
    else:
        used[i]=True
        members.append({'kind':ori(a),'edges':[a],'thick':None,'mid':mid(a),'len':round(length(a),3)})

texts=[]
for e in msp.query('MTEXT'):
    if e.dxf.layer!='Walls': continue
    raw=e.text
    clean=re.sub(r'\\\\[A-Za-z][^;]*;','',raw).replace('\\P',' | ')
    parts=re.findall(r'AS-(\d+)', clean)
    texts.append({'pos':(e.dxf.insert.x,e.dxf.insert.y),'text':clean.strip(),'parts':parts})

print("=== MEMBERS ===")
members.sort(key=lambda m:(m['kind'], m['mid'][0], m['mid'][1]))
for k,m in enumerate(members):
    m['id']=k
    print(f"  M{k:02d} {m['kind']} mid=({m['mid'][0]:7.2f},{m['mid'][1]:7.2f}) len={m['len']:7.2f} thick={m['thick']}")

print("\n=== CALLOUT -> NEAREST MEMBER ===")
for t in texts:
    if not t['parts']: continue
    d=sorted(((math.dist(t['pos'], m['mid']), m) for m in members), key=lambda x:x[0])
    near=d[0]
    print(f"  {'/'.join('AS-'+p for p in t['parts']):26s} @({t['pos'][0]:7.2f},{t['pos'][1]:7.2f}) -> M{near[1]['id']:02d} {near[1]['kind']} dist={near[0]:6.2f} | {t['text'][:52]}")

print("\n=== NON-PART TEXT ===")
for t in texts:
    if not t['parts']: print(f"  ({t['pos'][0]:7.2f},{t['pos'][1]:7.2f}) {t['text']}")

json.dump({'members':[{k:v for k,v in m.items() if k!='edges'}|{'edges':m['edges']} for m in members],
           'texts':texts}, open('members.json','w'), indent=1)
print("\nwrote members.json")
