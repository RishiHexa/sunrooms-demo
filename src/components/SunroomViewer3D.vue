<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { buildSunroom, disposeGroup } from '../sunroom/build3d.js'
import { applyExplode, prepareExplode, wallExplodeOffset } from '../sunroom/explode.js'
import { SECTIONS_4SEASON } from '../sunroom/spec4season.js'
import { outwardNormal, wallEndpoints, wallLength } from '../floorplan/geometry.js'
import { formatInches, formatMm } from '../floorplan/units.js'
import { useFloorPlan } from '../floorplan/useFloorPlan.js'
import { useWallEditor } from '../floorplan/useWallEditor.js'
import DimensionsPanel from './DimensionsPanel.vue'
import WallElevation from './WallElevation.vue'
import { panelAt, panelRows, rowAt, MAIN_ROLES } from '../sunroom/rows.js'
import { SLIDER_MOTION, easeSlide } from '../sunroom/slider.js'
import { click as drillClick, doubleClick as drillDoubleClick, level as drillLevel, reconcile, up as drillUp } from '../sunroom/drill.js'

const props = defineProps({
  layout: { type: Object, required: true },
  active: { type: Boolean, default: true },
})
const emit = defineEmits(['notes'])

const { plan, unit } = useFloorPlan()
// The wall editor's open wall is the 3D selection (edited in the Dimensions panel).
const { editor, open: selectWall, close: deselectWall, setLength, orientation, lock, house } = useWallEditor()

// Drill-down selection wall -> panel -> row(s) (UI only, sunroom/drill.js). The wall part is the
// wall editor's open wall; panel / rows are kept per wall, so changing the wall resets them.
const drill = ref({ wall: -1, panel: -1, rows: [] })
const selection = computed(() => {
  const wall = editor.open ? editor.wall : -1
  const d = drill.value
  return reconcile(d.wall === wall && wall >= 0 ? d : { wall, panel: -1, rows: [] }, props.layout)
})
const showElevation = computed(() => selection.value.wall >= 0 && !plan.value.walls[selection.value.wall]?.house)
function applyDrill(next) {
  const cur = selection.value
  if (next.wall !== cur.wall) {
    if (next.wall >= 0) selectWall(next.wall)
    else deselectWall()
  }
  drill.value = { wall: next.wall, panel: next.panel, rows: [...next.rows] }
}

const root = ref(null)
let renderer, labelRenderer, scene, camera, controls, sun, ground, model, dims, picks, resizeObserver, frame
let fitted = false

function init() {
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.25
  root.value.appendChild(renderer.domElement)

  // HTML labels (wall dimensions) projected from 3D; only the labels take pointer events
  labelRenderer = new CSS2DRenderer()
  labelRenderer.domElement.className = 'label-layer'
  root.value.appendChild(labelRenderer.domElement)

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xe8eef4)
  scene.fog = new THREE.Fog(0xe8eef4, 1500, 4000)

  camera = new THREE.PerspectiveCamera(40, 1, 1, 10000)
  camera.position.set(300, 220, 400)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.zoomToCursor = true
  controls.maxPolarAngle = Math.PI * 0.495
  controls.minDistance = 20
  controls.maxDistance = 3000

  scene.add(new THREE.HemisphereLight(0xffffff, 0xc8c0b0, 1.6))
  sun = new THREE.DirectionalLight(0xfff8ee, 2.2)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  sun.shadow.bias = -0.0005
  sun.shadow.normalBias = 0.5
  scene.add(sun, sun.target)

  ground = new THREE.Mesh(new THREE.CircleGeometry(3000, 64), new THREE.MeshStandardMaterial({ color: 0xcfd3cc, roughness: 1 }))
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.05
  ground.receiveShadow = true
  scene.add(ground)

  const el = renderer.domElement
  el.addEventListener('pointerdown', onPointerDown)
  el.addEventListener('pointerup', onPointerUp)
  el.addEventListener('pointermove', onPointerMove)
  el.addEventListener('pointerleave', onPointerLeave)
  el.addEventListener('dblclick', onDoubleClick)
  controls.addEventListener('start', cancelFlight) // user takes over the camera
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', onBlur)

  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(root.value)
  resize()
  loop()
}

