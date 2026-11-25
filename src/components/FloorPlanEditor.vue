<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useFloorPlan } from '../floorplan/useFloorPlan.js'
import { useWallEditor } from '../floorplan/useWallEditor.js'
import {
  bounds,
  interiorAngle,
  moveVertex,
  outwardNormal,
  snap,
  snapToRightAngles,
  splitWall,
  toggleLock,
  toggleOrientation,
  wallEndpoints,
  wallLength,
} from '../floorplan/geometry.js'
import { formatAngle, formatInches, formatMm, toFractionParts } from '../floorplan/units.js'
import DimensionEditor from './DimensionEditor.vue'
import ConstraintToggles from './ConstraintToggles.vue'
import { useSunroom } from '../sunroom/useSunroom.js'

const { plan, unit, canUndo, canRedo, commit, preview, commitFrom, undo, redo } = useFloorPlan()
const { layout } = useSunroom()
const wallNames = computed(() => new Map(layout.value.walls.map((w) => [w.index, w.name])))

// ---------------------------------------------------------------------------
// View transform (screen px = inches * scale + offset). Visual only.
// ---------------------------------------------------------------------------
const root = ref(null)
const size = reactive({ w: 0, h: 0 })
const view = reactive({ scale: 4, tx: 0, ty: 0 })
const MIN_SCALE = 0.3
const MAX_SCALE = 40
const FIT_MARGIN_PX = 150
const FIT_FRACTION = 0.6

const DIM_OFFSET_PX = 65 // distance of dimension line from the wall
const TOGGLE_GAP_PX = 16 // gap between a dimension label and its constraint toggles
const ARC_RADIUS_PX = 30

const toScreen = (p) => ({ x: p.x * view.scale + view.tx, y: p.y * view.scale + view.ty })
const toWorld = (sx, sy) => ({ x: (sx - view.tx) / view.scale, y: (sy - view.ty) / view.scale })

function fitToView() {
  if (!size.w || !size.h) return
  const b = bounds(plan.value)
  const bw = Math.max(b.maxX - b.minX, 1)
  const bh = Math.max(b.maxY - b.minY, 1)
  // Leave room for dimension lines/toggles, and keep the shape at most ~60% of the view.
  const availW = Math.max(Math.min(size.w - FIT_MARGIN_PX * 2, size.w * FIT_FRACTION), 50)
  const availH = Math.max(Math.min(size.h - FIT_MARGIN_PX * 2, size.h * FIT_FRACTION), 50)
  view.scale = Math.min(Math.max(Math.min(availW / bw, availH / bh), MIN_SCALE), MAX_SCALE)
  view.tx = size.w / 2 - ((b.minX + b.maxX) / 2) * view.scale
  view.ty = size.h / 2 - ((b.minY + b.maxY) / 2) * view.scale
}

let resizeObserver
let fitted = false
onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    size.w = entry.contentRect.width
    size.h = entry.contentRect.height
    if (!fitted && size.w && size.h) {
      fitted = true
      fitToView()
    }
  })
  resizeObserver.observe(root.value)
  window.addEventListener('keydown', onKeyDown)
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('keydown', onKeyDown)
  endPointer()
})

// ---------------------------------------------------------------------------
// Derived drawing data
// ---------------------------------------------------------------------------
const screenVertices = computed(() => plan.value.vertices.map(toScreen))

const polygonPoints = computed(() => screenVertices.value.map((p) => `${p.x},${p.y}`).join(' '))

function fractionLabel(inches) {
  const { negative, whole, num, den } = toFractionParts(inches)
  return { negative, whole, num, den }
}

