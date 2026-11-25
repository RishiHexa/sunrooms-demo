/**
 * Exploded-view offsets for the built sunroom (visual only).
 *
 * Every offset is a presentation distance in inches chosen for legibility; none of it is a
 * manufacturing value and nothing here reads back into the layout. Offsets are attached to the
 * objects produced by build3d.js as `userData.explode = { base, offset }` and applied with
 * applyExplode(model, t), t in [0, 1] (0 = assembled, exactly the built positions).
 */
import * as THREE from 'three'

export const EXPLODE_IN = {
  wall: 30, // whole wall, outward from the room
  panel: 10, // spacing added between neighbouring panels of a wall
  channel: 14, // bottom/top channel, down/up
  receiver: 7, // bottom/top receiver of a panel, down/up
  rail: 8, // knee/header rails, into the room
  corner: 6, // inside corner piece, into the room (relative to its post)
  roof: 54, // whole roof, up
  roofPanel: 8, // spacing added between roof panels
  roofLayer: 3, // skin layers apart from the foam
  seam: 8, // roof seams above the panels
  gutter: 14, // gutter, away from the house
  backChannel: 12, // back channel, toward the house
  fascia: 14, // fascia, sideways past the outer roof panels
}

const d3 = (d) => new THREE.Vector3(d.x, 0, d.y)

function offsetOf(o) {
  if (!o.userData.explode) o.userData.explode = { base: o.position.clone(), offset: new THREE.Vector3() }
  return o.userData.explode.offset
}

/** Attach explode offsets to the model returned by buildSunroom(layout). */
export function prepareExplode(model, layout) {
  const E = EXPLODE_IN
  const top = new Map(model.children.map((c) => [c.name, c]))
  const midOf = (wall) => (wall.openings.length - 1) / 2

  // walls --------------------------------------------------------------------------------------
  for (const wall of layout.walls) {
    const g = top.get(`wall-${wall.index}`)
    if (!g) continue
    const out = d3(wall.inward).negate()
    const inn = d3(wall.inward)
    const r = d3(wall.right)
    const mid = midOf(wall)
    offsetOf(g).addScaledVector(out, E.wall)
    for (const m of g.children) {
      const e = offsetOf(m)
      const n = m.name
      if (m.userData.panel) {
        e.addScaledVector(r, (m.userData.panel - 1 - mid) * E.panel)
        if (n.endsWith('-receiver-bottom')) e.y -= E.receiver
        else if (n.endsWith('-receiver-top')) e.y += E.receiver
        else if (n.endsWith('-rail')) e.addScaledVector(inn, E.rail)
      } else if (n === 'bottom-channel') e.y -= E.channel
      else if (n === 'top-channel') e.y += E.channel
      else if (n === 'wall-channel-left') e.addScaledVector(r, -(mid + 1) * E.panel)
      else if (n === 'wall-channel-right') e.addScaledVector(r, (mid + 1) * E.panel)
    }
  }

  // corners: follow both adjoining walls out, past their end panels ----------------------------
  for (const c of layout.corners) {
    const g = top.get(`corner-${c.vertex}`)
    if (!g) continue
    const wa = layout.walls.find((w) => w.index === c.wallLeft) // corner is at wa's right end
    const wb = layout.walls.find((w) => w.index === c.wallRight) // ... and at wb's left end
    if (!wa || !wb) continue
    const outA = d3(wa.inward).negate()
    const outB = d3(wb.inward).negate()
    offsetOf(g)
      .addScaledVector(outA, E.wall)
      .addScaledVector(outB, E.wall)
      .addScaledVector(d3(wa.right), (midOf(wa) + 1) * E.panel)
      .addScaledVector(d3(wb.right), -(midOf(wb) + 1) * E.panel)
    const inward = outA.clone().add(outB).normalize().negate()
    for (const m of g.children) if (m.name === 'inside-corner') offsetOf(m).addScaledVector(inward, E.corner)
  }

  // roof ---------------------------------------------------------------------------------------
  const roof = top.get('roof')
  const h = layout.house
  if (roof && h) {
    offsetOf(roof).y += E.roof
    const ea = d3(h.ea)
    const towardHouse = d3(h.eout).negate()
    let n = 0
    for (const m of roof.children) n = Math.max(n, m.userData.roofPanel || 0)
    const mid = (n - 1) / 2
    for (const m of roof.children) {
      const e = offsetOf(m)
      const u = m.userData
      if (u.roofPanel) {
        e.addScaledVector(ea, (u.roofPanel - 1 - mid) * E.roofPanel)
        if (u.layer === 'skin-top') e.y += E.roofLayer
        else if (u.layer === 'skin-bottom') e.y -= E.roofLayer
      } else if (u.seamAfter) {
        e.addScaledVector(ea, (u.seamAfter - 0.5 - mid) * E.roofPanel)
        e.y += E.roofLayer + E.seam
      } else if (m.name === 'gutter') {
        e.addScaledVector(towardHouse, -E.gutter)
      } else if (m.name === 'back-channel') {
        e.addScaledVector(towardHouse, E.backChannel)
      } else if (m.name === 'fascia-left') {
        e.addScaledVector(ea, -(mid * E.roofPanel + E.fascia))
      } else if (m.name === 'fascia-right') {
        e.addScaledVector(ea, mid * E.roofPanel + E.fascia)
      } else if (m.name.startsWith('wedge-wall-')) {
        // the wedge sits on its wall's top channel: follow that wall, not the roof
        const wall = layout.walls.find((w) => `wedge-wall-${w.index}` === m.name)
        if (wall) e.addScaledVector(d3(wall.inward), -E.wall)
        e.y += -E.roof + E.channel + 6
      }
    }
  }
}

/** Offset of a top-level wall group at the given explode factor (for its pick surface). */
export function wallExplodeOffset(model, wallIndex, t, target = new THREE.Vector3()) {
  const g = model.children.find((c) => c.name === `wall-${wallIndex}`)
  const ex = g?.userData.explode
  return ex ? target.copy(ex.offset).multiplyScalar(t) : target.set(0, 0, 0)
}

/** Position every prepared object at base + offset * t. */
export function applyExplode(model, t) {
  model.traverse((o) => {
    const ex = o.userData.explode
    if (ex) o.position.copy(ex.base).addScaledVector(ex.offset, t)
  })
}
