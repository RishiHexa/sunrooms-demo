"""Build 225-series panel: 225-Door-SolidTrap.

Same overall dimensions as 225-Solid-Window-FixTrap (32.387" W x 2.280" D,
80.000" left -> 90.000" right, +17.157 deg top rake):
  - Left_A26948_Female       : X = 0.0000 .. 1.1250", bevel-cut to top slope (80.000" at X=0)
  - Right_A26949_Male        : X = 31.1250 .. 32.3870", bevel-cut to top slope (90.000" at X=32.387")
  - Header_A26948_Horizontal : 1 horizontal A26948 rail at Z = 78.8750 .. 80.0000" (top at 80.000"),
                               deep U-pocket facing UP to receive the solid trapezoid infill panel,
                               flange-notched & coped into both vertical U-pockets, with 4 coaxial
                               #10 clearance screw holes (2 per vertical).
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
    panel_name="225-Door-SolidTrap",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=80.0,
    height_right_in=90.0,
    rails=[
        {"name": "Header_A26948_Horizontal", "z_bottom": 78.8750, "pocket_dir": "up"},
    ],
    screw_hole_dia_in=0.201,
    slider_opening_z=None,
    glass_adaptor_opening_z=None,
    save_path=os.path.join(PANELS_DIR, "225-Door-SolidTrap.FCStd"),
)
