import ezdxf, json, math, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

msp=ezdxf.readfile("/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/SideWall-Description.dxf").modelspace()
M=json.load(open('members.json')); members=M['members']

fig,ax=plt.subplots(figsize=(20,16))
# walls geometry
for e in msp.query('LINE'):
    s,t=e.dxf.start,e.dxf.end
    if e.dxf.layer=='Walls':
        ax.plot([s.x,t.x],[s.y,t.y],color='#222',lw=2.0,zorder=3)
    else:
        ax.plot([s.x,t.x],[s.y,t.y],color='#c8102e',lw=1.0,ls='--',alpha=.8,zorder=2)
for e in msp.query('CIRCLE'):
    c=e.dxf.center
    ax.add_patch(plt.Circle((c.x,c.y),e.dxf.radius,fill=False,color='#222',lw=1.5,zorder=3))

# member labels
for m in members:
    mx,my=m['mid']
    th = f"{m['thick']:.3f}" if m['thick'] else "-"
    ax.plot(mx,my,'o',color='#0057b8',ms=22,zorder=5)
    ax.text(mx,my,f"M{m['id']:02d}",color='white',ha='center',va='center',
            fontsize=11,fontweight='bold',zorder=6)
    ax.text(mx,my-5.5,f"{m['kind']}  L={m['len']:.2f}  t={th}",color='#0057b8',
            ha='center',va='top',fontsize=9,zorder=6,
            bbox=dict(fc='white',ec='none',alpha=.75,pad=1))

# callout text
for e in msp.query('MTEXT'):
    if e.dxf.layer!='Walls': continue
    clean=re.sub(r'\\\\[A-Za-z][^;]*;','',e.text).replace('\\P','\n')
    ip=e.dxf.insert
    isprt='AS-' in clean
    ax.text(ip.x,ip.y,clean,fontsize=9,color='#c8102e' if isprt else '#444',
            fontweight='bold' if isprt else 'normal', va='top', zorder=7,
            bbox=dict(fc='#fff8e7' if isprt else 'white',ec='#c8102e' if isprt else '#bbb',lw=.8,alpha=.95,pad=2))

ax.set_aspect('equal'); ax.grid(alpha=.25,ls=':')
ax.set_xlabel('inches'); ax.set_ylabel('inches')
ax.set_title('SideWall-Description  —  member IDs for markup\n'
             'black = wall geometry   red dashed = leader lines   blue = member ID',fontsize=14)
ax.legend(handles=[Line2D([],[],color='#222',lw=2,label='wall member edges'),
                   Line2D([],[],color='#c8102e',lw=1,ls='--',label='leader lines (Existing layer)'),
                   Line2D([],[],marker='o',color='#0057b8',lw=0,ms=10,label='member ID / kind / length / thickness')],
          loc='lower right',fontsize=10)
plt.tight_layout()
plt.savefig('SideWall_member_map.png',dpi=110)
print("wrote SideWall_member_map.png")
print("\nMember list:")
for m in members:
    th=f"{m['thick']:.3f}" if m['thick'] else "-"
    print(f"  M{m['id']:02d}  {m['kind']}  mid=({m['mid'][0]:7.2f},{m['mid'][1]:7.2f})  len={m['len']:7.2f}  thick={th}")
