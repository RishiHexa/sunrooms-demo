/**
 * Window / door options per panel. Expected values come from the supplier sources:
 *   PanelCalcs-4Season.dxf "WITH DOOR"     X = (L - C - W - D - N*P) / N
 *   build_mf1door.py / build_mf2doortrap.py  72" door, no bottom T02, no knee rail, raked header 1" clear
 *   build_mf3v.py / build_mf3vtrap.py       transom 10" fin-to-fin below the top (68.1780" printed for 3Vtrap)
 *   supplier email limits                    fixed 8-72, slider 30-72, casement 24-36, solid 6-48
 */
import { describe, expect, it } from 'vitest'
import { computeLayout, panelSizeWithDoors } from './layout.js'
import { SPEC_4SEASON as S } from './spec4season.js'
import { clonePlan, setHouseWall, setPanelOption } from '../floorplan/geometry.js'

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
    })),
    heights: opts.heights ?? { front: null, back: null },
  }
}
const wallOf = (lay, i) => lay.walls.find((w) => w.index === i)
const Z0 = S.seatBottom
const FRONT_RUN = 216 - 2 * S.cornerAllowance // 204.972

describe('defaults (no options stored)', () => {
  const lay = computeLayout(room(216, 144, { panels: { 1: 2, 2: 4, 3: 2 } }), S)
  it('every panel is a fixed 2V panel: bottom receiver + knee rail only', () => {
    for (const w of lay.walls) {
      for (const p of w.panels) {
        expect(p.type).toBe('fixed')
        expect(p.transom).toBe(false)
        expect(p.bottomReceiver).toBe(true)
        expect(p.rails.map((r) => r.name)).toEqual(['knee'])
        expect(p.rails[0].bodyTop).toBeCloseTo(Z0 + 25.125, 12)
        expect(p.rails[0].fits).toBe(true)
      }
      expect(w.bottomChannelGaps).toEqual([])
    }
    expect(lay.warnings).toEqual([])
    expect(lay.errors).toEqual([])
  })
  it('last panel of a run is M-M, the others M-F', () => {
    const f = wallOf(lay, 2)
    expect(f.panels.map((p) => p.right)).toEqual(['T03', 'T03', 'T03', 'T02'])
  })
})

describe('door (PanelCalcs "WITH DOOR")', () => {
  const lay = computeLayout(room(216, 144, { panels: { 2: 3 }, windows: { 2: [null, { type: 'door' }] } }), S)
  const f = wallOf(lay, 2)

  it('door is the fixed 72" opening, the others share X = (run - D - N*P) / N', () => {
    const X = (FRONT_RUN - 72 - 2 * 1.5) / 2
    expect(panelSizeWithDoors(FRONT_RUN, 3, 1, 72, 1.5)).toBeCloseTo(X, 12)
    expect(f.panelSize).toBeCloseTo(X, 12)
    expect(f.panels.map((p) => p.width)).toEqual([expect.closeTo(X, 9), expect.closeTo(72, 9), expect.closeTo(X, 9)])
    expect(f.doors).toBe(1)
  })
  it('the run still closes exactly', () => {
    expect(f.openings[2][1] + S.cornerAllowance).toBeCloseTo(216, 9)
    expect(f.openings[1][0] - f.openings[0][1]).toBeCloseTo(S.panelJoint, 12)
    expect(f.openings[2][0] - f.openings[1][1]).toBeCloseTo(S.panelJoint, 12)
  })
  it('no bottom receiver, no knee rail, bottom channel removed across the opening', () => {
    const d = f.panels[1]
    expect(d.door).toBe(true)
    expect(d.bottomReceiver).toBe(false)
    expect(d.rails).toEqual([]) // level wall: M-F-1Door has no header
    expect(f.bottomChannelGaps).toEqual([[d.s0, d.s1]])
  })
  it('flags the door height: the supplier door frame is 80" tall, this panel is not', () => {
    expect(lay.warnings.some((w) => w.wall === 2 && /80" tall/.test(w.message))).toBe(true)
  })
  it('rejects a second door instead of extrapolating the formula', () => {
    const l2 = computeLayout(room(216, 144, { panels: { 2: 3 }, windows: { 2: [{ type: 'door' }, { type: 'door' }] } }), S)
    expect(wallOf(l2, 2).error).toMatch(/Only one door per wall/)
    expect(wallOf(l2, 2).openings).toEqual([])
  })
  it('rejects a wall that is only a door', () => {
    const l2 = computeLayout(room(216, 144, { panels: { 2: 1 }, windows: { 2: [{ type: 'door' }] } }), S)
    expect(wallOf(l2, 2).error).toMatch(/at least one other panel/)
  })
})

describe('window type width limits (supplier email)', () => {
  it('auto count uses the intersection of the chosen types (casement 24-36)', () => {
    const lay = computeLayout(room(216, 144, { windows: { 2: [{ type: 'casement' }] } }), S)
    const f = wallOf(lay, 2)
    // fixed + casement -> 24..36; N >= (run + P) / (36 + P) = 5.43 -> 6
    expect(f.limits.min).toBe(24)
    expect(f.limits.max).toBe(36)
    expect(f.count).toBe(6)
    expect(f.panelSize).toBeLessThanOrEqual(36)
  })
  it('requested count outside the combined limits is an error with the valid counts', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'casement' }] } }), S)
    expect(wallOf(lay, 2).error).toMatch(/must be 24"–36"\. Use 6–8 panels/)
  })
  it('solid panels have no rails (assumption: "solid full vertical panel")', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 5 }, windows: { 2: [{ type: 'solid' }] } }), S)
    const p = wallOf(lay, 2).panels[0]
    expect(p.type).toBe('solid')
    expect(p.rails).toEqual([])
    expect(p.bottomReceiver).toBe(true)
  })
  it('transom is ignored on solid and door panels', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 5 }, windows: { 2: [{ type: 'solid', transom: true }] } }), S)
    expect(wallOf(lay, 2).panels[0].transom).toBe(false)
  })
})

