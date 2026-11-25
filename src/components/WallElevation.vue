<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useFloorPlan } from '../floorplan/useFloorPlan.js'
import { choosePanelOption, choosePanelSize, typeAvailability } from '../sunroom/panelOptions.js'
import LengthField from './LengthField.vue'
import { formatMm } from '../floorplan/units.js'
import { panelOption, panelTopAt } from '../sunroom/layout.js'
import { MAIN_ROLES, ROW_LABELS, mainRoleOf, mergeRows, panelRows, setRowType, splitRow } from '../sunroom/rows.js'
import { click, doubleClick, level, up } from '../sunroom/drill.js'

/**
 * 2D elevation of the selected wall, seen from outside (left -> right), with drill-down
 * selection: click = wall, double-click = panel, double-click again = row; Ctrl + click adds
 * rows of the selected panel for merging.
 *
 * Drawing only consumes layout values (openings, rails, heights); nothing is measured from the
 * drawing. Edits go through choosePanelOption (sunroom/panelOptions.js), the same path and stored
 * option the Dimensions panel uses.
 */
const props = defineProps({
  layout: { type: Object, required: true },
  unit: { type: String, default: 'in' },
  selection: { type: Object, required: true }, // { wall, panel, rows }
  slidable: { type: Array, default: () => [] }, // `${wall}:${panel}` of sliders the 3D view can open
  slideGoals: { type: Object, default: () => ({}) }, // key -> open
})
const emit = defineEmits(['select', 'slide'])

const { plan, commit } = useFloorPlan()
const spec = computed(() => props.layout.spec)
const exact = (v) => (props.unit === 'mm' ? formatMm(v) : `${parseFloat(v.toFixed(4))}"`)
const typeLabel = (id) => spec.value.panelTypes.find((t) => t.id === id)?.label ?? id

const wall = computed(() => props.layout.walls.find((w) => w.index === props.selection.wall) ?? null)
const planWall = computed(() => plan.value.walls[props.selection.wall] ?? null)
const lvl = computed(() => level(props.selection))

// ---- geometry (inches -> px) ------------------------------------------------------------------
const box = ref(null)
const size = ref({ w: 600, h: 200 })
let ro
onMounted(() => {
  ro = new ResizeObserver(([e]) => (size.value = { w: e.contentRect.width, h: e.contentRect.height }))
  ro.observe(box.value)
})
onBeforeUnmount(() => ro?.disconnect())

const M = { l: 18, r: 18, t: 22, b: 30 }
const view = computed(() => {
  const w = wall.value
  if (!w) return null
  const H = Math.max(w.topLeft, w.topRight)
  const k = Math.max(0.1, Math.min((size.value.w - M.l - M.r) / w.length, (size.value.h - M.t - M.b) / H))
  const ox = (size.value.w - w.length * k) / 2
  const oy = M.t + (size.value.h - M.t - M.b - H * k) / 2
  return { k, X: (s) => ox + s * k, Y: (z) => oy + (H - z) * k }
})
const pts = (list) => list.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')

const outline = computed(() => {
  const w = wall.value
  const v = view.value
  if (!w || !v) return ''
  return pts([[v.X(0), v.Y(0)], [v.X(w.length), v.Y(0)], [v.X(w.length), v.Y(w.topRight)], [v.X(0), v.Y(w.topLeft)]])
})