function resize() {
  const w = root.value.clientWidth
  const h = root.value.clientHeight
  if (!w || !h) return
  renderer.setSize(w, h)
  labelRenderer.setSize(w, h)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

let lastTime = 0
function loop(now = performance.now()) {
  frame = requestAnimationFrame(loop)
  const dt = Math.min((now - (lastTime || now)) / 1000, 0.1)
  lastTime = now
  if (!props.active) return
  stepExplode(dt)
  stepSlides(dt)
  stepFlight(now)
  controls.update()
  renderer.render(scene, camera)
  labelRenderer.render(scene, camera)
}

// ---------------------------------------------------------------------------
// Wall dimensions in 3D (visual; edits go through the shared wall editor)
// ---------------------------------------------------------------------------
const DIM_OFFSET_IN = 30 // dimension line distance from the wall's exterior line, inches
const DIM_HEIGHT_IN = 0.5
const dimMaterial = new THREE.LineBasicMaterial({ color: 0x51627a })

function disposeDims() {
  if (!dims) return
  scene.remove(dims)
  dims.traverse((o) => {
    if (o.isLineSegments) o.geometry.dispose()
    if (o.isCSS2DObject) o.element.remove()
  })
  dims = null
}

function buildDims() {
  disposeDims()
  dims = new THREE.Group()
  dims.name = 'dimensions'
  const p = plan.value
  const pts = []
  const at = (q, y = DIM_HEIGHT_IN) => new THREE.Vector3(q.x, y, q.y)
  p.walls.forEach((w, i) => {
    const [a, b] = wallEndpoints(p, i)
    const n = outwardNormal(p, i)
    // the house wall's outside is inside the house: draw its dimension inside the room
    const k = w.house ? -DIM_OFFSET_IN : DIM_OFFSET_IN
    const a2 = { x: a.x + n.x * k, y: a.y + n.y * k }
    const b2 = { x: b.x + n.x * k, y: b.y + n.y * k }
    const ext = (q) => ({ x: q.x + n.x * Math.sign(k) * 6, y: q.y + n.y * Math.sign(k) * 6 })
    pts.push(at(a2), at(b2)) // dimension line
    pts.push(at(a), at(ext(a2)), at(b), at(ext(b2))) // extension lines

    const el = document.createElement('button')
    el.className = 'dim3d' + (w.house ? ' house' : '') + (editor.open && editor.wall === i ? ' active' : '')
    const len = wallLength(p, i)
    el.textContent = unit.value === 'mm' ? formatMm(len) : formatInches(len)
    el.title = w.house ? 'House wall — select to edit width' : 'Select wall to edit width'
    el.addEventListener('pointerdown', (e) => e.stopPropagation())
    el.addEventListener('click', () => selectWall(i))
    const label = new CSS2DObject(el)
    label.position.copy(at({ x: (a2.x + b2.x) / 2, y: (a2.y + b2.y) / 2 }))
    dims.add(label)
  })
  dims.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), dimMaterial))
  scene.add(dims)
}

// ---------------------------------------------------------------------------
// Wall selection (visual only). Each plan wall gets an invisible pick surface on its exterior
// line, from the floor to the top-of-channel heights the layout computed. Picking uses these
// surfaces rather than the members, so a click through a panel opening selects the wall in
// front instead of a wall behind it, and walls that are not built (errors) stay selectable.
// ---------------------------------------------------------------------------
const pickHidden = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false, side: THREE.DoubleSide })
const pickSelected = new THREE.MeshBasicMaterial({
  color: 0x2c4770, transparent: true, opacity: 0.14, depthWrite: false, side: THREE.DoubleSide,
})
const highlightMats = new Map() // base material -> highlighted clone (per build)
const hoverMats = new Map() // base material -> hover clone (per build)
const raycaster = new THREE.Raycaster()
const ndc = new THREE.Vector2()

function disposePicks() {
  if (!picks) return
  scene.remove(picks)
  picks.traverse((o) => o.isMesh && o.geometry.dispose())
  picks = null
}

function buildPicks() {
  disposePicks()
  picks = new THREE.Group()
  picks.name = 'wall-picks'
  const p = plan.value
  const lay = props.layout
  const fallback = lay.spec.lowWallHeight // visual fallback only, when the layout has no heights
  p.walls.forEach((w, i) => {
    const [a, b] = wallEndpoints(p, i)
    let ha = fallback
    let hb = fallback
    if (w.house && lay.house) {
      ha = hb = lay.house.heightAtHouse
    } else {
      const lw = lay.walls.find((q) => q.index === i)
      if (lw) {
        const aIsLeft = Math.hypot(a.x - lw.origin.x, a.y - lw.origin.y) < 1e-6
        ha = aIsLeft ? lw.topLeft : lw.topRight
        hb = aIsLeft ? lw.topRight : lw.topLeft
      }
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute([
      a.x, 0, a.y, b.x, 0, b.y, b.x, hb, b.y,
      a.x, 0, a.y, b.x, hb, b.y, a.x, ha, a.y,
    ], 3))
    const m = new THREE.Mesh(geo, pickHidden)
    m.userData.wallIndex = i
    m.renderOrder = 10
    picks.add(m)
  })
  scene.add(picks)
}

