/**
 * Slider window opening motion — VISUAL ONLY.
 *
 * Source: the supplier's 225-series slider macros (Extracted/Sunroom-Drawings/sunroom_build/v2/Macro):
 *   SliderSash225_Build.FCMacro   two sashes; the INTERIOR sash is the one that moves. Its X axis
 *                                 runs left -> right seen from INSIDE, the interior sash is on the
 *                                 right and slides in -X until it would hit the frame or the
 *                                 exterior sash ("hard stop"); TRAVEL = hard stop - 1/8".
 *   SliderSash225_Animate.FCMacro 3 s to open, same to close, eased 0.5 - 0.5 cos(pi t).
 * Seen from OUTSIDE (our wall-local s axis) that is: interior sash on the LEFT, sliding RIGHT.
 *
 * The 4-Season (GF50) system has no sash profiles in the supplier files, so the sashes moved here
 * are the placeholder sashes from build3d.js and the hard stop is the placeholder geometry (the
 * interior sash's leading edge reaching the far side of the lite). Whether a 4-Season slider
 * opens the same way as the 225 slider is NOT confirmed. Nothing here is product data.
 */

export const SLIDER_MOTION = Object.freeze({
  stopShort: 0.125, // SliderSash225_Build: stop 1/8" short of the hard stop
  seconds: 3.0, // SliderSash225_Animate: SECONDS (open; close takes the same)
  direction: 1, // +s (to the right seen from outside) = -X of the 225 macro (seen from inside)
})

/**
 * Travel of the placeholder interior sash. It spans [s0, mid + overlap/2] (see build3d.js), so it
 * reaches the far edge of the lite after (width/2 - overlap/2); the 225 rule stops it 1/8" short.
 * Returns 0 when there is no room to move.
 */
export function sliderTravel(liteWidth, overlap) {
  const hardStop = liteWidth / 2 - overlap / 2
  return Math.max(0, hardStop - SLIDER_MOTION.stopShort)
}

/** SliderSash225_Animate ease: smooth start and stop. t in [0, 1]. */
export function easeSlide(t) {
  const c = Math.min(1, Math.max(0, t))
  return 0.5 - 0.5 * Math.cos(Math.PI * c)
}
