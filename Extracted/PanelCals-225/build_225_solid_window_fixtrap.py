"""Build 225-series panel: 225-Solid-Window-FixTrap.

Identical to 225-Solid-Window-Fix except Right_A26949_Male extends by 10.000"
(from 80.000" to 90.000"), turning the top fixed opening into a trapezoid:
  - Panel_Frame        : Left A26948 (80" at X=0) -> Right A26949 (90" at X=32.387"),
                         horizontal lower & upper A26948 rails, raked top A26948 (+17.157 deg),
                         clean flange notches & 12 coaxial #10 clearance holes
  - Slider_Window      : Toggleable SliderSash225 in the 30.000" x 45.000" middle opening
  - Top_Glass_Adaptors : Toggleable 4 angle-bisector mitered A26950 glass adaptors around
                         the trapezoidal top fixed opening
"""

import importlib
import os
import sys

PANELS_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\v2\panels"
if PANELS_DIR not in sys.path:
    sys.path.insert(0, PANELS_DIR)

import panel225_builder
importlib.reload(panel225_builder)

panel225_builder.build_225_panel(
    panel_name="225-Solid-Window-FixTrap",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=90.0,
    rails=[
        {"name": "Lower_A26948_Horizontal", "z_bottom": 21.6880, "pocket_dir": "down"},
        {"name": "Upper_A26948_Horizontal", "z_bottom": 67.8130, "pocket_dir": "up"},
        {"name": "Top_A26948_Horizontal",   "z_bottom": 78.8750, "pocket_dir": "down", "raked_top": True},
    ],
    screw_hole_dia_in=0.201,
    slider_opening_z=(22.8130, 67.8130),         # middle 45.000" rectangular opening
    glass_adaptor_opening_z=(68.9380, "raked_top"),  # top trapezoidal fixed opening
    glass_adaptor_sides=("bottom", "top", "left", "right"),
    save_path=os.path.join(PANELS_DIR, "225-Solid-Window-FixTrap.FCStd"),
)