function highlightOf(mat) {
  if (!highlightMats.has(mat)) {
    const h = mat.clone()
    if (h.emissive) {
      h.emissive.set(0x2c4770)
      h.emissiveIntensity = 0.45
    }
    highlightMats.set(mat, h)
  }
  return highlightMats.get(mat)
}

function hoverOf(mat) {
  if (!hoverMats.has(mat)) {
    const h = mat.clone()
    if (h.emissive) {
      h.emissive.set(0x2f80ed)
      h.emissiveIntensity = 0.6
    }
    hoverMats.set(mat, h)
  }
  return hoverMats.get(mat)
}

const drillMats = new Map() // base material -> drill-selection clone (selected panel / rows)
function drillOf(mat) {
  if (!drillMats.has(mat)) {
    const h = mat.clone()
    if (h.emissive) {
      h.emissive.set(0xe0a100)
      h.emissiveIntensity = 0.55
    }
    if (h.transparent) {
      // glass is nearly clear: tint and thicken it so the selected lite reads
      h.color.set(0xf2c14e)
      h.opacity = Math.max(h.opacity, 0.6)
    }
    drillMats.set(mat, h)
  }
  return drillMats.get(mat)
}

function clearHighlightMats() {
  for (const m of highlightMats.values()) m.dispose()
  highlightMats.clear()
  for (const m of hoverMats.values()) m.dispose()
  hoverMats.clear()
  for (const m of drillMats.values()) m.dispose()
  drillMats.clear()
}

/**
 * Mesh-name test for the drilled panel / rows of the selected wall (names from build3d.js:
 * p<n>-..., lite j glass p<n>-glass-<j+1>[a|b], the main lite's sash / door leaf / solid infill).
 */
function drillMatcher() {
  const s = selection.value
  if (s.panel < 0) return null
  const n = s.panel + 1
  const prefix = `p${n}-`
  if (!s.rows.length) return (name) => name.startsWith(prefix)
  const lw = props.layout.walls.find((w) => w.index === s.wall)
  const p = lw?.panels[s.panel]
  if (!p) return null
  const rows = panelRows(lw, p, props.layout.spec).rows.filter((r) => s.rows.includes(r.role))
  const glass = new Set(rows.map((r) => r.index + 1))
  const main = rows.some((r) => MAIN_ROLES.includes(r.role))
  const mainRe = new RegExp(`^p${n}-(sash|door-leaf|solid-infill|door-handle|sash-handle)`)
  const glassRe = new RegExp(`^p${n}-glass-(\\d+)[ab]?$`)
  return (name) => {
    const g = glassRe.exec(name)
    if (g) return glass.has(Number(g[1]))
    return main && mainRe.test(name)
  }
}

/** Tint the selected wall's members (or the house wall), the hovered component, and show the wall's pick surface. */
function applySelection() {
  if (!model || !picks) return
  const sel = editor.open ? editor.wall : -1
  const houseSelected = sel >= 0 && !!plan.value.walls[sel]?.house
  const drilled = drillMatcher()
  model.traverse((o) => {
    if (!o.isMesh) return
    if (o.userData.baseMaterial === undefined) o.userData.baseMaterial = o.material
    let wallGroup = null
    for (let q = o.parent; q && q !== model; q = q.parent) {
      if (q.name.startsWith('wall-')) wallGroup = q
    }
    const on = (wallGroup && wallGroup.name === `wall-${sel}`) || (houseSelected && o.name === 'house-wall')
    const hovered = hoverKey !== null && !o.userData.context && componentKey(o) === hoverKey
    const base = o.userData.baseMaterial
    const drill = on && wallGroup && drilled && drilled(o.name)
    o.material = hovered ? hoverOf(base) : drill ? drillOf(base) : on ? highlightOf(base) : base
  })
  for (const m of picks.children) m.material = m.userData.wallIndex === sel ? pickSelected : pickHidden
}

function pickAt(e) {
  return pickHit(e)?.wall ?? -1
}

/**
 * Drill hit under the pointer: { wall, panel, role }, or null on empty space. The panel / row
 * come from the hit point on the wall's pick surface mapped to wall-local (s, z) and looked up
 * in the layout openings and rails — selection only, never fed back into any size.
 */
function drillHitAt(e) {
  const h = pickHit(e)
  if (!h) return null
  const lw = props.layout.walls.find((w) => w.index === h.wall)
  if (!lw || !h.point || !lw.panels.length) return { wall: h.wall, panel: -1, role: null }
  const q = h.point.clone().sub(h.object.position) // undo the exploded-view offset
  const s = (q.x - lw.origin.x) * lw.right.x + (q.z - lw.origin.y) * lw.right.y
  const k = panelAt(lw, s, props.layout.spec.panelJoint)
  if (k < 0) return { wall: h.wall, panel: -1, role: null }
  const role = rowAt(panelRows(lw, lw.panels[k], props.layout.spec).rows, q.y)
  return { wall: h.wall, panel: k, role }
}

