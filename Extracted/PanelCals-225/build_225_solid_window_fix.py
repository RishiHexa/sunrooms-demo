"""Build 225-series panel: 225-Solid-Window-Fix with toggleable Slider & Top Glass Adaptors.

Model Tree layers (click group & press Spacebar to show/hide independently):
  - Panel_Frame        : 5 structural channels (A26948 left/horizontals, A26949 right) + #10 screw holes
  - Slider_Window      : SliderSash225 window assembly sized to snap into the 30.000" x 45.000" middle opening
  - Top_Glass_Adaptors : 4 mitered A26950 glass adaptors snapped around the 30.000" x 9.937" top opening
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
    panel_name="225-Solid-Window-Fix",
    left_die="A26948",
    right_die="A26949",
    opening_width_in=30.0,
    height_in=80.0,
    rails=[
        {"name": "Lower_A26948_Horizontal", "z_bottom": 21.6880, "pocket_dir": "down"},
        {"name": "Upper_A26948_Horizontal", "z_bottom": 67.8130, "pocket_dir": "up"},
        {"name": "Top_A26948_Horizontal",   "z_bottom": 78.8750, "pocket_dir": "down"},
    ],
    screw_hole_dia_in=0.201,
    slider_opening_z=(22.8130, 67.8130),        # middle 45.000" opening
    glass_adaptor_opening_z=(68.9380, 78.8750), # top 9.937" fixed transom opening
    glass_adaptor_sides=("bottom", "top", "left", "right"),
    save_path=os.path.join(PANELS_DIR, "225-Solid-Window-Fix.FCStd"),
)