const panels = computed(() => {
  const w = wall.value
  const v = view.value
  if (!w || !v) return []
  return w.panels.map((p, k) => {
    const { rows, rails } = panelRows(w, p, spec.value)
    const x0 = v.X(p.s0)
    const x1 = v.X(p.s1)
    const frame = pts([[x0, v.Y(0)], [x1, v.Y(0)], [x1, v.Y(panelTopAt(w, p.s1, spec.value))], [x0, v.Y(panelTopAt(w, p.s0, spec.value))]])
    return {
      k,
      p,
      x0,
      x1,
      frame,
      rows: rows.map((r) => {
        const yb = v.Y(r.z0)
        const ytL = v.Y(r.top0)
        const ytR = v.Y(r.top1)
        return {
          ...r,
          poly: pts([[x0, yb], [x1, yb], [x1, ytR], [x0, ytL]]),
          cx: (x0 + x1) / 2,
          cy: (yb + (ytL + ytR) / 2) / 2,
          hPx: yb - Math.max(ytL, ytR),
          fill: r.role === 'solid' ? 'solid' : r.role === 'door' ? 'door' : 'glass',
          text: MAIN_ROLES.includes(r.role) ? typeLabel(p.type) : r.label,
          yb,
          yt: Math.min(ytL, ytR),
        }
      }),
      rails: rails.map((r) => ({ name: r.name, y: v.Y(r.z1), h: (r.z1 - r.z0) * v.k, custom: !!p.rails.find((x) => x.name === r.name)?.custom })),
      bad: p.errors.length > 0,
    }
  })
})

// ---- selection -------------------------------------------------------------------------------
const additive = (e) => e.ctrlKey || e.metaKey || e.shiftKey
const hit = (k, role = null) => ({ wall: props.selection.wall, panel: k, role })
const onClick = (e, k, role) => emit('select', click(props.selection, hit(k, role), additive(e)))
const onDbl = (k, role) => emit('select', doubleClick(props.selection, hit(k, role)))
// background (around the wall) = back to the wall level, the wall stays selected
const onBackground = () => emit('select', { wall: props.selection.wall, panel: -1, rows: [] })
const isSel = (k, role) => props.selection.panel === k && props.selection.rows.includes(role)

// ---- the selected panel / rows ------------------------------------------------------------------
const selPanel = computed(() => (props.selection.panel >= 0 ? panels.value[props.selection.panel] ?? null : null))
const option = computed(() => (selPanel.value ? panelOption(planWall.value, selPanel.value.k, spec.value) : null))
const selRows = computed(() => (selPanel.value ? selPanel.value.rows.filter((r) => props.selection.rows.includes(r.role)) : []))
const singleRow = computed(() => (selRows.value.length === 1 ? selRows.value[0] : null))
const mergeCheck = computed(() => (selRows.value.length >= 2 ? mergeRows(option.value, selPanel.value.rows, props.selection.rows) : null))
const splitCheck = computed(() => (singleRow.value ? splitRow(option.value, singleRow.value.role) : null))

const actionError = ref('')
watch(() => [props.selection, plan.value], () => (actionError.value = ''))
// notice from the last edit (e.g. panel count changed); shown only while that plan is current
const notice = shallowRef(null) // { text, plan } — shallow, so .plan stays the raw plan object for the identity check
const noticeText = computed(() =>
  notice.value && notice.value.plan === plan.value && notice.value.wall === props.selection.wall ? notice.value.text : '',
)
// types that cannot be chosen for the selected panel (no buildable count, second door)
const availability = computed(() =>
  selPanel.value && singleRow.value && MAIN_ROLES.includes(singleRow.value.role)
    ? typeAvailability(plan.value, props.selection.wall, selPanel.value.k, spec.value)
    : {},
)

function apply(res, nextRows) {
  if (!res.ok) {
    actionError.value = res.error
    return
  }
  const out = choosePanelOption(plan.value, props.selection.wall, selPanel.value.k, res.option, spec.value)
  if (!out.ok) {
    actionError.value = out.error
    return
  }
  actionError.value = ''
  commit(out.plan)
  notice.value = out.notice ? { text: out.notice, plan: out.plan, wall: props.selection.wall } : null
  emit('select', { wall: props.selection.wall, panel: props.selection.panel, rows: nextRows })
}
const doMerge = () => apply(mergeCheck.value, ['main'])
const doSplit = () => apply(splitCheck.value, ['main'])
function doType(type) {
  apply(setRowType(option.value, singleRow.value.role, type), [mainRoleOf(type)])
}