/** { wall, point, object } of the wall pick surface under the pointer, or null. */
function pickHit(e) {
  if (!picks) return null
  const r = renderer.domElement.getBoundingClientRect()
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
  raycaster.setFromCamera(ndc, camera)
  // the house context mesh is wider than the house wall: it also selects the house wall
  const houseMesh = model?.getObjectByName('house-wall')
  const houseIdx = plan.value.walls.findIndex((w) => w.house)
  const targets = houseMesh && houseIdx >= 0 ? [...picks.children, houseMesh] : picks.children
  const hit = raycaster.intersectObjects(targets, false)[0]
  if (!hit) return null
  if (hit.object === houseMesh) return { wall: houseIdx, point: null, object: hit.object }
  // the roof hides the walls under it: a nearer roof hit wins
  const roof = model?.getObjectByName('roof')
  if (roof) {
    const roofHit = raycaster.intersectObject(roof, true)[0]
    if (roofHit && roofHit.distance < hit.distance - 0.5) return null
  }
  return { wall: hit.object.userData.wallIndex, point: hit.point, object: hit.object }
}

const CLICK_SLOP_PX = 5
let down = null
function onPointerDown(e) {
  down = e.button === 0 ? { x: e.clientX, y: e.clientY } : null
}
function onPointerUp(e) {
  if (!down || e.button !== 0) return
  const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y)
  down = null
  if (moved > CLICK_SLOP_PX) return // orbit drag, not a click
  if (e.shiftKey) {
    const mesh = pickComponent(e)
    if (mesh) isolate(componentKey(mesh), { frame: true })
    return
  }
  if (isolated.value) return // wall selection is off while a component is isolated
  applyDrill(drillClick(selection.value, drillHitAt(e), e.ctrlKey || e.metaKey))
}
// Double-click drills down: wall -> panel -> row (see sunroom/drill.js)
function onDoubleClick(e) {
  if (e.shiftKey || isolated.value) return
  applyDrill(drillDoubleClick(selection.value, drillHitAt(e)))
}
// ---------------------------------------------------------------------------
// Hover: while Shift is held, the component under the cursor (what Shift+click would isolate)
// is highlighted. Visual only.
// ---------------------------------------------------------------------------
let hoverKey = null
let lastPointer = null // { clientX, clientY } of the last move over the canvas
let shiftDown = false
let hoverQueued = false

function setHover(key) {
  if (key === hoverKey) return
  hoverKey = key
  applySelection()
}
function updateHover() {
  if (!renderer || !lastPointer) return
  const mesh = shiftDown ? pickComponent(lastPointer) : null
  setHover(mesh ? componentKey(mesh) : null)
  const over = shiftDown ? !!mesh : !isolated.value && pickAt(lastPointer) >= 0
  renderer.domElement.style.cursor = over ? 'pointer' : ''
}
function onPointerMove(e) {
  shiftDown = e.shiftKey
  if (e.buttons) {
    // orbit / pan drag: no hover feedback
    setHover(null)
    return
  }
  lastPointer = { clientX: e.clientX, clientY: e.clientY }
  if (hoverQueued) return
  hoverQueued = true
  requestAnimationFrame(() => {
    hoverQueued = false
    updateHover()
  })
}
function onPointerLeave() {
  lastPointer = null
  setHover(null)
}
function onKeyDown(e) {
  if (e.key === 'Escape' && props.active) {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName ?? '')
    if (isolated.value) exitIsolation()
    else if (!typing && drillLevel(selection.value) !== 'none') applyDrill(drillUp(selection.value))
  }
  if (e.key === 'Shift' && !shiftDown && props.active) {
    shiftDown = true
    updateHover()
  }
}
function onKeyUp(e) {
  if (e.key === 'Shift') {
    shiftDown = false
    updateHover()
  }
}
function onBlur() {
  shiftDown = false // a Shift released outside the window never sends keyup here
  setHover(null)
}

// ---------------------------------------------------------------------------
// Component isolation (Shift+click) — visual only. A component is one built mesh, or the meshes
// sharing userData.component (a roof panel's skins + foam). The info shown is identification
// only (names, part codes, wall/panel numbers); no dimensions are read from the geometry.
// ---------------------------------------------------------------------------
const isolated = ref(null) // { key, title, part, where } | null
let isolatedMeshes = []
let savedView = null // camera before isolating, restored on exit

