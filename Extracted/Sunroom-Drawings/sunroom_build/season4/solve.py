"""Identify every die instance in an assembly DXF and solve rotation/mirror/translation.
Transform convention: die-local p (relative to die bbox min) -> R(rot)·M(mir)·p  then translate so
the transformed die's bbox-min lands at 'pos'.  mirror = x -> -x applied BEFORE rotation."""
import ezdxf, json, math, sys, collections
sys.path.insert(0,'/home/claude/s4')
from loops import *
P=json.load(open('profiles.json'))
def T(rot,mir,p):
    x,y=p
    if mir: x=-x
    return {0:(x,y),90:(-y,x),180:(-x,-y),270:(y,-x)}[rot]
def seg_points(segs):
    pts=[]
    for s in segs:
        pts.append(s[1]);
        if s[0]=='arc': pts.append(s[2])
    return pts
ORI=[(r,m) for r in (0,90,180,270) for m in (False,True)]
def die_oriented(k,rot,mir):
    """returns list of (outer loop pts transformed, bbox) with whole-die bbox min at origin"""
    allp=[T(rot,mir,p) for L in P[k]['loops'] for p in seg_points(L['segs'])]
    mx=min(p[0] for p in allp); my=min(p[1] for p in allp)
    out=[]
    for L in P[k]['loops']:
        if L['depth']!=0: continue
        pts=[(q[0]-mx,q[1]-my) for q in (T(rot,mir,p) for p in seg_points(L['segs']))]
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        out.append({'pts':pts,'bb':(min(xs),min(ys),max(xs),max(ys)),'area':L['area']})
    return out
def mean_nn(A,B):
    step=max(1,len(A)//60); s=0;n=0
    for a in A[::step]:
        s+=min(math.dist(a,b) for b in B); n+=1
    return s/n
def solve_file(path, layers=None):
    d=ezdxf.readfile(path); raw=raw_segments(d.modelspace(),layers)
    AL,op=stitch(raw)
    print(f"{path}: {len(AL)} closed loops, {len(op)} open chains")
    cands=[]
    for k in P:
        for rot,mir in ORI:
            DL=die_oriented(k,rot,mir)
            for di,dl in enumerate(DL):
                w=dl['bb'][2]-dl['bb'][0]; h=dl['bb'][3]-dl['bb'][1]
                for ai,al in enumerate(AL):
                    b=al['bb']
                    if abs((b[2]-b[0])-w)>0.004 or abs((b[3]-b[1])-h)>0.004: continue
                    if abs(abs(al['area'])-dl['area'])>0.01*dl['area']+1e-4: continue
                    off=(b[0]-dl['bb'][0], b[1]-dl['bb'][1])   # implied die origin
                    moved=[(p[0]+off[0],p[1]+off[1]) for p in dl['pts']]
                    err=mean_nn(moved, al['pts'])
                    if err<0.003: cands.append((k,rot,mir,round(off[0],3),round(off[1],3),di,ai,err,off))
    # group by die instance (k,rot,mir,origin)
    G=collections.defaultdict(dict)
    for k,rot,mir,ox,oy,di,ai,err,off in cands:
        G[(k,rot,mir,ox,oy)][di]=(ai,err,off)
    inst=[]
    for (k,rot,mir,ox,oy),m in G.items():
        n_outer=sum(1 for L in P[k]['loops'] if L['depth']==0)
        if len(m)==n_outer:
            off=tuple(sum(v[2][i] for v in m.values())/len(m) for i in (0,1))
            inst.append({'part':k,'rot':rot,'mir':mir,'pos':off,'loops':sorted(v[0] for v in m.values()),
                         'err':max(v[1] for v in m.values())})
    # drop instances whose loop set is a strict subset of another (e.g. strut-only matches) and dedupe symmetric
    inst.sort(key=lambda i:(-len(i['loops']),i['err']))
    used=set(); final=[]
    for i in inst:
        if any(l in used for l in i['loops']): continue
        final.append(i); used.update(i['loops'])
    unclaimed=[ai for ai in range(len(AL)) if ai not in used]
    return final, AL, unclaimed
if __name__=='__main__':
    res={}
    for f in ('PlanAssembly','VertSection'):
        fin,AL,un=solve_file(f'dxf/{f}.dxf')
        for i in sorted(fin,key=lambda i:(round(i['pos'][1]),i['pos'][0])):
            sz=P[i['part']]['size']; w,h=(sz if i['rot'] in (0,180) else sz[::-1])
            print(f"   {i['part']:12s} rot{i['rot']:3d}{'M' if i['mir'] else ' '} bbox x {i['pos'][0]:.4f}..{i['pos'][0]+w:.4f}  y {i['pos'][1]:.4f}..{i['pos'][1]+h:.4f}  err {i['err']:.1e}")
        print("   unclaimed loops:", [(u, [round(v,3) for v in AL[u]['bb']], round(abs(AL[u]['area']),4)) for u in un])
        res[f]=[{k:v for k,v in i.items() if k!='loops'} for i in fin]
    json.dump(res,open('instances.json','w'),indent=1)
