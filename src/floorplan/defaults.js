/**
 * Starting floor plan for a new configuration.
 *
 * 81" x 55" rectangle, taken from the reference workspace (sunroom.hexacoder.co).
 * PLACEHOLDER — replace with the documented product default before production use.
 */
export const DEFAULT_WIDTH_IN = 81
export const DEFAULT_DEPTH_IN = 55

export function createDefaultPlan() {
  const w = DEFAULT_WIDTH_IN
  const d = DEFAULT_DEPTH_IN
  return {
    vertices: [
      { x: 0, y: 0 }, // back-left
      { x: w, y: 0 }, // back-right
      { x: w, y: d }, // front-right
      { x: 0, y: d }, // front-left
    ],
    // Back wall (top of the 2D view) is the house wall by default.
    walls: [
      { orientation: 'h', locked: false, house: true, panels: null, windows: null }, // back (house)
      { orientation: 'v', locked: false, house: false, panels: null, windows: null }, // right
      { orientation: 'h', locked: false, house: false, panels: null, windows: null }, // front
      { orientation: 'v', locked: false, house: false, panels: null, windows: null }, // left
    ],
    // null = system default heights (SPEC lowWallHeight / roofSlope)
    heights: { front: null, back: null },
  }
}
