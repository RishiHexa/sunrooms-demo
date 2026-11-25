import { reactive, watch } from 'vue'
import { useFloorPlan } from './useFloorPlan.js'
import { setHouseWall, setWallLength, toggleLock, toggleOrientation, wallLength } from './geometry.js'
import { editValue, parseLength } from './units.js'

/**
 * Wall dimension editor state + actions, shared by the 2D and 3D views so both apply edits
 * through the same geometry operations (same constraints, validation and undo history).
 * Each view creates its own instance (its own popup).
 */
export function useWallEditor() {
  const { plan, unit, commit } = useFloorPlan()
  const editor = reactive({ open: false, wall: -1, text: '', error: '' })

  function open(i) {
    editor.open = true
    editor.wall = i
    editor.text = editValue(wallLength(plan.value, i), unit.value)
    editor.error = ''
  }

  function close() {
    editor.open = false
    editor.wall = -1
    editor.error = ''
  }

  function apply(result) {
    if (result.ok) {
      commit(result.plan)
      editor.error = ''
      return true
    }
    editor.error = result.error
    return false
  }

  function submit() {
    const inches = parseLength(editor.text, unit.value)
    if (!Number.isFinite(inches)) {
      editor.error = unit.value === 'mm' ? 'Enter a number in mm.' : 'Enter inches, e.g. 81 or 44 13/16.'
      return
    }
    if (setLength(inches)) close()
  }

  /** Apply a length (inches) to the open wall, keeping the editor open. Returns success. */
  function setLength(inches) {
    if (!editor.open) return false
    const ok = apply(setWallLength(plan.value, editor.wall, inches))
    if (ok) editor.text = editValue(wallLength(plan.value, editor.wall), unit.value)
    return ok
  }

  const orientation = (o) => apply(toggleOrientation(plan.value, editor.wall, o))
  const lock = () => apply(toggleLock(plan.value, editor.wall))
  const house = () => {
    if (!plan.value.walls[editor.wall]?.house) apply(setHouseWall(plan.value, editor.wall))
  }

  // Keep the popup consistent when the plan changes underneath it (undo, other view, toggles).
  watch(plan, (p) => {
    if (editor.open && editor.wall >= p.walls.length) close()
  })
  watch(unit, () => {
    if (editor.open) editor.text = editValue(wallLength(plan.value, editor.wall), unit.value)
  })

  return { editor, open, close, submit, setLength, orientation, lock, house }
}