const crumbs = computed(() => {
  const out = [{ label: wall.value ? `${wall.value.name} wall` : 'Wall', to: { wall: props.selection.wall, panel: -1, rows: [] } }]
  if (selPanel.value) out.push({ label: `Panel ${selPanel.value.k + 1}`, to: { wall: props.selection.wall, panel: selPanel.value.k, rows: [] } })
  if (selRows.value.length) out.push({ label: selRows.value.length === 1 ? `${selRows.value[0].label} row` : `${selRows.value.length} rows`, to: null })
  return out
})

// ---- panel sizes (width lock, rail heights) ---------------------------------------------------
// Stored as per-panel overrides (plan.walls[i].sizes) through choosePanelSize, which refuses a
// change that would break the wall. Not supplier standards: the layout flags every override.
function setSize(patch) {
  const out = choosePanelSize(plan.value, props.selection.wall, selPanel.value.k, patch, spec.value)
  if (!out.ok) {
    actionError.value = out.error
    return
  }
  actionError.value = ''
  notice.value = null
  commit(out.plan)
}
const sp = computed(() => selPanel.value?.p ?? null)
/** Lock at the current width: for an unlocked panel that is the shared size X itself. */
const lockNow = () => setSize({ width: wall.value.panelSize ?? sp.value.width })
const railCustom = (name) => !!sp.value?.rails.find((r) => r.name === name)?.custom
/** Rails editable here: all of the panel's rails at panel level; the ones bounding the row at row level. */
const editRails = computed(() => {
  const p = sp.value
  if (!p) return []
  const has = { knee: p.kneeTop != null, transom: p.transomClear != null }
  let names = ['knee', 'transom']
  if (lvl.value === 'row') {
    const role = singleRow.value?.role
    names = role === 'knee' ? ['knee'] : role === 'main' ? ['knee', 'transom'] : role === 'transom' ? ['transom'] : []
  }
  return names.filter((n) => has[n])
})

// slider open / close (visual, animated by the 3D view)
const slideKey = computed(() => (selPanel.value ? `${props.selection.wall}:${selPanel.value.k}` : ''))
const isSlider = computed(() => selPanel.value?.p.type === 'slider')
const canSlide = computed(() => isSlider.value && props.slidable.includes(slideKey.value))
const isOpen = computed(() => !!props.slideGoals[slideKey.value])

const collapsed = ref(false)
</script>

