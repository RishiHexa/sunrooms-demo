import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import { DEFAULT_PARAMS, buildSlabSection, calloutAnchors } from './slabSection.js'

const host = document.getElementById('app')
const renderer = new THREE.WebGLRenderer({ antialias: true })
renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
renderer.outputColorSpace = THREE.SRGBColorSpace
renderer.toneMapping = THREE.ACESFilmicToneMapping
renderer.toneMappingExposure = 1.15
host.appendChild(renderer.domElement)

const labels = new CSS2DRenderer()
labels.domElement.className = 'label-layer'
host.appendChild(labels.domElement)

const scene = new THREE.Scene()
scene.background = new THREE.Color(0xe9ecef)

const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 500)
const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true
controls.zoomToCursor = true

scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c6, 1.4))
const key = new THREE.DirectionalLight(0xffffff, 2.4)
key.position.set(-14, 26, 22)
key.castShadow = true
key.shadow.mapSize.set(2048, 2048)
key.shadow.camera.left = -14
key.shadow.camera.right = 14
key.shadow.camera.top = 14
key.shadow.camera.bottom = -14
key.shadow.bias = -0.0004
key.shadow.normalBias = 0.02
scene.add(key)
const fill = new THREE.DirectionalLight(0xf3f6ff, 0.6)
fill.position.set(18, 8, -6)
scene.add(fill)

// tiled floor (like the reference photo), the slab stands on it
const tile = document.createElement('canvas')
tile.width = tile.height = 256
{
  const g = tile.getContext('2d')
  g.fillStyle = '#d9dcdc'
  g.fillRect(0, 0, 256, 256)
  for (let k = 0; k < 3000; k++) {
    g.fillStyle = `rgba(120,125,125,${Math.random() * 0.08})`
    g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2)
  }
  g.strokeStyle = 'rgba(150,155,155,0.7)'
  g.lineWidth = 2
  g.strokeRect(0, 0, 256, 256)
}
const tileTex = new THREE.CanvasTexture(tile)
tileTex.colorSpace = THREE.SRGBColorSpace
tileTex.wrapS = tileTex.wrapT = THREE.RepeatWrapping
tileTex.repeat.set(8, 8)
const floor = new THREE.Mesh(new THREE.PlaneGeometry(192, 192), new THREE.MeshStandardMaterial({ map: tileTex, roughness: 0.6 }))
floor.rotation.x = -Math.PI / 2
floor.receiveShadow = true
scene.add(floor)

// ---------------------------------------------------------------------------
const ui = {
  thickness: document.getElementById('thickness'),
  skin: document.getElementById('skin'),
  emboss: document.getElementById('emboss'),
  back: document.getElementById('back'),
  labels: document.getElementById('labels'),
}
const fmt = (v) => `${(+v).toFixed(3).replace(/0+$/, '').replace(/\.$/, '')}"`

let slab = null
let materials
let callouts = []

function params() {
  return {
    ...DEFAULT_PARAMS,
    thickness: +ui.thickness.value,
    skin: +ui.skin.value,
    embossScale: +ui.emboss.value,
    embossBack: ui.back.checked,
  }
}

function rebuild() {
  document.getElementById('thickness-v').textContent = fmt(ui.thickness.value)
  document.getElementById('skin-v').textContent = fmt(ui.skin.value)
  document.getElementById('emboss-v').textContent = `${(+ui.emboss.value).toFixed(2)}×`
  if (slab) {
    scene.remove(slab)
    slab.traverse((o) => o.isMesh && o.geometry.dispose())
  }
  for (const c of callouts) c.element.remove()
  callouts = []

  const p = params()
  const res = buildSlabSection(p, materials)
  materials = res.materials
  slab = res.group
  // stand the piece on the floor, face toward the camera's side
  slab.position.set(-p.width / 2, 0, -p.thickness / 2)
  scene.add(slab)

  if (ui.labels.checked) {
    for (const a of calloutAnchors(p)) {
      const el = document.createElement('div')
      el.className = 'callout'
      el.textContent = a.text
      const obj = new CSS2DObject(el)
      obj.position.copy(a.at)
      // lift labels above the cut face, fanned out
      const lift = { skin: [2.2, 1.2, 3.5], profile: [-0.5, 3.2, 1.5], foam: [2.6, 1.3, -2.5], stile: [-3, 2, -0.5] }[a.key]
      obj.position.add(new THREE.Vector3(...lift))
      obj.center.set(0, 0.5)
      slab.add(obj)
      callouts.push(obj)
      // leader line
      const geo = new THREE.BufferGeometry().setFromPoints([a.at, obj.position.clone()])
      const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0x2b2f36 }))
      line.userData.leader = true
      slab.add(line)
    }
  }
}

function resetView() {
  const p = params()
  controls.target.set(0.5, p.height * 0.7, 0)
  camera.position.set(-7, p.height + 10.5, 16.5)
  controls.update()
}

function resize() {
  const w = host.clientWidth
  const h = host.clientHeight
  renderer.setSize(w, h)
  labels.setSize(w, h)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

function exportGlb() {
  const clone = new THREE.Group()
  slab.traverse((o) => {
    if (o.isMesh) {
      const m = o.clone()
      m.position.add(slab.position)
      clone.add(m)
    }
  })
  new GLTFExporter().parse(
    clone,
    (buf) => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([buf], { type: 'model/gltf-binary' }))
      a.download = 'slab-cross-section.glb'
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 1000)
    },
    (err) => console.error(err),
    { binary: true },
  )
}

for (const el of Object.values(ui)) el.addEventListener('input', rebuild)
document.getElementById('export').addEventListener('click', exportGlb)
document.getElementById('reset').addEventListener('click', resetView)
addEventListener('resize', resize)

rebuild()
resize()
resetView()
renderer.setAnimationLoop(() => {
  controls.update()
  renderer.render(scene, camera)
  labels.render(scene, camera)
})
