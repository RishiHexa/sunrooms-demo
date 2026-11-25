"""Build panel M-F-2Vtrap (Trapezoidal copy of M-F-2v).

Left vertical T02GR-Male: 80.000" (at X = 0)
Right vertical T03GR-Female: 90.000" (at X = 32.209")
Top T02GR-Male: raked continuously along top slope from (0, 80") to (32.209", 90")
Mullion T04GR-Horizontal: stays horizontal, top flat body face at Z = 25.125"
"""

import os
import sys
import importlib

PANELS_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\season4\panels"
if PANELS_DIR not in sys.path:
    sys.path.insert(0, PANELS_DIR)

import panel_builder
importlib.reload(panel_builder)

panel_builder.build_panel(
    panel_name="M-F-2Vtrap",
    left_die="T02",
    right_die="T03",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=90.0,
    mullion_top_heights_in=(25.125,),
    screw_hole_dia_in=0.201,
    save_path=os.path.join(PANELS_DIR, "M-F-2Vtrap.FCStd"),
)
