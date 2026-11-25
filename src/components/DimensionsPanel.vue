<script setup>
import { computed, ref, watch } from 'vue'
import LengthField from './LengthField.vue'
import ConstraintToggles from './ConstraintToggles.vue'
import { useFloorPlan } from '../floorplan/useFloorPlan.js'
import { MIN_WALL_LENGTH_IN, clearPanelOptions, resetRoomHeights, setPanelOption, setRoomHeights, wallLength } from '../floorplan/geometry.js'
import { formatInches, formatMm } from '../floorplan/units.js'
import { panelOption, supportsTransom } from '../sunroom/layout.js'

/**
 * Dimensions panel (3D view): global front / back heights, and the width of the selected wall.
 * Heights are stored on the plan (plan.heights) and applied through setRoomHeights; the wall
 * width goes through the shared wall editor (setWallLength), so the 2D and 3D views apply the
 * same constraints and share undo history.
 */
const props = defineProps({
  layout: { type: Object, required: true },
  unit: { type: String, default: 'in' },
  wall: { type: Number, default: -1 }, // selected wall index, -1 = none
  wallError: { type: String, default: '' },
})
const emit = defineEmits(['width', 'orientation', 'lock', 'house', 'close'])

const { plan, commit } = useFloorPlan()
/** Exact value for computed sizes (no 1/16" rounding, which could understate a minimum). */
const exact = (v) => (props.unit === 'mm' ? formatMm(v) : `${parseFloat(v.toFixed(4))}"`)

// ---- heights ---------------------------------------------------------------------------------
const house = computed(() => props.layout.house)
const heightError = ref('')
watch([plan, () => props.wall], () => (heightError.value = ''))

function applyHeights(front, back) {
  const res = setRoomHeights(plan.value, front, back)
  if (!res.ok) {
    heightError.value = res.error
    return
  }
  heightError.value = ''
  commit(res.plan)
}
// While the back height has not been entered, it keeps following the default slope.
const setFront = (v) => applyHeights(v, plan.value.heights?.back ?? null)
const setBack = (v) => applyHeights(house.value.frontHeight, v)
function reset() {
  heightError.value = ''
  commit(resetRoomHeights(plan.value).plan)
}
const slopeText = computed(() => {
  if (!house.value) return ''
  const perFoot = house.value.slope * 12
  return props.unit === 'mm' ? `${formatMm(perFoot).replace(' mm', '')} mm per foot` : `${formatInches(perFoot)} per foot`
})

// ---- selected wall ---------------------------------------------------------------------------
const planWall = computed(() => (props.wall >= 0 ? plan.value.walls[props.wall] : null))
const layoutWall = computed(() => props.layout.walls.find((w) => w.index === props.wall) ?? null)
const width = computed(() => (planWall.value ? wallLength(plan.value, props.wall) : null))
const wallName = computed(() => {
  if (!planWall.value) return ''
  if (planWall.value.house) return 'House wall'
  return layoutWall.value?.name ? `${layoutWall.value.name} wall` : `Wall ${props.wall + 1}`
})
/** Shortest wall that fits one panel: allowances at both ends + the panel minimum (supplier limits). */
const shortest = computed(() => {
  const w = layoutWall.value
  return w ? w.length - w.run + w.limits.min : MIN_WALL_LENGTH_IN
})
const widthHint = computed(() => {
  if (planWall.value?.house) return 'No panels on the house wall. Changing it moves the walls that meet it.'
  const w = layoutWall.value
  if (!w) return ''
  const parts = []
  if (w.count != null && w.panelSize != null) parts.push(`${w.count} panel${w.count > 1 ? 's' : ''} × ${exact(w.panelSize)}`)
  parts.push(`shortest buildable ${exact(shortest.value)}`)
  return parts.join(' · ')
})
const widthError = computed(() => props.wallError || layoutWall.value?.error || '')

