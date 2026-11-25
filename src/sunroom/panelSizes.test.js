/**
 * Per-panel size overrides (plan.walls[i].sizes[k] = { width, kneeTop, transomClear }).
 * User-requested extension of the supplier rules, flagged on the wall:
 *   - locked widths: unlocked panels share the rest  X = (run - D*doors - sum(locked) - (N-1)P) / free
 *   - knee / transom heights per panel, limited only by the existing rail fit check
 * Without overrides the layout must be exactly the supplier formula (checked bit-for-bit).
 */
import { describe, expect, it } from 'vitest'
import { computeLayout } from './layout.js'
import { SPEC_4SEASON as S } from './spec4season.js'
import { panelRows } from './rows.js'
import { choosePanelSize } from './panelOptions.js'
import { clearPanelSizes, clonePlan, setHouseWall, setPanelSize } from '../floorplan/geometry.js'

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
    heights: { front: null, back: null },
  }
}
const wallOf = (lay, i) => lay.walls.find((w) => w.index === i)
const C = S.cornerAllowance
const P = S.panelJoint
const Z0 = S.seatBottom
const FRONT_RUN = 216 - 2 * C

describe('no overrides = supplier formula, bit for bit', () => {
  it('plans with sizes null / missing / all-null entries lay out identically', () => {
    const a = room(216, 144, { panels: { 2: 4 } })
    const b = clonePlan(a)
    delete b.walls[2].sizes
    const c = room(216, 144, { panels: { 2: 4 }, sizes: { 2: [null, null] } })
    const la = computeLayout(a, S)
    for (const other of [computeLayout(b, S), computeLayout(c, S)]) {
      for (const w of la.walls) {
        const o = wallOf(other, w.index)
        expect(o.openings).toEqual(w.openings) // exact equality, not toBeCloseTo
        expect(o.panels.map((p) => p.rails)).toEqual(w.panels.map((p) => p.rails))
      }
    }
    expect(la.warnings).toEqual([])
  })
})

