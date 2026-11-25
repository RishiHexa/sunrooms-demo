import { describe, expect, it } from 'vitest'
import { computeLayout, panelCountRange, panelSize } from './layout.js'
import { SPEC_4SEASON as S } from './spec4season.js'
import sections from './data/sections4.json'

const M = sections.modelLayout // supplier room model (216 x 144), fin-tip openings
const FIN = 0.625 // T02/T03 fin (panel_builder FIN_HEIGHT)

function room(w, d, opts = {}) {
  return {
    vertices: [
      { x: 0, y: 0 },
      { x: w, y: 0 },
      { x: w, y: d },
      { x: 0, y: d },
    ],
    walls: [0, 1, 2, 3].map((i) => ({ orientation: i % 2 ? 'v' : 'h', locked: false, house: i === 0, panels: opts.panels?.[i] ?? null })),
  }
}

describe('panel size formula', () => {
  it('matches the supplier example X = (L-C-W-(N-1)P)/N', () => {
    expect(panelSize(144 - 5.514 - 1.5, 2, 1.5)).toBeCloseTo(67.743, 9)
  })
  it('gives the valid panel-count range for the limits', () => {
    // run 200.472 (216 front), fixed 8..72
    expect(panelCountRange(216 - 2 * 5.514, { min: 8, max: 72 }, 1.5)).toEqual({ nMin: 3, nMax: 21 })
  })
})

describe('216 x 144 room vs supplier room model', () => {
  const lay = computeLayout(room(216, 144, { panels: { 1: 2, 2: 4, 3: 2 } }), S)
  const front = lay.walls.find((w) => w.index === 2)
  const left = lay.walls.find((w) => w.index === 3)

  it('builds without errors', () => {
    expect(lay.errors).toEqual([])
    expect(lay.house.depth).toBe(144)
  })

  it('front wall: corner at both ends, 4 openings within 0.005" of the model', () => {
    expect(front.leftEnd.kind).toBe('corner')
    expect(front.rightEnd.kind).toBe('corner')
    expect(front.openings.length).toBe(4)
    M.front_open.forEach(([a, b], k) => {
      expect(Math.abs(front.openings[k][0] - (a - FIN))).toBeLessThan(0.006)
      expect(Math.abs(front.openings[k][1] - (b + FIN))).toBeLessThan(0.006)
    })
  })

  it('side wall: house at the outside-left end, openings within 0.05" of the model', () => {
    // seen from outside the left wall, left->right runs house -> front corner
    expect(left.leftEnd.kind).toBe('house')
    expect(left.rightEnd.kind).toBe('corner')
    // model Y is measured from the front: s = 144 - Y; body faces = fin tips -/+ FIN
    const model = M.side_open.map(([a, b]) => [144 - (b + FIN), 144 - (a - FIN)]).reverse()
    model.forEach(([a, b], k) => {
      expect(Math.abs(left.openings[k][0] - a)).toBeLessThan(0.05)
      expect(Math.abs(left.openings[k][1] - b)).toBeLessThan(0.05)
    })
  })

  it('heights: 84" at the front, 96" at the house, side walls raked', () => {
    expect(front.topLeft).toBeCloseTo(84, 9)
    expect(front.slope).toBeCloseTo(0, 12)
    expect(left.topLeft).toBeCloseTo(96, 9) // house end
    expect(left.topRight).toBeCloseTo(84, 9)
  })

  it('openings close the run exactly', () => {
    for (const w of [front, left]) {
      const A = (e) => (e.kind === 'house' ? S.wallAllowance : S.cornerAllowance)
      const last = w.openings[w.openings.length - 1][1]
      expect(last + A(w.rightEnd)).toBeCloseTo(w.length, 9)
    }
  })
})

describe('automatic and requested panel counts', () => {
  it('auto picks the fewest panels within the max', () => {
    const lay = computeLayout(room(216, 144), S)
    const front = lay.walls.find((w) => w.index === 2)
    expect(front.count).toBe(3)
    expect(front.panelSize).toBeLessThanOrEqual(72)
  })

  it('rejects a requested count outside the limits and does not build openings', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 2 } }), S)
    const front = lay.walls.find((w) => w.index === 2)
    expect(front.error).toMatch(/must be 8"–72"/)
    expect(front.openings).toEqual([])
    expect(lay.ok).toBe(false)
  })

  it('reports a wall too short for any panel', () => {
    const lay = computeLayout(room(216, 12), S) // side run 12 - 5.514 - 1.5 = 4.986 < 8
    expect(lay.walls.find((w) => w.index === 1).error).toBeTruthy()
  })
})

