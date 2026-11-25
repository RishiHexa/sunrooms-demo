/**
 * Rows of a panel — the lites between a panel's horizontal members — and the row edits the
 * wall elevation offers (merge, split, change the main row's type). Pure logic, INCHES.
 *
 * Rows are NOT a new stored value. They are read from the layout's rails (layout.js
 * panelMembers: knee rail, 3V transom rail, raked door header), which come from the supplier
 * builders. Every row edit maps back onto the panel option that is already stored
 * (plan.walls[i].windows[k] = { type, transom }), and only to configurations the supplier
 * files document:
 *   2V  knee + main               (M-F-2V / M-F-2Vtrap)        { type, transom: false }
 *   3V  knee + main + transom     (M-F-3V / M-F-3Vtrap)        { type, transom: true }
 *   door (+ header row when raked) (M-F-1Door / M-F-2DoorTrap) { type: 'door' }
 *   solid, no rails               (supplier email "solid full vertical panel", see spec)
 * So "merge main + transom" = 3V -> 2V and "split main" = 2V -> 3V. Anything else (removing the
 * knee rail, removing a door header) has no documented panel and is refused with the reason.
 *
 * Row z extents are the fin tips of the members around each lite, the same edges build3d.js
 * draws the glass to. They are for drawing and hit-testing only, not glass or cut sizes.
 */
import { panelTopAt, supportsTransom } from './layout.js'

export const ROW_LABELS = Object.freeze({
  knee: 'Knee',
  main: 'Main',
  transom: 'Transom',
  door: 'Door',
  header: 'Above door header',
  solid: 'Solid',
})

/** Roles whose fill is the panel type (the main lite). Knee / transom / header fills are not documented. */
export const MAIN_ROLES = Object.freeze(['main', 'door', 'solid'])

/** Role the main lite takes for a panel type. */
export const mainRoleOf = (type) => (type === 'door' ? 'door' : type === 'solid' ? 'solid' : 'main')

/**
 * Rows of one laid-out panel, bottom -> top.
 * @returns {{ rows: { index, role, label, z0, top0, top1, railBelow, railAbove }[], rails: { name, z0, z1 }[] }}
 *   top0 / top1: top edge at the panel's left (s0) / right (s1) side (only the top row can be raked).
 */
export function panelRows(wall, panel, spec) {
  const fin = spec.finHeight
  const stretch = Math.sqrt(1 + wall.slope * wall.slope)
  const topFin = (s) => panelTopAt(wall, s, spec) - (spec.maleBody + fin) * stretch
  // rails that do not fit are reported by the layout and not drawn (same as build3d.js)
  const fitting = panel.rails.filter((r) => r.fits)
  const rails = fitting.map((r) => ({ name: r.name, z0: r.bodyTop - spec.railBodyTop, z1: r.bodyTop + fin }))
  const rows = []
  let z0 = panel.bottomReceiver ? spec.seatBottom + spec.maleBody + fin : 0 // a door lite starts at the floor
  let below = null
  for (const r of rails) {
    rows.push({ z0, top0: r.z0, top1: r.z0, railBelow: below, railAbove: r.name })
    z0 = r.z1
    below = r.name
  }
  rows.push({ z0, top0: topFin(panel.s0), top1: topFin(panel.s1), railBelow: below, railAbove: null })
  rows.forEach((row, j) => {
    let role
    if (panel.type === 'solid') role = 'solid'
    else if (row.railAbove === 'knee') role = 'knee'
    else if (row.railBelow === 'transom') role = 'transom'
    else if (row.railBelow === 'door-header') role = 'header'
    else role = panel.door ? 'door' : 'main'
    row.index = j
    row.role = role
    row.label = ROW_LABELS[role]
  })
  return { rows, rails }
}

/** Panel index at wall-local s (joints split halfway between the openings), or -1. */
export function panelAt(wall, s, joint) {
  return wall.panels.findIndex((p) => s >= p.s0 - joint / 2 && s <= p.s1 + joint / 2)
}

/** Role of the row at height z (rails split halfway between the rows). */
export function rowAt(rows, z) {
  for (let j = 0; j < rows.length - 1; j++) {
    const split = (Math.min(rows[j].top0, rows[j].top1) + rows[j + 1].z0) / 2
    if (z < split) return rows[j].role
  }
  return rows[rows.length - 1]?.role ?? null
}

const KNEE_MSG =
  'The knee rail cannot be removed: every documented 4-Season window panel has one (2V: knee; 3V: knee + transom). ' +
  'A panel with no rails is Solid; a full-height glass panel is not in the supplier files.'

/**
 * Merge the selected rows of one panel.
 * @param option  the panel's stored option { type, transom } (layout.panelOption)
 * @param rows    panelRows(...).rows of that panel
 * @param roles   selected row roles
 * @returns {{ ok: true, option } | { ok: false, error }}
 */
export function mergeRows(option, rows, roles) {
  const idx = [...new Set(roles)].map((r) => rows.findIndex((x) => x.role === r)).sort((a, b) => a - b)
  if (idx.length < 2 || idx.some((i) => i < 0)) return { ok: false, error: 'Select two or more rows of the same panel to merge (Ctrl + click).' }
  if (idx.some((v, i) => v !== idx[0] + i)) return { ok: false, error: 'Only neighbouring rows can be merged.' }
  const set = new Set(idx.map((i) => rows[i].role))
  if (set.has('knee')) return { ok: false, error: KNEE_MSG }
  if (set.has('header')) return { ok: false, error: 'The door header comes from the door rule (raked door, M-F-2DoorTrap) and cannot be removed.' }
  if (set.size === 2 && set.has('main') && set.has('transom')) {
    return { ok: true, option: { type: option.type, transom: false } } // 3V -> 2V
  }
  return { ok: false, error: 'These rows cannot be merged: no supplier panel has that layout.' }
}

/** Split a row by adding a rail. Only the main lite of a window panel splits: 2V -> 3V (transom). */
export function splitRow(option, role) {
  if (role === 'main' && supportsTransom(option.type)) {
    if (option.transom) return { ok: false, error: 'This panel already has a transom (3V).' }
    return { ok: true, option: { type: option.type, transom: true } }
  }
  const why = {
    knee: 'The knee row has no documented split.',
    transom: 'The transom row has no documented split.',
    header: 'The row above a door header has no documented split.',
    door: 'A door gets its header from the door rule, not from a transom.',
    solid: 'Solid panels have no rails (supplier: solid full vertical panel).',
  }
  return { ok: false, error: why[role] ?? 'This row cannot be split.' }
}

/** Change what fills a row. Only the main lite has documented types (the panel type). */
export function setRowType(option, role, type) {
  if (!MAIN_ROLES.includes(role)) {
    return { ok: false, error: `The ${ROW_LABELS[role]?.toLowerCase() ?? role} row's fill is not defined in the 4-Season supplier files; only the main row has a type.` }
  }
  return { ok: true, option: { type, transom: supportsTransom(type) ? !!option.transom : false } }
}
