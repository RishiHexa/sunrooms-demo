<script setup>
defineProps({
  orientation: { type: String, default: null }, // 'h' | 'v' | null
  locked: { type: Boolean, default: false },
  showLock: { type: Boolean, default: true },
  layout: { type: String, default: 'row' }, // 'row' | 'column'
})
const emit = defineEmits(['orientation', 'lock'])
</script>

<template>
  <div class="toggles" :class="layout">
    <button
      v-if="showLock"
      class="tg"
      :class="{ on: locked }"
      :title="locked ? 'Unlock length' : 'Lock length'"
      @click="emit('lock')"
    >
      <svg viewBox="0 0 16 16">
        <rect x="3.5" y="7" width="9" height="6.5" rx="1" />
        <path v-if="locked" d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
        <path v-else d="M5.5 7V5a2.5 2.5 0 0 1 4.9-.7" />
      </svg>
    </button>
    <button
      class="tg"
      :class="{ on: orientation === 'h' }"
      title="Keep horizontal"
      @click="emit('orientation', 'h')"
    >
      <span class="bar h" />
    </button>
    <button
      class="tg"
      :class="{ on: orientation === 'v' }"
      title="Keep vertical"
      @click="emit('orientation', 'v')"
    >
      <span class="bar v" />
    </button>
  </div>
</template>

<style scoped>
.toggles {
  display: flex;
  gap: 4px;
}
.toggles.column {
  flex-direction: column;
}
.tg {
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  border-radius: 3px;
  background: #d5d9df;
  color: #fff;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.tg:hover {
  background: #a9b3c2;
}
.tg.on {
  background: var(--brand);
}
.tg.on:hover {
  background: var(--brand-hover);
}
.bar {
  display: block;
  background: currentColor;
  border-radius: 1px;
}
.bar.h {
  width: 9px;
  height: 2px;
}
.bar.v {
  width: 2px;
  height: 9px;
}
svg {
  width: 11px;
  height: 11px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
}
</style>
