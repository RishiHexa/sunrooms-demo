/**
 * Split the raw 4-Season sunroom GLB into individual part GLBs.
 *
 *   node scripts/split-sunroom-glb.mjs
 *
 * Input : public/raw_sunroom/Sunroom_4Season.glb   (Blender export of the FreeCAD model)
 * Output: public/sunroom/4season/raw/<node>.glb    every mesh node, geometry untouched (source units/position)
 *         public/sunroom/4season/parts/<id>.glb    one canonical asset per part type, normalised (see below)
 *         public/sunroom/4season/manifest.json     what was exported, sizes, offsets, instance checks
 *
 * SOURCE UNITS: 1 source unit = 1/1000 inch (FreeCAD inch values exported as mm, then mm -> m).
 *   Verified against known values: roof panel 46.3125" (46 5/16" per supplier), corner post 5.125",
 *   front overall 216.000", side wall 144.000".
 *
 * CANONICAL PART FRAME (parts/*.glb), units = INCHES, glTF Y-up:
 *   X = along the wall, left -> right as seen from OUTSIDE
 *   Y = up
 *   Z = wall depth; z = 0 is the wall's exterior reference plane, exterior is +Z
 *       (Z is kept exactly as in the source so profiles from one wall still line up in depth)
 *   Origin: X and Y shifted so the part's bounding box starts at 0 (left end / bottom).
 *   Side-wall parts are rotated into this frame (+90 deg about Y for the LEFT wall).
 *   The source X/Y offset is written to the manifest so the original model can be re-assembled.
 *
 * The geometry itself (vertices, triangles) is not altered beyond that rigid transform + scale.
 */
import { Logger, NodeIO } from '@gltf-transform/core'
import { cloneDocument, prune, transformMesh } from '@gltf-transform/functions'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, '$1')), '..')
const INPUT = path.join(ROOT, 'public/raw_sunroom/Sunroom_4Season.glb')
const OUT = path.join(ROOT, 'public/sunroom/4season')
const SOURCE_UNITS_PER_INCH = 0.001
const TOL_IN = 1e-3 // tolerance for "identical geometry" checks, inches

/**
 * Canonical part types. `source` is the node used as the asset; `instances` are matched by
 * regex and compared to it so we know whether one asset really represents them all.
 * frame: 'front' (identity) | 'left' (+90 deg about Y) | 'roof' (identity)
 */
const PARTS = [
  // --- corners --------------------------------------------------------------
  { id: 'corner-post', source: 'CORNER CP_L CornerPost', frame: 'front', axis: 'y', instances: /^CORNER CP_/ },
  { id: 'inside-corner', source: 'CORNER IC_L InsideCorner', frame: 'front', axis: 'y', instances: /^CORNER IC_/ },
  // --- wall frame (die profiles) ---------------------------------------------
  { id: 't01-wall-channel', source: 'LEFT WC T01', frame: 'left', axis: 'y', instances: /^(LEFT|RIGHT) WC T01$/ },
  { id: 't02-vertical-male', source: 'FRONT MU1_M T02', frame: 'front', axis: 'y', instances: /^(FRONT|LEFT|RIGHT) (M\d|MU\d_M) T02$/ },
  { id: 't03-vertical-female', source: 'FRONT MU1_F T03', frame: 'front', axis: 'y', instances: /^(FRONT|LEFT|RIGHT) MU\d_F T03$/ },
  { id: 't02-receiver-bottom', source: 'FRONT P1_RCV_B T02', frame: 'front', axis: 'x', instances: /^(FRONT|LEFT|RIGHT) P\d_RCV_B T02$/ },
  { id: 't02-receiver-top', source: 'FRONT P1_RCV_T T02', frame: 'front', axis: 'x', instances: /^FRONT P\d_RCV_T T02$/ },
  { id: 't04-horizontal-high', source: 'FRONT P1_HHI T04', frame: 'front', axis: 'x', instances: /^(FRONT|LEFT|RIGHT) P\d_HHI T04$/ },
  { id: 't04-horizontal-low', source: 'FRONT P1_HLO T04', frame: 'front', axis: 'x', instances: /^(FRONT|LEFT|RIGHT) P\d_HLO T04$/ },
  { id: 't05-bottom-channel', source: 'FRONT BC T05', frame: 'front', axis: 'x', instances: /^(FRONT|LEFT|RIGHT) BC T05$/ },
  { id: 't05-top-channel', source: 'FRONT TC T05', frame: 'front', axis: 'x', instances: /^FRONT TC T05$/ },
  // Raked (sloped) side-wall members — specific to this model's roof slope.
  { id: 't05-top-channel-raked', source: 'LEFT TC T05', frame: 'left', axis: 'x', instances: /^(LEFT|RIGHT) TC T05$/ },
  { id: 't02-receiver-top-raked', source: 'LEFT P1_RCV_T T02', frame: 'left', axis: 'x', instances: /^(LEFT|RIGHT) P\d_RCV_T T02$/ },
  // --- roof -----------------------------------------------------------------
  { id: 'roof-panel-foam', source: 'ROOF P1 Foam', frame: 'roof', axis: 'z', instances: /^ROOF P\d Foam$/ },
  { id: 'roof-panel-skin-top', source: 'ROOF P1 SkinTop', frame: 'roof', axis: 'z', instances: /^ROOF P\d SkinTop$/ },
  { id: 'roof-panel-skin-bottom', source: 'ROOF P1 SkinBottom', frame: 'roof', axis: 'z', instances: /^ROOF P\d SkinBottom$/ },
  { id: 'roof-seam', source: 'ROOF Seam1', frame: 'roof', axis: 'z', instances: /^ROOF Seam\d$/ },
  { id: 'roof-back-channel', source: 'ROOF BackChannel', frame: 'roof', axis: 'x', instances: /^ROOF BackChannel$/ },
  { id: 'roof-gutter', source: 'ROOF Gutter', frame: 'roof', axis: 'x', instances: /^ROOF Gutter$/ },
  { id: 'roof-fascia-left', source: 'ROOF FasciaL', frame: 'roof', axis: 'z', instances: /^ROOF FasciaL$/ },
  { id: 'roof-fascia-right', source: 'ROOF FasciaR', frame: 'roof', axis: 'z', instances: /^ROOF FasciaR$/ },
  { id: 'roof-wedge', source: 'ROOF Wedge', frame: 'roof', axis: 'x', instances: /^ROOF Wedge$/ },
]

