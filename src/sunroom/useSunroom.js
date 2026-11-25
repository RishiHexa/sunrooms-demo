import { computed } from 'vue'
import { useFloorPlan } from '../floorplan/useFloorPlan.js'
import { computeLayout } from './layout.js'
import { SPEC_4SEASON } from './spec4season.js'

const { plan } = useFloorPlan()

/** Sunroom layout derived from the current floor plan (recomputed on every plan change). */
const layout = computed(() => computeLayout(plan.value, SPEC_4SEASON))

export function useSunroom() {
  return { layout, spec: SPEC_4SEASON }
}
