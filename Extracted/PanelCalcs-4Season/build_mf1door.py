"""Build panel M-F-1Door (72" wide door opening frame, no bottom T02, no T04 mullions).

Left vertical T02GR-Male: 80.000" (X = 0 .. 1.625")
Right vertical T03GR-Female: 80.000" (X = 72.375 .. 74.209")
Top T02GR-Male: 72.000" span between vertical body faces (X = 1.000 .. 73.000")
No bottom T02GR-Male, no T04GR-Horizontal mullions.
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
    panel_name="M-F-1Door",
    left_die="T02",
    right_die="T03",
    opening_width_in=72.0,
    height_in=80.0,
    mullion_top_heights_in=(),
    include_bottom=False,
    screw_hole_dia_in=0.201,
    save_path=os.path.join(PANELS_DIR, "M-F-1Door.FCStd"),
)