/** Top-level group under the model ('wall-2', 'corner-3', 'roof'), or '' for direct meshes. */
function topGroupOf(o) {
  let q = o
  while (q.parent && q.parent !== model) q = q.parent
  return q === o ? '' : q.name
}
function componentKey(mesh) {
  return `${topGroupOf(mesh)}/${mesh.userData.component ?? mesh.name}`
}
function isShown(o) {
  for (let q = o; q; q = q.parent) if (!q.visible) return false
  return true
}

function pickComponent(e) {
  if (!model) return null
  const r = renderer.domElement.getBoundingClientRect()
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
  raycaster.setFromCamera(ndc, camera)
  // the raycaster ignores visibility: skip hidden meshes (isolation) and the house context
  const hit = raycaster.intersectObject(model, true).find((h) => h.object.isMesh && !h.object.userData.context && isShown(h.object))
  return hit ? hit.object : null
}

const PART_NAMES = [
  [/^p\d+-left-male$/, 'Left male'],
  [/^p\d+-right-male$/, 'Right male'],
  [/^p\d+-right-female$/, 'Right female'],
  [/^p\d+-receiver-bottom$/, 'Bottom receiver'],
  [/^p\d+-receiver-top$/, 'Top receiver'],
  [/^p\d+-knee-rail$/, 'Knee rail'],
  [/^p\d+-header-rail$/, 'Header rail'],
  [/^p\d+-transom-rail$/, 'Transom rail'],
  [/^p\d+-door-header-rail$/, 'Door header'],
  [/^p\d+-(door|sash)-handle$/, 'Handle (visual)'],
  [/^p\d+-glass-/, 'Glass (visual)'],
  [/^p\d+-sash/, 'Sash (visual)'],
  [/^p\d+-door-leaf$/, 'Door leaf (visual)'],
  [/^p\d+-solid-infill$/, 'Solid infill (visual)'],
  [/^bottom-channel$/, 'Bottom channel'],
  [/^top-channel$/, 'Top channel'],
  [/^wall-channel-left$/, 'Wall channel (left)'],
  [/^wall-channel-right$/, 'Wall channel (right)'],
  [/^corner-post$/, 'Corner post'],
  [/^inside-corner$/, 'Inside corner'],
  [/^gutter$/, 'Gutter'],
  [/^back-channel$/, 'Roof back channel'],
  [/^fascia-left$/, 'Fascia (left)'],
  [/^fascia-right$/, 'Fascia (right)'],
  [/^wedge-wall-\d+$/, 'Wood wedge'],
]
function describe(mesh) {
  const u = mesh.userData
  const group = topGroupOf(mesh)
  let title = PART_NAMES.find(([re]) => re.test(mesh.name))?.[1] ?? mesh.name
  if (u.roofPanel) title = `Roof panel ${u.roofPanel}`
  else if (u.seamAfter) title = `Roof seam ${u.seamAfter}`
  const where = []
  const wm = /^wall-(\d+)$/.exec(group)
  if (wm) where.push(`Wall ${Number(wm[1]) + 1}`)
  if (u.panel) where.push(`Panel ${u.panel}`)
  if (group.startsWith('corner-')) where.push('Corner')
  if (group === 'roof') where.push('Roof')
  return { title, part: u.part ?? null, where: where.join(' · ') }
}

/** Show only the meshes of `key`. Returns false (and changes nothing) if none exist. */
function isolate(key, { frame = false } = {}) {
  if (!model) return false
  const meshes = []
  model.traverse((o) => o.isMesh && componentKey(o) === key && meshes.push(o))
  if (!meshes.length) return false
  if (!isolated.value) savedView = { position: camera.position.clone(), target: controls.target.clone() }
  model.traverse((o) => {
    if (o.isMesh) o.visible = meshes.includes(o)
  })
  isolatedMeshes = meshes
  isolated.value = { key, ...describe(meshes[0]) }
  updateOverlays()
  if (frame) frameObjects(meshes, true)
  return true
}

function exitIsolation() {
  if (!isolated.value) return
  model?.traverse((o) => {
    if (o.isMesh) o.visible = true
  })
  isolatedMeshes = []
  isolated.value = null
  updateOverlays()
  if (savedView) flyTo(savedView.position, savedView.target)
  savedView = null
}

/** Dimensions and wall pick surfaces only make sense on the assembled, un-isolated model. */
function updateOverlays() {
  if (dims) dims.visible = !isolated.value && explodeT === 0
  if (picks) picks.visible = !isolated.value
}

// ---------------------------------------------------------------------------
// Exploded view (visual only; offsets from sunroom/explode.js, animated)
// ---------------------------------------------------------------------------
const EXPLODE_SECONDS = 0.45
const exploded = ref(false)
let explodeT = 0 // animated 0..1
const pickOffset = new THREE.Vector3()

