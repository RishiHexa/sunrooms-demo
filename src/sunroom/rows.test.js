/**
 * Panel rows (lites between rails), row edits and drill-down selection.
 * Rows are derived from the layout rails only; edits must map onto the stored panel option
 * { type, transom } and only to documented supplier panels (2V, 3V, door, solid).
 */
import { describe, expect, it } from 'vitest'
import { computeLayout, panelOption } from './layout.js'
import { SPEC_4SEASON as S } from './spec4season.js'
import { mergeRows, panelAt, panelRows, rowAt, setRowType, splitRow } from './rows.js'
import { NO_SELECTION, click, doubleClick, level, reconcile, up } from './drill.js'
import { setPanelOption } from '../floorplan/geometry.js'

function room(w, d, opts = {}) {
  return {
    vertices: [
      { x: 0, y: 0 },
      { x: w, y: 0 },
      { x: w, y: d },
      { x: 0, y: d },
    ],
    walls: [0, 1, 2, 3].map((i) => ({
      orientation: i % 2 ? 'v' : 'h',
      locked: false,
      house: i === 0,
      panels: opts.panels?.[i] ?? null,
      windows: opts.windows?.[i] ?? null,
      sizes: opts.sizes?.[i] ?? null,
    })),
    heights: opts.heights ?? { front: null, back: null },
  }
}
const wallOf = (lay, i) => lay.walls.find((w) => w.index === i)
const roles = (w, k) => panelRows(w, w.panels[k], S).rows.map((r) => r.role)
const fin = S.finHeight
const Z0 = S.seatBottom

describe('panelRows', () => {
  const plan = room(216, 144, {
    panels: { 1: 2, 2: 4, 3: 2 },
    windows: { 2: [null, { type: 'fixed', transom: true }, { type: 'door' }, { type: 'solid' }], 1: [null, { type: 'door' }] },
  })
  const lay = computeLayout(plan, S)
  const front = wallOf(lay, 2)
  const side = wallOf(lay, 1) // raked

  it('layout is valid for the fixture', () => {
    expect(lay.errors).toEqual([])
  })
  it('2V: knee + main; 3V: knee + main + transom; door; solid', () => {
    expect(roles(front, 0)).toEqual(['knee', 'main'])
    expect(roles(front, 1)).toEqual(['knee', 'main', 'transom'])
    expect(roles(front, 2)).toEqual(['door'])
    expect(roles(front, 3)).toEqual(['solid'])
  })
  it('raked door panel gets a row above the door header', () => {
    expect(roles(side, 1)).toEqual(['door', 'header'])
  })
  it('row edges are the fin tips of the layout members (same edges build3d draws glass to)', () => {
    const p = front.panels[1]
    const { rows, rails } = panelRows(front, p, S)
    const knee = p.rails.find((r) => r.name === 'knee')
    expect(rows[0].z0).toBeCloseTo(Z0 + S.maleBody + fin, 12) // bottom receiver fin tip
    expect(rows[0].top0).toBeCloseTo(knee.bodyTop - S.railBodyTop, 12)
    expect(rows[1].z0).toBeCloseTo(knee.bodyTop + fin, 12)
    expect(rails.map((r) => r.name)).toEqual(['knee', 'transom'])
    // door lite starts at the floor (no bottom receiver)
    expect(panelRows(front, front.panels[2], S).rows[0].z0).toBe(0)
  })
  it('rails that do not fit are not drawn as row boundaries', () => {
    const p = { ...front.panels[1], rails: front.panels[1].rails.map((r) => (r.name === 'transom' ? { ...r, fits: false } : r)) }
    expect(panelRows(front, p, S).rows.map((r) => r.role)).toEqual(['knee', 'main'])
  })
  it('hit-testing: panelAt splits joints halfway, rowAt splits rails halfway', () => {
    const [p0, p1] = front.panels
    expect(panelAt(front, (p0.s0 + p0.s1) / 2, S.panelJoint)).toBe(0)
    expect(panelAt(front, p0.s1 + S.panelJoint * 0.4, S.panelJoint)).toBe(0)
    expect(panelAt(front, p1.s0 - S.panelJoint * 0.4, S.panelJoint)).toBe(1)
    expect(panelAt(front, 0.5, S.panelJoint)).toBe(-1) // corner allowance
    const { rows } = panelRows(front, p1, S)
    expect(rowAt(rows, 5)).toBe('knee')
    expect(rowAt(rows, 50)).toBe('main')
    expect(rowAt(rows, 200)).toBe('transom')
  })
})

