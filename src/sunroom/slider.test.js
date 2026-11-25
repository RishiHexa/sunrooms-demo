/**
 * Slider open motion (visual). Rule from the supplier's 225 macros:
 *   SliderSash225_Build.FCMacro    interior sash moves; TRAVEL = hard stop - 1/8"
 *   SliderSash225_Animate.FCMacro  ease 0.5 - 0.5 cos(pi t), 3 s
 */
import { describe, expect, it } from 'vitest'
import { SLIDER_MOTION, easeSlide, sliderTravel } from './slider.js'
import { computeLayout } from './layout.js'
import { SPEC_4SEASON as S, SECTIONS_4SEASON } from './spec4season.js'
import { buildSunroom, disposeGroup } from './build3d.js'

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
    heights: { front: null, back: null },
  }
}

describe('motion rule', () => {
  it('travel = placeholder hard stop (width/2 - overlap/2) minus 1/8"', () => {
    expect(SLIDER_MOTION.stopShort).toBe(0.125)
    expect(sliderTravel(48, 1)).toBeCloseTo(24 - 0.5 - 0.125, 12)
    expect(sliderTravel(0.5, 1)).toBe(0) // no room: never negative
  })
  it('ease matches the macro: 0 -> 0, 0.5 -> 0.5, 1 -> 1, clamped', () => {
    expect(easeSlide(0)).toBeCloseTo(0, 12)
    expect(easeSlide(0.5)).toBeCloseTo(0.5, 12)
    expect(easeSlide(1)).toBeCloseTo(1, 12)
    expect(easeSlide(-1)).toBeCloseTo(0, 12)
    expect(easeSlide(2)).toBeCloseTo(1, 12)
  })
})

describe('3D build: movable interior sash', () => {
  // 216 x 144 lean-to: front wall level, side walls raked
  const plan = room(216, 144, {
    panels: { 1: 2, 2: 4, 3: 2 },
    windows: {
      2: [{ type: 'slider' }, null, { type: 'slider', transom: true }],
      1: [{ type: 'slider' }, { type: 'slider', transom: true }],
    },
  })
  const layout = computeLayout(plan, S)
  const { group } = buildSunroom(layout, SECTIONS_4SEASON)
  const wall = (i) => group.getObjectByName(`wall-${i}`)
  const slideGroup = (i, n) => wall(i).getObjectByName(`p${n}-slider-sash`)

  it('layout is valid', () => {
    expect(layout.errors).toEqual([])
  })
  it('level opening: interior sash + its glass are in the slide group, exterior sash stays on the wall', () => {
    const g = slideGroup(2, 1)
    expect(g.parent).toBe(wall(2))
    expect(g.children.map((m) => m.name).sort()).toEqual(['p1-glass-2a', 'p1-sash-interior'])
    expect(wall(2).getObjectByName('p1-sash-exterior').parent).toBe(wall(2))
    const p = layout.walls.find((w) => w.index === 2).panels[0]
    expect(g.userData.slide.travel).toBeCloseTo(sliderTravel(p.width, 1.0), 12)
    expect(g.userData.panel).toBe(1)
  })
  it('slides along the wall to the right seen from outside (225: -X seen from inside)', () => {
    const w = layout.walls.find((x) => x.index === 2)
    const dir = slideGroup(2, 1).userData.slide.dir
    expect(dir.x).toBeCloseTo(w.right.x, 12)
    expect(dir.z).toBeCloseTo(w.right.y, 12)
    expect(dir.y).toBe(0)
  })
  it('raked main opening is not animated; with a transom (level top) it is', () => {
    expect(slideGroup(1, 1).userData.slide).toBe(null)
    expect(slideGroup(1, 2).userData.slide.travel).toBeGreaterThan(0)
  })
  it('sash meshes are built at the closed position (positions zero)', () => {
    for (const m of slideGroup(2, 1).children) expect(m.position.length()).toBe(0)
  })
  disposeGroup(group)
})
