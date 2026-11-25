/**
 * Sunroom layout — pure, deterministic numeric logic (INCHES). No rendering here.
 *
 * Input: the floor plan (outside corners of the corner posts, plan coords x right / y down) and
 * a system spec. Output: per-wall panel layout, corner and house-end conditions, heights, and
 * the lean-to roof frame. The 3D builder only consumes this; it never feeds back into it.
 *
 * Wall-local frame used throughout:
 *   s  along the wall, LEFT -> RIGHT as seen from OUTSIDE (s = 0 at the outside-left end)
 *   d  depth, from the exterior plane inward
 *   z  height above the underside of the bottom channel (floor level)
 *
 * Rules applied (sources in spec4season.js):
 *   - Panels are M-F (male left, female right, seen from outside); the last panel of a run is
 *     M-M so a male enters the corner post / wall channel at both ends.
 *   - Panel size  X = (L - A_left - A_right - (N-1)*P) / N,  A = C at a corner, W at the house.
 *   - Opening k spans  [A_left + k*(X+P),  A_left + k*(X+P) + X].
 *   - Lean-to: top-of-channel height rises with distance toward the house wall at `roofSlope`,
 *     lowest point = `lowWallHeight`. If the plan stores explicit heights (plan.heights), the
 *     front height replaces `lowWallHeight` and slope = (back - front) / depth.
 */
import { interiorAngle, outwardNormal, signedArea, wallEndpoints, wallLength } from '../floorplan/geometry.js'

const EPS = 1e-9
const ANGLE_TOL_DEG = 1e-4

const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y })
const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y })
const mul = (a, k) => ({ x: a.x * k, y: a.y * k })
const dot = (a, b) => a.x * b.x + a.y * b.y
const unit = (a) => {
  const l = Math.hypot(a.x, a.y)
  return { x: a.x / l, y: a.y / l }
}

/** Valid panel-count range for a clear run `run` (L - allowances). */
export function panelCountRange(run, limits, joint) {
  // X <= max  <=>  N >= (run + P) / (max + P);   X >= min  <=>  N <= (run + P) / (min + P)
  const nMin = Math.max(1, Math.ceil((run + joint) / (limits.max + joint) - EPS))
  const nMax = Math.floor((run + joint) / (limits.min + joint) + EPS)
  return { nMin, nMax }
}

export function panelSize(run, count, joint) {
  return (run - (count - 1) * joint) / count
}

/**
 * Variable panel size with doors (PanelCalcs-4Season.dxf "WITH DOOR"):
 *   X = (run - D - N*P) / N,  N = variable panels, total panels = N + 1.
 * With doors = 0 this is panelSize(run, total, joint).
 */
export function panelSizeWithDoors(run, total, doors, doorWidth, joint) {
  return (run - doors * doorWidth - (total - 1) * joint) / (total - doors)
}

/** Stored option of panel k (0-based, left -> right seen from outside), defaults applied. */
export function panelOption(planWall, k, spec) {
  const e = planWall?.windows?.[k]
  const type = e?.type ?? spec.defaultPanelType
  return { type, transom: !!e?.transom && supportsTransom(type), stored: !!e }
}

/** Transom (3V) applies to window panels; doors get their header from the door rule; solid none. */
export function supportsTransom(type) {
  return type === 'fixed' || type === 'slider' || type === 'casement'
}

/** Intersection of the width limits of the given (non-door) panel types. */
export function combinedLimits(types, spec) {
  const uniq = [...new Set(types)]
  const ls = uniq.map((t) => spec.panelLimits[t])
  if (ls.some((l) => !l)) return null
  const label = uniq.map((t) => spec.panelLimits[t].label.replace(/ section$/, '').replace(/ full vertical panel$/, '')).join(' + ')
  return {
    min: Math.max(...ls.map((l) => l.min)),
    max: Math.min(...ls.map((l) => l.max)),
    label: uniq.length === 1 ? ls[0].label : `${label} width`,
    types: uniq,
  }
}

