"""Build panel M-F-3Vtrap (Trapezoidal 3-lite panel based on M-F-2Vtrap).

Left vertical T02GR-Male: 80.000" (at X = 0)
Right vertical T03GR-Female: 90.000" (at X = 32.209")
Top T02GR-Male: raked continuously along top slope from (0, 80") to (32.209", 90")
Mullion 1 (lower T04GR-Horizontal): horizontal, top flat body face at Z = 25.125"
Mullion 2 (upper T04GR-Horizontal): horizontal, top fin tip 10.000" below the
  top raked fin tip measured at the left opening edge (X = 1.625"):
  - Top raked fin tip at X = 1.625": Z = 78.8030"
  - Mullion 2 top fin tip: Z = 68.8030" (top flat body face at Z = 68.1780")
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

OPENING_W = 30.0
H_LEFT = 80.0
H_RIGHT = 90.0
TOTAL_W = panel_builder.BODY_THICKNESS["T02"] + OPENING_W + panel_builder.BODY_THICKNESS["T03"]  # 32.209"

tan_rake = (H_RIGHT - H_LEFT) / TOTAL_W
cos_rake = 1.0 / math.sqrt(1.0 + tan_rake * tan_rake)

# Leftmost visible point of the top raked fin (where it meets Left_T02_Male's fin tip at X = 1.625")
x_left_fin = panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT  # 1.625"
z_top_fin_left = H_LEFT + tan_rake * x_left_fin - (panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT) / cos_rake

TRANSOM_CLEAR_LEFT_IN = 10.0
UPPER_MULLION_TOP_FIN_Z = z_top_fin_left - TRANSOM_CLEAR_LEFT_IN
UPPER_MULLION_TOP_BODY_Z = UPPER_MULLION_TOP_FIN_Z - panel_builder.FIN_HEIGHT

print(f"Top raked fin tip at left fin (X={x_left_fin:.3f}\"): Z={z_top_fin_left:.4f}\"")
print(f"Upper T04 mullion: top_fin_Z={UPPER_MULLION_TOP_FIN_Z:.4f}\", top_body_Z={UPPER_MULLION_TOP_BODY_Z:.4f}\"")

panel_builder.build_panel(
    panel_name="M-F-3Vtrap",
    left_die="T02",
    right_die="T03",
    opening_width_in=OPENING_W,
    height_in=H_LEFT,
    height_right_in=H_RIGHT,
    mullion_top_heights_in=(25.125, UPPER_MULLION_TOP_BODY_Z),
    screw_hole_dia_in=0.201,
    save_path=os.path.join(PANELS_DIR, "M-F-3Vtrap.FCStd"),
)
