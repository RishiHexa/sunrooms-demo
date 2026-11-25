"""Build 225-series panel: 225-Door-FixTrap.

Based on 225-Door-SolidTrap with:
  - Left vertical A26948 raised to 84.000" (at X = 0") and Right vertical A26949
    raised to 94.000" (at X = 32.387", preserving the exact +17.157 deg top rake)
  - Horizontal Header_A26948_Horizontal kept at Z = 78.8750 .. 80.0000" (deep pocket UP)
  - Added sloped Top_A26948_Horizontal along the 84"->94" top rake (deep pocket DOWN)
  - Toggleable Top_Glass_Adaptors layer with 4 angle-bisector mitered A26950 glass
    adaptors around the trapezoidal fixed opening above the door header
    (3.170" opening on left rising to 12.433" on right)
  - 8 coaxial #10 clearance holes (4 per vertical: 0 deg at Header, +17.157 deg at Top)
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
    panel_name="225-Door-FixTrap",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=84.0,
    height_right_in=94.0,
    rails=[
        {"name": "Header_A26948_Horizontal", "z_bottom": 78.8750, "pocket_dir": "up"},
        {"name": "Top_A26948_Horizontal",    "z_bottom": 82.8750, "pocket_dir": "down", "raked_top": True},
    ],
    screw_hole_dia_in=0.201,
    slider_opening_z=None,
    glass_adaptor_opening_z=(80.0000, "raked_top"),
    glass_adaptor_sides=("bottom", "top", "left", "right"),
    save_path=os.path.join(PANELS_DIR, "225-Door-FixTrap.FCStd"),
)
