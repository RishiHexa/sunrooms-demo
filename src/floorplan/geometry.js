/**
 * Floor plan model — pure, deterministic numeric logic. No DOM / rendering here.
 *
 * Units: all coordinates and lengths are INCHES (canonical unit).
 * Axes: plan coordinates, x to the right, y DOWN (same as the 2D screen view).
 *       A later 3D step should map plan (x, y) -> world (x, z).
 *
 * Plan shape:
 *   {
 *     vertices: [{ x, y }, ...],                 // closed polygon, n >= 3
 *     walls:    [{ orientation, locked, house, panels, windows }, ...],  // wall i goes vertices[i] -> vertices[(i+1) % n]
 *   }
 *   orientation: 'h' (kept horizontal) | 'v' (kept vertical) | null (free)
 *   locked:      true = wall length is fixed
 *   house:       true = this side is the existing house wall (no sunroom wall is built there)
 *   panels:      requested panel count for this wall, or null = automatic
 *   windows:     per-panel options, or null. windows[k] = { type, transom } for panel k (0-based,
 *                left -> right seen from outside), or null = system default type, no transom.
 *                type: 'fixed' | 'slider' | 'casement' | 'solid' | 'door' (see spec panelTypes).
 *   heights:     { front, back } room heights in inches, or null = system default (see layout.js).
 *                front = top of top channel on the low (front) wall's exterior line,
 *                back  = the same at the house wall; null = follows the default slope.
 *
 * Every operation returns { ok: true, plan } or { ok: false, error } and never
 * mutates its input. Rejected operations leave the stored plan untouched.
 */

/** Numerical tolerance (inches) for equality checks. */
export const EPS = 1e-9

/**
 * Smallest wall length the editor accepts, in inches.
 * UI guard against collapsing walls — NOT a product rule. Confirm with product data.
 */
export const MIN_WALL_LENGTH_IN = 1

/** Drag positions snap to 1/16" (the display precision). */
export const SNAP_IN = 1 / 16

// ---------------------------------------------------------------------------
// Basic helpers
// ---------------------------------------------------------------------------

export function clonePlan(plan) {
  return {
    vertices: plan.vertices.map((v) => ({ x: v.x, y: v.y })),
    walls: plan.walls.map((w) => ({
      orientation: w.orientation,
      locked: w.locked,
      house: !!w.house,
      panels: w.panels ?? null,
      windows: w.windows ? w.windows.map((e) => (e ? { type: e.type, transom: !!e.transom } : null)) : null,
    })),
    heights: {
      front: plan.heights?.front ?? null,
      back: plan.heights?.back ?? null,
    },
  }
}

const freshWall = () => ({ orientation: null, locked: false, house: false, panels: null, windows: null })

const mod = (i, n) => ((i % n) + n) % n

export function wallEndpoints(plan, i) {
  const n = plan.vertices.length
  return [plan.vertices[i], plan.vertices[mod(i + 1, n)]]
}

export function wallLength(plan, i) {
  const [a, b] = wallEndpoints(plan, i)
  return Math.hypot(b.x - a.x, b.y - a.y)
}

/** Shoelace signed area. Sign tells winding direction. */
export function signedArea(plan) {
  const v = plan.vertices
  let s = 0
  for (let i = 0; i < v.length; i++) {
    const a = v[i]
    const b = v[(i + 1) % v.length]
    s += a.x * b.y - b.x * a.y
  }
  return s / 2
}

/** Unit normal of wall i pointing OUT of the polygon. */
export function outwardNormal(plan, i) {
  const [a, b] = wallEndpoints(plan, i)
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  // For positive shoelace area the interior is on the (-dy, dx) side.
  return signedArea(plan) > 0 ? { x: dy / len, y: -dx / len } : { x: -dy / len, y: dx / len }
}