// ---- windows & doors (per-panel options) ------------------------------------------------------
// Stored on the plan (walls[i].windows) through setPanelOption; the layout applies the sizes and
// frame members. Choosing an option pins an automatic panel count so options stay on their panel.
const spec = computed(() => props.layout.spec)
const optionError = ref('')
watch([plan, () => props.wall], () => (optionError.value = ''))
const panelRows = computed(() => {
  const w = layoutWall.value
  if (!w || planWall.value?.house || w.count == null) return []
  return Array.from({ length: w.count }, (_, k) => {
    const o = panelOption(planWall.value, k, spec.value)
    const p = w.panels[k]
    return { k, type: o.type, transom: o.transom, width: p ? p.width : null, errors: p?.errors ?? [] }
  })
})
const doorAt = computed(() => panelRows.value.findIndex((r) => r.type === 'door'))
const wallWarnings = computed(() => props.layout.warnings.filter((x) => x.wall === props.wall).map((x) => x.message))
function setOption(k, patch) {
  const cur = panelRows.value[k]
  if (!cur) return
  const next = { type: cur.type, transom: cur.transom, ...patch }
  if (!supportsTransom(next.type)) next.transom = false
  const res = setPanelOption(plan.value, props.wall, k, next, layoutWall.value.count)
  if (!res.ok) {
    optionError.value = res.error
    return
  }
  optionError.value = ''
  commit(res.plan)
}
function resetOptions() {
  const res = clearPanelOptions(plan.value, props.wall)
  if (res.ok) commit(res.plan)
}
</script>

<template>
  <aside class="dims" @pointerdown.stop>
    <h2>Dimensions</h2>

    <!-- global heights -->
    <section>
      <div class="sec-head">
        <span>Room height</span>
        <button class="reset" :disabled="!house?.customHeights" title="Use the system default heights" @click="reset">
          <svg viewBox="0 0 16 16"><path d="M2.5 5.5h9l-2-2M13.5 10.5h-9l2 2" /></svg>
          Reset to default
        </button>
      </div>
      <template v-if="house">
        <LengthField
          label="Front Height"
          :value="house.frontHeight"
          :unit="unit"
          hint="Top of the top channel at the front (low) wall"
          @change="setFront"
        />
        <LengthField
          label="Back Height"
          :value="house.heightAtHouse"
          :unit="unit"
          hint="Top of the top channel at the house wall"
          @change="setBack"
        />
        <p v-if="heightError" class="error">{{ heightError }}</p>
        <p class="note">
          Roof slope {{ slopeText }}<span v-if="plan.heights?.back == null"> · default slope (back height follows the front height and depth)</span>
        </p>
      </template>
      <p v-else class="note">Heights are available once the plan has one house wall.</p>
    </section>

    <!-- selected wall -->
    <section>
      <div class="sec-head">
        <span>{{ planWall ? wallName : 'Wall width' }}</span>
        <button v-if="planWall" class="close" title="Deselect wall" @click="emit('close')">×</button>
      </div>
      <template v-if="planWall">
        <LengthField
          label="Width"
          :value="width"
          :unit="unit"
          :min="shortest"
          :hint="widthHint"
          :error="widthError"
          @change="(v) => emit('width', v)"
        />
        <div class="wall-tools">
          <ConstraintToggles
            :orientation="planWall.orientation"
            :locked="planWall.locked"
            @orientation="(o) => emit('orientation', o)"
            @lock="emit('lock')"
          />
          <button class="house-btn" :class="{ on: planWall.house }" :disabled="planWall.house" @click="emit('house')">
            {{ planWall.house ? 'House wall' : 'Set as house wall' }}
          </button>
        </div>
      </template>
      <p v-else class="empty">Click a wall (or its dimension) in the 3D view to change its width.</p>
    </section>

    <!-- windows & doors of the selected wall -->
    <section v-if="planWall && !planWall.house">
      <div class="sec-head">
        <span>Windows &amp; doors</span>
        <button class="reset" :disabled="!planWall.windows" title="All panels back to Fixed, no transom" @click="resetOptions">
          <svg viewBox="0 0 16 16"><path d="M2.5 5.5h9l-2-2M13.5 10.5h-9l2 2" /></svg>
          Reset
        </button>
      </div>
      <template v-if="panelRows.length">
        <div class="prow head">
          <span>#</span><span>Type</span><span>Transom</span><span class="pw">Opening</span>
        </div>
        <div v-for="r in panelRows" :key="r.k" class="prow">
          <span class="pnum">{{ r.k + 1 }}</span>
          <select :value="r.type" :aria-label="`Panel ${r.k + 1} type`" @change="setOption(r.k, { type: $event.target.value })">
            <option
              v-for="t in spec.panelTypes"
              :key="t.id"
              :value="t.id"
              :disabled="t.id === 'door' && doorAt >= 0 && doorAt !== r.k"
            >
              {{ t.label }}
            </option>
          </select>
          <label class="tr" :title="r.type === 'door' ? 'A door gets its header from the door rule (raked walls only)' : r.type === 'solid' ? 'Solid panels have no rails' : '3V: transom rail 10&quot; below the top'">
            <input
              type="checkbox"
              :checked="r.transom"
              :disabled="r.type === 'door' || r.type === 'solid'"
              @change="setOption(r.k, { transom: $event.target.checked })"
            />
          </label>
          <span class="pw">{{ r.width != null ? exact(r.width) : '–' }}</span>
          <p v-for="(e, i) in r.errors" :key="i" class="error full">{{ e }}</p>
        </div>
        <p v-if="optionError" class="error">{{ optionError }}</p>
        <p v-for="(m, i) in wallWarnings" :key="'w' + i" class="warn">{{ m }}</p>
        <p class="note">
          Panels numbered left → right, seen from outside. Width limits:
          {{ layoutWall.limits.label.toLowerCase() }} {{ exact(layoutWall.limits.min) }}–{{ exact(layoutWall.limits.max) }}.
          A door is a fixed {{ exact(spec.doorWidth) }} opening, one per wall. Glass, sashes and the door leaf are visual only.
        </p>
      </template>
      <p v-else class="empty">Fix this wall's width or panel count first; panel options need a valid layout.</p>
    </section>
  </aside>
