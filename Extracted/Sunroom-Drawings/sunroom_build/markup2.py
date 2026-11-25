import ezdxf, json, math, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

msp=ezdxf.readfile("/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/SideWall-Description.dxf").modelspace()
members=json.load(open('members.json'))['members']

segs=[((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)) for e in msp.query('LINE') if e.dxf.layer=='Existing']
TOL=0.6
k=lambda p:(round(p[0]/TOL),round(p[1]/TOL))
adj={}; pos={}
for a,b in segs:
    adj.setdefault(k(a),set()).add(k(b)); adj.setdefault(k(b),set()).add(k(a)); pos[k(a)]=a; pos[k(b)]=b
seen=set(); comps=[]
for n in adj:
    if n in seen: continue
    st=[n]; c=set()
    while st:
        x=st.pop()
        if x in c: continue
        c.add(x); seen.add(x); st.extend(adj[x]-c)
    comps.append(c)

callouts=[]
for e in msp.query('MTEXT'):
    if e.dxf.layer!='Walls': continue
    clean=re.sub(r'\\\\[A-Za-z][^;]*;','',e.text).replace('\\P','\n')
    if 'AS-' not in clean: continue
    callouts.append({'pos':(e.dxf.insert.x,e.dxf.insert.y),'text':clean.strip()})

dist=lambda p,q: math.hypot(p[0]-q[0],p[1]-q[1])
used=set()
for co in callouts:
    best=None
    for ci,c in enumerate(comps):
        if ci in used: continue
        d=min(dist(co['pos'],pos[n]) for n in c)
        if best is None or d<best[1]: best=(ci,d)
    co['comp']=best[0]; used.add(best[0])

COLORS=['#c8102e','#0057b8','#0b8457','#e07b00','#7d3c98','#00838f','#a0522d','#b0006e']
fig,ax=plt.subplots(figsize=(22,15))
for e in msp.query('LINE'):
    if e.dxf.layer!='Walls': continue
    s,t=e.dxf.start,e.dxf.end
    ax.plot([s.x,t.x],[s.y,t.y],color='#111',lw=2.2,zorder=4)
for e in msp.query('CIRCLE'):
    c=e.dxf.center; ax.add_patch(plt.Circle((c.x,c.y),e.dxf.radius,fill=False,color='#111',lw=1.5,zorder=4))

handles=[]
for i,co in enumerate(callouts):
    col=COLORS[i%len(COLORS)]
    for a,b in segs:
        if k(a) in comps[co['comp']]:
            ax.plot([a[0],b[0]],[a[1],b[1]],color=col,lw=1.8,ls='--',alpha=.9,zorder=3)
    ax.text(co['pos'][0],co['pos'][1],co['text'],fontsize=10,color=col,fontweight='bold',
            va='top',zorder=8,bbox=dict(fc='white',ec=col,lw=1.4,alpha=.97,pad=3))
    handles.append(Line2D([],[],color=col,lw=1.8,ls='--',label=co['text'].split('\n')[0]))

for m in members:
    mx,my=m['mid']; th=f"{m['thick']:.3f}" if m['thick'] else "-"
    ax.plot(mx,my,'o',color='#111',ms=26,zorder=6)
    ax.text(mx,my,f"M{m['id']:02d}",color='white',ha='center',va='center',fontsize=12,fontweight='bold',zorder=7)
    ax.text(mx,my-6,f"{m['kind']} L={m['len']:.2f} t={th}",color='#111',ha='center',va='top',
            fontsize=9,zorder=7,bbox=dict(fc='#ffe9a8',ec='none',alpha=.9,pad=1.5))

ax.set_aspect('equal'); ax.grid(alpha=.25,ls=':')
ax.set_xlabel('inches'); ax.set_ylabel('inches')
ax.set_title('SideWall-Description — member map for markup   (each callout has its own leader colour)',fontsize=15,pad=14)
ax.legend(handles=handles,loc='upper left',bbox_to_anchor=(1.01,1),fontsize=9,title='callouts')
plt.tight_layout(); plt.savefig('SideWall_member_map.png',dpi=115,bbox_inches='tight')
print("ok")