describe('3V transom and raked door header vs the supplier builders', () => {
  it('level wall: transom top fin 10" below the top receiver fin tip', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] } }), S)
    const p = wallOf(lay, 2).panels[0]
    const top = 84 - S.seatTop // seat line under the front top channel
    expect(p.rails.map((r) => r.name)).toEqual(['knee', 'transom'])
    // build_mf3v.py: top fin = H - 1.0 - 0.625; transom top fin = that - 10; body top = fin - 0.625
    expect(p.rails[1].bodyTop).toBeCloseTo(top - 1.625 - 10 - 0.625, 12)
    expect(p.rails[1].fits).toBe(true)
  })

  // Reproduce M-F-3Vtrap: 30" opening, 80" at the left outer edge rising to 90" at 32.209".
  // Right wall seen from outside runs front corner -> house, so it rises to the right like the builder.
  it('M-F-3Vtrap: transom top body at 68.1780" above the panel bottom (supplier printout)', () => {
    const totalW = S.maleBody + 30 + S.femaleBody // 32.209
    const tan = 10 / totalW
    const stretch = Math.sqrt(1 + tan * tan)
    const depth = S.cornerAllowance + 30 + S.wallAllowance // one 30" panel on the side wall
    const o0 = S.cornerAllowance
    // panel top (seat line) at the left outer edge (s = o0 - 1) must be Z0 + 80
    const front = Z0 + 80 + S.seatTop * stretch - tan * (o0 - S.maleBody)
    const lay = computeLayout(
      room(100, depth, { panels: { 1: 1 }, windows: { 1: [{ type: 'fixed', transom: true }] }, heights: { front, back: front + tan * depth } }),
      S,
    )
    const side = wallOf(lay, 1)
    expect(side.slope).toBeCloseTo(tan, 12)
    expect(side.panels[0].s0).toBeCloseTo(o0, 12)
    expect(side.panels[0].width).toBeCloseTo(30, 12)
    const transom = side.panels[0].rails.find((r) => r.name === 'transom')
    expect(transom.bodyTop - Z0).toBeCloseTo(68.178, 3)
  })
  it('M-F-2DoorTrap: door header top fin 1" below the raked top fin at the left fin', () => {
    const totalW = S.maleBody + 72 + S.femaleBody // 74.209
    const tan = 10 / totalW
    const cos = 1 / Math.sqrt(1 + tan * tan)
    const stretch = 1 / cos
    // build_mf2doortrap.py, transcribed: z_top_fin_left = H_LEFT + tan*x_left_fin - (1.0 + 0.625)/cos
    const zTopFinLeft = 80 + tan * (S.maleBody + S.finHeight) - (S.maleBody + S.finHeight) / cos
    const expectedBodyTop = zTopFinLeft - 1.0 - S.finHeight
    const other = 20
    const depth = S.cornerAllowance + 72 + S.panelJoint + other + S.wallAllowance
    const o0 = S.cornerAllowance
    const front = Z0 + 80 + S.seatTop * stretch - tan * (o0 - S.maleBody)
    const lay = computeLayout(
      room(100, depth, { panels: { 1: 2 }, windows: { 1: [{ type: 'door' }] }, heights: { front, back: front + tan * depth } }),
      S,
    )
    const side = wallOf(lay, 1)
    expect(side.error).toBeNull()
    const d = side.panels[0]
    expect(d.width).toBeCloseTo(72, 12)
    expect(side.panels[1].width).toBeCloseTo(other, 9)
    expect(d.rails.map((r) => r.name)).toEqual(['door-header'])
    expect(d.rails[0].bodyTop - Z0).toBeCloseTo(expectedBodyTop, 9)
    expect(d.rails[0].fits).toBe(true)
  })
  it('wall falling to the right: clearance measured at the low side, with a note', () => {
    // left wall (index 3) seen from outside runs house -> front corner: falls to the right
    const lay = computeLayout(room(216, 144, { panels: { 3: 2 }, windows: { 3: [{ type: 'fixed', transom: true }] } }), S)
    const left = wallOf(lay, 3)
    const p = left.panels[0]
    const t = p.rails.find((r) => r.name === 'transom')
    const stretch = Math.sqrt(1 + left.slope * left.slope)
    const seat = (s) => left.topLeft + left.slope * s - S.seatTop * stretch
    const lowFin = seat(p.s1 - S.finHeight) - 1.625 * stretch
    expect(t.bodyTop + S.finHeight).toBeCloseTo(lowFin - 10, 9)
    expect(lay.warnings.some((w) => w.wall === 3 && /low \(right\) side/.test(w.message))).toBe(true)
  })
})

