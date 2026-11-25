import { ref, computed, shallowRef } from 'vue'
import { createDefaultPlan } from './defaults.js'
import { clonePlan } from './geometry.js'

const HISTORY_LIMIT = 100

/**
 * Floor plan state with undo/redo. Module-level singleton so later steps
 * (3D view, etc.) read the same plan.
 */
const plan = shallowRef(createDefaultPlan())
const undoStack = ref([])
const redoStack = ref([])
/** Display / input unit only. Stored values are always inches. */
const unit = ref('in')

function pushHistory(snapshot) {
  undoStack.value.push(clonePlan(snapshot))
  if (undoStack.value.length > HISTORY_LIMIT) undoStack.value.shift()
  redoStack.value = []
}

/** Replace the plan with a new one, recording the previous plan for undo. */
function commit(next) {
  pushHistory(plan.value)
  plan.value = next
}

/** Live update during a drag — history is recorded once via `commitFrom`. */
function preview(next) {
  plan.value = next
}

/** Finish a drag: record `before` for undo if anything changed. */
function commitFrom(before) {
  if (JSON.stringify(before) !== JSON.stringify(plan.value)) pushHistory(before)
}

function undo() {
  if (!undoStack.value.length) return
  redoStack.value.push(clonePlan(plan.value))
  plan.value = undoStack.value.pop()
}

function redo() {
  if (!redoStack.value.length) return
  undoStack.value.push(clonePlan(plan.value))
  plan.value = redoStack.value.pop()
}

export function useFloorPlan() {
  return {
    plan,
    unit,
    canUndo: computed(() => undoStack.value.length > 0),
    canRedo: computed(() => redoStack.value.length > 0),
    commit,
    preview,
    commitFrom,
    undo,
    redo,
  }
}
