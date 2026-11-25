<script setup>
import { computed } from 'vue'
import { formatInches, formatMm } from '../floorplan/units.js'

const props = defineProps({
  layout: { type: Object, required: true },
  unit: { type: String, default: 'in' },
  notes: { type: Array, default: () => [] },
})
const emit = defineEmits(['count'])

const len = (v) => (props.unit === 'mm' ? formatMm(v) : formatInches(v))
/** Exact value for constants and computed sizes (no 1/16" rounding). */
const exact = (v) => (props.unit === 'mm' ? formatMm(v) : `${parseFloat(v.toFixed(4))}"`)
const endLabel = (e) => (e.kind === 'house' ? 'House' : 'Corner')

const generalErrors = computed(() => props.layout.errors.filter((e) => e.wall == null && e.vertex == null))
const walls = computed(() =>
  [...props.layout.walls].sort((a, b) => order(a.name) - order(b.name) || a.name.localeCompare(b.name)),
)
function order(name) {
  return ['Left', 'Front left', 'Front', 'Front right', 'Right', 'Back'].findIndex((n) => name.startsWith(n))
}

/** "Fixed ×2 · Door" — panel types of a wall, in order of first appearance. */
function typesText(w) {
  if (!w.panels.length) return ''
  const label = (id) => props.layout.spec.panelTypes.find((t) => t.id === id)?.label ?? id
  const counts = new Map()
  for (const p of w.panels) counts.set(p.type, (counts.get(p.type) ?? 0) + 1)
  const transoms = w.panels.filter((p) => p.transom).length
  const parts = [...counts].map(([t, n]) => (n > 1 ? `${label(t)} ×${n}` : label(t)))
  if (transoms) parts.push(`${transoms} transom${transoms > 1 ? 's' : ''}`)
  return parts.join(' · ')
}

function step(w, delta) {
  const current = w.count ?? w.countRange?.nMin ?? 1
  const next = current + delta
  if (next < 1) return
  emit('count', w.index, next)
}
</script>

<template>
  <aside class="summary">
    <h2>Build summary <span class="sys">{{ layout.spec.name }}</span></h2>

    <ul v-if="generalErrors.length" class="msgs error">
      <li v-for="(e, i) in generalErrors" :key="'e' + i">{{ e.message }}</li>
    </ul>

    <div v-if="layout.house" class="house">
      House wall · room depth {{ len(layout.house.depth) }} · wall top {{ len(layout.house.frontHeight) }} →
      {{ len(layout.house.heightAtHouse) }} at the house
    </div>
    <ul v-if="layout.warnings.length" class="msgs note">
      <li v-for="(w, i) in layout.warnings" :key="'w' + i">{{ w.message }}</li>
    </ul>

    <section v-for="w in walls" :key="w.index" class="wall" :class="{ bad: !w.buildable }">
      <header>
        <span class="name">{{ w.name }}</span>
        <span class="len">{{ len(w.length) }}</span>
      </header>
      <div class="row">
        <span class="muted">{{ endLabel(w.leftEnd) }} → {{ endLabel(w.rightEnd) }}</span>
      </div>
      <div class="row">
        <span class="muted">Panels</span>
        <span class="stepper">
          <button :disabled="(w.count ?? 1) <= 1" title="Fewer panels" @click="step(w, -1)">−</button>
          <b>{{ w.count ?? '–' }}</b>
          <button title="More panels" @click="step(w, 1)">+</button>
        </span>
        <button v-if="w.requested != null" class="auto" title="Use the automatic panel count" @click="emit('count', w.index, null)">Auto</button>
        <span v-else class="auto-tag">auto</span>
      </div>
      <div v-if="w.panelSize != null" class="row">
        <span class="muted">Panel size (X)</span>
        <span :title="len(w.panelSize)">{{ exact(w.panelSize) }}</span>
      </div>
      <div v-if="w.panels.length" class="row">
        <span class="muted">Windows</span>
        <span>{{ typesText(w) }}</span>
      </div>
      <div v-if="w.doors" class="row">
        <span class="muted">Door opening (D)</span>
        <span>{{ exact(layout.spec.doorWidth) }}</span>
      </div>
      <div class="row">
        <span class="muted">{{ w.limits.label }}</span>
        <span>{{ len(w.limits.min) }} – {{ len(w.limits.max) }}</span>
      </div>
      <p v-if="w.error" class="err">{{ w.error }}</p>
      <p v-for="(e, i) in w.panels.flatMap((p) => p.errors)" :key="'pe' + i" class="err">{{ e }}</p>
    </section>

    <ul v-for="v in layout.errors.filter((e) => e.vertex != null)" :key="'v' + v.vertex" class="msgs error">
      <li>{{ v.message }}</li>
    </ul>
    <ul v-if="notes.length" class="msgs note">
      <li v-for="(n, i) in notes" :key="'n' + i">{{ n }}</li>
    </ul>

    <p class="foot">
      X = (L − C − W − (N−1)·P) / N<br />
      with a door: X = (L − C − W − D − N·P) / N, N = panels besides the door, D {{ exact(layout.spec.doorWidth) }}<br />
      C {{ exact(layout.spec.cornerAllowance) }} (corner) · W {{ exact(layout.spec.wallAllowance) }} (house) · P
      {{ exact(layout.spec.panelJoint) }}
    </p>
  </aside>
</template>

<style scoped>
.summary {
  height: 100%;
  overflow-y: auto;
  padding: 12px 14px 16px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  font-size: 13px;
}
h2 {
  font-size: 14px;
  margin: 0 0 10px;
  color: var(--brand);
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.sys {
  font-size: 11px;
  font-weight: 500;
  color: #667;
}
.house {
  font-size: 12px;
  color: #555;
  margin-bottom: 10px;
  line-height: 1.4;
}
.wall {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.wall.bad {
  border-color: #e7b4ae;
}
.wall header {
  display: flex;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 4px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
  min-height: 24px;
}
.muted {
  color: #6b7280;
}
.stepper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.stepper button,
.auto {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  color: var(--brand);
}
.stepper button:disabled {
  color: #bbb;
  cursor: default;
}
.auto-tag {
  font-size: 11px;
  color: #8a8f97;
  width: 36px;
  text-align: center;
}
.auto {
  font-size: 11px;
  width: 36px;
}
.err {
  margin: 6px 0 0;
  color: #b42318;
  font-size: 12px;
  line-height: 1.35;
}
.msgs {
  margin: 0 0 8px;
  padding: 8px 10px 8px 24px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
}
.msgs.error {
  background: #fdecea;
  color: #8a1c13;
}
.msgs.note {
  background: #fff6e0;
  color: #6b4e00;
}
.foot {
  margin-top: 12px;
  font-size: 11px;
  color: #8a8f97;
  line-height: 1.4;
}
</style>
