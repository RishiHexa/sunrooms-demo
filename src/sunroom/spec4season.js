/**
 * 4-Season (GF50 profile set) system constants. INCHES.
 *
 * Every value states where it comes from. Values marked MODEL are taken from the supplier's
 * 4-Season room model (Extracted/.../season4/members4.py, roof4.py) — a fixed 216" x 144" room —
 * and still need confirming as general rules. Nothing here is invented; if a value is missing,
 * the layout reports an error instead of guessing.
 */
import sections from './data/sections4.json'

const L = sections.modelLayout

export const SPEC_4SEASON = Object.freeze({
  id: '4season-gf50',
  name: '4 Season',

  // --- Panel size formula -------------------------------------------------------------
  // PanelCalcs-4Season.dxf, "NO DOOR":  X = (L - C - W - (N-1)*P) / N
  //   C = corner side allowance, W = wall (house) side allowance, P = between panels.
  // X matches panel_builder.py's `opening_width_in` (body face to body face): checked against
  // the room model to within 0.005" on the front wall (see layout tests).
  // ASSUMPTION (needs supplier confirmation): a wall with corners at both ends deducts C twice.
  cornerAllowance: 5.514, // C
  wallAllowance: 1.5, // W
  panelJoint: 1.5, // P

  // --- Panel size limits (supplier email, 4 season) -----------------------------------
  panelLimits: Object.freeze({
    fixed: { min: 8, max: 72, label: 'Fixed section' },
    slider: { min: 30, max: 72, label: 'Slider section' },
    casement: { min: 24, max: 36, label: 'Casement section' },
    solid: { min: 6, max: 48, label: 'Solid full vertical panel' },
  }),
  // Panel type of a panel with no stored choice (plan.walls[i].windows[k] null / missing).
  defaultPanelType: 'fixed',

  // --- Window / door options per panel ---------------------------------------------------
  // Types offered per panel. fixed/slider/casement/solid carry the supplier-email width limits
  // above; 'door' is a fixed-size door frame. Only the frame members come from supplier data;
  // the glass, sashes and door leaf drawn in 3D are visual placeholders (no GF50 sash, slider,
  // casement or door-leaf profiles exist in the supplier files).
  panelTypes: Object.freeze([
    { id: 'fixed', label: 'Fixed' },
    { id: 'slider', label: 'Slider' },
    { id: 'casement', label: 'Casement' },
    { id: 'solid', label: 'Solid' },
    { id: 'door', label: 'Door' },
  ]),
  // PanelCalcs-4Season.dxf "WITH DOOR": X = (L - C - W - D - N*P) / N, D = FIXED DOOR SIZE.
  // D = 72: opening_width_in of M-F-1Door / M-F-2DoorTrap (build_mf1door.py, build_mf2doortrap.py).
  // The formula documents ONE door per wall; more than one is rejected, not extrapolated.
  // NOTE: the older room model (members4.py DOORS) used a door panel the same width as the others.
  doorWidth: 72.0,
  // M-F-1Door (rectangular) is 80" tall with no header; panels of other heights need confirming.
  doorFrameHeight: 80.0,
  // 3V transom rail: top fin tip 10" below the top receiver's fin tip (build_mf3v.py,
  // build_mf3vtrap.py TRANSOM_CLEAR_FIN_IN / TRANSOM_CLEAR_LEFT_IN), measured at the opening's
  // fin on the panel's low side (the supplier builders only show panels rising to the right,
  // where that is the left fin).
  transomClearFin: 10.0,
  // Raked door header (M-F-2DoorTrap): top fin tip 1" below the top receiver's fin tip, same
  // reference point. Rectangular door (M-F-1Door): no header.
  doorHeaderClearFin: 1.0,
  // ASSUMPTION (needs supplier confirmation): supplier email calls solid a "solid full vertical
  // panel", so a solid panel gets no knee rail and no transom.

  // --- Profile body thicknesses (panel_builder.py BODY_THICKNESS) ----------------------
  maleBody: 1.0, // T02
  femaleBody: 1.209, // T03
  railBodyTop: 1.625, // T04: die origin -> top of body (panel_builder T04_TOP_BODY_Y)
  finHeight: 0.625, // T02/T03/T04 fin (panel_builder FIN_HEIGHT)

  // --- Heights --------------------------------------------------------------------------
  // MODEL: low wall top-of-top-channel height and lean-to slope (84" front, 96" at 144").
  lowWallHeight: 84.0,
  roofSlope: L.tan, // rise per inch of run (1" per foot)
  // MODEL: vertical members sit this far above the channel underside / below the channel top.
  seatBottom: L.z0,
  seatTop: 84.0 - L.z1_front,
  // Knee rail: top of T04 body 25.125" above the panel bottom (panel_builder.py, all M-F / M-M
  // specs). Supplier email: 25 11/16" bottom of channel to top of horizontal (= 25.6875).
  kneeRailTopAbovePanelBottom: 25.125,
  // MODEL: header rail top of body (RAIL_TOPS[1] in members4.py), absolute. The room model put
  // it on every panel; the newer panel builders (2V / 3V / door) have no such rail, so it is no
  // longer drawn. Kept for reference until the supplier confirms which is current.
  headerRailTop: 80.625,

  // --- Roof (roof4.py) -------------------------------------------------------------------
  roofPanelWidth: 46.3125, // supplier email: standard roof panel 46 5/16"
  roofPanelThickness: 4.0,
  roofSkin: 0.025,
  roofOverhangSide: 16.0, // MODEL
  roofOverhangFront: 24.0, // MODEL
  roofLip: 0.6711811023618459, // front top channel drip lip outboard of the wall line (members4 LIP)
  roofSeam: { height: 1.0, thickness: 0.1, cutLow: 1.0, cutHigh: 3.0 }, // stand-in seams (roof4.py)
  fasciaExtraLength: 10.0, // roof4.py: fascia runs to house + 10 then is cut at the house
  channelInnerDepth: 4.4082, // roof4.py CH_D_IN (wedge depth)
  roofPanelMaxLength: 24 * 12, // supplier email: max roof panel length 24'
  roofPanelMinWidth: 6, // supplier email
})

export const SECTIONS_4SEASON = sections.sections