const walls = computed(() => {
  const p = plan.value
  return p.walls.map((wall, i) => {
    const [wa, wb] = wallEndpoints(p, i)
    const a = toScreen(wa)
    const b = toScreen(wb)
    const n = outwardNormal(p, i)
    const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
    const off = (pt, d) => ({ x: pt.x + n.x * d, y: pt.y + n.y * d })
    const horizontalish = Math.abs(b.x - a.x) >= Math.abs(b.y - a.y)
    const lengthIn = wallLength(p, i)
    // Push the toggles clear of the label: project the label's half-size onto the normal.
    const labelText = unit.value === 'mm' ? formatMm(lengthIn) : formatInches(lengthIn)
    const labelHalfW = labelText.length * 3.6 + 4
    const toggleOffset = DIM_OFFSET_PX + Math.abs(n.x) * labelHalfW + Math.abs(n.y) * 9 + TOGGLE_GAP_PX
    return {
      index: i,
      wall,
      a,
      b,
      mid,
      screenLength: Math.hypot(b.x - a.x, b.y - a.y),
      lengthIn,
      dimA: off(a, DIM_OFFSET_PX),
      dimB: off(b, DIM_OFFSET_PX),
      extA: [off(a, 6), off(a, DIM_OFFSET_PX + 8)],
      extB: [off(b, 6), off(b, DIM_OFFSET_PX + 8)],
      label: off(mid, DIM_OFFSET_PX),
      toggles: off(mid, toggleOffset),
      togglesLayout: horizontalish ? 'row' : 'column',
      fraction: fractionLabel(lengthIn),
      mm: formatMm(lengthIn),
      name: wall.house ? 'House' : wallNames.value.get(i) ?? '',
      nameAt: off(mid, -24),
    }
  })
})

const houseWalls = computed(() => walls.value.filter((w) => w.wall.house))

const angles = computed(() => {
  const p = plan.value
  const sv = screenVertices.value
  const n = sv.length
  return sv.map((cur, i) => {
    const prev = sv[(i - 1 + n) % n]
    const next = sv[(i + 1) % n]
    const deg = interiorAngle(p, i)
    const tPrev = Math.atan2(prev.y - cur.y, prev.x - cur.x)
    const tNext = Math.atan2(next.y - cur.y, next.x - cur.x)
    const rad = (deg * Math.PI) / 180
    // Pick the sweep direction that walks from "next" to "prev" through the interior.
    const norm = (a) => Math.atan2(Math.sin(a), Math.cos(a))
    const positive = Math.abs(norm(tNext + rad - tPrev)) < 1e-6
    const dirSign = positive ? 1 : -1
    const R = ARC_RADIUS_PX
    const start = { x: cur.x + Math.cos(tNext) * R, y: cur.y + Math.sin(tNext) * R }
    const end = { x: cur.x + Math.cos(tPrev) * R, y: cur.y + Math.sin(tPrev) * R }
    const largeArc = deg > 180 ? 1 : 0
    const sweep = positive ? 1 : 0
    const bis = tNext + (dirSign * rad) / 2
    const labelR = R + 4
    return {
      index: i,
      path: `M ${start.x} ${start.y} A ${R} ${R} 0 ${largeArc} ${sweep} ${end.x} ${end.y}`,
      label: { x: cur.x + Math.cos(bis) * labelR, y: cur.y + Math.sin(bis) * labelR },
      text: formatAngle(deg),
    }
  })
})

// Background grid (visual only), step chosen so cells stay readable.
const grid = computed(() => {
  const steps = [3, 6, 12, 24, 48, 120, 240, 480]
  const stepIn = steps.find((s) => s * view.scale >= 22) ?? steps[steps.length - 1]
  const px = stepIn * view.scale
  return { px, ox: ((view.tx % px) + px) % px, oy: ((view.ty % px) + px) % px }
})

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------
const message = ref('')
let messageTimer
function flash(text) {
  message.value = text
  clearTimeout(messageTimer)
  messageTimer = setTimeout(() => (message.value = ''), 2800)
}

function apply(result) {
  if (result.ok) {
    commit(result.plan)
    return true
  }
  flash(result.error)
  return false
}

// ---------------------------------------------------------------------------
// Pointer interaction: vertex drag, background pan
// ---------------------------------------------------------------------------
let pointer = null // { kind: 'vertex'|'pan', ... }

function localPoint(e) {
  const r = root.value.getBoundingClientRect()
  return { x: e.clientX - r.left, y: e.clientY - r.top }
}

