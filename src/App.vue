<script setup>
import { ref } from 'vue'
import FloorPlanEditor from './components/FloorPlanEditor.vue'
import SunroomViewer3D from './components/SunroomViewer3D.vue'
import BuildSummary from './components/BuildSummary.vue'
import { useFloorPlan } from './floorplan/useFloorPlan.js'
import { useSunroom } from './sunroom/useSunroom.js'
import { setPanelCount } from './floorplan/geometry.js'

const { plan, unit, commit } = useFloorPlan()
const { layout } = useSunroom()

const view = ref('2d')
const viewerMounted = ref(false) // create the WebGL context only once 3D is first opened
const notes = ref([])

function show(v) {
  view.value = v
  if (v === '3d') viewerMounted.value = true
}

function onCount(wallIndex, count) {
  const res = setPanelCount(plan.value, wallIndex, count)
  if (res.ok) commit(res.plan)
}
</script>

<template>
  <div class="app">
    <header class="header">
      <svg class="logo" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 11 12 4l9 7" />
        <path d="M5 10v9h14v-9" />
        <path d="M9 19v-5h6v5" />
      </svg>
      <span class="brand">SUNROOM</span>
    </header>
    <main class="workspace">
      <BuildSummary class="side" :layout="layout" :unit="unit" :notes="view === '3d' ? notes : []" @count="onCount" />
      <div class="stage">
        <FloorPlanEditor v-show="view === '2d'" />
        <SunroomViewer3D v-if="viewerMounted" v-show="view === '3d'" :layout="layout" :active="view === '3d'" @notes="notes = $event" />
        <div class="view-toggle">
          <button :class="{ on: view === '2d' }" title="2D floor plan" @click="show('2d')">
            <svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="1.5" /></svg>
          </button>
          <button :class="{ on: view === '3d' }" title="3D view" @click="show('3d')">
            <svg viewBox="0 0 24 24">
              <path d="M12 3 4 7.5v9L12 21l8-4.5v-9z" />
              <path d="M4 7.5 12 12l8-4.5M12 12v9" />
            </svg>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.header {
  height: 44px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  background: #f6f7f9;
  border-bottom: 1px solid var(--border);
}
.logo {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: var(--brand);
  stroke-width: 2;
  stroke-linejoin: round;
}
.brand {
  color: var(--brand);
  font-size: 18px;
  letter-spacing: 0.5px;
}
.workspace {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}
.side {
  flex: 0 0 290px;
}
.stage {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
}
.view-toggle {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  z-index: 4;
}
.view-toggle button {
  width: 46px;
  height: 36px;
  border: none;
  background: #eef0f3;
  color: #333;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.view-toggle button.on {
  background: var(--brand);
  color: #fff;
}
.view-toggle svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linejoin: round;
}
</style>