/** Stored size overrides of panel k (plan.walls[i].sizes[k]); null fields = supplier value. */
export function panelSizeOverride(planWall, k) {
  const e = planWall?.sizes?.[k]
  return { width: e?.width ?? null, kneeTop: e?.kneeTop ?? null, transomClear: e?.transomClear ?? null }
}

/**
 * Size a wall run for `total` panels with the given per-panel options.
 * `locks[k]` = locked opening width of panel k or null (doors are never locked: fixed size).
 * Without locks this is exactly the supplier formula (panelSizeWithDoors). With locks, the
 * unlocked panels share what the doors and locked panels leave:
 *   X = (run - D*doors - sum(locked) - (N-1)*P) / (N - doors - locked)
 * EXTENSION (user-requested, not in PanelCalcs, flagged on the wall): unequal panel widths.
 * @returns {{ ok: boolean, error?: string, X?: number|null, limits?: object, doors?: number }}
 */
function sizeRun(run, total, options, spec, locks = []) {
  const doors = options.filter((o) => o.type === 'door').length
  if (doors > 1) return { ok: false, doors, error: 'Only one door per wall: the supplier panel formula (PanelCalcs "WITH DOOR") has a single fixed door size.' }
  if (total - doors < 1) {
    return { ok: false, doors, error: `A door wall needs at least one other panel: the supplier formula sizes the other panels around the fixed ${spec.doorWidth}" door.` }
  }
  const lockedIdx = options.map((o, k) => (o.type !== 'door' && locks[k] != null ? k : -1)).filter((k) => k >= 0)
  if (!lockedIdx.length) {
    const limits = combinedLimits(options.filter((o) => o.type !== 'door').map((o) => o.type), spec)
    if (!limits) return { ok: false, doors, error: 'Unknown panel type.' }
    if (limits.min > limits.max + EPS) return { ok: false, doors, limits, error: `${limits.label}: the chosen panel types have no common width.` }
    const X = panelSizeWithDoors(run, total, doors, spec.doorWidth, spec.panelJoint)
    const fits = X >= limits.min - EPS && X <= limits.max + EPS
    return { ok: fits, doors, limits, X }
  }

  // locked panels: each within its own type's limits
  for (const k of lockedIdx) {
    const lim = spec.panelLimits[options[k].type]
    if (!lim) return { ok: false, doors, error: 'Unknown panel type.' }
    const v = locks[k]
    if (v < lim.min - EPS || v > lim.max + EPS) {
      return { ok: false, doors, error: `Panel ${k + 1} is locked at ${fmt(v)}; a ${lim.label.toLowerCase()} must be ${lim.min}"–${lim.max}".` }
    }
  }
  const free = options.filter((o, k) => o.type !== 'door' && !lockedIdx.includes(k))
  const left = run - doors * spec.doorWidth - lockedIdx.reduce((s, k) => s + locks[k], 0) - (total - 1) * spec.panelJoint
  if (!free.length) {
    if (Math.abs(left) > 1e-6) {
      return {
        ok: false, doors, X: null, limits: null,
        error: `Every panel is locked and the widths ${left > 0 ? `leave ${fmt(left)} unfilled` : `are ${fmt(-left)} too wide`}: unlock a panel or change a width so the wall closes.`,
      }
    }
    return { ok: true, doors, X: null, limits: null }
  }
  const limits = combinedLimits(free.map((o) => o.type), spec)
  if (!limits) return { ok: false, doors, error: 'Unknown panel type.' }
  if (limits.min > limits.max + EPS) return { ok: false, doors, limits, error: `${limits.label}: the unlocked panel types have no common width.` }
  const X = left / free.length
  const fits = X >= limits.min - EPS && X <= limits.max + EPS
  if (!fits) {
    return {
      ok: false, doors, limits, X,
      error: `With the locked widths, the ${free.length} unlocked panel${free.length > 1 ? 's get' : ' gets'} ${fmt(X)}; ${limits.label.toLowerCase()} must be ${limits.min}"–${limits.max}". Change a locked width or unlock a panel.`,
    }
  }
  return { ok: true, doors, limits, X }
}