function toggleExplode() {
  exploded.value = !exploded.value
}
const ease = (x) => (x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2)
let explodeLinear = 0 // un-eased progress
function stepExplode(dt) {
  const goal = exploded.value ? 1 : 0
  if (explodeLinear === goal) return
  explodeLinear = goal > explodeLinear ? Math.min(1, explodeLinear + dt / EXPLODE_SECONDS) : Math.max(0, explodeLinear - dt / EXPLODE_SECONDS)
  explodeT = ease(explodeLinear)
  applyExplodeNow()
}
function applyExplodeNow() {
  if (!model) return
  applyExplode(model, explodeT)
  // wall pick surfaces travel with their walls so wall selection keeps working while exploded
  if (picks) for (const m of picks.children) m.position.copy(wallExplodeOffset(model, m.userData.wallIndex, explodeT, pickOffset))
  updateOverlays()
}

// ---------------------------------------------------------------------------
// Slider windows open / close (visual only; motion rule from the 225 slider macros, see
// sunroom/slider.js). build3d.js puts each movable interior sash in a group carrying
// userData.slide = { dir, travel }; the sash meshes inside it are moved along dir.
// Key = `${wallIndex}:${panelIndex}` (panel index 0-based, left -> right seen from outside).
// ---------------------------------------------------------------------------
const slideGoals = ref({}) // key -> true when the window should be open
const slidable = ref([]) // keys of the sliders in the current build that can move
const slideProgress = new Map() // key -> un-eased progress 0..1
let sliders = [] // [{ key, group }] of the current build

function collectSliders() {
  sliders = []
  model?.traverse((o) => {
    if (!o.userData.slide) return
    const wm = /^wall-(\d+)$/.exec(o.parent?.name ?? '')
    if (wm) sliders.push({ key: `${wm[1]}:${o.userData.panel - 1}`, group: o })
  })
  slidable.value = sliders.map((s) => s.key)
  // forget windows that are no longer sliders (type changed, panel removed)
  const keep = new Set(slidable.value)
  const goals = Object.fromEntries(Object.entries(slideGoals.value).filter(([k]) => keep.has(k)))
  if (Object.keys(goals).length !== Object.keys(slideGoals.value).length) slideGoals.value = goals
  for (const k of [...slideProgress.keys()]) if (!keep.has(k)) slideProgress.delete(k)
}
function applySlides() {
  for (const { key, group } of sliders) {
    const { dir, travel } = group.userData.slide
    const x = travel * easeSlide(slideProgress.get(key) ?? 0)
    for (const m of group.children) m.position.copy(dir).multiplyScalar(x)
  }
}
function stepSlides(dt) {
  let moved = false
  for (const { key } of sliders) {
    const goal = slideGoals.value[key] ? 1 : 0
    const x = slideProgress.get(key) ?? 0
    if (x === goal) continue
    const step = dt / SLIDER_MOTION.seconds
    slideProgress.set(key, goal > x ? Math.min(1, x + step) : Math.max(0, x - step))
    moved = true
  }
  if (moved) applySlides()
}
function setSlide(key, open) {
  slideGoals.value = { ...slideGoals.value, [key]: open }
}
const anySliderClosed = computed(() => slidable.value.some((k) => !slideGoals.value[k]))
function toggleAllSliders() {
  const open = anySliderClosed.value
  slideGoals.value = Object.fromEntries(slidable.value.map((k) => [k, open]))
}

// ---------------------------------------------------------------------------
// Camera flights (fit / isolate / restore)
// ---------------------------------------------------------------------------
const FLIGHT_MS = 380
let flight = null
function flyTo(position, target) {
  flight = {
    p0: camera.position.clone(), p1: position.clone(),
    t0: controls.target.clone(), t1: target.clone(),
    start: performance.now(),
  }
}
function cancelFlight() {
  flight = null
}
function stepFlight(now) {
  if (!flight) return
  const k = Math.min(1, (now - flight.start) / FLIGHT_MS)
  const e = ease(k)
  camera.position.lerpVectors(flight.p0, flight.p1, e)
  controls.target.lerpVectors(flight.t0, flight.t1, e)
  if (k >= 1) flight = null
}

/** Frame a set of meshes keeping the current viewing direction. */
function frameObjects(objects, animate) {
  model.updateMatrixWorld(true)
  const box = new THREE.Box3()
  for (const o of objects) box.expandByObject(o)
  if (box.isEmpty()) return
  const c = box.getCenter(new THREE.Vector3())
  const r = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 6)
  // bounding-sphere fit with a margin, so long thin members (posts, channels) are not cropped
  const dist = Math.max((r / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.15, controls.minDistance)
  const dir = camera.position.clone().sub(controls.target).normalize()
  const pos = c.clone().addScaledVector(dir, dist)
  camera.near = Math.max(Math.min(dist / 200, camera.near), 0.1)
  camera.far = Math.max(camera.far, dist * 20)
  camera.updateProjectionMatrix()
  if (animate) flyTo(pos, c)
  else {
    cancelFlight()
    controls.target.copy(c)
    camera.position.copy(pos)
    controls.update()
  }
}