function onVertexDown(i, e) {
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()
  closeEditor()
  const start = localPoint(e)
  const v = plan.value.vertices[i]
  const sv = toScreen(v)
  pointer = {
    kind: 'vertex',
    index: i,
    before: JSON.parse(JSON.stringify(plan.value)),
    grab: { x: start.x - sv.x, y: start.y - sv.y },
    lastError: null,
  }
  beginPointer()
}

function onBackgroundDown(e) {
  if (e.button !== 0 && e.button !== 1) return
  closeEditor()
  const start = localPoint(e)
  pointer = { kind: 'pan', start, tx: view.tx, ty: view.ty }
  beginPointer()
}

function beginPointer() {
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function endPointer() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
  pointer = null
}

function onPointerMove(e) {
  if (!pointer) return
  const p = localPoint(e)
  if (pointer.kind === 'pan') {
    view.tx = pointer.tx + (p.x - pointer.start.x)
    view.ty = pointer.ty + (p.y - pointer.start.y)
    return
  }
  // Always solve from the plan as it was at drag start: deterministic, no drift.
  const w = toWorld(p.x - pointer.grab.x, p.y - pointer.grab.y)
  let target = { x: snap(w.x), y: snap(w.y) }
  // Nearly-square corners snap exactly square (hold Alt to drag freely).
  if (!e.altKey) target = snapToRightAngles(pointer.before, pointer.index, target)
  const res = moveVertex(pointer.before, pointer.index, target)
  if (res.ok) {
    preview(res.plan)
    pointer.lastError = null
  } else {
    pointer.lastError = res.error
  }
}

function onPointerUp() {
  if (pointer?.kind === 'vertex') {
    commitFrom(pointer.before)
    if (pointer.lastError) flash(pointer.lastError)
  }
  endPointer()
}

function onWheel(e) {
  e.preventDefault()
  const p = localPoint(e)
  const before = toWorld(p.x, p.y)
  const factor = Math.exp(-e.deltaY * 0.0015)
  view.scale = Math.min(Math.max(view.scale * factor, MIN_SCALE), MAX_SCALE)
  view.tx = p.x - before.x * view.scale
  view.ty = p.y - before.y * view.scale
}

// ---------------------------------------------------------------------------
// Wall actions
// ---------------------------------------------------------------------------
function onSplit(i) {
  closeEditor()
  apply(splitWall(plan.value, i))
}

function onToggleOrientation(i, o) {
  apply(toggleOrientation(plan.value, i, o))
}

function onToggleLock(i) {
  apply(toggleLock(plan.value, i))
}

// ---------------------------------------------------------------------------
// Dimension editor
// ---------------------------------------------------------------------------
const {
  editor,
  open: openEditor,
  close: closeEditor,
  submit: submitEditor,
  orientation: editorOrientation,
  lock: editorLock,
  house: editorHouse,
} = useWallEditor()

const editorWall = computed(() => (editor.open ? walls.value[editor.wall] : null))

// ---------------------------------------------------------------------------
// Keyboard
// ---------------------------------------------------------------------------
function onKeyDown(e) {
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  const ctrl = e.ctrlKey || e.metaKey
  if (ctrl && e.key.toLowerCase() === 'z' && !e.shiftKey) {
    e.preventDefault()
    undo()
  } else if (ctrl && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
    e.preventDefault()
    redo()
  } else if (e.key === 'Escape') {
    closeEditor()
  }
}

function onUndo() {
  closeEditor()
  undo()
}
function onRedo() {
  closeEditor()
  redo()
}
function onFit() {
  nextTick(fitToView)
}
</script>

