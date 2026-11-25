/**
 * Procedural cross-section (cutaway) of an embossed door slab — VISUAL REFERENCE ONLY.
 *
 * Layers (front to back): embossed fiberglass skin, polyurethane foam core (wood lock stile at
 * the edge), embossed back skin. The embossment is a raised-panel moulding that follows a
 * rectangular panel outline with mitred corners; the piece is cut on top so the profile shows.
 *
 * All dimensions are ILLUSTRATIVE PLACEHOLDERS (inches), not product data. Replace them with
 * the slab supplier's skin / moulding drawings before using this for anything but visuals.
 *
 * Axes: x across the slab (0 = hinge/lock edge), y up, z through the thickness (0 = back face,
 * T = front face). 1 unit = 1 inch.
 */
import * as THREE from 'three'
import { mergeGeometries, mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

export const DEFAULT_PARAMS = Object.freeze({
  width: 9, // piece width shown
  height: 12, // piece height shown
  thickness: 1.75, // slab thickness T
  skin: 0.07, // skin thickness
  stileWidth: 1.25, // wood lock stile width
  panelX: 3.0, // moulding starts here (distance from the edge)
  panelY: 4.0, // moulding starts here (distance from the bottom of the piece)
  embossScale: 1, // multiplies all moulding depths
  embossBack: true, // emboss the back skin as well (mirror)
})

// ---------------------------------------------------------------------------
// Moulding profile: depth d(u) (<= 0 is into the slab) vs distance u from moulding start
// ---------------------------------------------------------------------------
const PROFILE = {
  flat: 0.12,
  coveW: 0.24,
  coveD: 0.16,
  beadW: 0.4,
  beadH: 0.16,
  grooveW: 0.16,
  grooveD: 0.28,
  bevelW: 0.6,
  fieldD: 0.12,
}
export const PROFILE_WIDTH = PROFILE.flat + PROFILE.coveW + PROFILE.beadW + PROFILE.grooveW + PROFILE.bevelW

const ease = (t) => (1 - Math.cos(Math.PI * t)) / 2

export function profileDepth(u, k = 1) {
  const P = PROFILE
  if (u <= P.flat) return 0
  let a = P.flat
  if (u < a + P.coveW) return -k * P.coveD * ease((u - a) / P.coveW)
  a += P.coveW
  if (u < a + P.beadW) {
    const t = (u - a) / P.beadW
    return k * (-P.coveD + P.beadH * Math.sqrt(Math.sin(Math.PI * t)))
  }
  a += P.beadW
  if (u < a + P.grooveW) {
    const t = (u - a) / P.grooveW
    return -k * (P.coveD + (P.grooveD - P.coveD) * Math.sin(Math.PI * t))
  }
  a += P.grooveW
  if (u < a + P.bevelW) {
    const t = (u - a) / P.bevelW
    return -k * (P.coveD + (P.fieldD - P.coveD) * ease(t))
  }
  return -k * P.fieldD
}

/** Depth of the embossed surface at (x, y): mitred raised-panel outline. */
function makeDepthFn(p) {
  return (x, y) => {
    if (x <= p.panelX || y <= p.panelY) return 0
    return profileDepth(Math.min(x - p.panelX, y - p.panelY), p.embossScale)
  }
}

// ---------------------------------------------------------------------------
// Sampling: coarse everywhere, dense across the moulding band
// ---------------------------------------------------------------------------
function samples(from, to, coarse, bands) {
  const s = new Set()
  for (let v = from; v <= to + 1e-9; v += coarse) s.add(+v.toFixed(5))
  s.add(to)
  for (const [a, b, step] of bands) {
    for (let v = Math.max(from, a); v <= Math.min(to, b) + 1e-9; v += step) s.add(+v.toFixed(5))
  }
  return [...s].filter((v) => v >= from - 1e-9 && v <= to + 1e-9).sort((p, q) => p - q)
}

// ---------------------------------------------------------------------------
// Closed solid between two height fields over a rectangular grid
// ---------------------------------------------------------------------------
function heightSolid(xs, ys, zTop, zBot, uv) {
  const nx = xs.length
  const ny = ys.length
  const surf = (zf, up) => {
    const pos = new Float32Array(nx * ny * 3)
    const uvs = new Float32Array(nx * ny * 2)
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const k = j * nx + i
        pos.set([xs[i], ys[j], zf(xs[i], ys[j])], k * 3)
        uvs.set(uv.face(xs[i], ys[j]), k * 2)
      }
    }
    const idx = []
    for (let j = 0; j < ny - 1; j++) {
      for (let i = 0; i < nx - 1; i++) {
        const a = j * nx + i
        const b = a + 1
        const c = a + nx + 1
        const d = a + nx
        if (up) idx.push(a, b, c, a, c, d)
        else idx.push(a, c, b, a, d, c)
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('uv', new THREE.BufferAttribute(uvs, 2))
    g.setIndex(idx)
    g.computeVertexNormals()
    return g.toNonIndexed()
  }

  // side walls along the boundary (flat shaded)
  const pos = []
  const uvs = []
  const quad = (p0, p1, p2, p3, nrm, uvf) => {
    const e1 = new THREE.Vector3().subVectors(p1, p0)
    const e2 = new THREE.Vector3().subVectors(p2, p0)
    const flip = new THREE.Vector3().crossVectors(e1, e2).dot(nrm) < 0
    const tri = flip ? [p0, p2, p1, p0, p3, p2] : [p0, p1, p2, p0, p2, p3]
    for (const p of tri) {
      pos.push(p.x, p.y, p.z)
      uvs.push(...uvf(p))
    }
  }
  const side = (pts, nrm, uvf) => {
    for (let k = 0; k < pts.length - 1; k++) {
      const [x0, y0] = pts[k]
      const [x1, y1] = pts[k + 1]
      quad(
        new THREE.Vector3(x0, y0, zBot(x0, y0)),
        new THREE.Vector3(x1, y1, zBot(x1, y1)),
        new THREE.Vector3(x1, y1, zTop(x1, y1)),
        new THREE.Vector3(x0, y0, zTop(x0, y0)),
        nrm,
        uvf,
      )
    }
  }
  const X0 = xs[0], X1 = xs[nx - 1], Y0 = ys[0], Y1 = ys[ny - 1]
  side(ys.map((y) => [X0, y]), new THREE.Vector3(-1, 0, 0), (p) => uv.sideX(p))
  side(ys.map((y) => [X1, y]), new THREE.Vector3(1, 0, 0), (p) => uv.sideX(p))
  side(xs.map((x) => [x, Y0]), new THREE.Vector3(0, -1, 0), (p) => uv.sideY(p))
  side(xs.map((x) => [x, Y1]), new THREE.Vector3(0, 1, 0), (p) => uv.sideY(p))
  const sides = new THREE.BufferGeometry()
  sides.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
  sides.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  sides.computeVertexNormals()

  // weld identical vertices (smooth surfaces share them; flat side walls keep their own normals)
  return mergeVertices(mergeGeometries([surf(zTop, true), surf(zBot, false), sides]), 1e-6)
}

// ---------------------------------------------------------------------------
// Procedural textures (canvas)
// ---------------------------------------------------------------------------
function rng(seed) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

function canvasTexture(size, draw, { srgb = true, repeat = [1, 1] } = {}) {
  const c = document.createElement('canvas')
  c.width = c.height = size
  draw(c.getContext('2d'), size)
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.repeat.set(...repeat)
  t.anisotropy = 8
  if (srgb) t.colorSpace = THREE.SRGBColorSpace
  return t
}

/** Wood-grain emboss for the fiberglass skin (grain runs along v). */
function grainPainter(base, lineRGB, alpha, seed) {
  return (g, n) => {
    g.fillStyle = base
    g.fillRect(0, 0, n, n)
    const r = rng(seed)
    for (let k = 0; k < 260; k++) {
      const x0 = r() * n
      const w = 0.6 + r() * 2.2
      const amp = 2 + r() * 10
      const freq = 1 + Math.floor(r() * 3)
      const phase = r() * Math.PI * 2
      g.strokeStyle = `rgba(${lineRGB},${alpha * (0.3 + r() * 0.7)})`
      g.lineWidth = w
      g.beginPath()
      for (let y = 0; y <= n; y += 8) {
        const x = x0 + amp * Math.sin((y / n) * Math.PI * 2 * freq + phase)
        if (y === 0) g.moveTo(x, y)
        else g.lineTo(x, y)
      }
      g.stroke()
    }
  }
}

function makeMaterials() {
  const skinMap = canvasTexture(1024, grainPainter('#ebe6dc', '150,140,120', 0.22, 7), { repeat: [1, 1] })
  const skinBump = canvasTexture(1024, grainPainter('#808080', '20,20,20', 0.9, 7), { srgb: false })
  const foamPaint = (base, dots, seed) => (g, n) => {
    g.fillStyle = base
    g.fillRect(0, 0, n, n)
    const r = rng(seed)
    for (let k = 0; k < 9000; k++) {
      const s = 0.5 + r() * 2.5
      g.fillStyle = `rgba(${dots},${0.08 + r() * 0.25})`
      g.beginPath()
      g.arc(r() * n, r() * n, s, 0, Math.PI * 2)
      g.fill()
    }
  }
  const foamMap = canvasTexture(512, foamPaint('#efe0a6', '170,140,60', 3), { repeat: [2, 2] })
  const foamBump = canvasTexture(512, foamPaint('#9a9a9a', '0,0,0', 3), { srgb: false, repeat: [2, 2] })
  // LVL: veneer laminations parallel to the slab faces (stripes vary with v = thickness)
  const lvlMap = canvasTexture(512, (g, n) => {
    g.fillStyle = '#c99a66'
    g.fillRect(0, 0, n, n)
    const r = rng(11)
    let y = 0
    while (y < n) {
      const h = 10 + r() * 22
      g.fillStyle = `rgba(${120 + r() * 50},${80 + r() * 30},${40 + r() * 20},${0.25 + r() * 0.35})`
      g.fillRect(0, y, n, h)
      g.fillStyle = 'rgba(90,55,25,0.55)'
      g.fillRect(0, y + h - 1.5, n, 1.5)
      y += h
    }
    for (let k = 0; k < 400; k++) {
      g.fillStyle = `rgba(110,70,35,${r() * 0.25})`
      g.fillRect(r() * n, r() * n, 6 + r() * 40, 1)
    }
  })
  return {
    skin: new THREE.MeshStandardMaterial({ map: skinMap, bumpMap: skinBump, bumpScale: 0.6, roughness: 0.72, color: 0xffffff }),
    foam: new THREE.MeshStandardMaterial({ map: foamMap, bumpMap: foamBump, bumpScale: 1.5, roughness: 0.95 }),
    wood: new THREE.MeshStandardMaterial({ map: lvlMap, roughness: 0.8 }),
  }
}

// ---------------------------------------------------------------------------
// Builder
// ---------------------------------------------------------------------------
export function buildSlabSection(params = DEFAULT_PARAMS, materials = makeMaterials()) {
  const p = { ...DEFAULT_PARAMS, ...params }
  const T = p.thickness
  const ts = p.skin
  const d = makeDepthFn(p)
  const dBack = p.embossBack ? d : () => 0
  const band = (s) => [s - 0.05, s + PROFILE_WIDTH + 0.1, 0.02]
  const xs = samples(0, p.width, 0.25, [band(p.panelX), [p.stileWidth, p.stileWidth, 1]])
  const ys = samples(0, p.height, 0.25, [band(p.panelY)])
  const xsFoam = xs.filter((x) => x >= p.stileWidth)
  const xsWood = xs.filter((x) => x <= p.stileWidth)

  // UV mappers (inches -> texture space)
  const S = 1 / 12
  const uvSkin = { face: (x, y) => [x * S, y * S], sideX: (q) => [q.y * S, q.z * S], sideY: (q) => [q.x * S, q.z * S] }
  const uvFoam = { face: (x, y) => [x / 6, y / 6], sideX: (q) => [q.y / 6, q.z / 6], sideY: (q) => [q.x / 6, q.z / 6] }
  const uvWood = { face: (x, y) => [x / 4, y / 4], sideX: (q) => [q.y / 4, q.z / T], sideY: (q) => [q.x / 4, q.z / T] }

  const group = new THREE.Group()
  group.name = 'slab-section'
  const add = (geo, mat, name, label) => {
    const m = new THREE.Mesh(geo, mat)
    m.name = name
    m.castShadow = true
    m.receiveShadow = true
    m.userData.label = label
    group.add(m)
    return m
  }

  add(heightSolid(xs, ys, (x, y) => T + d(x, y), (x, y) => T + d(x, y) - ts, uvSkin), materials.skin, 'front-skin', 'Fiberglass skin, embossed')
  add(heightSolid(xs, ys, (x, y) => -dBack(x, y) + ts, (x, y) => -dBack(x, y), uvSkin), materials.skin, 'back-skin', 'Fiberglass skin, back')
  add(
    heightSolid(xsFoam, ys, (x, y) => T + d(x, y) - ts, (x, y) => -dBack(x, y) + ts, uvFoam),
    materials.foam, 'foam-core', 'Polyurethane foam core',
  )
  add(heightSolid(xsWood, ys, () => T - ts, () => ts, uvWood), materials.wood, 'lock-stile', 'Engineered wood (LVL) lock stile')

  return { group, params: p, materials }
}

/** Points (on the top cut face) where callout leaders should point. */
export function calloutAnchors(params = DEFAULT_PARAMS) {
  const p = { ...DEFAULT_PARAMS, ...params }
  const T = p.thickness
  const xm = p.panelX + PROFILE.flat + PROFILE.coveW + PROFILE.beadW / 2
  return [
    { key: 'skin', text: 'Fiberglass skin with wood-grain emboss', at: new THREE.Vector3(p.width - 1.5, p.height, T - p.skin / 2) },
    { key: 'profile', text: 'Embossed raised-panel moulding', at: new THREE.Vector3(xm, p.height, T + profileDepth(xm - p.panelX, p.embossScale)) },
    { key: 'foam', text: 'Polyurethane foam core', at: new THREE.Vector3(p.width - 2.5, p.height, T / 2) },
    { key: 'stile', text: 'Engineered wood (LVL) lock stile', at: new THREE.Vector3(p.stileWidth / 2, p.height, T / 2) },
  ]
}