describe('locked widths', () => {
  const plan = room(216, 144, { panels: { 2: 4 }, sizes: { 2: [{ width: 40 }] } })
  const lay = computeLayout(plan, S)
  const f = wallOf(lay, 2)
  it('locked panel keeps its width, the others share the rest equally', () => {
    expect(lay.errors).toEqual([])
    const X = (FRONT_RUN - 40 - 3 * P) / 3
    expect(f.panels.map((p) => p.width)).toEqual([40, X, X, X].map((v) => expect.closeTo(v, 9)))
    expect(f.panelSize).toBeCloseTo(X, 12)
    expect(f.panels.map((p) => p.locked)).toEqual([true, false, false, false])
  })
  it('the run still closes: last opening + corner allowance = wall length', () => {
    expect(f.openings[0][0]).toBeCloseTo(C, 12)
    expect(f.openings[3][1] + C).toBeCloseTo(216, 9)
    for (let k = 1; k < 4; k++) expect(f.openings[k][0] - f.openings[k - 1][1]).toBeCloseTo(P, 12)
  })
  it('flagged as not a supplier standard', () => {
    expect(lay.warnings.some((w) => /locked width; the supplier panel formula \(PanelCalcs\) gives equal panels/.test(w.message))).toBe(true)
  })
  it('wall length changes are absorbed by the unlocked panels', () => {
    const p2 = clonePlan(plan)
    p2.vertices[1].x = 228
    p2.vertices[2].x = 228
    const f2 = wallOf(computeLayout(p2, S), 2)
    expect(f2.panels[0].width).toBeCloseTo(40, 9)
    expect(f2.panels[1].width).toBeCloseTo((228 - 2 * C - 40 - 3 * P) / 3, 9)
  })
  it('a locked width outside its type limit is an error', () => {
    const l = computeLayout(room(216, 144, { panels: { 2: 4 }, sizes: { 2: [{ width: 80 }] } }), S)
    expect(wallOf(l, 2).error).toMatch(/Panel 1 is locked at 80"; a fixed section must be 8"–72"/)
  })
  it('unlocked panels pushed outside their limit is an error naming the shared width', () => {
    const l = computeLayout(room(216, 144, { panels: { 2: 4 }, sizes: { 2: [{ width: 72 }, { width: 72 }, { width: 55 }] } }), S)
    expect(wallOf(l, 2).error).toMatch(/unlocked panel gets 1\.472"/)
  })
  it('all panels locked: must close exactly', () => {
    const x = (FRONT_RUN - 3 * P) / 4
    const ok = computeLayout(room(216, 144, { panels: { 2: 4 }, sizes: { 2: [{ width: x }, { width: x }, { width: x }, { width: x }] } }), S)
    expect(wallOf(ok, 2).error).toBe(null)
    const bad = computeLayout(room(216, 144, { panels: { 2: 4 }, sizes: { 2: [{ width: 50 }, { width: 50 }, { width: 50 }, { width: 50 }] } }), S)
    expect(wallOf(bad, 2).error).toMatch(/Every panel is locked and the widths leave 0\.472" unfilled/)
  })
  it('a door keeps its fixed 72" width; a stored width on it is reported unused', () => {
    const l = computeLayout(room(216, 144, { panels: { 2: 3 }, windows: { 2: [null, { type: 'door' }] }, sizes: { 2: [{ width: 60 }, { width: 30 }] } }), S)
    const w = wallOf(l, 2)
    expect(w.error).toBe(null)
    expect(w.panels[1].width).toBeCloseTo(72, 9)
    expect(w.panels[0].width).toBeCloseTo(60, 9)
    expect(w.panels[2].width).toBeCloseTo(FRONT_RUN - 72 - 60 - 2 * P, 9) // 69.972, inside 8–72
    expect(l.warnings.some((x) => /stored width is not used; a door is the fixed 72"/.test(x.message))).toBe(true)
  })
  it('valid panel counts take the locks into account', () => {
    // 40" locked: N=2 leaves 163.472 for one panel (> 72), so 2 is not valid; N=3 gives 81.986 (> 72) no; N=4 fits
    const l = computeLayout(room(216, 144, { sizes: { 2: [{ width: 40 }] } }), S)
    expect(wallOf(l, 2).countRange.counts[0]).toBe(4)
  })
})

describe('row heights per panel', () => {
  it('knee override moves the knee rail; flagged; rows follow', () => {
    const l = computeLayout(room(216, 144, { panels: { 2: 4 }, sizes: { 2: [null, { kneeTop: 30 }] } }), S)
    const w = wallOf(l, 2)
    expect(l.errors).toEqual([])
    expect(w.panels[1].rails[0]).toMatchObject({ name: 'knee', bodyTop: Z0 + 30, custom: true, fits: true })
    expect(w.panels[0].rails[0].bodyTop).toBeCloseTo(Z0 + 25.125, 12) // neighbour untouched
    expect(w.panels[1].kneeTop).toBe(30)
    const knee = panelRows(w, w.panels[1], S).rows[0]
    expect(knee.top0).toBeCloseTo(Z0 + 30 - S.railBodyTop, 12)
    expect(l.warnings.some((x) => /panel 2: knee rail at 30" .*supplier standard 25\.125"/.test(x.message))).toBe(true)
  })
  it('transom override: clearance below the top; flagged', () => {
    const base = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] } }), S)
    const l = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] }, sizes: { 2: [{ transomClear: 14 }] } }), S)
    const t0 = wallOf(base, 2).panels[0].rails.find((r) => r.name === 'transom')
    const t1 = wallOf(l, 2).panels[0].rails.find((r) => r.name === 'transom')
    expect(t0.bodyTop - t1.bodyTop).toBeCloseTo(4, 12) // 14" instead of 10" below the top
    expect(t1.custom).toBe(true)
    expect(wallOf(l, 2).panels[0].transomClear).toBe(14)
    expect(l.warnings.some((x) => /transom 14" below the top \(supplier standard 10" fin to fin\)/.test(x.message))).toBe(true)
  })
  it('only the fit check limits heights: a knee above the transom is an error', () => {
    const l = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] }, sizes: { 2: [{ kneeTop: 78 }] } }), S)
    expect(l.errors.some((e) => /Panel 1: the transom rail does not fit/.test(e.message))).toBe(true)
  })
  it('heights stored on a panel without that rail are reported unused, not applied', () => {
    // 5 panels: 39.794" each, inside both fixed 8–72 and solid 6–48
    const l = computeLayout(room(216, 144, { panels: { 2: 5 }, windows: { 2: [{ type: 'solid' }] }, sizes: { 2: [{ kneeTop: 30, transomClear: 12 }] } }), S)
    const p = wallOf(l, 2).panels[0]
    expect(p.rails).toEqual([])
    expect(l.warnings.some((x) => /stored knee rail height is not used \(a solid panel has no knee rail\)/.test(x.message))).toBe(true)
    expect(l.warnings.some((x) => /stored transom clearance is not used/.test(x.message))).toBe(true)
  })
})

