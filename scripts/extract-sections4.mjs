/**
 * Extract member cross-sections for the 4-Season (GF50) system from the supplier's solved
 * room model, so the configurator reuses the supplier's orientation of every profile
 * instead of re-deriving it.
 *
 *   node scripts/extract-sections4.mjs
 *
 * Inputs (supplier data, read-only):
 *   Extracted/Sunroom-Drawings/sunroom_build/season4/members4.json  (wall members, world coords)
 *   Extracted/Sunroom-Drawings/sunroom_build/season4/roof4.json     (roof members, world coords)
 *   Supplier world: X along front wall 0->216, Y front exterior (0) -> house (144), Z up, inches.
 *
 * Output: src/sunroom/data/sections4.json
 *   Each section is a list of loops; each loop is a list of segments
 *   ['line', a, b] or ['arc', a, mid, b] with 2D points in the section's LOCAL frame
 *   (documented per entry in `frame`). `depth` = nesting depth (even = solid, odd = hole).
 *
 * Only rigid translations / axis swaps are applied here. No values are rounded.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'Extracted/Sunroom-Drawings/sunroom_build/season4')
const OUT = path.join(ROOT, 'src/sunroom/data/sections4.json')

const members = JSON.parse(readFileSync(path.join(SRC, 'members4.json'), 'utf8'))
const roof = JSON.parse(readFileSync(path.join(SRC, 'roof4.json'), 'utf8'))
const byName = new Map([...members.members, ...roof.members].map((m) => [m.name, m]))

function get(name) {
  const m = byName.get(name)
  if (!m) throw new Error(`member not found: ${name}`)
  return m
}

/** Map every point of a member's loops through f(p3) -> [u, v]. */
function mapLoops(m, f) {
  return m.loops.map((L) => ({
    depth: L.depth,
    segs: L.segs.map((s) => [s[0], ...s.slice(1).map((p) => f(p).map((v) => v))]),
  }))
}

function bounds(loops) {
  let minU = Infinity, minV = Infinity, maxU = -Infinity, maxV = -Infinity
  for (const L of loops) for (const s of L.segs) for (const [u, v] of s.slice(1)) {
    minU = Math.min(minU, u); maxU = Math.max(maxU, u)
    minV = Math.min(minV, v); maxV = Math.max(maxV, v)
  }
  return { minU, minV, maxU, maxV }
}

function assertPlanar(m, axis, value, tol = 1e-6) {
  for (const L of m.loops) for (const s of L.segs) for (const p of s.slice(1)) {
    if (Math.abs(p[axis] - value) > tol) throw new Error(`${m.name}: section not planar on axis ${axis}`)
  }
}

const layout = members.layout
const Z0 = layout.z0 // vertical member bottom (seat on bottom channel), inches
const sections = {}

// ---------------------------------------------------------------------------
// Vertical members (plan sections). Supplier FRONT wall: X = along wall (left->right seen
// from outside), Y = depth from exterior plane. Local frame: u = s (along wall), v = d (depth).
// ---------------------------------------------------------------------------
function plan(name, key, sOrigin, note) {
  const m = get(name)
  assertPlanar(m, 2, Z0)
  const loops = mapLoops(m, (p) => [p[0] - sOrigin(m), p[1]])
  sections[key] = { source: name, part: m.part, frame: 'plan: u = along wall (s), v = depth from exterior plane (d)', note, loops, bounds: bounds(loops) }
}
const minX = (m) => Math.min(...m.loops.flatMap((L) => L.segs.flatMap((s) => s.slice(1).map((p) => p[0]))))
const maxX = (m) => Math.max(...m.loops.flatMap((L) => L.segs.flatMap((s) => s.slice(1).map((p) => p[0]))))

// Corner pieces: corner = plan origin; u along the wall whose outside-LEFT end is the corner.
plan('CORNER CP_L', 'cornerPost', () => 0, 'u along the wall leaving the corner, v = that wall inward')
plan('CORNER IC_L', 'insideCorner', () => 0, 'same frame as cornerPost')
// Panel verticals: male as LEFT vertical (leg tip at u=0, body toward -s side i.e. u in [0, 1.0])
plan('FRONT M0', 'maleLeft', minX, 'left vertical of a panel; leg tip at u=0')
// Female as RIGHT vertical (leg tip at u=0, profile extends to -u)
plan('FRONT MU1_F', 'femaleRight', maxX, 'right vertical of a panel; leg tip at u=0')

// Wall channel at the house: supplier LEFT wall has X = depth, Y = along wall toward the house.
{
  const m = get('LEFT WC')
  // vertical, but extruded with a top cut; base plane z = Z0
  for (const L of m.loops) for (const s of L.segs) for (const p of s.slice(1)) if (Math.abs(p[2] - Z0) > 1e-6) throw new Error('WC not planar')
  const loops = mapLoops(m, (p) => [p[1] - 144.0, p[0]])
  sections.wallChannelRight = {
    source: 'LEFT WC', part: m.part,
    frame: 'plan: u = s measured from the house line (house end on the RIGHT, u <= 0), v = depth',
    loops, bounds: bounds(loops),
  }
}

