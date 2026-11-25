"""Build panel M-F-2DoorTrap (72" wide trapezoidal door frame with upper transom).

Based on M-F-2Vtrap + M-F-1Door:
  - Opening width between vertical body faces: 72.000" (overall width 74.209")
  - Left vertical T02GR-Male: 80.000" (at X = 0")
  - Right vertical T03GR-Female: 90.000" (at X = 74.209")
  - No bottom T02GR-Male (door opening)
  - Top T02GR-Male: raked continuously along top slope (+7.675 deg)
  - Single horizontal T04GR-Horizontal door header/mullion positioned so its
    top fin tip is 1.000" below the top raked fin tip at the left fin (X = 1.625").
"""

import math
import os
import sys
import importlib

PANELS_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\season4\panels"
if PANELS_DIR not in sys.path:
    sys.path.insert(0, PANELS_DIR)

import panel_builder
importlib.reload(panel_builder)

OPENING_W = 72.0
H_LEFT = 80.0
H_RIGHT = 90.0
TOTAL_W = panel_builder.BODY_THICKNESS["T02"] + OPENING_W + panel_builder.BODY_THICKNESS["T03"]  # 74.209"

tan_rake = (H_RIGHT - H_LEFT) / TOTAL_W
cos_rake = 1.0 / math.sqrt(1.0 + tan_rake * tan_rake)

x_left_fin = panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT  # 1.625"
z_top_fin_left = H_LEFT + tan_rake * x_left_fin - (panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT) / cos_rake

TRANSOM_CLEAR_LEFT_IN = 1.0
MULLION_TOP_FIN_Z = z_top_fin_left - TRANSOM_CLEAR_LEFT_IN
MULLION_TOP_BODY_Z = MULLION_TOP_FIN_Z - panel_builder.FIN_HEIGHT

x_right_fin = panel_builder.BODY_THICKNESS["T02"] + OPENING_W - panel_builder.FIN_HEIGHT  # 72.375"
z_top_fin_right = H_LEFT + tan_rake * x_right_fin - (panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT) / cos_rake

print(f"Top raked fin tip at left fin (X={x_left_fin:.3f}\"): Z={z_top_fin_left:.4f}\"")
print(f"Top raked fin tip at right fin (X={x_right_fin:.3f}\"): Z={z_top_fin_right:.4f}\"")
print(f"T04 header: top_fin_Z={MULLION_TOP_FIN_Z:.4f}\", top_body_Z={MULLION_TOP_BODY_Z:.4f}\"")
print(f"Transom fin-to-fin height: left={z_top_fin_left - MULLION_TOP_FIN_Z:.4f}\", right={z_top_fin_right - MULLION_TOP_FIN_Z:.4f}\"")

panel_builder.build_panel(
    panel_name="M-F-2DoorTrap",
    left_die="T02",
    right_die="T03",
    opening_width_in=OPENING_W,
    height_in=H_LEFT,
    height_right_in=H_RIGHT,
    mullion_top_heights_in=(MULLION_TOP_BODY_Z,),
    include_bottom=False,
    screw_hole_dia_in=0.201,
    save_path=os.path.join(PANELS_DIR, "M-F-2DoorTrap.FCStd"),
)
