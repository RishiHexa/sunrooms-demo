"""Build panel M-F-3V (Male left, Female right, 3 vertical lites).

Same as M-F-2v with an added upper T04GR-Horizontal transom mullion placed
10.000" clear (fin-tip to fin-tip) below Top_T02_Male:
  - Top_T02_Male fin tip: Z = 78.375"
  - Upper T04 top fin tip: Z = 68.375"  (top flat body face at Z = 67.750")
"""

import os
import sys

PANELS_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\season4\panels"
if PANELS_DIR not in sys.path:
    sys.path.insert(0, PANELS_DIR)

import importlib
import panel_builder
importlib.reload(panel_builder)

HEIGHT = 80.0
TOP_T02_FIN_Z = HEIGHT - panel_builder.BODY_THICKNESS["T02"] - panel_builder.FIN_HEIGHT  # 78.375"
TRANSOM_CLEAR_FIN_IN = 10.0
UPPER_MULLION_TOP_BODY_Z = (TOP_T02_FIN_Z - TRANSOM_CLEAR_FIN_IN) - panel_builder.FIN_HEIGHT  # 67.750"

panel_builder.build_panel(
    panel_name="M-F-3V",
    left_die="T02",
    right_die="T03",
    opening_width_in=30.0,
    height_in=HEIGHT,
    mullion_top_heights_in=(25.125, UPPER_MULLION_TOP_BODY_Z),
    screw_hole_dia_in=0.201,
    save_path=os.path.join(PANELS_DIR, "M-F-3V.FCStd"),
)
