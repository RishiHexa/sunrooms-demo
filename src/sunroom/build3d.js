/**
 * 3D sunroom builder (visual only). Consumes the numeric layout from layout.js and the
 * supplier cross-sections; produces a THREE.Group. Nothing here feeds back into sizing.
 *
 * World: X = plan x, Z = plan y, Y = up. 1 unit = 1 inch.
 */
import * as THREE from 'three'
import { panelTopAt, wallPoint, wallTopAt } from './layout.js'

// VISUAL ONLY — infill placeholders. No GF50 glass stop, sash, slider, casement or door-leaf
// profiles are in the supplier files, so these sizes are display choices, not product data.
const VIS = {
  glassThickness: 0.75,
  glassDepth: 2.245, // centre of the glass in the wall depth (middle of the T02/T03 depth)
  sashWidth: 1.75, // sash frame face width
  sashDepth: 1.0,
  doorStile: 3.0,
  sliderOverlap: 1.0,
  handle: [0.6, 5, 1.2], // width, height, projection
}

// ---------------------------------------------------------------------------
// Section preparation (2D loops -> triangulated contours), cached per key
// ---------------------------------------------------------------------------
const ARC_STEP = Math.PI / 16

function arcPoints(a, m, b) {
  // circle through 3 points
  const ax = a[0], ay = a[1], bx = m[0], by = m[1], cx = b[0], cy = b[1]
  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
  if (Math.abs(d) < 1e-12) return [a] // collinear: treat as a line
  const ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
  const uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
  const r = Math.hypot(ax - ux, ay - uy)
  const t0 = Math.atan2(ay - uy, ax - ux)
  const tm = Math.atan2(by - uy, bx - ux)
  const t1 = Math.atan2(cy - uy, cx - ux)
  const norm = (t) => ((t % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)
  // sweep from t0 to t1 in the direction that passes through tm
  let sweep = norm(t1 - t0)
  if (norm(tm - t0) > sweep) sweep = sweep - 2 * Math.PI
  const steps = Math.max(2, Math.ceil(Math.abs(sweep) / ARC_STEP))
  const pts = []
  for (let i = 0; i < steps; i++) {
    const t = t0 + (sweep * i) / steps
    pts.push([ux + r * Math.cos(t), uy + r * Math.sin(t)])
  }
  return pts
}

function loopPoints(loop) {
  const pts = []
  for (const s of loop.segs) {
    if (s[0] === 'arc') pts.push(...arcPoints(s[1], s[2], s[3]))
    else pts.push(s[1])
  }
  // drop consecutive duplicates (incl. closing point)
  const out = []
  for (const p of pts) {
    const q = out[out.length - 1]
    if (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > 1e-7) out.push(p)
  }
  if (out.length > 2 && Math.hypot(out[0][0] - out[out.length - 1][0], out[0][1] - out[out.length - 1][1]) < 1e-7) out.pop()
  return out
}

const area2 = (pts) => {
  let s = 0
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i]
    const b = pts[(i + 1) % pts.length]
    s += a[0] * b[1] - b[0] * a[1]
  }
  return s / 2
}

