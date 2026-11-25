"""Build 225-series panel: 225-Fix-Window-FixTrap.

Based on 225-Solid-Window-FixTrap with a bottom horizontal A26948 rail added
(Z = 0.0000 .. 1.1250", deep U-pocket UP) and 4 mitered A26950 glass adaptors
around the bottom opening to turn it into a fixed-glass opening.

Toggleable Model Tree layers (click & press Spacebar):
  - Panel_Frame           : 6 structural channels (Left A26948, Right A26949, 4 A26948 rails) + 16 #10 holes
  - Bottom_Glass_Adaptors : 4 mitered A26950 glass adaptors around the bottom 30.000" x 20.563" opening
  - Slider_Window         : SliderSash225 in the middle 30.000" x 45.000" opening
  - Top_Glass_Adaptors    : 4 angle-bisector mitered A26950 adaptors around the top trapezoidal opening
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
    panel_name="225-Fix-Window-FixTrap",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=90.0,
    rails=[
        {"name": "Bottom_A26948_Horizontal", "z_bottom": 0.0000,  "pocket_dir": "up"},
        {"name": "Lower_A26948_Horizontal",  "z_bottom": 21.6880, "pocket_dir": "down"},
        {"name": "Upper_A26948_Horizontal",  "z_bottom": 67.8130, "pocket_dir": "up"},
        {"name": "Top_A26948_Horizontal",    "z_bottom": 78.8750, "pocket_dir": "down", "raked_top": True},
    ],
    screw_hole_dia_in=0.201,
    slider_opening_z=(22.8130, 67.8130),
    glass_adaptor_openings=[
        {
            "group_name": "Bottom_Glass_Adaptors",
            "prefix": "Bottom",
            "z": (1.1250, 21.6880),
        },
        {
            "group_name": "Top_Glass_Adaptors",
            "prefix": "Top",
            "z": (68.9380, "raked_top"),
        },
    ],
    save_path=os.path.join(PANELS_DIR, "225-Fix-Window-FixTrap.FCStd"),
)