describe('choosePanelSize refuses changes that break the wall', () => {
  const base = room(216, 144, { panels: { 2: 4 } })
  it('valid lock is stored', () => {
    const r = choosePanelSize(base, 2, 0, { width: 40 }, S)
    expect(r.ok).toBe(true)
    expect(r.plan.walls[2].sizes[0].width).toBe(40)
  })
  it('lock outside the type limit is refused, nothing stored', () => {
    const r = choosePanelSize(base, 2, 0, { width: 80 }, S)
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/locked at 80"/)
  })
  it('a knee rail that no longer fits is refused', () => {
    const p = room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] } })
    const r = choosePanelSize(p, 2, 0, { kneeTop: 78 }, S)
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/does not fit/)
  })
  it('an error the wall already had does not block an unrelated valid change', () => {
    const broken = room(216, 144, { panels: { 2: 4 }, sizes: { 2: [null, null, null, { width: 80 }] } })
    const r = choosePanelSize(broken, 2, 3, { width: null }, S) // unlock fixes it
    expect(r.ok).toBe(true)
  })
})

describe('setPanelSize / clearPanelSizes', () => {
  const base = room(216, 144)
  it('stores the override, pins an automatic count, keeps other fields', () => {
    const r1 = setPanelSize(base, 2, 1, { width: 40 }, 3)
    expect(r1.ok).toBe(true)
    expect(r1.plan.walls[2].panels).toBe(3)
    expect(r1.plan.walls[2].sizes).toEqual([null, { width: 40, kneeTop: null, transomClear: null }])
    const r2 = setPanelSize(r1.plan, 2, 1, { kneeTop: 30 }, 3)
    expect(r2.plan.walls[2].sizes[1]).toEqual({ width: 40, kneeTop: 30, transomClear: null })
    const r3 = setPanelSize(r2.plan, 2, 1, { width: null, kneeTop: null }, 3)
    expect(r3.plan.walls[2].sizes).toBe(null) // all-null entries are dropped
    expect(base.walls[2].sizes).toBe(null) // input not mutated
  })
  it('rejects non-positive values, unknown fields, the house wall and missing panels', () => {
    expect(setPanelSize(base, 2, 0, { width: 0 }, 3).ok).toBe(false)
    expect(setPanelSize(base, 2, 0, { width: NaN }, 3).ok).toBe(false)
    expect(setPanelSize(base, 2, 0, { depth: 3 }, 3).ok).toBe(false)
    expect(setPanelSize(base, 0, 0, { width: 30 }, 3).ok).toBe(false)
    expect(setPanelSize(base, 2, 5, { width: 30 }, 3).ok).toBe(false)
  })
  it('clonePlan keeps sizes; clearPanelSizes and setHouseWall clear them', () => {
    const p = setPanelSize(base, 2, 0, { width: 40 }, 3).plan
    expect(clonePlan(p).walls[2].sizes).toEqual(p.walls[2].sizes)
    expect(clearPanelSizes(p, 2).plan.walls[2].sizes).toBe(null)
    expect(clearPanelSizes(p, 2).plan.walls[2].panels).toBe(3)
    expect(setHouseWall(p, 2).plan.walls[2].sizes).toBe(null)
  })
})