/**
 * @returns {{ ok: boolean, errors: object[], warnings: object[], walls: object[], corners: object[], house: object|null, spec: object }}
 */
export function computeLayout(plan, spec) {
  const errors = []
  const warnings = []
  const n = plan.vertices.length
  const area = signedArea(plan)

  // ---- house wall & lean-to frame ---------------------------------------------------------
  const houseIdx = plan.walls.map((w, i) => (w.house ? i : -1)).filter((i) => i >= 0)
  if (houseIdx.length !== 1) {
    errors.push({ message: houseIdx.length ? 'Only one wall can be the house wall.' : 'Mark one wall as the house wall.' })
    return { ok: false, errors, warnings, walls: [], corners: [], house: null, spec }
  }
  const hi = houseIdx[0]
  const [h0, h1] = wallEndpoints(plan, hi)
  const ea = unit(sub(h1, h0))
  const nOut = outwardNormal(plan, hi)
  const eout = { x: -nOut.x, y: -nOut.y } // from the house into the room
  const distFromHouse = (p) => dot(sub(p, h0), eout)
  const along = (p) => dot(sub(p, h0), ea)
  let D = 0
  let amin = Infinity
  let amax = -Infinity
  for (const v of plan.vertices) {
    const d = distFromHouse(v)
    if (d < -1e-6) {
      errors.push({ message: 'Every corner must be on the room side of the house wall.' })
      return { ok: false, errors, warnings, walls: [], corners: [], house: null, spec }
    }
    D = Math.max(D, d)
    amin = Math.min(amin, along(v))
    amax = Math.max(amax, along(v))
  }
  // Heights. Default (plan.heights null): spec lowWallHeight at the front and spec roofSlope,
  // so the back height follows the depth. Explicit heights: both stored, the slope follows.
  const hs = plan.heights ?? {}
  const custom = hs.front != null || hs.back != null
  const frontHeight = hs.front ?? spec.lowWallHeight
  let slope = spec.roofSlope
  if (hs.back != null) {
    if (!(D > 0)) {
      errors.push({ message: 'Room depth is zero: the back height cannot be applied.' })
      return { ok: false, errors, warnings, walls: [], corners: [], house: null, spec }
    }
    slope = (hs.back - frontHeight) / D
  }
  if (!(slope > 0)) {
    errors.push({ message: 'Back height must be greater than the front height (the roof drains to the front gutter).' })
    return { ok: false, errors, warnings, walls: [], corners: [], house: null, spec }
  }
  if (custom && Math.abs(slope - spec.roofSlope) > 1e-9) {
    warnings.push({
      message: `Roof slope ${fmtNum(slope * 12)}" per foot differs from the supplier room model (${fmtNum(spec.roofSlope * 12)}" per foot). No slope or height limits are documented yet; confirm with the supplier.`,
    })
  }
  const heightAt = (p) => frontHeight + slope * (D - distFromHouse(p))
  const house = {
    index: hi, origin: h0, ea, eout, depth: D, amin, amax,
    frontHeight,
    slope,
    heightAtHouse: frontHeight + slope * D,
    customHeights: custom,
  }

  // ---- walls ------------------------------------------------------------------------------
  const walls = []
  for (let i = 0; i < n; i++) {
    if (i === hi) continue
    const [a, b] = wallEndpoints(plan, i)
    const nrm = outwardNormal(plan, i)
    const inward = { x: -nrm.x, y: -nrm.y }
    const right = { x: nrm.y, y: -nrm.x } // left->right seen from outside (forward x up)
    const u = unit(sub(b, a))
    const forward = dot(u, right) > 0 // traversal a->b runs left->right
    const leftPt = forward ? a : b
    const rightPt = forward ? b : a
    const leftVertex = forward ? i : (i + 1) % n
    const rightVertex = forward ? (i + 1) % n : i
    const L = wallLength(plan, i)

    const endKind = (vertex) => {
      // the other wall meeting at this vertex
      const other = vertex === i ? (i - 1 + n) % n : (i + 1) % n
      return { kind: other === hi ? 'house' : 'corner', vertex, otherWall: other }
    }
    const leftEnd = endKind(leftVertex)
    const rightEnd = endKind(rightVertex)
    const allowance = (e) => (e.kind === 'house' ? spec.wallAllowance : spec.cornerAllowance)
    const run = L - allowance(leftEnd) - allowance(rightEnd)

    const hLeft = heightAt(leftPt)
    const hRight = heightAt(rightPt)
    const slope = (hRight - hLeft) / L

    const wall = {
      index: i,
      length: L,
      origin: leftPt,
      end: rightPt,
      right,
      inward,
      leftEnd,
      rightEnd,
      topLeft: hLeft,
      topRight: hRight,
      slope,
      panelType: spec.defaultPanelType,
      limits: null,
      run,
      requested: plan.walls[i].panels ?? null,
      count: null,
      countRange: null,
      panelSize: null,
      doors: 0,
      openings: [],
      panels: [], // per opening: type, members (rails, receivers) — see below
      bottomChannelGaps: [], // [s0, s1] spans with no bottom channel (door openings)
      error: null,
      notes: [], // per-wall warnings, prefixed with the wall name once names are known
    }

    // Per-panel options (plan.walls[i].windows[k]); panels with nothing stored use the default type.
    const optsFor = (N) => Array.from({ length: N }, (_, k) => panelOption(plan.walls[i], k, spec))
    // Per-panel size overrides (plan.walls[i].sizes); locked widths take part in sizing.
    const sizesFor = (N) => Array.from({ length: N }, (_, k) => panelSizeOverride(plan.walls[i], k))
    const locksFor = (N) => sizesFor(N).map((z) => z.width)
    // Valid panel counts. With per-panel types and a fixed door the valid set depends on N, so
    // scan every count that could fit the smallest documented panel minimum.
    const minAll = Math.min(...Object.values(spec.panelLimits).map((l) => l.min))
    const nScanMax = run > 0 ? Math.floor((run + spec.panelJoint) / (minAll + spec.panelJoint) + EPS) + 1 : 0
    const valid = []
    for (let N = 1; N <= nScanMax; N++) if (sizeRun(run, N, optsFor(N), spec, locksFor(N)).ok) valid.push(N)
    wall.countRange = valid.length ? { nMin: valid[0], nMax: valid[valid.length - 1], counts: valid } : null
    const countsText = () =>
      !valid.length ? 'No panel count fits' : `Use ${valid.length === 1 ? valid[0] : valid.length === valid[valid.length - 1] - valid[0] + 1 ? `${valid[0]}–${valid[valid.length - 1]}` : valid.join(', ')} panels`

    const N = wall.requested ?? valid[0] ?? null
    if (N == null) {
      // auto and nothing fits: report the limits of the stored (or default) types
      const lim = combinedLimits(optsFor(1).map((o) => (o.type === 'door' ? spec.defaultPanelType : o.type)), spec)
      wall.limits = lim
      wall.error = `Wall is ${fmt(L)}: no panel count gives a ${lim.label.toLowerCase()} between ${lim.min}" and ${lim.max}".`
    } else {
      const opts = optsFor(N)
      const sizes = sizesFor(N)
      const r = sizeRun(run, N, opts, spec, sizes.map((z) => z.width))
      wall.count = N
      wall.doors = r.doors
      wall.limits = r.limits ?? combinedLimits([spec.defaultPanelType], spec)
      if (r.error) wall.error = r.error
      else {
        wall.panelSize = r.X
        if (!r.ok) {
          const lim = r.limits
          wall.error = `${N} panel${N > 1 ? 's' : ''} gives ${fmt(r.X)}; ${lim.label.toLowerCase()} must be ${lim.min}"–${lim.max}". ${countsText()}.`
        } else {
          let s = allowance(leftEnd)
          for (let k = 0; k < N; k++) {
            const w = opts[k].type === 'door' ? spec.doorWidth : sizes[k].width ?? r.X
            wall.openings.push([s, s + w])
            s += w + spec.panelJoint
          }
          wall.panels = wall.openings.map(([o0, o1], k) => panelMembers(wall, o0, o1, k, opts[k], N, spec, errors, sizes[k]))
          // unequal widths are a user extension of the supplier formula: flag them
          const lockedK = sizes.map((z, k) => (z.width != null && opts[k].type !== 'door' ? k + 1 : null)).filter((k) => k != null)
          if (lockedK.length) {
            wall.notes.push(
              `panel${lockedK.length > 1 ? 's' : ''} ${lockedK.join(', ')} ${lockedK.length > 1 ? 'have' : 'has'} a locked width; the supplier panel formula (PanelCalcs) gives equal panels. Unequal panel widths are not a supplier standard; confirm with the supplier.`,
            )
          }
          const doorLocked = sizes.map((z, k) => (z.width != null && opts[k].type === 'door' ? k + 1 : null)).filter((k) => k != null)
          if (doorLocked.length) wall.notes.push(`panel ${doorLocked.join(', ')}: the stored width is not used; a door is the fixed ${spec.doorWidth}" size.`)
          wall.bottomChannelGaps = wall.panels.filter((p) => p.door).map((p) => [p.s0, p.s1])
        }
      }
    }
    // stored options that the current count does not reach are kept but reported
    const unused = (plan.walls[i].windows ?? []).map((e, k) => (e && k >= (wall.count ?? 0) ? k + 1 : null)).filter((k) => k != null)
    if (unused.length) wall.notes.push(`options stored for panel ${unused.join(', ')} are not used (the wall has ${wall.count ?? 0} panels).`)
    const unusedSizes = (plan.walls[i].sizes ?? []).map((e, k) => (e && k >= (wall.count ?? 0) ? k + 1 : null)).filter((k) => k != null)
    if (unusedSizes.length) wall.notes.push(`sizes stored for panel ${unusedSizes.join(', ')} are not used (the wall has ${wall.count ?? 0} panels).`)
    if (wall.error) errors.push({ wall: i, message: wall.error })
    walls.push(wall)
  }

  // ---- corners (two sunroom walls meet) -----------------------------------------------------
  const corners = []
  for (let v = 0; v < n; v++) {
    const wIn = (v - 1 + n) % n
    const wOut = v
    if (wIn === hi || wOut === hi) {
      // house end: the house wall must meet the sunroom wall square (wall channel sits flat on it)
      const ang = interiorAngle(plan, v)
      if (Math.abs(ang - 90) > ANGLE_TOL_DEG) {
        errors.push({ vertex: v, message: `House connection at ${fmtAngle(ang)}: only 90° is supported (wall channel data is for square connections).` })
      }
      continue
    }
    const ang = interiorAngle(plan, v)
    // wall whose outside-left end is this vertex
    const wb = walls.find((w) => w.leftEnd.vertex === v)
    const wa = walls.find((w) => w.rightEnd.vertex === v)
    const corner = { vertex: v, point: plan.vertices[v], angle: ang, wallLeft: wa?.index, wallRight: wb?.index, supported: true }
    if (Math.abs(ang - 90) > ANGLE_TOL_DEG) {
      corner.supported = false
      const message =
        Math.abs(ang - 270) <= ANGLE_TOL_DEG
          ? 'Inside corner (270°): the 4-Season profile set has no inside corner post or panel allowance for it yet (supplier drawings mark it "? INSIDE OUTSIDE CORNER POST"). The two walls meeting here are not built.'
          : `Corner at ${fmtAngle(ang)}: only 90° corner posts are available for this system. The two walls meeting here are not built.`
      errors.push({ vertex: v, message })
    }
    corners.push(corner)
  }

  // Names as seen by someone standing outside, facing the house.
  const viewerRight = { x: eout.y, y: -eout.x }
  const used = {}
  // number duplicates left -> right as seen from the front
  const midAlong = (w) => dot({ x: (w.origin.x + w.end.x) / 2, y: (w.origin.y + w.end.y) / 2 }, viewerRight)
  for (const w of [...walls].sort((p, q) => midAlong(p) - midAlong(q))) {
    const nrm = { x: -w.inward.x, y: -w.inward.y }
    const f = dot(nrm, eout)
    const r = dot(nrm, viewerRight)
    let name
    if (f > 0.7071) name = 'Front'
    else if (r > 0.7071) name = 'Right'
    else if (r < -0.7071) name = 'Left'
    else if (f < -0.7071) name = 'Back'
    else name = r > 0 ? 'Front right' : 'Front left'
    used[name] = (used[name] ?? 0) + 1
    w.name = name
    w.nameIndex = used[name]
  }
  for (const w of walls) if (used[w.name] > 1) w.name = `${w.name} ${w.nameIndex}`
  for (const w of walls) for (const m of w.notes) warnings.push({ wall: w.index, message: `${w.name} wall: ${m}` })

  // A wall can only be built if both of its ends are buildable.
  const badVertex = new Set(errors.filter((e) => e.vertex != null).map((e) => e.vertex))
  for (const w of walls) {
    w.buildable = !w.error && !badVertex.has(w.leftEnd.vertex) && !badVertex.has(w.rightEnd.vertex)
  }

  return { ok: errors.length === 0, errors, warnings, walls, corners, house, spec, area, planRef: plan }
}