function rebuild() {
  if (model) {
    scene.remove(model)
    disposeGroup(model)
    model = null
  }
  clearHighlightMats()
  const { group, notes } = buildSunroom(props.layout, SECTIONS_4SEASON)
  model = group
  scene.add(model)
  buildDims()
  buildPicks()
  applySelection()
  emit('notes', notes)

  // light + shadow camera around the assembled model (before explode offsets are applied)
  const box = new THREE.Box3().setFromObject(model)
  const c = box.getCenter(new THREE.Vector3())
  const r = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 50)
  sun.position.set(c.x + r * 0.8, c.y + r * 1.6, c.z + r * 1.1)
  sun.target.position.copy(c)
  const sc = sun.shadow.camera
  sc.left = -r * 1.3
  sc.right = r * 1.3
  sc.top = r * 1.3
  sc.bottom = -r * 1.3
  sc.near = 1
  sc.far = r * 6
  sc.updateProjectionMatrix()

  // keep the exploded state and the isolated component across layout edits
  prepareExplode(model, props.layout)
  applyExplodeNow()
  // keep open windows open across layout edits
  collectSliders()
  applySlides()
  if (isolated.value) {
    const key = isolated.value.key
    if (!isolate(key)) {
      // the component no longer exists in the new layout (e.g. a panel was removed)
      isolated.value = { key, title: '', part: null, where: '' } // so exitIsolation restores the camera
      exitIsolation()
    }
  }

  if (!fitted) {
    fitted = true
    fit()
  }
}

function fit() {
  if (!model) return
  if (isolated.value) return frameObjects(isolatedMeshes, true)
  const box = new THREE.Box3()
  model.traverse((o) => {
    if (o.isMesh && !o.userData.context) box.expandByObject(o)
  })
  if (box.isEmpty()) box.setFromObject(model)
  const c = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const r = size.length() / 2
  const dist = r / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 0.9
  // view from the outside, opposite the house wall
  const h = props.layout.house
  const out = h ? new THREE.Vector3(h.eout.x, 0, h.eout.y) : new THREE.Vector3(0, 0, 1)
  const side = new THREE.Vector3(h ? h.ea.x : 1, 0, h ? h.ea.y : 0)
  const dir = out.multiplyScalar(0.8).addScaledVector(side, 0.55).add(new THREE.Vector3(0, 0.45, 0)).normalize()
  controls.target.copy(c)
  camera.position.copy(c).addScaledVector(dir, dist)
  camera.near = Math.max(dist / 200, 0.5)
  camera.far = dist * 20
  camera.updateProjectionMatrix()
  controls.update()
}

let pending = false
watch(
  () => props.layout,
  () => {
    if (pending) return
    pending = true
    requestAnimationFrame(() => {
      pending = false
      if (renderer) rebuild()
    })
  },
)
watch(
  () => props.active,
  (a) => {
    if (a) requestAnimationFrame(resize)
  },
)
// label text follows the unit; label + wall highlight follow the selection
watch([unit, () => editor.open, () => editor.wall, selection], () => {
  if (renderer && model) {
    buildDims()
    applySelection()
    updateOverlays()
  }
})

onMounted(() => {
  init()
  rebuild()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  resizeObserver?.disconnect()
  renderer?.domElement.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement.removeEventListener('pointerup', onPointerUp)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  renderer?.domElement.removeEventListener('dblclick', onDoubleClick)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', onBlur)
  disposeDims()
  disposePicks()
  clearHighlightMats()
  pickHidden.dispose()
  pickSelected.dispose()
  labelRenderer?.domElement.remove()
  if (model) disposeGroup(model)
  controls?.dispose()
  renderer?.dispose()
  renderer?.domElement.remove()
})

defineExpose({ fit })
</script>

