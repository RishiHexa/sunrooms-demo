import ezdxf, json, sys
sys.path.insert(0,'/home/claude/s4')
from loops import *
DIES={'T01':'WallChannel','T02':'Male','T03':'Female','T04':'Horizontal','T05':'TopBottomChannel','CornerPost':'CornerPost','InsideCorner':'InsideCorner'}
out={}
for k,name in DIES.items():
    d=ezdxf.readfile(f'dxf/{k}.dxf'); raw=raw_segments(d.modelspace(),{'0'})
    L,op=stitch(raw); nest(L)
    x0=min(l['bb'][0] for l in L); y0=min(l['bb'][1] for l in L); x1=max(l['bb'][2] for l in L); y1=max(l['bb'][3] for l in L)
    print(f"{k:12s} raw={len(raw)} loops={len(L)} open={len(op)} size={x1-x0:.4f} x {y1-y0:.4f}")
    for i,l in enumerate(L):
        b=l['bb']; print(f"    loop{i} depth={l['depth']} area={abs(l['area']):.4f} bb={b[2]-b[0]:.4f}x{b[3]-b[1]:.4f} at ({b[0]-x0:.4f},{b[1]-y0:.4f})")
    out[k]={'name':name,'origin':[x0,y0],'size':[x1-x0,y1-y0],
            'loops':[{'segs':[[s[0]]+[[p[0]-x0,p[1]-y0] for p in s[1:]] for s in l['segs']],'depth':l['depth'],'area':abs(l['area'])} for l in L]}
json.dump(out,open('profiles.json','w'))