/** Interior angle at vertex i, in degrees (0, 360). */
export function interiorAngle(plan, i) {
  const v = plan.vertices
  const n = v.length
  const prev = v[mod(i - 1, n)]
  const cur = v[i]
  const next = v[mod(i + 1, n)]
  const ax = prev.x - cur.x
  const ay = prev.y - cur.y
  const bx = next.x - cur.x
  const by = next.y - cur.y
  // Angle swept from "to next" to "to prev", oriented by winding.
  let ang = Math.atan2(ax * by - ay * bx, ax * bx + ay * by) // (-pi, pi]
  const sign = signedArea(plan) > 0 ? -1 : 1
  ang = ang * sign
  if (ang < 0) ang += 2 * Math.PI
  return (ang * 180) / Math.PI
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function segmentsIntersect(p1, p2, p3, p4) {
  const d = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
  const onSeg = (a, b, c) =>
    Math.min(a.x, b.x) - EPS <= c.x &&
    c.x <= Math.max(a.x, b.x) + EPS &&
    Math.min(a.y, b.y) - EPS <= c.y &&
    c.y <= Math.max(a.y, b.y) + EPS
  const d1 = d(p3, p4, p1)
  const d2 = d(p3, p4, p2)
  const d3 = d(p1, p2, p3)
  const d4 = d(p1, p2, p4)
  if (((d1 > EPS && d2 < -EPS) || (d1 < -EPS && d2 > EPS)) && ((d3 > EPS && d4 < -EPS) || (d3 < -EPS && d4 > EPS))) {
    return true
  }
  if (Math.abs(d1) <= EPS && onSeg(p3, p4, p1)) return true
  if (Math.abs(d2) <= EPS && onSeg(p3, p4, p2)) return true
  if (Math.abs(d3) <= EPS && onSeg(p1, p2, p3)) return true
  if (Math.abs(d4) <= EPS && onSeg(p1, p2, p4)) return true
  return false
}

/** Returns an error string, or null when the plan is a valid editable floor. */
export function validatePlan(plan) {
  const v = plan.vertices
  const n = v.length
  if (n < 3) return 'A floor needs at least 3 walls.'
  if (plan.walls.length !== n) return 'Wall/vertex count mismatch.'
  for (const p of v) {
    if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) return 'Invalid coordinate.'
  }
  for (let i = 0; i < n; i++) {
    if (wallLength(plan, i) < MIN_WALL_LENGTH_IN - EPS) return 'Wall would be too short.'
  }
  // Non-adjacent walls must not touch or cross.
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue
      const [a, b] = wallEndpoints(plan, i)
      const [c, d] = wallEndpoints(plan, j)
      if (segmentsIntersect(a, b, c, d)) return 'Walls would cross each other.'
    }
  }
  // Constraints must hold.
  for (let i = 0; i < n; i++) {
    const [a, b] = wallEndpoints(plan, i)
    const o = plan.walls[i].orientation
    if (o === 'h' && Math.abs(a.y - b.y) > 1e-6) return 'Horizontal constraint broken.'
    if (o === 'v' && Math.abs(a.x - b.x) > 1e-6) return 'Vertical constraint broken.'
  }
  return null
}

// ---------------------------------------------------------------------------
// Constraint propagation
// ---------------------------------------------------------------------------

/**
 * How a displacement (dx, dy) of one end of a wall is passed to its other end so
 * that the wall keeps its constraints:
 *   locked          -> whole wall translates          (dx, dy)
 *   horizontal      -> other end follows vertically   (0, dy)
 *   vertical        -> other end follows horizontally (dx, 0)
 *   free            -> nothing propagates             (0, 0)
 */
function transmit(wall, d) {
  if (wall.locked) return { x: d.x, y: d.y }
  if (wall.orientation === 'h') return { x: 0, y: d.y }
  if (wall.orientation === 'v') return { x: d.x, y: 0 }
  return { x: 0, y: 0 }
}

const isZero = (d) => Math.abs(d.x) <= EPS && Math.abs(d.y) <= EPS
const same = (a, b) => Math.abs(a.x - b.x) <= EPS && Math.abs(a.y - b.y) <= EPS

/**
 * Apply displacements to seed vertices and propagate them around the polygon
 * through constrained walls. Walls in `blocked` do not propagate (their both
 * ends are being controlled by the caller).
 *
 * @param {object} plan
 * @param {Map<number, {x:number,y:number}>} seeds vertex index -> displacement
 * @param {Set<number>} blocked wall indices
 * @returns {object|null} new plan, or null on conflicting constraints
 */