function pointInPoly(pt, poly) {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]
    const [xj, yj] = poly[j]
    if (yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** loops: [{depth, segs}] -> [{contours: [outer, ...holes], faces}] with outer CCW, holes CW. */
function prepareSection(loops) {
  const items = loops.map((L) => ({ depth: L.depth, pts: loopPoints(L) })).filter((l) => l.pts.length >= 3)
  const groups = []
  for (const outer of items.filter((l) => l.depth % 2 === 0)) {
    const holes = items.filter((h) => h.depth === outer.depth + 1 && pointInPoly(h.pts[0], outer.pts))
    const o = area2(outer.pts) < 0 ? [...outer.pts].reverse() : outer.pts
    const hs = holes.map((h) => (area2(h.pts) > 0 ? [...h.pts].reverse() : h.pts))
    const faces = THREE.ShapeUtils.triangulateShape(
      o.map((p) => new THREE.Vector2(p[0], p[1])),
      hs.map((h) => h.map((p) => new THREE.Vector2(p[0], p[1]))),
    )
    groups.push({ contours: [o, ...hs], faces })
  }
  return groups
}

const sectionCache = new Map()
function section(key, loops, mirrorU = false) {
  const k = mirrorU ? key + ':mirror' : key
  if (!sectionCache.has(k)) {
    const src = mirrorU
      ? loops.map((L) => ({ depth: L.depth, segs: L.segs.map((s) => [s[0], ...s.slice(1).map((p) => [-p[0], p[1]])]) }))
      : loops
    sectionCache.set(k, prepareSection(src))
  }
  return sectionCache.get(k)
}

/** Section given directly as one polygon [[u,v],...] (roof slabs, wedge). */
function polySection(poly) {
  return prepareSection([{ depth: 0, segs: poly.map((p, i) => ['line', p, poly[(i + 1) % poly.length]]) }])
}

// ---------------------------------------------------------------------------
// Prism builder: section (u,v) -> origin + u*ex + v*ey, extruded `length` along ez.
// Optional cut planes {point, normal} replace the start/end caps by projecting the cap
// vertices along ez onto the plane (exact for planar cuts).
// ---------------------------------------------------------------------------
const tmp = new THREE.Vector3()
function prism(groups, { origin, ex, ey, ez, length, startCut = null, endCut = null }) {
  const det = new THREE.Vector3().crossVectors(ex, ey).dot(ez)
  const flip = det < 0
  const pos = []
  const project = (p, cut) => {
    if (!cut) return p
    const denom = ez.dot(cut.normal)
    if (Math.abs(denom) < 1e-9) return p
    const t = tmp.copy(cut.point).sub(p).dot(cut.normal) / denom
    return p.addScaledVector(ez, t)
  }
  const pushTri = (a, b, c) => {
    if (flip) pos.push(a.x, a.y, a.z, c.x, c.y, c.z, b.x, b.y, b.z)
    else pos.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z)
  }
  for (const g of groups) {
    const flat = g.contours.flat()
    const start = flat.map(([u, v]) => project(origin.clone().addScaledVector(ex, u).addScaledVector(ey, v), startCut))
    const end = flat.map(([u, v]) =>
      project(origin.clone().addScaledVector(ex, u).addScaledVector(ey, v).addScaledVector(ez, length), endCut),
    )
    for (const [i, j, k] of g.faces) {
      const a = flat[i], b = flat[j], c = flat[k]
      const ccw = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0
      if (ccw) {
        pushTri(end[i], end[j], end[k])
        pushTri(start[i], start[k], start[j])
      } else {
        pushTri(end[i], end[k], end[j])
        pushTri(start[i], start[j], start[k])
      }
    }
    let base = 0
    for (const c of g.contours) {
      for (let m = 0; m < c.length; m++) {
        const p = base + m
        const q = base + ((m + 1) % c.length)
        pushTri(start[p], start[q], end[q])
        pushTri(start[p], end[q], end[p])
      }
      base += c.length
    }
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
  geo.computeVertexNormals()
  return geo
}

// ---------------------------------------------------------------------------
// Materials
// ---------------------------------------------------------------------------
function makeMaterials() {
  return {
    aluminum: new THREE.MeshStandardMaterial({ color: 0xf1f2f0, metalness: 0.25, roughness: 0.5 }),
    channel: new THREE.MeshStandardMaterial({ color: 0xe6e8e6, metalness: 0.25, roughness: 0.5 }),
    roofSkin: new THREE.MeshStandardMaterial({ color: 0xf7f7f5, metalness: 0.1, roughness: 0.6 }),
    roofFoam: new THREE.MeshStandardMaterial({ color: 0xe9e2c4, roughness: 0.9 }),
    wood: new THREE.MeshStandardMaterial({ color: 0x9a6b3f, roughness: 0.8 }),
    glass: new THREE.MeshPhysicalMaterial({
      color: 0xbfd9e6, metalness: 0, roughness: 0.05, transparent: true, opacity: 0.28, depthWrite: false, side: THREE.DoubleSide,
    }),
    sash: new THREE.MeshStandardMaterial({ color: 0xdfe2e0, metalness: 0.25, roughness: 0.45 }),
    solidPanel: new THREE.MeshStandardMaterial({ color: 0xf4f4f1, roughness: 0.7 }),
    handle: new THREE.MeshStandardMaterial({ color: 0x3a3d40, metalness: 0.5, roughness: 0.4 }),
    house: new THREE.MeshStandardMaterial({ color: 0xc9c4bb, roughness: 0.95 }),
  }
}

// ---------------------------------------------------------------------------
// Builder
// ---------------------------------------------------------------------------
const v3 = (p, z) => new THREE.Vector3(p.x, z, p.y)
const dir3 = (d) => new THREE.Vector3(d.x, 0, d.y)
const UP = new THREE.Vector3(0, 1, 0)

/**
 * @param layout result of computeLayout
 * @param sections SECTIONS_4SEASON
 * @returns {{ group: THREE.Group, notes: string[] }}
 */
export function buildSunroom(layout, sections) {
  const spec = layout.spec
  const mats = makeMaterials()
  const group = new THREE.Group()
  group.name = 'sunroom'
  const notes = []

  const mesh = (geo, mat, name, userData = {}) => {
    const m = new THREE.Mesh(geo, mat)
    m.name = name
    m.castShadow = true
    m.receiveShadow = true
    m.userData = userData
    return m
  }

  const Z0 = spec.seatBottom
  const plan = layout.planRef

  // Cut planes at each wall end ---------------------------------------------------------
  function endPlane(wall, which) {
    const end = which === 'left' ? wall.leftEnd : wall.rightEnd
    if (end.kind === 'house') {
      const h = layout.house
      // plane along the house wall line
      const n = { x: -h.eout.x, y: -h.eout.y }
      return { point: v3(h.origin, 0), normal: dir3(n) }
    }
    // mitre: vertical plane through the corner along the interior bisector
    const V = plan.vertices[end.vertex]
    const n = plan.vertices.length
    const P = plan.vertices[(end.vertex - 1 + n) % n]
    const N = plan.vertices[(end.vertex + 1) % n]
    const u1 = norm2({ x: P.x - V.x, y: P.y - V.y })
    const u2 = norm2({ x: N.x - V.x, y: N.y - V.y })
    const b = norm2({ x: u1.x + u2.x, y: u1.y + u2.y })
    return { point: v3(V, 0), normal: dir3({ x: -b.y, y: b.x }) }
  }

  // Top cut plane for vertical members of a wall: parallel to the run slope, level across depth.
  function topSeatPlane(wall) {
    const k = wall.slope
    const z0 = wall.topLeft - spec.seatTop * Math.sqrt(1 + k * k)
    const r3 = dir3(wall.right)
    return { point: v3(wall.origin, z0), normal: UP.clone().addScaledVector(r3, -k) }
  }
  const seatTopAt = (wall, s) => panelTopAt(wall, s, spec)

  for (const wall of layout.walls) {
    if (!wall.buildable) continue
    const wg = new THREE.Group()
    wg.name = `wall-${wall.index}`
    const r3 = dir3(wall.right)
    const in3 = dir3(wall.inward)
    const k = wall.slope
    const t = r3.clone().addScaledVector(UP, k).normalize()
    const upPerp = UP.clone().addScaledVector(r3, -k).normalize()
    const stretch = Math.sqrt(1 + k * k)
    const at = (s, z) => v3(wallPoint(wall, s, 0), z)
    const topPlane = topSeatPlane(wall)
    const vertLen = Math.max(wall.topLeft, wall.topRight) + 10 - Z0
    const leftCut = endPlane(wall, 'left')
    const rightCut = endPlane(wall, 'right')
    const EXT = 8 // extrude past the ends, then cut

    // channels --------------------------------------------------------------------------
    // bottom channel, removed across door openings (members4.py DOORS: cut body face to body face)
    {
      const cuts = [[-EXT, leftCut], ...wall.bottomChannelGaps.flatMap(([g0, g1]) => [[g0, null], [g1, null]]), [wall.length + EXT, rightCut]]
      for (let j = 0; j < cuts.length; j += 2) {
        const [a, aCut] = cuts[j]
        const [b, bCut] = cuts[j + 1]
        if (b - a < 1e-6) continue
        wg.add(
          mesh(
            prism(section('channelBottom', sections.channelBottom.loops), {
              origin: at(a, 0), ex: in3, ey: UP, ez: r3, length: b - a, startCut: aCut, endCut: bCut,
            }),
            mats.channel, 'bottom-channel', { part: 'T05' },
          ),
        )
      }
    }
    wg.add(
      mesh(
        prism(section('channelTop', sections.channelTop.loops), {
          origin: at(-EXT, wallTopAt(wall, -EXT)), ex: in3, ey: upPerp, ez: t, length: (wall.length + 2 * EXT) * stretch,
          startCut: leftCut, endCut: rightCut,
        }),
        mats.channel, 'top-channel', { part: 'T05' },
      ),
    )

    // panels -----------------------------------------------------------------------------
    // Members come from layout (wall.panels): receivers, rails, hand. Infill is visual only.
    for (const p of wall.panels) {
      const idx = p.index
      const o0 = p.s0
      const o1 = p.s1
      const ud = (part, extra = {}) => ({ part, panel: p.number, panelType: p.type, ...extra })
      const vertical = (key, loops, mirror, s, part, name) =>
        wg.add(
          mesh(
            prism(section(key, loops, mirror), { origin: at(s, Z0), ex: r3, ey: in3, ez: UP, length: vertLen, endCut: topPlane }),
            mats.aluminum, name, ud(part),
          ),
        )
      vertical('maleLeft', sections.maleLeft.loops, false, o0 - spec.maleBody, 'T02', `p${idx + 1}-left-male`)
      if (p.right === 'T02') vertical('maleLeft', sections.maleLeft.loops, true, o1 + spec.maleBody, 'T02', `p${idx + 1}-right-male`)
      else vertical('femaleRight', sections.femaleRight.loops, false, o1 + spec.femaleBody, 'T03', `p${idx + 1}-right-female`)

      // bottom receiver (level, on the bottom seat) — none on a door
      if (p.bottomReceiver) {
        wg.add(
          mesh(
            prism(section('receiverBottom', sections.receiverBottom.loops), { origin: at(o0, Z0), ex: in3, ey: UP, ez: r3, length: o1 - o0 }),
            mats.aluminum, `p${idx + 1}-receiver-bottom`, ud('T02'),
          ),
        )
      }
      // top receiver (follows the rake, leg tips on the top seat line, cut square at the openings)
      wg.add(
        mesh(
          prism(section('receiverTop', sections.receiverTop.loops), {
            origin: at(o0 - 1, seatTopAt(wall, o0 - 1)), ex: in3, ey: upPerp, ez: t, length: (o1 - o0 + 2) * stretch,
            startCut: { point: at(o0, 0), normal: r3 }, endCut: { point: at(o1, 0), normal: r3 },
          }),
          mats.aluminum, `p${idx + 1}-receiver-top`, ud('T02'),
        ),
      )
      // rails (level), positions from the layout
      for (const r of p.rails) {
        if (!r.fits) continue // reported as a layout error
        wg.add(
          mesh(
            prism(section('rail', sections.rail.loops), { origin: at(o0, r.bodyTop - spec.railBodyTop), ex: in3, ey: UP, ez: r3, length: o1 - o0 }),
            mats.aluminum, `p${idx + 1}-${r.name}-rail`, ud('T04', { rail: r.name }),
          ),
        )
      }
      addInfill(wg, wall, p, { at, r3, in3, stretch, Z0, seatTopAt, spec, mats, mesh, ud })
    }

    // house end: wall channel ----------------------------------------------------------------
    for (const which of ['left', 'right']) {
      const end = which === 'left' ? wall.leftEnd : wall.rightEnd
      if (end.kind !== 'house') continue
      const s = which === 'left' ? 0 : wall.length
      wg.add(
        mesh(
          prism(section('wallChannelRight', sections.wallChannelRight.loops, which === 'left'), {
            origin: at(s, Z0), ex: r3, ey: in3, ez: UP, length: vertLen, endCut: topPlane,
          }),
          mats.aluminum, `wall-channel-${which}`, { part: 'T01' },
        ),
      )
    }
    group.add(wg)
  }

  // corners ------------------------------------------------------------------------------------
  for (const c of layout.corners) {
    if (!c.supported) continue
    const wb = layout.walls.find((w) => w.index === c.wallRight)
    const wa = layout.walls.find((w) => w.index === c.wallLeft)
    if (!wb?.buildable || !wa?.buildable) continue
    const top = Math.min(seatTopAt(wb, 0), seatTopAt(wa, wa.length))
    const frame = { origin: v3(c.point, Z0), ex: dir3(wb.right), ey: dir3(wb.inward), ez: UP, length: top - Z0 }
    const cg = new THREE.Group()
    cg.name = `corner-${c.vertex}`
    cg.add(mesh(prism(section('cornerPost', sections.cornerPost.loops), frame), mats.aluminum, 'corner-post', { part: 'CornerPost' }))
    cg.add(mesh(prism(section('insideCorner', sections.insideCorner.loops), frame), mats.aluminum, 'inside-corner', { part: 'InsideCorner' }))
    group.add(cg)
  }

  if (layout.walls.some((w) => w.buildable && w.panels.length)) {
    notes.push('Glass, sashes, solid infill and door leaves are visual placeholders: the supplier files have no GF50 glazing, sash, slider, casement or door profiles.')
  }

  // roof ----------------------------------------------------------------------------------------
  if (layout.ok) group.add(buildRoof(layout, sections, mats, mesh, notes))
  else notes.push('Roof is not built until every wall and corner is valid.')

  // house wall context (visual only)
  group.add(buildHouseContext(layout, mats))

  return { group, notes, materials: mats }
}

/**
 * Visual infill of one panel: glass in every lite, plus a stand-in sash (slider / casement),
 * door leaf or solid panel in the main lite. Lite edges are the fin tips of the frame members
 * from the layout; nothing here is product data. userData.visual marks these meshes.
 */
function addInfill(wg, wall, p, ctx) {
  const { at, r3, in3, stretch, Z0, seatTopAt, spec, mats, mesh, ud } = ctx
  const fin = spec.finHeight
  const a = p.s0
  const b = p.s1
  const topFin = (s) => seatTopAt(wall, s) - (spec.maleBody + fin) * stretch
  // lites bottom -> top, bounded by member fin tips; a door lite starts at the floor
  const rails = p.rails.filter((r) => r.fits)
  const edges = [p.bottomReceiver ? Z0 + spec.maleBody + fin : 0]
  for (const r of rails) edges.push(r.bodyTop - spec.railBodyTop, r.bodyTop + fin)
  const lites = []
  for (let j = 0; j < edges.length; j += 2) {
    const z0 = edges[j]
    const zt = j + 1 < edges.length ? edges[j + 1] : null
    lites.push({ z0, top: zt == null ? topFin : () => zt })
  }
  // main lite: the one above the knee rail; on a door the lowest one (the door itself)
  const main = !p.door && rails.some((r) => r.name === 'knee') ? 1 : 0

  const quad = (s0, s1, z0, zTop) => [[s0, z0], [s1, z0], [s1, zTop(s1)], [s0, zTop(s0)]]
  const place = (groups, depth, thick, mat, name, extra) => {
    const m = mesh(prism(groups, { origin: at(0, 0).addScaledVector(in3, depth - thick / 2), ex: r3, ey: UP, ez: in3, length: thick }),
      mat, name, ud(extra.part, { visual: true, ...extra }))
    if (mat === mats.glass) m.castShadow = false
    wg.add(m)
  }
  const face = (s0, s1, z0, zTop, depth, thick, mat, name, extra) => {
    const q = quad(s0, s1, z0, zTop)
    if (q[2][1] - z0 < 0.05 || q[3][1] - z0 < 0.05 || s1 - s0 < 0.05) return
    place(polySection(q), depth, thick, mat, name, extra)
  }
  const ring = (s0, s1, z0, zTop, w, depth, thick, mat, name, extra) => {
    const outer = quad(s0, s1, z0, zTop)
    const inner = [[s0 + w, z0 + w], [s1 - w, z0 + w], [s1 - w, zTop(s1 - w) - w * stretch], [s0 + w, zTop(s0 + w) - w * stretch]]
    if (inner[2][1] - inner[1][1] < 0.5 || inner[3][1] - inner[0][1] < 0.5 || s1 - s0 < 2 * w + 0.5) return
    const loop = (pts, depthIdx) => ({ depth: depthIdx, segs: pts.map((q, i) => ['line', q, pts[(i + 1) % pts.length]]) })
    place(prepareSection([loop(outer, 0), loop(inner, 1)]), depth, thick, mat, name, extra)
  }
  const handle = (s, z, depthFace, name) => {
    const [hw, hh, hp] = VIS.handle
    face(s - hw / 2, s + hw / 2, z, () => z + hh, depthFace + hp / 2, hp, mats.handle, name, { part: 'handle' })
  }

  const n = p.number
  const gd = VIS.glassDepth
  const thin = VIS.glassThickness * 0.5
  lites.forEach((L, j) => {
    const isMain = j === main
    if (p.type === 'solid') {
      face(a, b, L.z0, L.top, gd, VIS.glassThickness, mats.solidPanel, `p${n}-solid-infill`, { part: 'solid-infill' })
    } else if (isMain && p.door) {
      // door leaf stand-in: stile ring + glass, handle on the latch (right) side
      const dd = VIS.sashDepth + 0.5
      ring(a, b, L.z0, L.top, VIS.doorStile, gd, dd, mats.sash, `p${n}-door-leaf`, { part: 'door-leaf' })
      face(a, b, L.z0, L.top, gd, thin, mats.glass, `p${n}-glass-${j + 1}`, { part: 'glass' })
      handle(b - VIS.doorStile / 2, L.z0 + 36, gd - dd / 2 - VIS.handle[2], `p${n}-door-handle`)
    } else if (isMain && p.type === 'slider') {
      const mid = (a + b) / 2
      const ov = VIS.sliderOverlap / 2
      const d1 = gd - 0.6
      const d2 = gd + 0.6
      ring(a, mid + ov, L.z0, L.top, VIS.sashWidth, d1, VIS.sashDepth, mats.sash, `p${n}-sash-left`, { part: 'sash' })
      ring(mid - ov, b, L.z0, L.top, VIS.sashWidth, d2, VIS.sashDepth, mats.sash, `p${n}-sash-right`, { part: 'sash' })
      face(a, mid + ov, L.z0, L.top, d1, thin, mats.glass, `p${n}-glass-${j + 1}a`, { part: 'glass' })
      face(mid - ov, b, L.z0, L.top, d2, thin, mats.glass, `p${n}-glass-${j + 1}b`, { part: 'glass' })
    } else if (isMain && p.type === 'casement') {
      ring(a, b, L.z0, L.top, VIS.sashWidth, gd, VIS.sashDepth, mats.sash, `p${n}-sash`, { part: 'sash' })
      face(a, b, L.z0, L.top, gd, thin, mats.glass, `p${n}-glass-${j + 1}`, { part: 'glass' })
      const zMid = (L.z0 + Math.min(L.top(a), L.top(b))) / 2
      handle(b - VIS.sashWidth / 2, zMid - VIS.handle[1] / 2, gd - VIS.sashDepth / 2 - VIS.handle[2], `p${n}-sash-handle`)
    } else {
      face(a, b, L.z0, L.top, gd, VIS.glassThickness, mats.glass, `p${n}-glass-${j + 1}`, { part: 'glass' })
    }
  })
}

function norm2(a) {
  const l = Math.hypot(a.x, a.y)
  return { x: a.x / l, y: a.y / l }
}

function buildRoof(layout, sections, mats, mesh, notes) {
  const spec = layout.spec
  const h = layout.house
  const rg = new THREE.Group()
  rg.name = 'roof'
  // slope / front height come from the layout (spec defaults, or the entered room heights)
  const TAN = h.slope
  const COS = 1 / Math.sqrt(1 + TAN * TAN)
  const SIN = TAN * COS
  const D = h.depth
  const H_LOW = h.frontHeight
  const ea3 = dir3(h.ea)
  const towardHouse = dir3({ x: -h.eout.x, y: -h.eout.y }) // +Y of the lean-to frame
  // lean-to frame (a, Y, Z) -> world
  const P = (a, Y, Z) => {
    const p = { x: h.origin.x + h.ea.x * a + h.eout.x * (D - Y), y: h.origin.y + h.ea.y * a + h.eout.y * (D - Y) }
    return v3(p, Z)
  }
  const X0 = h.amin - spec.roofOverhangSide
  const X1 = h.amax + spec.roofOverhangSide
  const W = X1 - X0
  const t2w = towardHouse.clone().multiplyScalar(COS).addScaledVector(UP, SIN) // up the slope
  const n2w = towardHouse.clone().multiplyScalar(-SIN).addScaledVector(UP, COS) // roof normal
  const housePlane = { point: v3(h.origin, 0), normal: dir3({ x: -h.eout.x, y: -h.eout.y }) }

  // back channel at the house
  rg.add(mesh(prism(section('roofBackChannel', sections.roofBackChannel.loops), {
    origin: P(X0, D, h.heightAtHouse), ex: towardHouse, ey: UP, ez: ea3, length: W,
  }), mats.aluminum, 'back-channel', { part: 'A64048' }))

  // gutter along the low edge
  rg.add(mesh(prism(section('roofGutter', sections.roofGutter.loops), {
    origin: P(X0, 0, H_LOW), ex: towardHouse, ey: UP, ez: ea3, length: W,
  }), mats.aluminum, 'gutter', { part: 'GF50' }))

  // panels (roof4.py)
  const zUnder = (y) => H_LOW + TAN * (y + spec.roofLip)
  const Pyz = (y, hh) => [y + hh * -SIN, zUnder(y) + hh * COS]
  const yLo = -spec.roofOverhangFront
  const sTop = D - sections.roofPanelTopFromHouse
  const Lunder = (sTop - yLo) / COS
  const along = (p, d) => [p[0] + COS * d, p[1] + SIN * d]
  const quad = (h0, h1) => {
    const a = Pyz(yLo, h0)
    const b = Pyz(yLo, h1)
    return [a, b, along(b, Lunder), along(a, Lunder)]
  }
  if (Lunder > spec.roofPanelMaxLength) notes.push(`Roof panel length ${Lunder.toFixed(2)}" exceeds the ${spec.roofPanelMaxLength}" maximum.`)
  // userData.component groups meshes that the viewer isolates/explodes as one piece (visual only)
  const slab = (poly, x, w, mat, name, userData = { part: 'roof-panel' }) =>
    rg.add(mesh(prism(polySection(poly), { origin: P(x, 0, 0), ex: towardHouse, ey: UP, ez: ea3, length: w }), mat, name, userData))
  let x = X0
  let i = 0
  const widths = []
  while (X1 - x > 1e-6) {
    const w = Math.min(spec.roofPanelWidth, X1 - x)
    widths.push([x, w])
    i++
    const ud = (layer) => ({ part: 'roof-panel', component: `roof-p${i}`, roofPanel: i, layer })
    slab(quad(0, spec.roofSkin), x, w, mats.roofSkin, `roof-p${i}-skin-bottom`, ud('skin-bottom'))
    slab(quad(spec.roofSkin, spec.roofPanelThickness - spec.roofSkin), x, w, mats.roofFoam, `roof-p${i}-foam`, ud('foam'))
    slab(quad(spec.roofPanelThickness - spec.roofSkin, spec.roofPanelThickness), x, w, mats.roofSkin, `roof-p${i}-skin-top`, ud('skin-top'))
    x += w
  }
  const lastW = widths[widths.length - 1][1]
  if (widths.length > 1 && lastW < spec.roofPanelMinWidth) notes.push(`Last roof panel is ${lastW.toFixed(3)}" wide (minimum ${spec.roofPanelMinWidth}").`)
  // stand-in seams at interior joints
  const sm = spec.roofSeam
  widths.slice(1).forEach(([sx], j) => {
    const a = along(Pyz(yLo, spec.roofPanelThickness), sm.cutLow)
    const b = [a[0] - SIN * sm.height, a[1] + COS * sm.height]
    const L = Lunder - sm.cutLow - sm.cutHigh
    // seam j+1 sits between roof panels j+1 and j+2
    slab([a, b, along(b, L), along(a, L)], sx - sm.thickness / 2, sm.thickness, mats.aluminum, 'roof-seam', {
      part: 'roof-seam', component: `roof-seam-${j + 1}`, seamAfter: j + 1,
    })
  })

  // fascia on both sloped edges (section perpendicular to the slope), cut at the house
  const fas = sections.roofFasciaLeft
  const fasLen = (D + spec.fasciaExtraLength - yLo) / COS
  for (const side of ['left', 'right']) {
    const mirror = side === 'right'
    const aStart = mirror ? X1 : X0
    const origin = P(aStart, 0, H_LOW).addScaledVector(t2w, fas.tOffset)
    rg.add(mesh(prism(section('roofFasciaLeft', fas.loops, false), {
      origin, ex: mirror ? ea3.clone().negate() : ea3, ey: n2w, ez: t2w, length: fasLen, endCut: housePlane,
    }), mats.aluminum, `fascia-${side}`, { part: 'A66048' }))
  }

  // wood wedge on level walls facing the house (roof4.py: on the level front top channel)
  for (const wall of layout.walls) {
    if (!wall.buildable || Math.abs(wall.slope) > 1e-9) continue
    const facesHouse = wall.inward.x * -h.eout.x + wall.inward.y * -h.eout.y > 0.999
    if (!facesHouse) continue
    const dIn = spec.channelInnerDepth
    const poly = [[0, 0], [dIn, 0], [dIn, TAN * (dIn + spec.roofLip)], [0, TAN * spec.roofLip]]
    rg.add(mesh(prism(polySection(poly), {
      origin: v3(wall.origin, wall.topLeft), ex: dir3(wall.inward), ey: UP, ez: dir3(wall.right), length: wall.length,
    }), mats.wood, `wedge-wall-${wall.index}`, { part: 'wedge' }))
  }
  return rg
}

function buildHouseContext(layout, mats) {
  const h = layout.house
  const len = h.amax - h.amin + 120
  const height = h.heightAtHouse + 36
  const thick = 8
  const geo = new THREE.BoxGeometry(len, height, thick)
  const m = new THREE.Mesh(geo, mats.house)
  const mid = (h.amin + h.amax) / 2
  const c = { x: h.origin.x + h.ea.x * mid - h.eout.x * (thick / 2 + 0.25), y: h.origin.y + h.ea.y * mid - h.eout.y * (thick / 2 + 0.25) }
  m.position.set(c.x, height / 2, c.y)
  m.rotation.y = -Math.atan2(h.ea.y, h.ea.x)
  m.name = 'house-wall'
  m.receiveShadow = true
  m.castShadow = true
  m.userData = { context: true }
  return m
}

export function disposeGroup(group) {
  group.traverse((o) => {
    if (o.isMesh) o.geometry.dispose()
  })
}
