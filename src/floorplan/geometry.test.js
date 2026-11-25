import { describe, expect, it } from 'vitest'
import { createDefaultPlan } from './defaults.js'
import {
  snapToRightAngles,
  RIGHT_ANGLE_SNAP_DEG,
  interiorAngle,
  moveVertex,
  setWallLength,
  setRoomHeights,
  resetRoomHeights,
  splitWall,
  toggleLock,
  toggleOrientation,
  validatePlan,
  wallLength,
} from './geometry.js'

const close = (a, b) => expect(a).toBeCloseTo(b, 9)

/** Default plan without a house wall, so every wall can be split in geometry tests. */
function createPlainPlan() {
  const p = createDefaultPlan()
  p.walls.forEach((w) => (w.house = false))
  return p
}

describe('default plan', () => {
  it('is an 81 x 55 rectangle with 90Â° corners', () => {
    const p = createDefaultPlan()
    expect(validatePlan(p)).toBeNull()
    expect([0, 1, 2, 3].map((i) => wallLength(p, i))).toEqual([81, 55, 81, 55])
    for (let i = 0; i < 4; i++) close(interiorAngle(p, i), 90)
  })
})

describe('setWallLength', () => {
  it('grows symmetrically, keeps perpendicular walls vertical, locks the wall', () => {
    const p = createDefaultPlan()
    const res = setWallLength(p, 2, 100) // front wall
    expect(res.ok).toBe(true)
    const q = res.plan
    close(wallLength(q, 2), 100)
    expect(q.walls[2].locked).toBe(true)
    // back wall followed via vertical side walls
    close(wallLength(q, 0), 100)
    close(q.vertices[3].x, -9.5)
    close(q.vertices[2].x, 90.5)
    close(wallLength(q, 1), 55)
    close(wallLength(q, 3), 55)
    expect(validatePlan(q)).toBeNull()
    // input untouched
    expect(wallLength(p, 2)).toBe(81)
  })

  it('does not move the apex of a gable when the base changes', () => {
    let p = createPlainPlan()
    p = splitWall(p, 0).plan // back wall -> two walls, apex vertex 1
    p = moveVertex(p, 1, { x: 40.5, y: -20 }).plan
    const apex = { ...p.vertices[1] }
    const res = setWallLength(p, 3, 100) // front wall is now index 3
    expect(res.ok).toBe(true)
    expect(res.plan.vertices[1]).toEqual(apex)
  })

  it('rejects non-positive and non-numeric lengths without changing the plan', () => {
    const p = createDefaultPlan()
    expect(setWallLength(p, 0, 0).ok).toBe(false)
    expect(setWallLength(p, 0, NaN).ok).toBe(false)
    expect(setWallLength(p, 0, -5).ok).toBe(false)
  })

  it('rejects a length that conflicts with locked walls', () => {
    // Lock all four walls: changing one length is impossible.
    let p = createDefaultPlan()
    for (let i = 0; i < 4; i++) p = toggleLock(p, i).plan
    const res = setWallLength(p, 0, 90)
    expect(res.ok).toBe(false)
  })
})

describe('moveVertex', () => {
  it('drags a corner and keeps aligned walls aligned', () => {
    const p = createDefaultPlan()
    const res = moveVertex(p, 2, { x: 100, y: 70 })
    expect(res.ok).toBe(true)
    const q = res.plan
    expect(q.vertices[2]).toEqual({ x: 100, y: 70 })
    expect(q.vertices[1]).toEqual({ x: 100, y: 0 }) // right wall stays vertical
    expect(q.vertices[3]).toEqual({ x: 0, y: 70 }) // front wall stays horizontal
    expect(q.vertices[0]).toEqual({ x: 0, y: 0 })
  })

  it('translates the whole shape when every wall is locked', () => {
    let p = createDefaultPlan()
    for (let i = 0; i < 4; i++) p = toggleLock(p, i).plan
    const q = moveVertex(p, 0, { x: 10, y: 5 }).plan
    expect(q.vertices).toEqual([
      { x: 10, y: 5 },
      { x: 91, y: 5 },
      { x: 91, y: 60 },
      { x: 10, y: 60 },
    ])
  })

  it('rejects moves that make walls cross', () => {
    let p = createPlainPlan()
    p = splitWall(p, 0).plan
    const res = moveVertex(p, 1, { x: 40.5, y: 80 }) // pull apex through the front wall
    expect(res.ok).toBe(false)
  })
})

describe('splitWall', () => {
  it('inserts a 180Â° midpoint vertex with two free walls', () => {
    const res = splitWall(createPlainPlan(), 0)
    expect(res.ok).toBe(true)
    const q = res.plan
    expect(q.vertices.length).toBe(5)
    expect(q.vertices[1]).toEqual({ x: 40.5, y: 0 })
    close(interiorAngle(q, 1), 180)
    expect(q.walls[0]).toEqual({ orientation: null, locked: false, house: false, panels: null, windows: null })
    expect(q.walls[1]).toEqual({ orientation: null, locked: false, house: false, panels: null, windows: null })
    close(wallLength(q, 0), 40.5)
  })

  it('reports reflex angles above 180Â°', () => {
    let p = splitWall(createPlainPlan(), 0).plan
    p = moveVertex(p, 1, { x: 40.5, y: 20 }).plan // push apex inward
    expect(interiorAngle(p, 1)).toBeGreaterThan(180)
  })
})