export function propagate(plan, seeds, blocked = new Set()) {
  const n = plan.vertices.length
  const deltas = new Map(seeds)

  for (const [start, d0] of seeds) {
    // Walk forward (wall j: j -> j+1) and backward (wall j-1: j-1 -> j).
    for (const dir of [1, -1]) {
      let j = start
      let d = d0
      for (let step = 0; step < n; step++) {
        const wallIdx = dir === 1 ? j : mod(j - 1, n)
        if (blocked.has(wallIdx)) break
        const nd = transmit(plan.walls[wallIdx], d)
        if (isZero(nd)) break
        const k = mod(j + dir, n)
        const existing = deltas.get(k)
        if (existing) {
          if (!same(existing, nd)) return null // two constraints disagree
          break
        }
        deltas.set(k, nd)
        j = k
        d = nd
      }
    }
  }

  const next = clonePlan(plan)
  for (const [i, d] of deltas) {
    next.vertices[i].x += d.x
    next.vertices[i].y += d.y
  }
  return next
}

function finish(next, fallbackError) {
  if (!next) return { ok: false, error: fallbackError }
  const err = validatePlan(next)
  return err ? { ok: false, error: err } : { ok: true, plan: next }
}

// ---------------------------------------------------------------------------
// Operations
// ---------------------------------------------------------------------------

export function snap(value, step = SNAP_IN) {
  return Math.round(value / step) * step
}

/**
 * Move vertex i to `target`. If the full move conflicts with constraints, the
 * horizontal-only and vertical-only parts of the move are tried in turn.
 */
export function moveVertex(plan, i, target) {
  const cur = plan.vertices[i]
  const full = { x: target.x - cur.x, y: target.y - cur.y }
  if (isZero(full)) return { ok: true, plan: clonePlan(plan) } // no movement is a valid no-op
  const attempts = [full, { x: full.x, y: 0 }, { x: 0, y: full.y }]
  let lastError = 'That move conflicts with the wall constraints.'
  for (const d of attempts) {
    if (isZero(d)) continue
    const res = finish(propagate(plan, new Map([[i, d]])), lastError)
    if (res.ok) return res
    lastError = res.error
  }
  return { ok: false, error: lastError }
}

/**
 * Set wall i to `length` inches. Tries growing/shrinking symmetrically about the
 * wall's midpoint, then anchored at its start, then anchored at its end.
 * On success the wall becomes length-locked.
 */
export function setWallLength(plan, i, length) {
  if (!Number.isFinite(length) || length <= 0) return { ok: false, error: 'Enter a length greater than 0.' }
  if (length < MIN_WALL_LENGTH_IN) return { ok: false, error: `Minimum wall length is ${MIN_WALL_LENGTH_IN}".` }
  const n = plan.vertices.length
  const [a, b] = wallEndpoints(plan, i)
  const cur = Math.hypot(b.x - a.x, b.y - a.y)
  const ux = (b.x - a.x) / cur
  const uy = (b.y - a.y) / cur
  const c = length - cur
  const ia = i
  const ib = mod(i + 1, n)
  const blocked = new Set([i])
  const options = [
    new Map([
      [ia, { x: (-ux * c) / 2, y: (-uy * c) / 2 }],
      [ib, { x: (ux * c) / 2, y: (uy * c) / 2 }],
    ]),
    // Anchored variants pin the other end with a zero displacement so that
    // propagation arriving there is checked rather than silently moving it.
    new Map([
      [ia, { x: 0, y: 0 }],
      [ib, { x: ux * c, y: uy * c }],
    ]),
    new Map([
      [ia, { x: -ux * c, y: -uy * c }],
      [ib, { x: 0, y: 0 }],
    ]),
  ]
  let lastError = 'That length conflicts with locked or aligned walls.'
  for (const seeds of options) {
    const res = finish(propagate(plan, seeds, blocked), lastError)
    if (res.ok && Math.abs(wallLength(res.plan, i) - length) > 1e-6) {
      lastError = 'That length conflicts with locked or aligned walls.'
      continue
    }
    if (res.ok) {
      res.plan.walls[i].locked = true
      return res
    }
    lastError = res.error
  }
  return { ok: false, error: lastError }
}

/** Toggle the length lock of wall i (no geometry change). */
export function toggleLock(plan, i) {
  const next = clonePlan(plan)
  next.walls[i].locked = !next.walls[i].locked
  return { ok: true, plan: next }
}