<template>
  <div ref="root" class="viewer">
    <DimensionsPanel
      class="panel"
      :layout="layout"
      :unit="unit"
      :wall="editor.open ? editor.wall : -1"
      :wall-error="editor.error"
      @width="setLength"
      @orientation="orientation"
      @lock="lock"
      @house="house"
      @close="deselectWall"
    />
    <div class="tools">
      <button class="tool" title="Fit to view" @click="fit">
        <svg viewBox="0 0 24 24">
          <path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4" />
          <rect x="8" y="9" width="8" height="6" rx="1" />
        </svg>
      </button>
      <button
        class="tool"
        :class="{ on: exploded }"
        :title="exploded ? 'Assembled view' : 'Exploded view'"
        :aria-pressed="exploded"
        @click="toggleExplode"
      >
        <svg viewBox="0 0 24 24">
          <rect x="9.5" y="9.5" width="5" height="5" rx="0.8" />
          <path d="M12 2.5v4M10.5 4 12 2.5 13.5 4M12 21.5v-4M10.5 20l1.5 1.5 1.5-1.5M2.5 12h4M4 10.5 2.5 12 4 13.5M21.5 12h-4M20 10.5l1.5 1.5-1.5 1.5" />
        </svg>
      </button>
      <button
        class="tool"
        :class="{ on: slidable.length && !anySliderClosed }"
        :disabled="!slidable.length"
        :title="!slidable.length ? 'No sliding windows to open (choose Slider for a panel)' : anySliderClosed ? 'Open all sliding windows' : 'Close all sliding windows'"
        :aria-pressed="slidable.length > 0 && !anySliderClosed"
        @click="toggleAllSliders"
      >
        <svg viewBox="0 0 24 24">
          <rect x="3.5" y="5" width="17" height="14" rx="1" />
          <path d="M12 5v14M14.5 12h4M16.5 10l2 2-2 2" />
        </svg>
      </button>
    </div>

    <div v-if="isolated" class="isolation" role="status">
      <span class="iso-tag">Isolated</span>
      <span class="iso-title">{{ isolated.title }}</span>
      <span v-if="isolated.part" class="iso-part">{{ isolated.part }}</span>
      <span v-if="isolated.where" class="iso-where">{{ isolated.where }}</span>
      <button class="iso-exit" title="Show all (Esc)" @click="exitIsolation">
        Show all
        <kbd>Esc</kbd>
      </button>
    </div>
    <WallElevation
      v-if="showElevation && !isolated"
      class="elev-dock"
      :layout="layout"
      :unit="unit"
      :selection="selection"
      :slidable="slidable"
      :slide-goals="slideGoals"
      @select="applyDrill"
      @slide="setSlide"
    />
    <div v-else-if="!isolated" class="hint">Click a wall to select it · double-click to drill into panels and rows · <kbd>Shift</kbd> + click a part to isolate it</div>
  </div>
</template>

<style scoped>
.viewer {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.viewer :deep(canvas) {
  display: block;
}
.viewer :deep(.label-layer) {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.viewer :deep(.dim3d) {
  pointer-events: auto;
  border: 1px solid #c9d1dc;
  background: rgba(255, 255, 255, 0.92);
  color: #1f2328;
  font: 600 12px/1 Roboto, 'Segoe UI', system-ui, sans-serif;
  padding: 4px 7px;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}
.viewer :deep(.dim3d:hover),
.viewer :deep(.dim3d.active) {
  border-color: var(--brand);
  box-shadow: 0 0 0 1px var(--brand);
}
.viewer :deep(.dim3d.house) {
  color: #5b6472;
  background: rgba(238, 240, 243, 0.92);
}
.panel {
  position: absolute;
  top: 12px;
  right: 12px;
  max-height: calc(100% - 72px); /* clear the 2D/3D toggle at the bottom right */
  z-index: 6;
}
.tools {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.tool {
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: var(--brand);
}
.tool:hover {
  background: #eef2f8;
}
.tool.on {
  background: var(--brand);
  color: #fff;
}
.tool:disabled {
  color: #b5bac1;
  background: transparent;
  cursor: default;
}
.isolation {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  max-width: calc(100% - 140px);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 5px 5px 10px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(20, 30, 50, 0.08);
  font: 13px/1.2 Roboto, 'Segoe UI', system-ui, sans-serif;
  color: #1f2328;
  z-index: 5;
  white-space: nowrap;
}
.iso-tag {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--brand);
}
.iso-title {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}
.iso-part {
  padding: 2px 6px;
  border-radius: 4px;
  background: #eef2f8;
  color: var(--brand);
  font-weight: 600;
  font-size: 12px;
}
.iso-where {
  color: #5b6472;
}
.iso-exit {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: #fff;
  color: var(--brand);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.iso-exit:hover {
  background: #eef2f8;
}
kbd {
  font: 600 10px/1 Roboto, 'Segoe UI', system-ui, sans-serif;
  padding: 2px 4px;
  border: 1px solid #c9d1dc;
  border-bottom-width: 2px;
  border-radius: 3px;
  background: #f6f7f9;
  color: #5b6472;
}
.elev-dock {
  position: absolute;
  left: 12px;
  right: 304px; /* clear the Dimensions panel (280px + gutters) */
  bottom: 12px;
  z-index: 5;
}
.hint {
  position: absolute;
  left: 12px;
  bottom: 12px;
  font: 12px/1 Roboto, 'Segoe UI', system-ui, sans-serif;
  color: #5b6472;
  pointer-events: none;
}
.tool svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