describe('row edits map onto documented panels only', () => {
  const lay = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [null, { type: 'slider', transom: true }, { type: 'door' }] } }), S)
  const front = wallOf(lay, 2)
  const rowsOf = (k) => panelRows(front, front.panels[k], S).rows

  it('merge main + transom = 3V -> 2V, type kept', () => {
    const r = mergeRows({ type: 'slider', transom: true }, rowsOf(1), ['transom', 'main'])
    expect(r).toEqual({ ok: true, option: { type: 'slider', transom: false } })
  })
  it('merging the knee row is refused (no documented panel without a knee rail)', () => {
    expect(mergeRows({ type: 'fixed', transom: false }, rowsOf(0), ['knee', 'main']).ok).toBe(false)
    expect(mergeRows({ type: 'slider', transom: true }, rowsOf(1), ['knee', 'main', 'transom']).ok).toBe(false)
  })
  it('non-neighbouring or single rows are refused', () => {
    expect(mergeRows({ type: 'slider', transom: true }, rowsOf(1), ['knee', 'transom']).error).toMatch(/neighbouring/)
    expect(mergeRows({ type: 'slider', transom: true }, rowsOf(1), ['main']).ok).toBe(false)
  })
  it('split main = 2V -> 3V for window types only', () => {
    expect(splitRow({ type: 'fixed', transom: false }, 'main')).toEqual({ ok: true, option: { type: 'fixed', transom: true } })
    expect(splitRow({ type: 'fixed', transom: true }, 'main').ok).toBe(false)
    expect(splitRow({ type: 'door', transom: false }, 'door').ok).toBe(false)
    expect(splitRow({ type: 'solid', transom: false }, 'solid').ok).toBe(false)
    expect(splitRow({ type: 'fixed', transom: false }, 'knee').ok).toBe(false)
  })
  it('row type: only the main row has a type; transom dropped for door / solid', () => {
    expect(setRowType({ type: 'fixed', transom: true }, 'main', 'casement')).toEqual({ ok: true, option: { type: 'casement', transom: true } })
    expect(setRowType({ type: 'fixed', transom: true }, 'main', 'door')).toEqual({ ok: true, option: { type: 'door', transom: false } })
    expect(setRowType({ type: 'fixed', transom: false }, 'knee', 'slider').ok).toBe(false)
    expect(setRowType({ type: 'fixed', transom: true }, 'transom', 'slider').ok).toBe(false)
  })
  it('a merge round-trips through setPanelOption and the layout (stored shape unchanged)', () => {
    const plan = room(216, 144, { panels: { 2: 4 }, windows: { 2: [null, { type: 'slider', transom: true }] } })
    const opt = panelOption(plan.walls[2], 1, S)
    const m = mergeRows(opt, rowsOf(1), ['main', 'transom'])
    const res = setPanelOption(plan, 2, 1, m.option, 4)
    expect(res.ok).toBe(true)
    expect(res.plan.walls[2].windows[1]).toEqual({ type: 'slider', transom: false })
    const lay2 = computeLayout(res.plan, S)
    expect(roles(wallOf(lay2, 2), 1)).toEqual(['knee', 'main'])
    // other walls / panels untouched
    expect(res.plan.walls[1]).toEqual(plan.walls[1])
    expect(res.plan.walls[2].windows[0]).toBe(null)
  })
})

describe('drill-down selection', () => {
  const hit = (panel, role = null, wall = 2) => ({ wall, panel, role })
  it('click selects the wall; double-clicks drill wall -> panel -> row', () => {
    let s = click(NO_SELECTION, hit(1, 'main'))
    expect(s).toEqual({ wall: 2, panel: -1, rows: [] })
    // a double-click is click, click, dblclick
    s = click(s, hit(1, 'main'))
    s = click(s, hit(1, 'main'))
    s = doubleClick(s, hit(1, 'main'))
    expect(s).toEqual({ wall: 2, panel: 1, rows: [] })
    expect(level(s)).toBe('panel')
    s = click(s, hit(1, 'main'))
    s = click(s, hit(1, 'main'))
    s = doubleClick(s, hit(1, 'main'))
    expect(s).toEqual({ wall: 2, panel: 1, rows: ['main'] })
    expect(level(s)).toBe('row')
  })
  it('row level: click picks another row, Ctrl+click toggles (multi-select)', () => {
    let s = { wall: 2, panel: 1, rows: ['main'] }
    s = click(s, hit(1, 'transom'), true)
    expect(s.rows).toEqual(['main', 'transom'])
    s = click(s, hit(1, 'main'), true)
    expect(s.rows).toEqual(['transom'])
    s = click(s, hit(1, 'knee'))
    expect(s.rows).toEqual(['knee'])
  })
  it('click on another panel returns to the wall level; another wall or empty space changes / clears', () => {
    expect(click({ wall: 2, panel: 1, rows: ['main'] }, hit(0, 'main'))).toEqual({ wall: 2, panel: -1, rows: [] })
    expect(click({ wall: 2, panel: 1, rows: [] }, hit(0, 'main', 3))).toEqual({ wall: 3, panel: -1, rows: [] })
    expect(click({ wall: 2, panel: 1, rows: [] }, null)).toBe(NO_SELECTION)
  })
  it('double-click on a different panel selects that panel', () => {
    expect(doubleClick({ wall: 2, panel: 1, rows: ['main'] }, hit(3, 'main'))).toEqual({ wall: 2, panel: 3, rows: [] })
  })
  it('up: row -> panel -> wall -> none', () => {
    let s = { wall: 2, panel: 1, rows: ['main'] }
    s = up(s)
    expect(level(s)).toBe('panel')
    s = up(s)
    expect(level(s)).toBe('wall')
    expect(up(s)).toBe(NO_SELECTION)
  })
  it('reconcile drops rows / panels the layout no longer has', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 4 } }), S)
    expect(reconcile({ wall: 2, panel: 1, rows: ['main', 'transom'] }, lay)).toEqual({ wall: 2, panel: 1, rows: ['main'] })
    expect(reconcile({ wall: 2, panel: 9, rows: [] }, lay)).toEqual({ wall: 2, panel: -1, rows: [] })
    expect(reconcile({ wall: 0, panel: 0, rows: [] }, lay)).toEqual({ wall: 0, panel: -1, rows: [] }) // house wall
    const same = { wall: 2, panel: 1, rows: ['knee'] }
    expect(reconcile(same, lay)).toBe(same)
  })
})