/**
 * Toggle wall i's orientation constraint. Selecting the active orientation
 * clears it. Selecting a new one straightens the wall about its midpoint,
 * keeping its length; if that conflicts, it projects the ends onto the
 * midpoint line instead.
 */
export function toggleOrientation(plan, i, orientation) {
  if (orientation !== 'h' && orientation !== 'v') return { ok: false, error: 'Unknown orientation.' }
  if (plan.walls[i].orientation === orientation) {
    const next = clonePlan(plan)
    next.walls[i].orientation = null
    return { ok: true, plan: next }
  }
  const n = plan.vertices.length
  const [a, b] = wallEndpoints(plan, i)
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const len = Math.hypot(b.x - a.x, b.y - a.y)
  const ia = i
  const ib = mod(i + 1, n)
  let rotated
  let projected
  if (orientation === 'h') {
    const s = b.x >= a.x ? 1 : -1
    rotated = [
      { x: mx - (s * len) / 2, y: my },
      { x: mx + (s * len) / 2, y: my },
    ]
    projected = [
      { x: a.x, y: my },
      { x: b.x, y: my },
    ]
  } else {
    const s = b.y >= a.y ? 1 : -1
    rotated = [
      { x: mx, y: my - (s * len) / 2 },
      { x: mx, y: my + (s * len) / 2 },
    ]
    projected = [
      { x: mx, y: a.y },
      { x: mx, y: b.y },
    ]
  }

  // Set the constraint first so propagation through this wall is irrelevant
  // (it is blocked) but validation checks it.
  const base = clonePlan(plan)
  base.walls[i].orientation = orientation
  const blocked = new Set([i])
  const candidates = plan.walls[i].locked ? [rotated] : [rotated, projected]
  let lastError = 'Cannot straighten this wall with the current constraints.'
  for (const [pa, pb] of candidates) {
    // Both ends are seeded (even with zero) so neither can be moved by propagation.
    const seeds = new Map([
      [ia, { x: pa.x - a.x, y: pa.y - a.y }],
      [ib, { x: pb.x - b.x, y: pb.y - b.y }],
    ])
    const res = finish(propagate(base, seeds, blocked), lastError)
    if (res.ok) return res
    lastError = res.error
  }
  return { ok: false, error: lastError }
}

/** Insert a vertex at the midpoint of wall i, producing two free, unlocked walls. */
export function splitWall(plan, i) {
  if (plan.walls[i].house) return { ok: false, error: 'The house wall cannot be split.' }
  const n = plan.vertices.length
  const [a, b] = wallEndpoints(plan, i)
  const next = clonePlan(plan)
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  next.vertices.splice(i + 1, 0, mid)
  next.walls.splice(i, 1, freshWall(), freshWall())
  if (next.vertices.length !== n + 1) return { ok: false, error: 'Split failed.' }
  return finish(next, 'Split failed.')
}

/** Corners within this many degrees of square (90° or 270°) are snapped exactly square while dragging. */
export const RIGHT_ANGLE_SNAP_DEG = 1.5

/**
 * Adjust a drag target for vertex i so that corners that are nearly square become exactly
 * square. Considers the corner at the dragged vertex and the corners at both neighbours
 * (whose other walls stay fixed). Returns a new target; the caller still runs moveVertex.
 */
