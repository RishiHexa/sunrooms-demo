<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import ConstraintToggles from './ConstraintToggles.vue'

const props = defineProps({
  modelValue: { type: String, required: true },
  x: { type: Number, required: true },
  y: { type: Number, required: true },
  boundsW: { type: Number, required: true },
  boundsH: { type: Number, required: true },
  unit: { type: String, required: true },
  error: { type: String, default: '' },
  orientation: { type: String, default: null },
  locked: { type: Boolean, default: false },
  house: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'submit', 'close', 'orientation', 'lock', 'house'])

const input = ref(null)
onMounted(() =>
  nextTick(() => {
    input.value?.focus()
    input.value?.select()
  }),
)

const W = 136
const H = 130
const style = computed(() => {
  const left = Math.min(Math.max(props.x - W / 2, 8), Math.max(props.boundsW - W - 8, 8))
  const top = Math.min(Math.max(props.y - 20, 8), Math.max(props.boundsH - H - 8, 8))
  return { left: left + 'px', top: top + 'px', width: W + 'px' }
})

function onKey(e) {
  if (e.key === 'Enter') emit('submit')
  else if (e.key === 'Escape') emit('close')
}
</script>

<template>
  <div class="editor" :style="style" @pointerdown.stop>
    <button class="close" title="Close" @click="emit('close')">×</button>
    <label class="title">{{ unit === 'mm' ? 'Millimeters' : 'Inches' }}</label>
    <input
      ref="input"
      class="value"
      :value="modelValue"
      inputmode="decimal"
      @input="emit('update:modelValue', $event.target.value)"
      @keydown="onKey"
    />
    <div v-if="error" class="error">{{ error }}</div>
    <ConstraintToggles
      class="row"
      :orientation="orientation"
      :locked="locked"
      @orientation="(o) => emit('orientation', o)"
      @lock="emit('lock')"
    />
    <button class="house-btn" :class="{ on: house }" :disabled="house" @click="emit('house')">
      {{ house ? 'House wall' : 'Set as house wall' }}
    </button>
  </div>
</template>

<style scoped>
.editor {
  position: absolute;
  background: #f4f5f7;
  border: 1px solid #e1e4e8;
  border-radius: 4px;
  padding: 10px 10px 8px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  z-index: 5;
}
.title {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}
.close {
  position: absolute;
  top: 2px;
  right: 4px;
  border: none;
  background: none;
  font-size: 16px;
  line-height: 16px;
  cursor: pointer;
  color: #333;
}
.value {
  width: 100%;
  height: 22px;
  border: 1px solid #c8cdd4;
  border-radius: 2px;
  padding: 0 5px;
  font-size: 12px;
  background: #fff;
}
.value:focus {
  outline: 1px solid var(--brand);
}
.error {
  color: #b42318;
  font-size: 11px;
  margin-top: 4px;
  line-height: 1.25;
}
.row {
  justify-content: center;
  margin-top: 8px;
}
.house-btn {
  display: block;
  width: 100%;
  margin-top: 8px;
  height: 24px;
  border: 1px solid #c8cdd4;
  border-radius: 3px;
  background: #fff;
  color: var(--brand);
  font-size: 11px;
  cursor: pointer;
}
.house-btn.on {
  background: #e8ebf0;
  color: #555;
  cursor: default;
}
.row :deep(.tg) {
  width: 22px;
  height: 22px;
}
</style>
