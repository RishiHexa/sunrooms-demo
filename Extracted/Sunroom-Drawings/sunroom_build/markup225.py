import ezdxf, json, math, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
D=json.load(open('room225.json'))
members=D['members']; leaders=D['leaders']; mapping=D['mapping']; callouts=D['callouts']
msp=ezdxf.readfile("/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/225-Room-Description.dxf").modelspace()

fig,ax=plt.subplots(figsize=(26,11))
for m in members:
    for e in m['edges']:
        (x1,y1),(x2,y2)=e
        ax.plot([x1,x2],[y1,y2],color='#111',lw=2.4,zorder=4)
for a,b in leaders:
    ax.plot([a[0],b[0]],[a[1],b[1]],color='#c8102e',lw=1.2,ls='--',alpha=.75,zorder=3)
for e in msp.query('CIRCLE'):
    c=e.dxf.center; ax.add_patch(plt.Circle((c.x,c.y),e.dxf.radius,fill=False,color='#111',lw=1.6,zorder=4))
for e in msp.query('MTEXT'):
    t=re.sub(r'\{[^}]*\}','',e.text); t=re.sub(r'\\\\?[A-Za-z][^;]*;','',t).replace('\\P','\n').strip()
    if not t: continue
    ip=e.dxf.insert; ispart=bool(re.search(r'\bA\d{4,6}\b',t))
    ax.text(ip.x,ip.y,t,fontsize=8.5,color='#c8102e' if ispart else '#555',
            fontweight='bold' if ispart else 'normal',va='top',zorder=8,
            bbox=dict(fc='#fff8e7' if ispart else 'white',ec='#c8102e' if ispart else '#ccc',lw=.7,alpha=.95,pad=1.6))
for m in members:
    mx,my=m['mid']; th=f"{m['thick']:.2f}" if m['thick'] is not None else "-"
    ax.plot(mx,my,'o',color='#0057b8',ms=24,zorder=6)
    ax.text(mx,my,f"M{m['id']:02d}",color='white',ha='center',va='center',fontsize=11,fontweight='bold',zorder=7)
    ax.text(mx,my-5.5,f"{m['kind']} L={m['len']:.2f} t={th}",color='#0057b8',ha='center',va='top',
            fontsize=8,zorder=7,bbox=dict(fc='white',ec='none',alpha=.85,pad=1))
ax.text(9.5,-40,'LEFT WALL   144.00 long   96.00 @ house  ->  84.00 @ corner   (1:12 rake)',
        ha='center',fontsize=13,fontweight='bold',color='#0b8457')
ax.text(223.9,-40,'FRONT WALL   216.00 long   84.00 high   (flat)',
        ha='center',fontsize=13,fontweight='bold',color='#0b8457')
ax.set_aspect('equal'); ax.grid(alpha=.2,ls=':')
ax.set_xlabel('inches'); ax.set_ylabel('inches')
ax.set_title('225-Room-Description  —  member map   (black = structure, red dashed = leaders, blue = member ID)',fontsize=15,pad=12)
plt.tight_layout(); plt.savefig('Room225_member_map.png',dpi=110,bbox_inches='tight')
print("ok")