describe('toggleOrientation', () => {
  it('clears an active constraint without moving geometry', () => {
    const p = createDefaultPlan()
    const q = toggleOrientation(p, 0, 'h').plan
    expect(q.walls[0].orientation).toBeNull()
    expect(q.vertices).toEqual(p.vertices)
  })

  it('straightens a slanted wall keeping its length', () => {
    let p = splitWall(createPlainPlan(), 0).plan
    p = moveVertex(p, 1, { x: 40.5, y: -20 }).plan
    const before = wallLength(p, 0)
    const res = toggleOrientation(p, 0, 'h')
    expect(res.ok).toBe(true)
    close(res.plan.vertices[0].y, res.plan.vertices[1].y)
    close(wallLength(res.plan, 0), before)
    expect(res.plan.walls[0].orientation).toBe('h')
  })
})

describe('snapToRightAngles', () => {
  const W = (orientation = null, locked = false, house = false) => ({ orientation, locked, house, panels: null })

  // L-shaped plan like the user's: house on top, Front 2 free between two vertical walls.
  function lPlan() {
    return {
      vertices: [
        { x: 0, y: 0 }, // 0
        { x: 317.4375, y: 0 }, // 1
        { x: 317.4375, y: 281.8125 }, // 2  (Right bottom)
        { x: 160.0625, y: 281.8125 }, // 3  (Front 2 left / Left 2 bottom)
        { x: 160.0625, y: 150 }, // 4  (270 corner)
        { x: 0, y: 150 }, // 5
      ],
      walls: [W('h', false, true), W('v'), W(null), W('v'), W('h'), W('v')],
    }
  }

  it('makes a nearly-square corner exactly square (user case: Front 2 off by 0.05")', () => {
    // start from the off-square state: Front 2's left end 1/16" low (89.98° / 90.02°)
    const p = lPlan()
    p.vertices[3] = { x: 160.0625, y: 281.875 }
    expect(Math.abs(interiorAngle(p, 2) - 90)).toBeGreaterThan(0.01)
    // drag that vertex a little: the snap pulls it onto Right's square line
    const target = { x: 160.0625, y: 281.9375 }
    const snapped = snapToRightAngles(p, 3, target)
    const res = moveVertex(p, 3, snapped)
    expect(res.ok).toBe(true)
    expect(snapped.y).toBe(281.8125)
    close(interiorAngle(res.plan, 2), 90)
    close(interiorAngle(res.plan, 3), 90)
    close(interiorAngle(res.plan, 4), 270)
  })

  it('squares the dragged corner itself when both of its walls are free', () => {
    const p = createPlainPlan()
    p.walls.forEach((w) => (w.orientation = null))
    // corner 2 of the 81 x 55 rectangle, nudged 1/2" right
    const out = snapToRightAngles(p, 2, { x: 81.5, y: 55 })
    const q = moveVertex(p, 2, out).plan
    close(interiorAngle(q, 2), 90)
  })

  it('does not interfere with constrained walls (rectangle corner drag stays free)', () => {
    const p = createDefaultPlan()
    const target = { x: 90, y: 70 }
    expect(snapToRightAngles(p, 2, target)).toEqual(target)
  })

  it('leaves corners alone outside the tolerance', () => {
    const p = lPlan()
    const off = Math.tan(((RIGHT_ANGLE_SNAP_DEG + 1) * Math.PI) / 180) * (317.4375 - 160.0625)
    const target = { x: 160.0625, y: 281.8125 + off }
    expect(snapToRightAngles(p, 3, target)).toEqual(target)
  })
})

describe('room heights', () => {
  it('default plan has no explicit heights', () => {
    expect(createDefaultPlan().heights).toEqual({ front: null, back: null })
  })

  it('setRoomHeights stores both values without mutating the input', () => {
    const p = createDefaultPlan()
    const res = setRoomHeights(p, 90, 100)
    expect(res.ok).toBe(true)
    expect(res.plan.heights).toEqual({ front: 90, back: 100 })
    expect(p.heights).toEqual({ front: null, back: null })
  })

  it('rejects non-numbers, zero / negative, and back <= front', () => {
    const p = createDefaultPlan()
    expect(setRoomHeights(p, NaN, 100).ok).toBe(false)
    expect(setRoomHeights(p, 0, 100).ok).toBe(false)
    expect(setRoomHeights(p, 90, -1).ok).toBe(false)
    expect(setRoomHeights(p, 90, 90).ok).toBe(false)
    expect(setRoomHeights(p, 90, 80).ok).toBe(false)
  })

  it('front only (back null) keeps the back on the default slope', () => {
    const res = setRoomHeights(createDefaultPlan(), 90, null)
    expect(res.ok).toBe(true)
    expect(res.plan.heights).toEqual({ front: 90, back: null })
    expect(setRoomHeights(createDefaultPlan(), 90, undefined).ok).toBe(false)
  })

  it('heights survive other plan operations (clonePlan)', () => {
    const p = setRoomHeights(createDefaultPlan(), 90, 100).plan
    expect(setWallLength(p, 2, 120).plan.heights).toEqual({ front: 90, back: 100 })
    expect(toggleLock(p, 1).plan.heights).toEqual({ front: 90, back: 100 })
    expect(splitWall(p, 2).plan.heights).toEqual({ front: 90, back: 100 })
  })

  it('resetRoomHeights returns to null (system default)', () => {
    const p = setRoomHeights(createDefaultPlan(), 90, 100).plan
    expect(resetRoomHeights(p).plan.heights).toEqual({ front: null, back: null })
  })
})