<template>
  <div ref="root" class="plan" @wheel="onWheel">
    <svg class="plan-svg" :width="size.w" :height="size.h" @pointerdown="onBackgroundDown">
      <defs>
        <pattern
          id="plan-grid"
          patternUnits="userSpaceOnUse"
          :width="grid.px"
          :height="grid.px"
          :x="grid.ox"
          :y="grid.oy"
        >
          <path :d="`M ${grid.px} 0 L 0 0 0 ${grid.px}`" fill="none" class="grid-line" />
        </pattern>
      </defs>
      <rect x="0" y="0" :width="size.w" :height="size.h" fill="url(#plan-grid)" />

      <!-- dimension lines -->
      <g class="dims">
        <g v-for="w in walls" :key="'d' + w.index">
          <line :x1="w.extA[0].x" :y1="w.extA[0].y" :x2="w.extA[1].x" :y2="w.extA[1].y" />
          <line :x1="w.extB[0].x" :y1="w.extB[0].y" :x2="w.extB[1].x" :y2="w.extB[1].y" />
          <line :x1="w.dimA.x" :y1="w.dimA.y" :x2="w.dimB.x" :y2="w.dimB.y" />
        </g>
      </g>

      <!-- angle arcs -->
      <g class="arcs">
        <path v-for="a in angles" :key="'a' + a.index" :d="a.path" />
      </g>

      <!-- walls -->
      <polygon class="walls" :points="polygonPoints" />
      <line
        v-for="w in houseWalls"
        :key="'h' + w.index"
        class="house-line"
        :x1="w.a.x"
        :y1="w.a.y"
        :x2="w.b.x"
        :y2="w.b.y"
      />

      <!-- vertex handles -->
      <g class="handles">
        <rect
          v-for="(v, i) in screenVertices"
          :key="'v' + i"
          :x="v.x - 4.5"
          :y="v.y - 4.5"
          width="9"
          height="9"
          @pointerdown="onVertexDown(i, $event)"
        />
      </g>
    </svg>

    <!-- HTML overlay: labels and buttons -->
    <div class="overlay">
      <div
        v-for="a in angles"
        :key="'al' + a.index"
        class="angle-label"
        :style="{ left: a.label.x + 'px', top: a.label.y + 'px' }"
      >
        {{ a.text }}
      </div>

      <template v-for="w in walls" :key="'w' + w.index">
        <div
          v-if="w.name && w.screenLength > 70"
          class="wall-name"
          :class="{ house: w.wall.house }"
          :style="{ left: w.nameAt.x + 'px', top: w.nameAt.y + 'px' }"
        >
          {{ w.name }}
        </div>
        <button
          v-if="w.screenLength > 36 && !w.wall.house"
          class="split-btn"
          title="Add corner"
          :style="{ left: w.mid.x + 'px', top: w.mid.y + 'px' }"
          @pointerdown.stop
          @click="onSplit(w.index)"
        >
          +
        </button>

        <button
          class="dim-label"
          :class="{ active: editor.wall === w.index }"
          title="Edit length"
          :style="{ left: w.label.x + 'px', top: w.label.y + 'px' }"
          @pointerdown.stop
          @click="openEditor(w.index)"
        >
          <template v-if="unit === 'mm'">{{ w.mm }}</template>
          <template v-else>
            <span v-if="w.fraction.negative">-</span>
            <span v-if="w.fraction.whole || !w.fraction.num">{{ w.fraction.whole }}</span>
            <span v-if="w.fraction.num" class="frac"><sup>{{ w.fraction.num }}</sup>/<sub>{{ w.fraction.den }}</sub></span>"
          </template>
        </button>

        <ConstraintToggles
          class="wall-toggles"
          :style="{ left: w.toggles.x + 'px', top: w.toggles.y + 'px' }"
          :layout="w.togglesLayout"
          :orientation="w.wall.orientation"
          :locked="w.wall.locked"
          :show-lock="w.wall.locked"
          @pointerdown.stop
          @orientation="(o) => onToggleOrientation(w.index, o)"
          @lock="onToggleLock(w.index)"
        />
      </template>

      <DimensionEditor
        v-if="editorWall"
        v-model="editor.text"
        :x="editorWall.label.x"
        :y="editorWall.label.y"
        :bounds-w="size.w"
        :bounds-h="size.h"
        :unit="unit"
        :error="editor.error"
        :orientation="editorWall.wall.orientation"
        :locked="editorWall.wall.locked"
        :house="editorWall.wall.house"
        @house="editorHouse"
        @submit="submitEditor"
        @close="closeEditor"
        @orientation="editorOrientation"
        @lock="editorLock"
      />
    </div>

    <!-- toolbar -->
    <div class="toolbar" @pointerdown.stop>
      <div class="tool-group">
        <button class="tool" title="Undo (Ctrl+Z)" :disabled="!canUndo" @click="onUndo">
          <svg viewBox="0 0 24 24"><path d="M9 14 4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></svg>
        </button>
        <button class="tool" title="Redo (Ctrl+Y)" :disabled="!canRedo" @click="onRedo">
          <svg viewBox="0 0 24 24"><path d="m15 14 5-5-5-5" /><path d="M20 9H9a5 5 0 0 0 0 10h3" /></svg>
        </button>
        <button class="tool" title="Fit to Zoom" @click="onFit">
          <svg viewBox="0 0 24 24">
            <path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4" />
            <rect x="8" y="9" width="8" height="6" rx="1" />
          </svg>
        </button>
      </div>
      <div class="unit-group">
        <button class="unit" :class="{ on: unit === 'in' }" @click="unit = 'in'">in.</button>
        <button class="unit" :class="{ on: unit === 'mm' }" @click="unit = 'mm'">mm</button>
      </div>
    </div>

    <transition name="fade">
      <div v-if="message" class="message">{{ message }}</div>
    </transition>
  </div>