export function snapToRightAngles(plan, i, target, tolDeg = RIGHT_ANGLE_SNAP_DEG) {
  const v = plan.vertices
  const n = v.length
  if (n < 3) return target
  const A = v[mod(i - 1, n)]
  const B = v[mod(i + 1, n)]
  const Ap = v[mod(i - 2, n)]
  const Bn = v[mod(i + 2, n)]
  const sinTol = Math.sin((tolDeg * Math.PI) / 180)
  const sub2 = (p, q) => ({ x: p.x - q.x, y: p.y - q.y })
  const len2 = (p) => Math.hypot(p.x, p.y)
  const nearPerp = (u, w) => {
    const lu = len2(u)
    const lw = len2(w)
    if (lu < EPS || lw < EPS) return false
    return Math.abs((u.x * w.x + u.y * w.y) / (lu * lw)) < sinTol
  }

  // Walls that carry their neighbour along (orientation / length lock) keep their corners as the
  // constraints dictate; only FREE walls leave the neighbour fixed and so can be snapped against.
  const wPrev = plan.walls[mod(i - 1, n)] // A -> dragged vertex
  const wNext = plan.walls[i] // dragged vertex -> B
  const free = (w) => !w.orientation && !w.locked
  const knownDir = (w, from, to) =>
    w.orientation === 'h' ? { x: 1, y: 0 } : w.orientation === 'v' ? { x: 0, y: 1 } : w.locked ? sub2(to, from) : null
  const perp = (d) => ({ x: -d.y, y: d.x })

  // Lines the target should lie on.
  const lines = []
  // corner at A (A's other wall fixed) and corner at B
  if (free(wPrev)) {
    const dA = sub2(Ap, A)
    if (Ap !== B && nearPerp(dA, sub2(target, A))) lines.push({ p: A, d: perp(dA) })
  }
  if (free(wNext)) {
    const dB = sub2(Bn, B)
    if (Bn !== A && nearPerp(dB, sub2(target, B))) lines.push({ p: B, d: perp(dB) })
  }
  // corner at the dragged vertex, when exactly one of its walls has a known direction
  if (!free(wPrev) && free(wNext)) {
    const d = knownDir(wPrev, A, v[i])
    if (d && nearPerp(d, sub2(B, target))) lines.push({ p: B, d: perp(d) })
  } else if (free(wPrev) && !free(wNext)) {
    const d = knownDir(wNext, v[i], B)
    if (d && nearPerp(d, sub2(A, target))) lines.push({ p: A, d: perp(d) })
  }
  const project = (q, L) => {
    const l2 = L.d.x * L.d.x + L.d.y * L.d.y
    const t = ((q.x - L.p.x) * L.d.x + (q.y - L.p.y) * L.d.y) / l2
    return { x: L.p.x + L.d.x * t, y: L.p.y + L.d.y * t }
  }

  let out = target
  if (lines.length >= 2) {
    for (let a = 0; a < lines.length; a++) {
      for (let b = a + 1; b < lines.length; b++) {
        const L1 = lines[a]
        const L2 = lines[b]
        const den = L1.d.x * L2.d.y - L1.d.y * L2.d.x
        if (Math.abs(den) > EPS * len2(L1.d) * len2(L2.d)) {
          const t = ((L2.p.x - L1.p.x) * L2.d.y - (L2.p.y - L1.p.y) * L2.d.x) / den
          return { x: L1.p.x + L1.d.x * t, y: L1.p.y + L1.d.y * t }
        }
      }
    }
    out = project(target, lines[0])
  } else if (lines.length === 1) {
    out = project(target, lines[0])
  }

  // Corner at the dragged vertex with both walls free: square on the circle with diameter AB.
  if (free(wPrev) && free(wNext) && nearPerp(sub2(A, out), sub2(B, out))) {
    const c = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 }
    const r = len2(sub2(B, A)) / 2
    if (lines.length === 1) {
      // intersect the line with the circle, keep the point nearest the target
      const L = lines[0]
      const dl = len2(L.d)
      const d = { x: L.d.x / dl, y: L.d.y / dl }
      const f = sub2(L.p, c)
      const b = f.x * d.x + f.y * d.y
      const disc = b * b - (f.x * f.x + f.y * f.y - r * r)
      if (disc >= 0) {
        const s = Math.sqrt(disc)
        const cands = [-b - s, -b + s].map((t) => ({ x: L.p.x + d.x * t, y: L.p.y + d.y * t }))
        const dist = (p) => Math.hypot(p.x - target.x, p.y - target.y)
        out = dist(cands[0]) <= dist(cands[1]) ? cands[0] : cands[1]
      }
    } else {
      const off = sub2(out, c)
      const l = len2(off)
      if (l > EPS) out = { x: c.x + (off.x / l) * r, y: c.y + (off.y / l) * r }
    }
  }
  return out
}

/** Make wall i the (single) house wall. Its panel request and panel options are cleared. */
export function setHouseWall(plan, i) {
  const next = clonePlan(plan)
  next.walls.forEach((w, k) => {
    w.house = k === i
  })
  next.walls[i].panels = null
  next.walls[i].windows = null
  return { ok: true, plan: next }
}

