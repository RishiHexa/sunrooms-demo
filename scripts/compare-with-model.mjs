/**
 * Build the supplier's reference room (216" x 144", house at the back, 4 front panels,
 * 2 per side) with our layout + 3D builder and compare every member's bounding box with
 * the supplier GLB parts (public/sunroom/4season/manifest.json, raw split).
 *
 *   node scripts/compare-with-model.mjs
 *
 * Frames: GLB (x along front, y up, z = -supplier Y)  ->  ours (X = plan x, Y up, Z = plan y,
 * house at Z = 0, front at Z = 144)  =>  Z_ours = 144 + z_glb.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import * as THREE from 'three'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const json = (p) => JSON.parse(readFileSync(path.join(ROOT, p), 'utf8'))

// The app modules import JSON with ESM import syntax; load them via vite-node-free path:
const { computeLayout } = await import('../src/sunroom/layout.js')
const sections = json('src/sunroom/data/sections4.json')
const { buildSunroom } = await import('../src/sunroom/build3d.js')
const spec = (await import('../src/sunroom/spec4season.js')).SPEC_4SEASON

const plan = {
  vertices: [{ x: 0, y: 0 }, { x: 216, y: 0 }, { x: 216, y: 144 }, { x: 0, y: 144 }],
  walls: [
    { orientation: 'h', locked: false, house: true, panels: null },
    { orientation: 'v', locked: false, house: false, panels: 2 },
    { orientation: 'h', locked: false, house: false, panels: 4 },
    { orientation: 'v', locked: false, house: false, panels: 2 },
  ],
}
const layout = computeLayout(plan, spec)
if (!layout.ok) throw new Error(JSON.stringify(layout.errors))
const { group } = buildSunroom(layout, sections.sections)
group.updateMatrixWorld(true)

const ours = []
group.traverse((o) => {
  if (!o.isMesh || o.userData.context) return
  const b = new THREE.Box3().setFromObject(o)
  ours.push({ name: `${o.parent?.name}/${o.name}`, min: b.min.toArray(), max: b.max.toArray() })
})

const manifest = json('public/sunroom/4season/manifest.json')
const rows = []
for (const r of manifest.raw) {
  const min = [r.bboxMinIn[0], r.bboxMinIn[1], 144 + r.bboxMinIn[2]]
  const max = [min[0] + r.sizeIn[0], min[1] + r.sizeIn[1], min[2] + r.sizeIn[2]]
  let best = null
  for (const m of ours) {
    const d = Math.max(...[0, 1, 2].flatMap((k) => [Math.abs(m.min[k] - min[k]), Math.abs(m.max[k] - max[k])]))
    if (!best || d < best.d) best = { d, m }
  }
  rows.push({ glb: r.node, ours: best.m.name, d: best.d })
}
rows.sort((a, b) => a.d - b.d)
const bands = [0.01, 0.06, 0.5, 2, Infinity]
for (let i = 0; i < bands.length; i++) {
  const lo = i ? bands[i - 1] : 0
  const sel = rows.filter((r) => r.d >= lo && r.d < bands[i])
  console.log(`\n== max bbox deviation ${lo}" .. ${bands[i]}"  (${sel.length})`)
  for (const r of sel) console.log(`  ${r.d.toFixed(4).padStart(9)}  ${r.glb.padEnd(24)} ~ ${r.ours}`)
}
console.log(`\nour meshes: ${ours.length}, GLB parts: ${rows.length}`)