describe('fit checks', () => {
  it('a transom that would overlap the knee rail is an error, not drawn', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 4 }, windows: { 2: [{ type: 'fixed', transom: true }] }, heights: { front: 40, back: null } }), S)
    const p = wallOf(lay, 2).panels[0]
    const t = p.rails.find((r) => r.name === 'transom')
    expect(t.fits).toBe(false)
    expect(p.errors[0]).toMatch(/transom rail does not fit/)
    expect(lay.ok).toBe(false)
  })
  it('options stored beyond the panel count are kept but reported', () => {
    const lay = computeLayout(room(216, 144, { panels: { 2: 3 }, windows: { 2: [null, null, null, { type: 'slider' }] } }), S)
    expect(lay.warnings.some((w) => w.wall === 2 && /panel 4 are not used/.test(w.message))).toBe(true)
  })
})

describe('plan: setPanelOption', () => {
  const base = room(216, 144)
  it('stores the option and pins an automatic count', () => {
    const r = setPanelOption(base, 2, 1, { type: 'slider', transom: true }, 3)
    expect(r.ok).toBe(true)
    expect(r.plan.walls[2].panels).toBe(3)
    expect(r.plan.walls[2].windows).toEqual([null, { type: 'slider', transom: true }])
    expect(base.walls[2].windows).toBeNull() // input untouched
  })
  it('keeps a requested count', () => {
    const p = room(216, 144, { panels: { 2: 5 } })
    expect(setPanelOption(p, 2, 0, { type: 'fixed', transom: false }, 3).plan.walls[2].panels).toBe(5)
  })
  it('null clears an option; trailing nulls are dropped', () => {
    const a = setPanelOption(base, 2, 1, { type: 'door' }, 3).plan
    const b = setPanelOption(a, 2, 1, null, 3).plan
    expect(b.walls[2].windows).toBeNull()
  })
  it('rejects a second door, unknown types, panels out of range and the house wall', () => {
    const a = setPanelOption(base, 2, 0, { type: 'door' }, 3).plan
    expect(setPanelOption(a, 2, 2, { type: 'door' }, 3).error).toMatch(/already the door/)
    expect(setPanelOption(base, 2, 0, { type: 'awning' }, 3).ok).toBe(false)
    expect(setPanelOption(base, 2, 3, { type: 'fixed' }, 3).ok).toBe(false)
    expect(setPanelOption(base, 0, 0, { type: 'fixed' }, 3).ok).toBe(false)
    expect(setPanelOption(base, 2, 0, { type: 'fixed' }, null).ok).toBe(false)
  })
  it('clonePlan copies options; setHouseWall clears them', () => {
    const a = setPanelOption(base, 2, 0, { type: 'casement', transom: true }, 3).plan
    const c = clonePlan(a)
    expect(c.walls[2].windows).toEqual(a.walls[2].windows)
    expect(c.walls[2].windows).not.toBe(a.walls[2].windows)
    expect(setHouseWall(a, 2).plan.walls[2].windows).toBeNull()
  })
})