/** Panel types accepted by setPanelOption (the spec decides sizes and members). */
export const PANEL_OPTION_TYPES = Object.freeze(['fixed', 'slider', 'casement', 'solid', 'door'])

/**
 * Set the option of panel k on wall i. `option` = { type, transom }, or null to clear it back to
 * the default. `currentCount` is the wall's panel count as laid out now: if the count is still
 * automatic it is pinned to that value, so the chosen options stay on the panels they were set
 * for (an automatic count could otherwise change and move or drop them). Only one door per wall.
 */
export function setPanelOption(plan, i, k, option, currentCount) {
  const w = plan.walls[i]
  if (!w || w.house) return { ok: false, error: 'The house wall has no panels.' }
  const count = w.panels ?? currentCount
  if (!(Number.isInteger(count) && count >= 1)) return { ok: false, error: 'This wall has no valid panel layout yet: fix its size or panel count first.' }
  if (!(Number.isInteger(k) && k >= 0 && k < count)) return { ok: false, error: `Panel ${k + 1} does not exist on this wall.` }
  if (option !== null) {
    if (!PANEL_OPTION_TYPES.includes(option?.type)) return { ok: false, error: 'Unknown panel type.' }
    if (option.type === 'door') {
      const other = (w.windows ?? []).findIndex((e, j) => j !== k && j < count && e?.type === 'door')
      if (other >= 0) return { ok: false, error: `Panel ${other + 1} is already the door. Only one door per wall is documented by the supplier.` }
    }
  }
  const next = clonePlan(plan)
  const nw = next.walls[i]
  nw.panels = count
  const list = nw.windows ? [...nw.windows] : []
  while (list.length <= k) list.push(null)
  list[k] = option === null ? null : { type: option.type, transom: !!option.transom }
  // trailing nulls carry no information
  while (list.length && list[list.length - 1] === null) list.pop()
  nw.windows = list.length ? list : null
  return { ok: true, plan: next }
}

/** Clear every panel option of wall i (all panels back to the default type). The count is kept. */
export function clearPanelOptions(plan, i) {
  if (!plan.walls[i] || plan.walls[i].house) return { ok: false, error: 'The house wall has no panels.' }
  const next = clonePlan(plan)
  next.walls[i].windows = null
  return { ok: true, plan: next }
}

/** Request a panel count for wall i (null = automatic). Validity is checked by the layout. */
export function setPanelCount(plan, i, count) {
  if (count !== null && !(Number.isInteger(count) && count >= 1)) return { ok: false, error: 'Panel count must be a whole number of at least 1.' }
  if (plan.walls[i].house) return { ok: false, error: 'The house wall has no panels.' }
  const next = clonePlan(plan)
  next.walls[i].panels = count
  return { ok: true, plan: next }
}

/**
 * Store explicit room heights (inches).
 *   back = null: only the front is stored; the back follows the system default slope (and depth).
 *   back = number: both stored, so later depth changes keep both heights and the slope follows.
 * Only checks that cannot depend on product data are made here: positive numbers, and the
 * lean-to must fall away from the house. Product height limits are not documented yet.
 */
export function setRoomHeights(plan, front, back) {
  if (!Number.isFinite(front) || front <= 0) return { ok: false, error: 'Enter a front height greater than 0.' }
  if (back !== null) {
    if (!Number.isFinite(back) || back <= 0) return { ok: false, error: 'Enter a back height greater than 0.' }
    if (back <= front) return { ok: false, error: 'Back height must be greater than the front height (the roof drains to the front gutter).' }
  }
  const next = clonePlan(plan)
  next.heights = { front, back }
  return { ok: true, plan: next }
}

/** Return to the system default heights (stored as null). */
export function resetRoomHeights(plan) {
  const next = clonePlan(plan)
  next.heights = { front: null, back: null }
  return { ok: true, plan: next }
}

/** Axis-aligned bounds of the plan, in inches. */
export function bounds(plan) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const p of plan.vertices) {
    minX = Math.min(minX, p.x)
    minY = Math.min(minY, p.y)
    maxX = Math.max(maxX, p.x)
    maxY = Math.max(maxY, p.y)
  }
  return { minX, minY, maxX, maxY }
}