</template>

<style scoped>
.dims {
  width: 280px;
  max-height: calc(100% - 24px);
  overflow-y: auto;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  padding: 14px 16px 10px;
}
h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
  color: #1f2328;
}
section {
  border-top: 1px solid var(--border);
  padding-top: 10px;
  margin-top: 8px;
}
section:first-of-type {
  border-top: none;
  margin-top: 0;
}
.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.reset {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12px;
  color: #333;
  text-transform: none;
  letter-spacing: 0;
  font-weight: 400;
  padding: 3px 4px;
  border-radius: 4px;
}
.reset:hover:not(:disabled) {
  background: #eef2f8;
}
.reset:disabled {
  color: #b5bac1;
  cursor: default;
}
.reset svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.close {
  border: none;
  background: none;
  font-size: 18px;
  line-height: 18px;
  cursor: pointer;
  color: #555;
}
.note,
.empty,
.error {
  font-size: 11px;
  line-height: 1.4;
  margin: 6px 0 4px;
}
.note,
.empty {
  color: #7a818b;
}
.empty {
  font-size: 12px;
  padding: 6px 0 8px;
}
.error {
  color: #b42318;
}
.warn {
  font-size: 11px;
  line-height: 1.4;
  margin: 6px 0 4px;
  color: #9a6700;
}
.prow {
  display: grid;
  grid-template-columns: 22px minmax(92px, 1fr) 40px 56px;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}
.prow.head {
  font-size: 10px;
  color: #7a818b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding-top: 6px;
}
.prow .pnum {
  font-weight: 600;
  color: #1f2328;
  text-align: center;
}
.prow select {
  height: 26px;
  border: 1px solid #c8cdd4;
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  padding: 0 4px;
  min-width: 0;
}
.prow .tr {
  display: flex;
  justify-content: center;
}
.prow .pw {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #444;
}
.prow .full {
  grid-column: 1 / -1;
  margin: 0 0 2px;
}
.wall-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0 6px;
}
.house-btn {
  flex: 1;
  height: 26px;
  border: 1px solid #c8cdd4;
  border-radius: 4px;
  background: #fff;
  color: var(--brand);
  font-size: 12px;
  cursor: pointer;
}
.house-btn.on {
  background: #e8ebf0;
  color: #555;
  cursor: default;
}
</style>