// ---------------------------------------------------------------------------
// small math helpers (column-major mat4, as glTF / gl-matrix)
// ---------------------------------------------------------------------------
const FRAME_ROT = {
  front: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
  roof: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
  // +90 deg about Y: x' = z, z' = -x  (left wall exterior -X -> +Z, back->front becomes left->right)
  left: [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
  // -90 deg about Y: x' = -z, z' = x  (right wall exterior +X -> +Z, front->back becomes left->right)
  right: [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 0, 1],
}
const frameFor = (nodeName, fallback) =>
  nodeName.startsWith('LEFT ') ? 'left' : nodeName.startsWith('RIGHT ') ? 'right' : fallback

function mul(a, b) {
  const o = new Array(16).fill(0)
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) o[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k]
  return o
}
const scaleM = (s) => [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0, 0, 0, 1]
const transM = (x, y, z) => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
const apply = (m, p) => [
  m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
  m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
  m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
]

function positionsOf(mesh) {
  const out = []
  for (const prim of mesh.listPrimitives()) {
    const acc = prim.getAttribute('POSITION')
    const el = []
    for (let i = 0; i < acc.getCount(); i++) out.push(acc.getElement(i, el).slice())
  }
  return out
}
function trianglesOf(mesh) {
  let t = 0
  for (const prim of mesh.listPrimitives()) {
    const idx = prim.getIndices()
    t += (idx ? idx.getCount() : prim.getAttribute('POSITION').getCount()) / 3
  }
  return t
}
function bboxOf(points) {
  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]
  for (const p of points) for (let k = 0; k < 3; k++) {
    min[k] = Math.min(min[k], p[k])
    max[k] = Math.max(max[k], p[k])
  }
  return { min, max, size: max.map((v, k) => v - min[k]) }
}
const r4 = (v) => Math.round(v * 10000) / 10000
const r4a = (a) => a.map(r4)

/**
 * Exterior wall plane per frame, in source units, measured along the source axis that
 * becomes canonical Z. front: z = 0, left: x = 0, right: x = RIGHT_WALL_X (set from the model).
 */
let RIGHT_WALL_X = null
const wallPlaneShift = (frame) => (frame === 'right' ? -RIGHT_WALL_X / SOURCE_UNITS_PER_INCH : 0)

/** Matrix taking source coordinates into the canonical part frame (inches, bbox-min X/Y = 0). */
function canonicalMatrix(points, frame) {
  const base = mul(transM(0, 0, wallPlaneShift(frame)), mul(FRAME_ROT[frame], scaleM(1 / SOURCE_UNITS_PER_INCH)))
  const b = bboxOf(points.map((p) => apply(base, p)))
  return { matrix: mul(transM(-b.min[0], -b.min[1], 0), base), offsetIn: [b.min[0], b.min[1]] }
}

/**
 * Max over A of the distance to the nearest vertex of B (inches). Order/tessellation
 * independent; returns Infinity if some vertex has no neighbour within `cell`.
 */
