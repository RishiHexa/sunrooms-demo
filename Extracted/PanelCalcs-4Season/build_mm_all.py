"""Batch generator for all 6 Male-Male (M-M) 4-Season Sunroom Panels.

Exact duplicates of the 6 M-F panels with the right vertical profile swapped
from T03GR-Female to T02GR-Male (right_die="T02"):
  1. M-M-2v
  2. M-M-3V
  3. M-M-2Vtrap
  4. M-M-3Vtrap
  5. M-M-1Door
  6. M-M-2DoorTrap
"""

import importlib
import math
import os
import sys
import FreeCAD as App

PANELS_DIR = r"C:\DaVinci_Works\Lifestyle\sunroom_build\season4\panels"
SCRATCH_DIR = r"C:\Users\johnf\.gemini\antigravity\brain\85a6daa0-257e-4b60-964b-1610e7193489\scratch"
if PANELS_DIR not in sys.path:
    sys.path.insert(0, PANELS_DIR)

import panel_builder
importlib.reload(panel_builder)


def raked_transom_top_body_z(opening_w, h_left, h_right, clear_left_fin_in, left_die="T02", right_die="T02"):
    total_w = panel_builder.BODY_THICKNESS[left_die] + opening_w + panel_builder.BODY_THICKNESS[right_die]
    tan_r = (h_right - h_left) / total_w
    cos_r = 1.0 / math.sqrt(1.0 + tan_r * tan_r)
    x_left_fin = panel_builder.BODY_THICKNESS[left_die] + panel_builder.FIN_HEIGHT
    z_top_fin_left = h_left + tan_r * x_left_fin - (panel_builder.BODY_THICKNESS["T02"] + panel_builder.FIN_HEIGHT) / cos_r
    top_fin_z = z_top_fin_left - clear_left_fin_in
    return top_fin_z - panel_builder.FIN_HEIGHT


SPECS = [
    dict(
        panel_name="M-M-2v",
        opening_width_in=30.0,
        height_in=80.0,
        height_right_in=80.0,
        mullion_top_heights_in=(25.125,),
        include_bottom=True,
    ),
    dict(
        panel_name="M-M-3V",
        opening_width_in=30.0,
        height_in=80.0,
        height_right_in=80.0,
        mullion_top_heights_in=(
            25.125,
            (80.0 - panel_builder.BODY_THICKNESS["T02"] - panel_builder.FIN_HEIGHT - 10.0) - panel_builder.FIN_HEIGHT,
        ),
        include_bottom=True,
    ),
    dict(
        panel_name="M-M-2Vtrap",
        opening_width_in=30.0,
        height_in=80.0,
        height_right_in=90.0,
        mullion_top_heights_in=(25.125,),
        include_bottom=True,
    ),
    dict(
        panel_name="M-M-3Vtrap",
        opening_width_in=30.0,
        height_in=80.0,
        height_right_in=90.0,
        mullion_top_heights_in=(
            25.125,
            raked_transom_top_body_z(30.0, 80.0, 90.0, 10.0, left_die="T02", right_die="T02"),
        ),
        include_bottom=True,
    ),
    dict(
        panel_name="M-M-1Door",
        opening_width_in=72.0,
        height_in=80.0,
        height_right_in=80.0,
        mullion_top_heights_in=(),
        include_bottom=False,
    ),
    dict(
        panel_name="M-M-2DoorTrap",
        opening_width_in=72.0,
        height_in=80.0,
        height_right_in=90.0,
        mullion_top_heights_in=(
            raked_transom_top_body_z(72.0, 80.0, 90.0, 1.0, left_die="T02", right_die="T02"),
        ),
        include_bottom=False,
    ),
]

for idx, spec in enumerate(SPECS):
    name = spec["panel_name"]
    save_path = os.path.join(PANELS_DIR, f"{name}.FCStd")
    doc = panel_builder.build_panel(
        left_die="T02",
        right_die="T02",
        screw_hole_dia_in=0.201,
        save_path=save_path,
        **spec,
    )
    if App.GuiUp:
        import FreeCADGui as Gui
        view = Gui.ActiveDocument.ActiveView
        view.viewFront()
        Gui.SendMsgToActiveView("ViewFit")
        Gui.updateGui()
        if os.path.isdir(SCRATCH_DIR):
            view.saveImage(os.path.join(SCRATCH_DIR, f"preview_{name}.png"), 700, 600, "Current")
            if name == "M-M-2v":
                from FreeCAD import Vector as V
                from pivy import coin
                cam = view.getCameraNode()
                S = 25.4
                t = V(31.5, 2.09, 25.0) * S
                e = t + V(20, 0, 0) * S
                cam.position.setValue(e.x, e.y, e.z)
                cam.pointAt(coin.SbVec3f(t.x, t.y, t.z), coin.SbVec3f(0, 0, 1))
                cam.focalDistance.setValue((e - t).Length)
                cam.nearDistance.setValue(10.0)
                cam.farDistance.setValue(10000.0)
                if hasattr(cam, "height"):
                    cam.height.setValue(5.0 * S)
                Gui.updateGui()
                view.saveImage(os.path.join(SCRATCH_DIR, "mm_right_t02_holes.png"), 900, 700, "Current")
        view.viewIsometric()
        Gui.SendMsgToActiveView("ViewFit")

    # Close intermediate documents to keep memory lean; leave the last panel open
    if idx < len(SPECS) - 1:
        App.closeDocument(doc.Name)

print("\nALL 6 M-M PANELS GENERATED AND SAVED SUCCESSFULLY.")
