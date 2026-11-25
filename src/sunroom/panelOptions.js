/**
 * Choosing a panel option (type / transom) with the panel count kept buildable.
 *
 * Wraps floorplan setPanelOption (which stores the option and pins an automatic count) with two
 * rules, both based only on the supplier panel formula and width limits already in layout.js:
 *
 *   1. AUTOMATIC count (plan.walls[i].panels == null before the choice): if the new option makes
 *      the current count unbuildable but another count is valid, the nearest valid count is
 *      stored instead (never one that would drop a stored option), and a notice says so. The
 *      candidate counts are layout's own valid set (countRange), the same rule auto mode uses.
 *   2. NO valid count at all for the wall with the new option: the choice is refused with the
 *      panel sizes either side of the limits, instead of storing an unbuildable wall.
 *
 * A count the plan already stores (set by the user or pinned by an earlier option) is left alone:
 * if the option does not fit it, the option is still stored and the layout reports
 * "Use N panels" exactly as before.
 */
import { computeLayout, combinedLimits, panelOption, panelSizeWithDoors, supportsTransom } from './layout.js'
import { setPanelCount, setPanelOption } from '../floorplan/geometry.js'

const wallOf = (layout, i) => layout.walls.find((w) => w.index === i) ?? null
const inch = (v) => `${Math.round(v * 1000) / 1000}"`

/**
 * @returns {{ ok: true, plan, notice: string|null } | { ok: false, error: string }}
 */
export function choosePanelOption(plan, i, k, option, spec) {
  const lay = computeLayout(plan, spec)
  const lw = wallOf(lay, i)
  if (!lw) return { ok: false, error: 'The house wall has no panels.' }
  const res = setPanelOption(plan, i, k, option, lw.count)
  if (!res.ok) return res
  if (option === null) return { ok: true, plan: res.plan, notice: null }

  const lay2 = computeLayout(res.plan, spec)
  const w2 = wallOf(lay2, i)
  const N = res.plan.walls[i].panels
  const counts = w2.countRange?.counts ?? []
  if (counts.includes(N)) return { ok: true, plan: res.plan, notice: null }
  if (!counts.length) return { ok: false, error: noFitMessage(res.plan, w2, spec) }

  if (plan.walls[i].panels == null) {
    // automatic count: move to the nearest valid count that keeps every stored option
    const stored = res.plan.walls[i].windows?.length ?? 0
    const candidates = counts.filter((c) => c >= stored)
    if (candidates.length) {
      const best = candidates.reduce((a, c) => {
        const da = Math.abs(a - N)
        const dc = Math.abs(c - N)
        return dc < da || (dc === da && c > a) ? c : a
      })
      const out = setPanelCount(res.plan, i, best)
      if (out.ok) {
        const lw3 = wallOf(computeLayout(out.plan, spec), i)
        const lim = lw3?.limits
        const size = lw3?.panelSize != null ? ` × ${inch(lw3.panelSize)}` : ''
        return {
          ok: true,
          plan: out.plan,
          notice: `Panel count changed from ${N} to ${best}${size} so the panels fit the ${lim ? `${lim.label.toLowerCase()} limits (${lim.min}"–${lim.max}")` : 'width limits'}.`,
        }
      }
    }
  }
  return { ok: true, plan: res.plan, notice: null } // stored count kept: layout reports "Use N panels"
}

/** "Casement section doesn't fit the Left wall: 1 panel = 47.986" (max 36"), 2 panels = 23.243" (min 24")." */
function noFitMessage(plan, w, spec) {
  const N = plan.walls[w.index].panels ?? 1
  const opts = Array.from({ length: Math.max(N, plan.walls[w.index].windows?.length ?? 0) }, (_, k) => panelOption(plan.walls[w.index], k, spec))
  const lim = w.limits ?? combinedLimits(opts.filter((o) => o.type !== 'door').map((o) => o.type), spec)
  const doors = opts.filter((o) => o.type === 'door').length
  const name = `${w.name} wall (${inch(w.length)})`
  if (!lim) return `No panel count fits the ${name}.`
  if (lim.min > lim.max) return `${lim.label}: the chosen panel types have no common width, so no panel count fits the ${name}.`
  const size = (n) => panelSizeWithDoors(w.run, n, doors, spec.doorWidth, spec.panelJoint)
  let wide = null
  let narrow = null
  for (let n = doors + 1; n <= doors + 200; n++) {
    const x = size(n)
    if (x > lim.max) wide = n
    else if (x < lim.min) {
      narrow = n
      break
    }
  }
  if (doors && wide == null) {
    // even door + one panel leaves the panel under its minimum (or the door alone is too wide)
    return `The fixed ${spec.doorWidth}" door doesn't fit the ${name}: the door plus one panel of at least ${lim.min}" and a ${spec.panelJoint}" joint needs ${inch(spec.doorWidth + lim.min + spec.panelJoint)} of clear run; this wall has ${inch(w.run)}.`
  }
  const parts = []
  if (wide != null) parts.push(`${wide} panel${wide > 1 ? 's' : ''} = ${inch(size(wide))} (max ${lim.max}")`)
  if (narrow != null) parts.push(`${narrow} panel${narrow > 1 ? 's' : ''} = ${inch(size(narrow))} (min ${lim.min}")`)
  const why = parts.length ? `: ${parts.join(', ')}` : ''
  return `${lim.label} doesn't fit the ${name}${why}.`
}

/**
 * Which panel types can be chosen for panel k of wall i: { [typeId]: { ok, reason } }.
 * A type is unavailable when choosePanelOption would refuse it (no buildable count, second door).
 */
export function typeAvailability(plan, i, k, spec) {
  const cur = panelOption(plan.walls[i], k, spec)
  const out = {}
  for (const t of spec.panelTypes) {
    if (t.id === cur.type) {
      out[t.id] = { ok: true, reason: '' }
      continue
    }
    const r = choosePanelOption(plan, i, k, { type: t.id, transom: supportsTransom(t.id) ? cur.transom : false }, spec)
    out[t.id] = { ok: r.ok, reason: r.ok ? '' : r.error }
  }
  return out
}
