/**
 * Drill-down selection of the wall elevation and the 3D view: wall -> panel -> row(s).
 * Pure state transitions; UI only (nothing here is stored on the plan).
 *
 *   click        selects a wall. On the selected wall it keeps the current level (so the two
 *                clicks of a double-click do not reset it), returns to the wall level when it
 *                lands on another panel, and at the row level selects the clicked row.
 *                Additive (Ctrl / Cmd) click toggles a row of the selected panel (multi-select).
 *   double-click drills one level: wall -> panel under the pointer -> row under the pointer.
 *   up           (Esc) row -> panel -> wall -> nothing.
 *
 * A hit is { wall, panel, role }: wall index (-1 = empty space), panel index (-1 = not on a
 * panel, e.g. a corner post or the house wall), row role or null (on a rail / frame).
 */
import { panelRows } from './rows.js'

export const NO_SELECTION = Object.freeze({ wall: -1, panel: -1, rows: Object.freeze([]) })

const at = (wall, panel = -1, rows = []) => ({ wall, panel, rows })

export function level(sel) {
  if (sel.wall < 0) return 'none'
  if (sel.panel < 0) return 'wall'
  return sel.rows.length ? 'row' : 'panel'
}

export function click(sel, hit, additive = false) {
  if (!hit || hit.wall < 0) return NO_SELECTION
  if (hit.wall !== sel.wall) return at(hit.wall)
  if (sel.panel < 0) {
    // wall level: Ctrl + click on a row jumps straight to it
    return additive && hit.panel >= 0 && hit.role ? at(sel.wall, hit.panel, [hit.role]) : sel
  }
  if (hit.panel !== sel.panel) return at(sel.wall)
  if (!hit.role) return sel
  if (additive) {
    const rows = sel.rows.includes(hit.role) ? sel.rows.filter((r) => r !== hit.role) : [...sel.rows, hit.role]
    return at(sel.wall, sel.panel, rows)
  }
  return sel.rows.length ? at(sel.wall, sel.panel, [hit.role]) : sel
}

export function doubleClick(sel, hit) {
  if (!hit || hit.wall < 0) return sel
  if (hit.panel == null || hit.panel < 0) return hit.wall === sel.wall ? sel : at(hit.wall)
  if (hit.wall !== sel.wall || hit.panel !== sel.panel) return at(hit.wall, hit.panel)
  return hit.role ? at(sel.wall, sel.panel, [hit.role]) : sel
}

export function up(sel) {
  if (sel.rows.length) return at(sel.wall, sel.panel)
  if (sel.panel >= 0) return at(sel.wall)
  return NO_SELECTION
}

/**
 * Drop the parts of a selection the current layout no longer has (panel removed, rows merged,
 * house wall, wall not laid out). Returns the same object when nothing changed.
 */
export function reconcile(sel, layout) {
  if (sel.panel < 0) return sel
  const w = layout.walls.find((x) => x.index === sel.wall)
  const p = w?.panels[sel.panel]
  if (!p) return at(sel.wall)
  if (!sel.rows.length) return sel
  const roles = new Set(panelRows(w, p, layout.spec).rows.map((r) => r.role))
  const rows = sel.rows.filter((r) => roles.has(r))
  return rows.length === sel.rows.length ? sel : at(sel.wall, sel.panel, rows)
}