function directedVertexDistance(A, B, cell = 0.5) {
  const key = (x, y, z) => `${x},${y},${z}`
  const grid = new Map()
  for (const p of B) {
    const k = key(Math.floor(p[0] / cell), Math.floor(p[1] / cell), Math.floor(p[2] / cell))
    if (!grid.has(k)) grid.set(k, [])
    grid.get(k).push(p)
  }
  let worst = 0
  for (const p of A) {
    const cx = Math.floor(p[0] / cell), cy = Math.floor(p[1] / cell), cz = Math.floor(p[2] / cell)
    let best = Infinity
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
      for (const q of grid.get(key(cx + dx, cy + dy, cz + dz)) ?? []) {
        const d = Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2])
        if (d < best) best = d
      }
    }
    if (best === Infinity) return Infinity
    if (best > worst) worst = best
  }
  return worst
}
const shapeDistance = (A, B) => Math.max(directedVertexDistance(A, B), directedVertexDistance(B, A))

const AXIS = { x: 0, y: 1, z: 2 }
const SHAPE_TOL_IN = 0.02 // vertex-cloud distance accepted as "same shape"

/**
 * Classify an instance against the canonical asset (both already in canonical frame):
 *   same            identical shape (tessellation may differ)
 *   mirrored-x      same shape mirrored along the wall
 *   same-profile    same cross-section size, different length / end cuts
 *   different       anything else
 */
function classify(refPts, refBox, pts, box, lengthAxis) {
  const L = AXIS[lengthAxis]
  const crossSame = [0, 1, 2].every((k) => k === L || Math.abs(refBox.size[k] - box.size[k]) <= TOL_IN)
  const allSame = crossSame && Math.abs(refBox.size[L] - box.size[L]) <= TOL_IN
  if (allSame) {
    const d = shapeDistance(refPts, pts)
    if (d <= SHAPE_TOL_IN) return { match: 'same', shapeDistanceIn: r4(d) }
    const mirrored = pts.map((p) => [box.size[0] - p[0], p[1], p[2]])
    const dm = shapeDistance(refPts, mirrored)
    if (dm <= SHAPE_TOL_IN) return { match: 'mirrored-x', shapeDistanceIn: r4(dm) }
    return { match: 'different', shapeDistanceIn: Number.isFinite(d) ? r4(d) : null }
  }
  if (crossSame) return { match: 'same-profile', lengthIn: r4(box.size[L]) }
  return { match: 'different' }
}

// ---------------------------------------------------------------------------
const io = new NodeIO()
const doc = await io.read(INPUT)
const scene = doc.getRoot().getDefaultScene() ?? doc.getRoot().listScenes()[0]
const meshNodes = doc.getRoot().listNodes().filter((n) => n.getMesh())

// Sanity: the wrapper node must not carry a transform, otherwise "world" != mesh coordinates.
for (const n of doc.getRoot().listNodes()) {
  const t = n.getTranslation(), r = n.getRotation(), s = n.getScale()
  const identity = t.every((v) => v === 0) && r[0] === 0 && r[1] === 0 && r[2] === 0 && r[3] === 1 && s.every((v) => v === 1)
  if (!identity) throw new Error(`Node "${n.getName()}" has a transform; script assumes identity transforms.`)
}
// Right wall exterior plane = outer face of the right corner post (left post's outer face is x = 0).
{
  const cpL = meshNodes.find((n) => n.getName() === 'CORNER CP_L CornerPost')
  const cpR = meshNodes.find((n) => n.getName() === 'CORNER CP_R CornerPost')
  if (!cpL || !cpR) throw new Error('Corner posts not found; cannot locate wall planes.')
  const bl = bboxOf(positionsOf(cpL.getMesh()))
  if (Math.abs(bl.min[0]) > 1e-9) throw new Error(`Left corner post outer face is not at x=0 (${bl.min[0]}).`)
  RIGHT_WALL_X = bboxOf(positionsOf(cpR.getMesh())).max[0]
}
const names = meshNodes.map((n) => n.getName())
if (new Set(names).size !== names.length) throw new Error('Duplicate node names in source; cannot map parts unambiguously.')

rmSync(OUT, { recursive: true, force: true })
mkdirSync(path.join(OUT, 'raw'), { recursive: true })
mkdirSync(path.join(OUT, 'parts'), { recursive: true })

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

/** Make a document holding only `nodeName`, optionally transforming its mesh. */
async function isolate(nodeName, { matrix, rename, extras } = {}) {
  const d = cloneDocument(doc)
  d.setLogger(new Logger(Logger.Verbosity.WARN))
  const sc = d.getRoot().getDefaultScene() ?? d.getRoot().listScenes()[0]
  const keep = d.getRoot().listNodes().find((n) => n.getName() === nodeName)
  // Re-parent the kept node directly under the scene, drop everything else.
  for (const child of sc.listChildren()) sc.removeChild(child)
  keep.getParentNode()?.removeChild(keep)
  sc.addChild(keep)
  for (const n of d.getRoot().listNodes()) if (n !== keep) n.dispose()
  if (matrix) transformMesh(keep.getMesh(), matrix)
  if (rename) {
    keep.setName(rename)
    keep.getMesh().setName(rename)
  }
  if (extras) keep.setExtras(extras)
  await d.transform(prune())
  return d
}