describe('validation', () => {
  it('requires exactly one house wall', () => {
    const p = room(100, 80)
    p.walls[0].house = false
    expect(computeLayout(p, S).errors[0].message).toMatch(/house wall/)
  })

  it('rejects non-90° corners instead of guessing a post', () => {
    const p = {
      vertices: [
        { x: 0, y: 0 },
        { x: 120, y: 0 },
        { x: 120, y: 80 },
        { x: 60, y: 110 },
        { x: 0, y: 80 },
      ],
      walls: [0, 1, 2, 3, 4].map((i) => ({ orientation: null, locked: false, house: i === 0, panels: null })),
    }
    const lay = computeLayout(p, S)
    expect(lay.errors.some((e) => /Corner at/.test(e.message))).toBe(true)
    expect(lay.walls.filter((w) => !w.buildable).length).toBeGreaterThan(0)
  })
})

describe('room heights (plan.heights)', () => {
  const withHeights = (p, front, back) => ({ ...p, heights: { front, back } })

  it('defaults (null / missing) keep the spec front height and slope', () => {
    for (const p of [room(216, 144), withHeights(room(216, 144), null, null)]) {
      const lay = computeLayout(p, S)
      expect(lay.house.frontHeight).toBe(S.lowWallHeight)
      expect(lay.house.slope).toBe(S.roofSlope)
      expect(lay.house.heightAtHouse).toBe(S.lowWallHeight + S.roofSlope * 144)
      expect(lay.house.customHeights).toBe(false)
      expect(lay.warnings).toEqual([])
    }
  })

  it('explicit heights set the front and back channel tops; the slope follows', () => {
    const lay = computeLayout(withHeights(room(216, 144), 90, 110), S)
    expect(lay.errors).toEqual([])
    expect(lay.house.frontHeight).toBe(90)
    expect(lay.house.heightAtHouse).toBeCloseTo(110, 9)
    expect(lay.house.slope).toBeCloseTo(20 / 144, 12)
    const front = lay.walls.find((w) => w.index === 2)
    const side = lay.walls.find((w) => w.index === 1)
    expect(front.topLeft).toBeCloseTo(90, 9)
    expect(front.topRight).toBeCloseTo(90, 9)
    expect(Math.max(side.topLeft, side.topRight)).toBeCloseTo(110, 9)
    expect(Math.min(side.topLeft, side.topRight)).toBeCloseTo(90, 9)
    expect(lay.warnings.length).toBe(1) // slope differs from the supplier model
  })

  it('explicit heights stay fixed when the depth changes (slope changes instead)', () => {
    const a = computeLayout(withHeights(room(216, 144), 84, 96), S)
    const b = computeLayout(withHeights(room(216, 120), 84, 96), S)
    expect(a.house.heightAtHouse).toBeCloseTo(96, 9)
    expect(b.house.heightAtHouse).toBeCloseTo(96, 9)
    expect(b.house.slope).toBeCloseTo(12 / 120, 12)
  })

  it('84 -> 96 on a 144" depth equals the default (no warning)', () => {
    const lay = computeLayout(withHeights(room(216, 144), 84, 84 + S.roofSlope * 144), S)
    expect(lay.house.slope).toBeCloseTo(S.roofSlope, 12)
    expect(lay.warnings).toEqual([])
  })

  it('front only: back follows the default slope from the new front height', () => {
    const lay = computeLayout(withHeights(room(216, 144), 90, null), S)
    expect(lay.errors).toEqual([])
    expect(lay.house.frontHeight).toBe(90)
    expect(lay.house.slope).toBe(S.roofSlope)
    expect(lay.house.heightAtHouse).toBeCloseTo(90 + S.roofSlope * 144, 9)
    expect(lay.house.customHeights).toBe(true)
    expect(lay.warnings).toEqual([])
  })

  it('rejects a back height that is not above the front height', () => {
    for (const back of [84, 80]) {
      const lay = computeLayout(withHeights(room(216, 144), 84, back), S)
      expect(lay.ok).toBe(false)
      expect(lay.errors[0].message).toMatch(/Back height/)
    }
  })

  it('panel sizes do not depend on heights', () => {
    const a = computeLayout(room(216, 144), S)
    const b = computeLayout(withHeights(room(216, 144), 95, 125), S)
    expect(b.walls.map((w) => w.openings)).toEqual(a.walls.map((w) => w.openings))
  })
})