</template>

<style scoped>
.plan {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #fff;
  user-select: none;
  touch-action: none;
}
.plan-svg {
  position: absolute;
  inset: 0;
  display: block;
  cursor: grab;
}
.plan-svg:active {
  cursor: grabbing;
}
.grid-line {
  stroke: #eef0f3;
  stroke-width: 1;
}
.dims line {
  stroke: #cfd3d9;
  stroke-width: 1;
}
.arcs path {
  fill: none;
  stroke: #8a8f97;
  stroke-width: 1.2;
}
.walls {
  fill: none;
  stroke: #111;
  stroke-width: 4;
  stroke-linejoin: miter;
}
.house-line {
  stroke: #9aa1ab;
  stroke-width: 9;
  stroke-dasharray: 3 3;
}
.wall-name {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  color: #8a93a0;
  pointer-events: none !important;
  white-space: nowrap;
}
.wall-name.house {
  color: #6b7280;
}
.handles rect {
  fill: var(--brand);
  cursor: move;
}
.handles rect:hover {
  fill: #4b6fa8;
}

.overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.overlay > * {
  pointer-events: auto;
}

.angle-label {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 12px;
  color: #333;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 8px;
  padding: 0 3px;
  pointer-events: none !important;
  white-space: nowrap;
}

.split-btn {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: #fff;
  color: var(--brand);
  font-size: 16px;
  line-height: 16px;
  padding: 0;
  cursor: pointer;
  box-shadow: 0 0 0 1px #e5e7eb;
}
.split-btn:hover {
  background: var(--brand);
  color: #fff;
}

.dim-label {
  position: absolute;
  transform: translate(-50%, -50%);
  border: none;
  background: #fff;
  padding: 1px 4px;
  font-size: 13px;
  color: #222;
  cursor: pointer;
  white-space: nowrap;
  border-radius: 3px;
}
.dim-label:hover,
.dim-label.active {
  box-shadow: 0 0 0 1px var(--brand);
}
.frac {
  font-size: 9px;
  margin-left: 1px;
}
.frac sup {
  vertical-align: 4px;
  font-size: 9px;
}
.frac sub {
  vertical-align: -1px;
  font-size: 9px;
}

.wall-toggles {
  position: absolute;
  transform: translate(-50%, -50%);
}

.toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}
.tool-group {
  display: flex;
  gap: 2px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
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
.tool:hover:not(:disabled) {
  background: #eef2f8;
}
.tool:disabled {
  color: #b8bec8;
  cursor: default;
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
.unit-group {
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  overflow: hidden;
}
.unit {
  width: 36px;
  height: 30px;
  border: none;
  background: #eef0f3;
  color: #333;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.unit.on {
  background: var(--brand);
  color: #fff;
}

.message {
  position: absolute;
  left: 50%;
  bottom: 20px;
  transform: translateX(-50%);
  background: #2b2f36;
  color: #fff;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 13px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