const manifest = {
  source: 'public/raw_sunroom/Sunroom_4Season.glb',
  generatedBy: 'scripts/split-sunroom-glb.mjs',
  sourceUnitsPerInch: SOURCE_UNITS_PER_INCH,
  sourceModelIn: { frontWallPlaneZ: 0, leftWallPlaneX: 0, rightWallPlaneX: r4(RIGHT_WALL_X / SOURCE_UNITS_PER_INCH) },
  canonicalFrame: {
    units: 'inch',
    up: '+Y',
    x: 'along wall, left->right seen from outside',
    z: 'wall depth, z=0 exterior reference plane, exterior +Z (kept from source)',
    origin: 'bbox min X and min Y = 0',
  },
  raw: [],
  parts: [],
  unassigned: [],
}

// 1) raw split -------------------------------------------------------------
for (const node of meshNodes) {
  const name = node.getName()
  const file = `raw/${slug(name)}.glb`
  await io.write(path.join(OUT, file), await isolate(name))
  const b = bboxOf(positionsOf(node.getMesh()).map((p) => p.map((v) => v / SOURCE_UNITS_PER_INCH)))
  manifest.raw.push({ node: name, file, triangles: trianglesOf(node.getMesh()), bboxMinIn: r4a(b.min), sizeIn: r4a(b.size) })
}

// 2) canonical parts ---------------------------------------------------------
const assigned = new Set()
for (const part of PARTS) {
  const src = meshNodes.find((n) => n.getName() === part.source)
  if (!src) throw new Error(`Source node not found: ${part.source}`)
  const srcPts = positionsOf(src.getMesh())
  const { matrix, offsetIn } = canonicalMatrix(srcPts, part.frame)
  const canonPts = srcPts.map((p) => apply(matrix, p))
  const b = bboxOf(canonPts)

  // Check every instance of this type against the canonical asset.
  const instances = []
  for (const n of meshNodes.filter((n) => part.instances.test(n.getName()))) {
    assigned.add(n.getName())
    const pts = positionsOf(n.getMesh())
    const frame = frameFor(n.getName(), part.frame)
    const m = canonicalMatrix(pts, frame)
    const ipts = pts.map((p) => apply(m.matrix, p))
    const ib = bboxOf(ipts)
    const cmp = classify(canonPts, b, ipts, ib, part.axis)
    instances.push({ node: n.getName(), frame, sourceOffsetIn: r4a(m.offsetIn), sizeIn: r4a(ib.size), zRangeIn: [r4(ib.min[2]), r4(ib.max[2])], ...cmp })
  }

  const file = `parts/${part.id}.glb`
  const extras = { partId: part.id, sourceNode: part.source, units: 'inch', lengthAxis: part.axis }
  await io.write(path.join(OUT, file), await isolate(part.source, { matrix, rename: part.id, extras }))
  manifest.parts.push({
    id: part.id,
    file,
    sourceNode: part.source,
    frame: part.frame,
    lengthAxis: part.axis,
    sizeIn: r4a(b.size),
    zRangeIn: [r4(b.min[2]), r4(b.max[2])],
    sourceOffsetIn: r4a(offsetIn),
    triangles: trianglesOf(src.getMesh()),
    material: src.getMesh().listPrimitives()[0].getMaterial()?.getName() ?? null,
    instances,
  })
}
manifest.unassigned = names.filter((n) => !assigned.has(n))

writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2))

// Console summary
console.log(`raw parts: ${manifest.raw.length}  canonical parts: ${manifest.parts.length}  unassigned: ${manifest.unassigned.length}`)
for (const p of manifest.parts) {
  console.log(`${p.id.padEnd(26)} size ${p.sizeIn.join(' x ').padEnd(30)} z ${p.zRangeIn.join('..').padEnd(16)} tris ${String(p.triangles).padStart(5)}`)
  for (const i of p.instances) {
    const extra = i.match === 'same-profile' ? `length ${i.lengthIn}` : i.shapeDistanceIn != null ? `d=${i.shapeDistanceIn}` : ''
    console.log(`    ${i.match.padEnd(13)} ${i.node.padEnd(24)} ${extra.padEnd(16)} size ${i.sizeIn.join(' x ')}  z ${i.zRangeIn.join('..')}`)
  }
}
if (manifest.unassigned.length) console.log('unassigned:', manifest.unassigned.join(', '))
