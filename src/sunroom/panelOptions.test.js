/**
 * Choosing a panel type keeps the wall buildable (supplier formula + width limits only):
 *   casement 24"–36" (supplier email); X = (L - C - C - (N-1)P) / N, C 5.514, P 1.5.
 * Default room 81" x 55": front run 69.972 -> 1 panel 69.972, 2 panels 34.236;
 * side run 47.986 -> 1 panel 47.986, 2 panels 23.243 (no casement count exists).
 */
import { describe, expect, it } from 'vitest'
import { computeLayout } from './layout.js'
import { SPEC_4SEASON as S } from './spec4season.js'
import { choosePanelOption, typeAvailability } from './panelOptions.js'
import { createDefaultPlan } from '../floorplan/defaults.js'

const FRONT = 2
const RIGHT = 1
const wallOf = (plan, i) => computeLayout(plan, S).walls.find((w) => w.index === i)

describe('automatic count moves to the nearest buildable count', () => {
  const base = createDefaultPlan()
  const r = choosePanelOption(base, FRONT, 0, { type: 'casement', transom: false }, S)
  it('front wall: casement -> 2 panels × 34.236", buildable, notice shown', () => {
    expect(r.ok).toBe(true)
    expect(r.plan.walls[FRONT].panels).toBe(2)
    expect(r.plan.walls[FRONT].windows).toEqual([{ type: 'casement', transom: false }])
    const w = wallOf(r.plan, FRONT)
    expect(w.error).toBe(null)
    expect(w.panelSize).toBeCloseTo((81 - 2 * 5.514 - 1.5) / 2, 9)
    expect(r.notice).toMatch(/from 1 to 2/)
    expect(r.notice).toMatch(/24"–36"/)
  })
  it('nothing else in the plan changes', () => {
    for (const i of [0, 1, 3]) expect(r.plan.walls[i]).toEqual(base.walls[i])
    expect(r.plan.vertices).toEqual(base.vertices)
    expect(r.plan.heights).toEqual(base.heights)
  })
})

describe('no buildable count: refused with the sizes either side of the limits', () => {
  const base = createDefaultPlan()
  it('55" side wall cannot take a casement', () => {
    const r = choosePanelOption(base, RIGHT, 0, { type: 'casement', transom: false }, S)
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/Casement section doesn't fit the Right wall \(55"\)/)
    expect(r.error).toMatch(/1 panel = 47\.986" \(max 36"\)/)
    expect(r.error).toMatch(/2 panels = 23\.243" \(min 24"\)/)
  })
  it('a 72" door on a 55" wall gets a door message, not negative panel sizes', () => {
    const r = choosePanelOption(base, RIGHT, 0, { type: 'door', transom: false }, S)
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/72" door doesn't fit the Right wall/)
    expect(r.error).toMatch(/needs 81\.5" of clear run; this wall has 47\.986"/)
    expect(r.error).not.toMatch(/-\d/)
  })
  it('typeAvailability marks casement unavailable there, fixed/slider/solid available', () => {
    const a = typeAvailability(base, RIGHT, 0, S)
    expect(a.casement.ok).toBe(false)
    expect(a.fixed.ok).toBe(true)
    expect(a.slider.ok).toBe(true) // 47.986 within 30–72
    expect(a.solid.ok).toBe(true) // 47.986 within 6–48
  })
})

describe('unchanged behaviour', () => {
  it('a type that fits the current count does not touch the count and gives no notice', () => {
    const r = choosePanelOption(createDefaultPlan(), FRONT, 0, { type: 'slider', transom: false }, S)
    expect(r.ok).toBe(true)
    expect(r.notice).toBe(null)
    expect(r.plan.walls[FRONT].panels).toBe(1) // pinned to the count it was laid out with
  })
  it('a stored count is kept: the option is stored and the layout reports the fix', () => {
    const p = createDefaultPlan()
    p.walls[FRONT].panels = 1 // stored count (user or earlier option)
    const r = choosePanelOption(p, FRONT, 0, { type: 'casement', transom: false }, S)
    expect(r.ok).toBe(true)
    expect(r.plan.walls[FRONT].panels).toBe(1)
    expect(wallOf(r.plan, FRONT).error).toMatch(/Use 2 panels/)
  })
  it('one door per wall is still refused by setPanelOption', () => {
    const p = createDefaultPlan()
    p.vertices = [{ x: 0, y: 0 }, { x: 216, y: 0 }, { x: 216, y: 144 }, { x: 0, y: 144 }]
    const r1 = choosePanelOption(p, FRONT, 0, { type: 'door', transom: false }, S)
    expect(r1.ok).toBe(true)
    const r2 = choosePanelOption(r1.plan, FRONT, 1, { type: 'door', transom: false }, S)
    expect(r2.ok).toBe(false)
    expect(r2.error).toMatch(/already the door/)
  })
  it('clearing an option (null) is passed through', () => {
    const r1 = choosePanelOption(createDefaultPlan(), FRONT, 0, { type: 'slider', transom: false }, S)
    const r2 = choosePanelOption(r1.plan, FRONT, 0, null, S)
    expect(r2.ok).toBe(true)
    expect(r2.plan.walls[FRONT].windows).toBe(null)
  })
})
