"""FreeCAD builder. Run inside FreeCAD (see build_snippet).
Key point: to correct a member's opening direction we negate u and v in the PROFILE BASIS
and re-extrude. Rotating the finished solid 180 about its run axis is wrong for raked
members - it tips the profile out of vertical and skews the end cuts by twice the rake."""
