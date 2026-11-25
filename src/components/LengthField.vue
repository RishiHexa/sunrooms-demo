<script setup>
import { ref, watch } from 'vue'
import { editValue, formatInches, formatMm, mmToInches, parseLength } from '../floorplan/units.js'

/**
 * One length input: label, − / typed value / unit / +.
 * Value is INCHES; mm is display/input only. Emits `change` with the new value in inches.
 * Validation of the value itself (limits, geometry) is done by the caller.
 */
const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: null },
  unit: { type: String, default: 'in' },
  /** Lowest value the − button steps to (inches). Typed values are not blocked here. */
  min: { type: Number, default: null },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['change'])

const text = ref('')
const parseError = ref('')
const focused = ref(false)

// The text shown for the stored value. It is rounded for display (1/16" / 0.1 mm), so committing
// it unchanged would replace an exact stored value with the rounded one: only edited text commits.
let shown = ''
const sync = () => {
  text.value = props.value == null ? '' : editValue(props.value, props.unit)
  shown = text.value
  parseError.value = ''
}
watch(() => [props.value, props.unit], () => {
  if (!focused.value) sync()
}, { immediate: true })

/** Step: 1" in inches, 10 mm in mm. */
const step = () => (props.unit === 'mm' ? mmToInches(10) : 1)
const fmt = (v) => (props.unit === 'mm' ? formatMm(v) : formatInches(v))

function commitText() {
  if (text.value === shown) return sync() // not edited: keep the exact stored value
  const inches = parseLength(text.value, props.unit)
  if (!Number.isFinite(inches)) {
    parseError.value = props.unit === 'mm' ? 'Enter a number in mm.' : 'Enter inches, e.g. 84 or 84 1/2.'
    return
  }
  parseError.value = ''
  if (props.value == null || Math.abs(inches - props.value) > 1e-9) emit('change', inches)
  else sync()
}

function bump(dir) {
  if (props.value == null) return
  emit('change', props.value + dir * step())
}

const canDecrease = () => props.value != null && (props.min == null || props.value - step() >= props.min - 1e-9)

function onKey(e) {
  if (e.key === 'Enter') e.target.blur()
  else if (e.key === 'Escape') {
    sync()
    e.target.blur()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    bump(1)
  } else if (e.key === 'ArrowDown' && canDecrease()) {
    e.preventDefault()
    bump(-1)
  }
}
function onBlur() {
  focused.value = false
  commitText()
  // show the stored value again (a change arrives through the `value` prop); keep bad input
  // visible next to its parse error so it can be corrected
  if (!parseError.value) sync()
}
</script>

<template>
  <div class="field" :class="{ disabled }">
    <div class="label">{{ label }}</div>
    <div class="row">
      <button class="step" :disabled="disabled || !canDecrease()" :title="`Decrease by ${fmt(step())}`" @click="bump(-1)">
        <svg viewBox="0 0 16 16"><path d="M3 8h10" /></svg>
      </button>
      <input
        class="value"
        :value="text"
        :disabled="disabled"
        inputmode="decimal"
        :aria-label="label"
        @input="text = $event.target.value"
        @focus="focused = true; $event.target.select()"
        @blur="onBlur"
        @keydown="onKey"
      />
      <span class="unit">{{ unit === 'mm' ? 'mm' : 'inch' }}</span>
      <button class="step" :disabled="disabled || value == null" :title="`Increase by ${fmt(step())}`" @click="bump(1)">
        <svg viewBox="0 0 16 16"><path d="M3 8h10M8 3v10" /></svg>
      </button>
    </div>
    <div v-if="parseError || error" class="error">{{ parseError || error }}</div>
    <div v-else-if="hint" class="hint">{{ hint }}</div>
  </div>
</template>

<style scoped>
.field {
  padding: 8px 0 6px;
}
.label {
  font-size: 13px;
  color: #333;
  margin-bottom: 4px;
}
.row {
  display: grid;
  grid-template-columns: 30px 1fr auto 30px;
  align-items: center;
  gap: 6px;
}
.step {
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: #333;
}
.step:hover:not(:disabled) {
  background: #eef2f8;
}
.step:disabled {
  color: #c0c4ca;
  cursor: default;
}
.step svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  stroke-linecap: round;
}
.value {
  min-width: 0;
  height: 30px;
  border: 1px solid transparent;
  border-bottom-color: #d5d9df;
  background: transparent;
  text-align: center;
  font-size: 15px;
  color: #1f2328;
  border-radius: 3px 3px 0 0;
}
.value:hover:not(:disabled) {
  border-bottom-color: #9aa3ae;
}
.value:focus {
  outline: none;
  border-color: var(--brand);
  background: #fff;
}
.unit {
  font-size: 12px;
  color: #4a5568;
  min-width: 26px;
}
.hint,
.error {
  font-size: 11px;
  line-height: 1.35;
  margin-top: 4px;
}
.hint {
  color: #7a818b;
}
.error {
  color: #b42318;
}
.disabled .label,
.disabled .unit {
  color: #a0a6ae;
}
</style>
