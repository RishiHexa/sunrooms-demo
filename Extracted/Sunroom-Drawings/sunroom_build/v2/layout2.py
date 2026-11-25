"""Vertical-channel layout per wall.
Handedness rule: female on the LEFT, male on the RIGHT, as seen from OUTSIDE the wall.
  observer outside, forward = inward normal, up = +Z, right = forward x up
    FRONT  outside -Y, forward +Y -> right = +X   : female at X=0 end,  male at X=216 end
    LEFT   outside -X, forward +X -> right = -Y   : female at HOUSE end, male at CORNER end
    RIGHT  outside +X, forward -X -> right = +Y   : female at CORNER end, male at HOUSE end
This is confirmed by the section end conditions in 225-Assembly.dxf.
"""
import json
L=json.load(open('layout.json')); P=json.load(open('profiles_all.json'))
def dims(n):
    xs=[];ys=[]
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)
FW,DP = L['front_w'], L['depth']
FEMW,MALW,WCW = L['fem_w'], L['male_w'], L['wc_w']
# The corner post is 2.265 x 2.402 and NOT square, so its rotation decides which
# dimension faces which wall. Measured from 225-Assembly.dxf:
#   LEFT wall   : post presents 2.265 along the wall   (3 samples)
#   RIGHT wall  : post presents 2.402 along the wall   (3 samples)
#   FRONT wall  : 2.402 at the LEFT end (2 samples), 2.265 at the RIGHT end
POST_A, POST_B = 2.265, 2.402
P_FRONT_L, P_FRONT_R = POST_B, POST_A
P_LEFT, P_RIGHT      = POST_A, POST_B
E=lambda a,b: L['engage'][f"{a}|{b}"]
E_POST = E('A26952','A26948')          # 0.1270
E_MID  = E('A26949','A26948')          # 0.1173
NEST_M = E('A62420','A26949')          # 0.2071  male  nested in the wall channel
NEST_F = 0.0793                        # measured 2x on the left-side sections
                                       # (a third instance reads 0.1408 - see reference)

def run(n, start, direction, first_gap, W):
    """lay n panels from `start` moving in `direction` (+1/-1). returns list of
       (female_outer, male_outer) as world ordinates along the wall axis."""
    out=[]; x = start + direction*first_gap
    for i in range(n):
        f0 = x
        m1 = x + direction*W
        out.append((f0, m1))
        x = m1 - direction*E_MID
    return out

# ---- FRONT: post at both ends, female at X=0 end ----
NF=4
f_start = P_FRONT_L - E_POST                    # first female outer edge
f_end   = (FW - P_FRONT_R) + E_POST             # last male outer edge
W_FRONT = ((f_end - f_start) + (NF-1)*E_MID)/NF
front = run(NF, P_FRONT_L, +1, -E_POST, W_FRONT)

# ---- RIGHT: female at the CORNER end, male nested in the wall channel at the HOUSE end ----
NR=2
right_end = DP - NEST_M
W_RIGHT = ((right_end - (P_RIGHT - E_POST)) + (NR-1)*E_MID)/NR
right = run(NR, P_RIGHT, +1, -E_POST, W_RIGHT)

# ---- LEFT: female nested in the wall channel at the HOUSE end, male at the CORNER post ----
NL=2
left_start = DP - NEST_F                     # female outer edge, house end
left_end   = P_LEFT - E_POST                 # male outer edge, at the corner post
W_LEFT = ((left_start - left_end) + (NL-1)*E_MID)/NL
left = run(NL, left_start, -1, 0.0, W_LEFT)

print("=== panel widths (female outer edge to male outer edge) ===")
print(f"  FRONT  {NF} panels  W = {W_FRONT:.4f}")
print(f"  RIGHT  {NR} panels  W = {W_RIGHT:.4f}   (corner post -> male nested {NEST_M})")
print(f"  LEFT   {NL} panels  W = {W_LEFT:.4f}   (female nested {NEST_F} -> corner post)")
print(f"  left/right panel width difference: {abs(W_LEFT-W_RIGHT):.4f}\"")
print("\n=== closure ===")
print(f"  front: last male outer {front[-1][1]:.4f} + post engage -> {front[-1][1]-E_POST+P_FRONT_R:.4f}  target {FW}")
print(f"  right: last male outer {right[-1][1]:.4f} + nest {NEST_M} -> {right[-1][1]+NEST_M:.4f}  target {DP}")
print(f"  left : first female outer {left[0][0]:.4f} + nest {NEST_F} -> {left[0][0]+NEST_F:.4f}  target {DP}")
print(f"         last male outer {left[-1][1]:.4f}; corner post spans 0..{P_LEFT:.4f}, engage {P_LEFT-left[-1][1]:.4f}")
print("\n=== vertical channel positions (world Y or X) ===")
for name,seq in (("FRONT",front),("RIGHT",right),("LEFT",left)):
    print(f"  {name}")
    for i,(f0,m1) in enumerate(seq):
        d = 1 if m1>f0 else -1
        print(f"    panel {i+1}: female {min(f0,f0+d*FEMW):8.4f}..{max(f0,f0+d*FEMW):8.4f}   "
              f"male {min(m1-d*MALW,m1):8.4f}..{max(m1-d*MALW,m1):8.4f}")
L.update({'post_front_l':P_FRONT_L,'post_front_r':P_FRONT_R,'post_left':P_LEFT,'post_right':P_RIGHT,
          'w_front2':W_FRONT,'w_right':W_RIGHT,'w_left':W_LEFT,
          'nest_male':NEST_M,'nest_female':NEST_F,
          'front_seq':front,'right_seq':right,'left_seq':left})
json.dump(L, open('layout.json','w'), indent=1)
print("\nupdated layout.json")