<template>
  <section class="elev" :class="{ collapsed }" @pointerdown.stop>
    <header class="bar">
      <span class="title">Elevation</span>
      <nav class="crumbs">
        <template v-for="(c, i) in crumbs" :key="i">
          <span v-if="i" class="sep">›</span>
          <button v-if="c.to && i < crumbs.length - 1" class="crumb" @click="emit('select', c.to)">{{ c.label }}</button>
          <span v-else class="crumb cur">{{ c.label }}</span>
        </template>
      </nav>
      <span class="spacer" />
      <span class="view-note">Outside view · left → right</span>
      <button class="icon" :title="collapsed ? 'Show elevation' : 'Hide elevation'" @click="collapsed = !collapsed">
        {{ collapsed ? '▴' : '▾' }}
      </button>
    </header>

    <div v-show="!collapsed" class="body">
      <div ref="box" class="canvas">
        <svg v-if="view && wall" :width="size.w" :height="size.h" @click.self="onBackground">
          <polygon :points="outline" class="wall-outline" :class="{ on: lvl === 'wall' }" @click="onBackground" />
          <g
            v-for="pp in panels"
            :key="pp.k"
            class="panel"
            :class="{ on: selection.panel === pp.k, dim: selection.panel >= 0 && selection.panel !== pp.k, bad: pp.bad }"
          >
            <!-- frame area (receivers, rails, verticals): selects the panel, no row -->
            <polygon :points="pp.frame" class="frame" @click="onClick($event, pp.k, null)" @dblclick="onDbl(pp.k, null)" />
            <polygon
              v-for="r in pp.rows"
              :key="r.role"
              :points="r.poly"
              class="row"
              :class="[r.fill, { sel: isSel(pp.k, r.role) }]"
              @click="onClick($event, pp.k, r.role)"
              @dblclick="onDbl(pp.k, r.role)"
            />
            <!-- operation marks (visual only) -->
            <template v-for="r in pp.rows" :key="'m' + r.role">
              <line v-if="MAIN_ROLES.includes(r.role) && pp.p.type === 'slider'" class="mark" :x1="r.cx" :x2="r.cx" :y1="r.yb" :y2="r.yt" />
              <polyline
                v-if="MAIN_ROLES.includes(r.role) && pp.p.type === 'casement'"
                class="mark"
                :points="pts([[pp.x1, r.yb], [pp.x0, r.cy], [pp.x1, r.yt]])"
              />
              <circle v-if="r.role === 'door'" class="handle" :cx="pp.x1 - 4" :cy="r.cy" r="2.2" />
            </template>
            <rect v-for="rl in pp.rails" :key="rl.name" class="rail" :class="{ custom: rl.custom }" :x="pp.x0" :y="rl.y" :width="pp.x1 - pp.x0" :height="Math.max(rl.h, 1.5)" />
            <text v-for="r in pp.rows.filter((r) => r.hPx > 13 && pp.x1 - pp.x0 > 34)" :key="'t' + r.role" class="rlabel" :x="r.cx" :y="r.cy + 4">
              {{ r.text }}
            </text>
            <text class="pnum" :x="pp.x0 + 3" :y="view.Y(Math.max(wall.topLeft, wall.topRight)) - 6">P{{ pp.k + 1 }}</text>
            <text class="pwidth" :class="{ locked: pp.p.locked }" :x="(pp.x0 + pp.x1) / 2" :y="view.Y(0) + 16">
              {{ pp.p.locked ? '🔒 ' : '' }}{{ exact(pp.p.width) }}
            </text>
          </g>
        </svg>
        <p v-if="wall && !wall.panels.length" class="empty">{{ wall.error || 'This wall has no panel layout yet.' }}</p>
        <p v-else-if="!wall" class="empty">The house wall has no panels.</p>
      </div>

      <aside class="side">
        <p v-if="lvl === 'wall' && !wall?.panels.length" class="hint">Fix this wall's width, panel count or panel types first; panels and rows need a valid layout.</p>
        <template v-else-if="lvl === 'wall'">
          <p class="lead">{{ wall?.count ?? 0 }} panel{{ wall?.count === 1 ? '' : 's' }}<span v-if="wall?.panelSize"> × {{ exact(wall.panelSize) }}</span></p>
          <p class="hint">Double-click a panel to select it.</p>
        </template>

        <template v-else-if="lvl === 'panel' && selPanel">
          <p class="lead">Panel {{ selPanel.k + 1 }} · {{ typeLabel(selPanel.p.type) }}<span v-if="selPanel.p.transom"> + transom</span></p>
          <p class="sub">Opening {{ exact(selPanel.p.width) }} · {{ selPanel.rows.length }} row{{ selPanel.rows.length > 1 ? 's' : '' }}</p>
          <p class="hint">Double-click a row to select it. Ctrl + click to select several rows.</p>
        </template>

        <template v-else-if="lvl === 'row' && selPanel">
          <template v-if="singleRow">
            <p class="lead">{{ singleRow.label }} row · Panel {{ selPanel.k + 1 }}</p>
            <template v-if="MAIN_ROLES.includes(singleRow.role)">
              <div class="types">
                <button
                  v-for="t in spec.panelTypes"
                  :key="t.id"
                  :class="{ on: option.type === t.id }"
                  :disabled="availability[t.id] && !availability[t.id].ok"
                  :title="availability[t.id]?.reason ?? ''"
                  @click="doType(t.id)"
                >
                  {{ t.label }}
                </button>
              </div>
            </template>
            <p v-else class="sub">The fill of this row is not defined in the 4-Season supplier files; only the main row has a type.</p>
            <button v-if="splitCheck?.ok" class="act" title="Add a 3V transom rail 10&quot; below the top" @click="doSplit">Split: add transom</button>
            <p class="hint">Ctrl + click another row to merge.</p>
          </template>
          <template v-else>
            <p class="lead">{{ selRows.length }} rows · Panel {{ selPanel.k + 1 }}</p>
            <p class="sub">{{ selRows.map((r) => r.label).join(' + ') }}</p>
            <button class="act" :disabled="!mergeCheck?.ok" @click="doMerge">Merge rows</button>
            <p v-if="mergeCheck && !mergeCheck.ok" class="why">{{ mergeCheck.error }}</p>
          </template>
        </template>

        <!-- sizes of the selected panel / row (per-panel overrides, flagged as non-standard) -->
        <div v-if="sp && (lvl === 'panel' || singleRow)" class="sizes">
          <template v-if="lvl === 'panel'">
            <LengthField
              label="Width"
              :value="sp.width"
              :unit="unit"
              :disabled="sp.door"
              :hint="sp.door ? `Door: fixed ${exact(spec.doorWidth)} (supplier)` : sp.locked ? 'Locked · unlocked panels share the rest' : 'Shared equally · type a width to lock it'"
              @change="(v) => setSize({ width: v })"
            />
            <div v-if="!sp.door" class="size-tools">
              <button v-if="sp.locked" class="mini" @click="setSize({ width: null })">Unlock</button>
              <button v-else class="mini" @click="lockNow">Lock at this width</button>
              <span v-if="sp.locked" class="tag">Non-standard</span>
            </div>
          </template>
          <template v-for="name in editRails" :key="name">
            <LengthField
              v-if="name === 'knee'"
              label="Knee rail height"
              :value="sp.kneeTop"
              :unit="unit"
              :hint="`Top of rail above panel bottom · standard ${exact(spec.kneeRailTopAbovePanelBottom)}`"
              @change="(v) => setSize({ kneeTop: v })"
            />
            <LengthField
              v-else
              label="Transom below top"
              :value="sp.transomClear"
              :unit="unit"
              :hint="`Fin to fin under the top receiver · standard ${exact(spec.transomClearFin)}`"
              @change="(v) => setSize({ transomClear: v })"
            />
            <div v-if="railCustom(name)" class="size-tools">
              <button class="mini" @click="setSize(name === 'knee' ? { kneeTop: null } : { transomClear: null })">Reset to standard</button>
              <span class="tag">Non-standard</span>
            </div>
          </template>
        </div>

        <template v-if="isSlider && lvl !== 'wall'">
          <button v-if="canSlide" class="act" :class="{ on: isOpen }" @click="emit('slide', slideKey, !isOpen)">
            {{ isOpen ? 'Close window' : 'Open window' }}
          </button>
          <p v-else class="sub">Not animated: the main opening is raked, and a sliding sash needs a level-topped opening. Add a transom to give it a level top.</p>
          <p class="sub">Motion follows the supplier's 225 slider macro (interior sash slides, stops 1/8" short); not confirmed for 4-Season.</p>
        </template>
        <p v-for="(e, i) in selPanel?.p.errors ?? []" :key="'e' + i" class="error">{{ e }}</p>
        <p v-if="actionError" class="error">{{ actionError }}</p>
        <p v-if="noticeText" class="notice">{{ noticeText }}</p>
        <p class="foot">Esc goes up a level. Glass, sashes and door leaf are visual only.</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.elev {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  height: 250px;
  font: 12px/1.35 Roboto, 'Segoe UI', system-ui, sans-serif;
  color: #1f2328;
}
.elev.collapsed {
  height: auto;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px 6px 12px;
  border-bottom: 1px solid var(--border);
}
.collapsed .bar {
  border-bottom: none;
}
.title {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.crumbs {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.crumb {
  border: none;
  background: none;
  padding: 2px 4px;
  border-radius: 4px;
  font: inherit;
  color: #2f6fd0;
  cursor: pointer;
  white-space: nowrap;
}
.crumb:hover {
  background: #eef2f8;
}
.crumb.cur {
  color: #1f2328;
  font-weight: 600;
  cursor: default;
}
.sep {
  color: #9aa3ad;
}
.spacer {
  flex: 1;
}
.view-note {
  color: #7a818b;
  font-size: 11px;
  white-space: nowrap;
}
.icon {
  border: none;
  background: none;
  width: 24px;
  height: 22px;
  border-radius: 4px;
  cursor: pointer;
  color: #444;
}
.icon:hover {
  background: #eef2f8;
}
.body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.canvas {
  position: relative;
  flex: 1;
  min-width: 0;
}
.canvas svg {
  position: absolute;
  inset: 0;
  user-select: none;
}
.side {
  flex: 0 0 230px;
  border-left: 1px solid var(--border);
  padding: 8px 12px;
  overflow-y: auto;
}
.wall-outline {
  fill: #f3f5f8;
  stroke: #9aa3ad;
  stroke-width: 1;
}
.wall-outline.on {
  stroke: #2c4770;
  stroke-width: 2;
}
.frame {
  fill: #c3cad3;
  stroke: #7d8794;
  stroke-width: 1;
  cursor: pointer;
}
.row {
  stroke: #7d8794;
  stroke-width: 0.75;
  cursor: pointer;
}
.row.glass {
  fill: #dcebf7;
}
.row.door {
  fill: #e8e1d4;
}
.row.solid {
  fill: #d5d9de;
}
.row:hover {
  fill: #c9def3;
}
.panel.dim {
  opacity: 0.55;
}
.panel.on .frame {
  fill: #9fb4d0;
  stroke: #2c4770;
  stroke-width: 2;
}
.panel.bad .frame {
  stroke: #b42318;
  stroke-width: 2;
}
.row.sel {
  fill: #f7d77a;
  stroke: #c08a00;
  stroke-width: 2;
}
.rail {
  fill: #8c96a3;
  pointer-events: none;
}
.mark {
  fill: none;
  stroke: #5b6472;
  stroke-width: 1;
  stroke-dasharray: 4 3;
  pointer-events: none;
}
.handle {
  fill: #5b6472;
  pointer-events: none;
}
.rlabel {
  font-size: 11px;
  text-anchor: middle;
  fill: #33404f;
  pointer-events: none;
}
.pnum {
  font-size: 11px;
  font-weight: 600;
  fill: #2c4770;
  pointer-events: none;
}
.pwidth {
  font-size: 10px;
  text-anchor: middle;
  fill: #5b6472;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  padding: 16px;
  color: #b42318;
  text-align: center;
}
.lead {
  margin: 0 0 4px;
  font-weight: 600;
}
.sub,
.hint,
.foot,
.why,
.error {
  margin: 4px 0;
  font-size: 11px;
}
.sub,
.hint,
.foot {
  color: #7a818b;
}
.foot {
  margin-top: 10px;
}
.why {
  color: #9a6700;
}
.rail.custom {
  fill: #d9822b;
}
.pwidth.locked {
  fill: #9a5b13;
  font-weight: 600;
}
.sizes {
  margin: 8px 0 4px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}
.size-tools {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -2px 0 6px;
}
.mini {
  height: 22px;
  padding: 0 8px;
  border: 1px solid #c8cdd4;
  border-radius: 4px;
  background: #fff;
  font: inherit;
  font-size: 11px;
  color: var(--brand);
  cursor: pointer;
}
.tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #fbe7d3;
  color: #9a5b13;
}
.notice {
  margin: 4px 0;
  font-size: 11px;
  color: #1a6b3c;
}
.error {
  color: #b42318;
}
.types {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin: 6px 0;
}
.types button,
.act {
  height: 26px;
  padding: 0 9px;
  border: 1px solid #c8cdd4;
  border-radius: 4px;
  background: #fff;
  font: inherit;
  cursor: pointer;
}
.types button.on {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.types button:disabled,
.act:disabled {
  color: #b5bac1;
  cursor: default;
}
.act {
  margin: 6px 0 2px;
  color: var(--brand);
  font-weight: 600;
}
.act.on {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
</style>
