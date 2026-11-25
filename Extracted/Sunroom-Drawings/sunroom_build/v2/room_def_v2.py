"""225 Sunroom - room definition v2.
Authority split:
  225-Assembly.dxf  -> part ORDER, ORIENTATION and JOINT ENGAGEMENT (measured)
  225-Room-Description.dxf -> overall DIMENSIONS
  225 SunRoom Assembly.txt -> assembly RULES
Overall dimensions are to the OUTSIDE of the perimeter channels.
World: X along front 0->216 | Y depth, front=0 house=144 | Z height, floor=0
"""
import json, math

P=json.load(open('profiles_all.json'))
def dims(n):
    xs=[];ys=[]
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)

# ---- measured engagements (from 225-Assembly.dxf cross sections) ----
ENGAGE = {
 ('A26952','A26948'): 0.1270,   # corner post -> female      n=5, zero variance
 ('A26949','A26952'): 0.1270,   # male -> corner post
 ('A26949','A26948'): 0.1173,   # male -> female (mode; 0.1377 cluster also present)
 ('A26950','A26949'): 0.2196,   # glass adaptor -> male
 ('A26948','A26950'): 0.2196,   # female -> glass adaptor
 ('A26948','A33864'): 0.2166,   # female -> slider side track
 ('A26948','A45216'): 0.2192,   # female -> slider lock track
 ('A33864','A26949'): 0.2191,
 ('A45216','A26949'): 0.2192,
 ('A26948','A33861'): 0.2191,   # female -> slider top sill  (vertical)
 ('A33863','A26948'): 0.2287,   # slider bottom sill -> female (vertical)
 ('A62420','A26949'): 0.2071,   # male NESTS into wall channel; inset of male from
                                # the channel's outer face. measured 3x, zero variance.
}
MALE_FEMALE_ALT = 0.1377        # second cluster seen in the sections

# ---- overall (to outside of channels) ----
FRONT_W, DEPTH = 216.00, 144.00
H_LOW, H_HIGH  = 84.00, 96.00
CH_D, CH_H = dims('A62421')          # 2.405 deep, 1.688 high
POST_A, POST_B = dims('A26952')      # 2.265 / 2.402
FEM_W  = dims('A26948')[1]           # 1.125
MALE_W = dims('A26949')[1]           # 1.262
WC_W   = dims('A62420')[1]           # 1.250
# measured: post presents 2.402 along the FRONT wall, 2.265 along the SIDE walls
POST_FRONT, POST_SIDE = POST_B, POST_A

def panel_width(clear, n, e_end, e_mid):
    """n panels spanning `clear`, each female-left to male-right, engaging e_mid
       between panels and e_end at both ends."""
    return (clear + 2*e_end + (n-1)*e_mid) / n

# ---- front wall: 4 panels between the corner posts ----
FRONT_N = 4
front_clear = FRONT_W - 2*POST_FRONT
W_FRONT = panel_width(front_clear, FRONT_N, ENGAGE[('A26952','A26948')], ENGAGE[('A26949','A26948')])

# ---- side walls: 2 panels. corner post at the front end (edge joint),
#      wall channel at the house end (the male NESTS inside it, not an edge joint) ----
SIDE_N = 2
NEST = ENGAGE[('A62420','A26949')]
male_end = DEPTH - NEST                       # outer edge of the last male
e_post   = ENGAGE[('A26952','A26948')]
e_mid    = ENGAGE[('A26949','A26948')]
W_SIDE   = (male_end - POST_SIDE + e_post + (SIDE_N-1)*e_mid) / SIDE_N
side_clear = male_end - POST_SIDE

print("=== derived layout ===")
print(f"  channel {CH_D:.4f} deep x {CH_H:.4f} high      corner post {POST_A:.3f} x {POST_B:.3f}")
print(f"  front: {FRONT_N} panels, clear {front_clear:.4f}  -> panel width {W_FRONT:.4f}")
print(f"  side : {SIDE_N} panels, clear {side_clear:.4f}  -> panel width {W_SIDE:.4f}")

# ---- verify the run closes ----
def run_positions(start, n, W, e_end, e_mid):
    """returns [(female_x0, male_x1), ...] for each panel"""
    out=[]; x = start - e_end
    for i in range(n):
        out.append((x, x+W))
        x = x + W - e_mid
    return out
fp = run_positions(POST_FRONT, FRONT_N, W_FRONT, ENGAGE[('A26952','A26948')], ENGAGE[('A26949','A26948')])
end = fp[-1][1] - ENGAGE[('A26949','A26952')] + POST_FRONT
print(f"  front run closes at {end:.4f}  (target {FRONT_W})   error {end-FRONT_W:+.6f}")
sp = run_positions(POST_SIDE, SIDE_N, W_SIDE, e_post, e_mid)
end2 = sp[-1][1] + NEST
print(f"  side  run closes at {end2:.4f}  (target {DEPTH})   error {end2-DEPTH:+.6f}")

json.dump({'front_w':FRONT_W,'depth':DEPTH,'h_low':H_LOW,'h_high':H_HIGH,
           'ch_d':CH_D,'ch_h':CH_H,'post_front':POST_FRONT,'post_side':POST_SIDE,
           'fem_w':FEM_W,'male_w':MALE_W,'wc_w':WC_W,
           'w_front':W_FRONT,'w_side':W_SIDE,'engage':{f"{a}|{b}":v for (a,b),v in ENGAGE.items()},
           'front_panels':fp,'side_panels':sp}, open('layout.json','w'), indent=1)
print("\nwrote layout.json")