function fmt(inches) {
  return `${Math.round(inches * 1000) / 1000}"`
}
function fmtNum(v) {
  return String(Math.round(v * 1000) / 1000)
}
function fmtAngle(deg) {
  return `${Math.round(deg * 100) / 100}°`
}

/**
 * Frame members of one panel (numeric, wall-local; z absolute above the channel underside).
 * Sources: panel_builder.py + build_mf*.py (2V knee rail, 3V transom, door / raked door header).
 *   rails[].bodyTop  top of the T04 body (rails are level), fits = false when it collides.
 */
function panelMembers(wall, o0, o1, k, opt, N, spec, errors, size = { width: null, kneeTop: null, transomClear: null }) {
  const fin = spec.finHeight
  const Z0 = spec.seatBottom
  const door = opt.type === 'door'
  const raked = Math.abs(wall.slope) > 1e-9
  const stretch = Math.sqrt(1 + wall.slope * wall.slope)
  // top receiver (T02) fin tip: leg tips on the seat line, body + fin below it, measured vertically
  const topFinAt = (s) => panelTopAt(wall, s, spec) - (spec.maleBody + fin) * stretch
  // reference fin for transom / header clearance: the opening's fin on the panel's low side
  const fallsRight = wall.slope < -1e-9
  const sRef = fallsRight ? o1 - fin : o0 + fin
  const refTopFin = topFinAt(sRef)

  // Rail heights: supplier values unless the panel stores an override (plan.walls[i].sizes[k]).
  // EXTENSION (user-requested): overrides are not supplier standard heights and are flagged below;
  // only the fit check further down limits them (no supplier min/max exists yet).
  const kneeTop = size.kneeTop ?? spec.kneeRailTopAbovePanelBottom
  const transomClear = size.transomClear ?? spec.transomClearFin
  const hasKnee = !door && opt.type !== 'solid'
  const rails = []
  if (hasKnee) rails.push({ name: 'knee', bodyTop: Z0 + kneeTop, custom: size.kneeTop != null })
  if (opt.transom) rails.push({ name: 'transom', bodyTop: refTopFin - transomClear - fin, custom: size.transomClear != null })
  if (door && raked) rails.push({ name: 'door-header', bodyTop: refTopFin - spec.doorHeaderClearFin - fin })

  const panel = {
    index: k,
    number: k + 1,
    s0: o0,
    s1: o1,
    width: o1 - o0,
    type: opt.type,
    transom: opt.transom,
    door,
    left: 'T02',
    right: k === N - 1 ? 'T02' : 'T03', // last panel of a run is M-M
    bottomReceiver: !door, // M-F-1Door / M-F-2DoorTrap: include_bottom=False
    rails,
    locked: size.width != null && !door,
    kneeTop: hasKnee ? kneeTop : null, // top of knee rail body above the panel bottom
    transomClear: opt.transom ? transomClear : null, // transom fin-to-fin clearance below the top
    errors: [],
  }
  if (size.kneeTop != null) {
    wall.notes.push(
      hasKnee
        ? `panel ${k + 1}: knee rail at ${fmt(kneeTop)} above the panel bottom (supplier standard ${fmt(spec.kneeRailTopAbovePanelBottom)}); not a supplier standard height, confirm with the supplier.`
        : `panel ${k + 1}: the stored knee rail height is not used (a ${door ? 'door' : 'solid panel'} has no knee rail).`,
    )
  }
  if (size.transomClear != null) {
    wall.notes.push(
      opt.transom
        ? `panel ${k + 1}: transom ${fmt(transomClear)} below the top (supplier standard ${fmt(spec.transomClearFin)} fin to fin); not a supplier standard height, confirm with the supplier.`
        : `panel ${k + 1}: the stored transom clearance is not used (the panel has no transom).`,
    )
  }

  // Fit check bottom -> top: each rail's bottom fin must clear what is below it, and the last
  // member's top fin must stay under the top receiver's fin across the whole opening.
  const railName = { knee: 'knee rail', transom: 'transom rail', 'door-header': 'door header' }
  let below = door ? Z0 : Z0 + spec.maleBody + fin // bottom receiver fin tip
  let belowName = door ? 'the floor' : 'the bottom receiver'
  const topMin = Math.min(topFinAt(o0 + fin), topFinAt(o1 - fin))
  for (const r of rails) {
    const bottomFin = r.bodyTop - spec.railBodyTop
    const topFin = r.bodyTop + fin
    r.fits = bottomFin > below + EPS && topFin < topMin - EPS
    if (!r.fits) {
      const msg = `Panel ${k + 1}: the ${railName[r.name]} does not fit between ${belowName} and the top receiver (panel too short).`
      panel.errors.push(msg)
      errors.push({ wall: wall.index, panel: k + 1, message: msg })
    } else {
      below = topFin
      belowName = `the ${railName[r.name]}`
    }
  }

  if (door && !raked) {
    const h = panelTopAt(wall, o0, spec) - Z0
    if (Math.abs(h - spec.doorFrameHeight) > 1e-6) {
      wall.notes.push(
        `panel ${k + 1} (door): the supplier door frame (M-F-1Door) is ${spec.doorFrameHeight}" tall with no header; this panel is ${fmt(h)} tall. The door height and header for other heights are not documented; confirm with the supplier.`,
      )
    }
  }
  if (fallsRight && (opt.transom || (door && raked))) {
    wall.notes.push(
      `panel ${k + 1}: ${door ? 'door header' : 'transom'} clearance is measured at the low (right) side. The supplier builders only show panels rising to the right; confirm for this hand.`,
    )
  }
  return panel
}

/** Seat line under the top channel (where the top receiver's leg tips sit) at wall-local s. */
export function panelTopAt(wall, s, spec) {
  return wallTopAt(wall, s) - spec.seatTop * Math.sqrt(1 + wall.slope * wall.slope)
}

/** Plan point at wall-local (s, d). */
export function wallPoint(wall, s, d = 0) {
  return add(add(wall.origin, mul(wall.right, s)), mul(wall.inward, d))
}

/** Top-of-top-channel height at wall-local s (exterior line). */
export function wallTopAt(wall, s) {
  return wall.topLeft + wall.slope * s
}