// ---------------------------------------------------------------------------
// Horizontal members (wall sections). Supplier FRONT wall: Y = depth, Z = height.
// Local frame: u = d (depth from exterior), v = h (height relative to the reference stated).
// ---------------------------------------------------------------------------
function wallSection(name, key, hRef, note) {
  const m = get(name)
  const x0 = m.loops[0].segs[0][1][0]
  assertPlanar(m, 0, x0)
  const loops = mapLoops(m, (p) => [p[1], p[2] - hRef(m)])
  sections[key] = { source: name, part: m.part, frame: `wall section: u = depth from exterior (d), v = ${note}`, loops, bounds: bounds(loops) }
}
const minZ = (m) => Math.min(...m.loops.flatMap((L) => L.segs.flatMap((s) => s.slice(1).map((p) => p[2]))))
const maxZ = (m) => Math.max(...m.loops.flatMap((L) => L.segs.flatMap((s) => s.slice(1).map((p) => p[2]))))

wallSection('FRONT P1_HLO', 'rail', minZ, 'height above the die origin (bottom of profile)')
wallSection('FRONT P1_RCV_B', 'receiverBottom', minZ, 'height above the bottom seat line (leg tips at 0)')
wallSection('FRONT P1_RCV_T', 'receiverTop', maxZ, 'height relative to the top seat line (leg tips at 0, v <= 0)')
wallSection('FRONT BC', 'channelBottom', minZ, 'height above the channel underside')
wallSection('FRONT TC', 'channelTop', maxZ, 'height relative to the channel top surface (v <= 0)')

// ---------------------------------------------------------------------------
// Roof (supplier lean-to frame: Y = distance inward from the low wall's exterior line,
// Z = absolute height with the low wall top-of-channel at 84).
// ---------------------------------------------------------------------------
const H_LOW_MODEL = 84.0
const DP_MODEL = 144.0
{
  const m = get('ROOF BackChannel')
  assertPlanar(m, 0, m.loops[0].segs[0][1][0])
  const loops = mapLoops(m, (p) => [p[1] - DP_MODEL, p[2] - (H_LOW_MODEL + layout.tan * DP_MODEL)])
  sections.roofBackChannel = { source: m.name, part: m.part, frame: 'roof section, house-anchored: u = Y - house Y, v = Z - house height', loops, bounds: bounds(loops) }
}
{
  const m = get('ROOF Gutter')
  assertPlanar(m, 0, m.loops[0].segs[0][1][0])
  const loops = mapLoops(m, (p) => [p[1], p[2] - H_LOW_MODEL])
  sections.roofGutter = { source: m.name, part: m.part, frame: 'roof section, low-edge-anchored: u = Y, v = Z - low wall height', loops, bounds: bounds(loops) }
}
{
  // Fascia section lies in the plane perpendicular to the slope direction t = (0, COS, SIN).
  const m = get('ROOF FasciaL')
  const COS = 1 / Math.sqrt(1 + layout.tan ** 2), SIN = layout.tan * COS
  const X0 = -16.0
  let tMin = Infinity, tMax = -Infinity
  const loops = mapLoops(m, (p) => {
    const y = p[1], z = p[2] - H_LOW_MODEL
    const tc = y * COS + z * SIN
    tMin = Math.min(tMin, tc); tMax = Math.max(tMax, tc)
    return [p[0] - X0, -y * SIN + z * COS]
  })
  if (tMax - tMin > 1e-6) throw new Error('fascia section not perpendicular to slope')
  sections.roofFasciaLeft = {
    source: m.name, part: m.part,
    frame: 'roof fascia: u = along eave from roof start X0 (outward = -u), v = along roof normal (Y,Z-84).n; section lies at slope coordinate tOffset',
    tOffset: tMin, extrude: m.extrude, loops, bounds: bounds(loops),
  }
}

// Panel top end on the underside line, measured from the house (house-anchored).
{
  const m = get('ROOF P1 SkinBottom')
  const maxY = Math.max(...m.loops[0].segs.flatMap((s) => s.slice(1).map((p) => p[1])))
  sections.roofPanelTopFromHouse = DP_MODEL - maxY
}

const out = {
  system: '4season-gf50',
  sources: ['members4.json', 'roof4.json'],
  units: 'inch',
  modelLayout: layout,
  sections,
}
mkdirSync(path.dirname(OUT), { recursive: true })
writeFileSync(OUT, JSON.stringify(out))
for (const [k, v] of Object.entries(sections)) {
  if (typeof v === 'number') { console.log(k.padEnd(22), v.toFixed(4)); continue }
  const b = v.bounds
  console.log(k.padEnd(22), `${v.source.padEnd(18)} loops ${v.loops.length}  u ${b.minU.toFixed(4)}..${b.maxU.toFixed(4)}  v ${b.minV.toFixed(4)}..${b.maxV.toFixed(4)}`)
}
