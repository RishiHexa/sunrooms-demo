/**
 * Unit conversion, display formatting and input parsing.
 * Canonical stored unit is INCHES; mm is display/input only.
 */

export const MM_PER_INCH = 25.4

/** Display precision for inches: nearest 1/16". */
export const INCH_DENOMINATOR = 16

export const inchesToMm = (inches) => inches * MM_PER_INCH
export const mmToInches = (mm) => mm / MM_PER_INCH

/**
 * Split inches into whole + reduced fraction at 1/16" precision.
 * 44.8125 -> { negative: false, whole: 44, num: 13, den: 16 }
 */
export function toFractionParts(inches) {
  const negative = inches < 0
  const sixteenths = Math.round(Math.abs(inches) * INCH_DENOMINATOR)
  let whole = Math.floor(sixteenths / INCH_DENOMINATOR)
  let num = sixteenths % INCH_DENOMINATOR
  let den = INCH_DENOMINATOR
  while (num > 0 && num % 2 === 0) {
    num /= 2
    den /= 2
  }
  return { negative, whole, num, den }
}

/** Plain-text inches, e.g. 44 13/16" */
export function formatInches(inches) {
  const { negative, whole, num, den } = toFractionParts(inches)
  const sign = negative ? '-' : ''
  if (num === 0) return `${sign}${whole}"`
  if (whole === 0) return `${sign}${num}/${den}"`
  return `${sign}${whole} ${num}/${den}"`
}

/** Millimetres rounded to 0.1 mm, trailing zero dropped, e.g. 2057.4 mm */
export function formatMm(inches) {
  const mm = Math.round(inchesToMm(inches) * 10) / 10
  return `${Number.isInteger(mm) ? mm : mm.toFixed(1)} mm`
}

/** Angle in degrees, max 2 decimals, trailing zeros dropped: 90°, 116.36° */
export function formatAngle(deg) {
  const r = Math.round(deg * 100) / 100
  return `${parseFloat(r.toFixed(2))}°`
}

/** Value placed in the edit box (no unit suffix). */
export function editValue(inches, unit) {
  if (unit === 'mm') {
    const mm = Math.round(inchesToMm(inches) * 10) / 10
    return String(parseFloat(mm.toFixed(1)))
  }
  const { whole, num, den } = toFractionParts(inches)
  if (num === 0) return String(whole)
  return whole === 0 ? `${num}/${den}` : `${whole} ${num}/${den}`
}

/**
 * Parse user input into INCHES. Returns NaN when the input is not understood.
 * Inches accept: 81 | 81.5 | 44 13/16 | 44-13/16 | 13/16 (optional trailing ")
 * mm accepts a decimal number (optional trailing "mm").
 */
export function parseLength(text, unit) {
  const s = String(text ?? '').trim()
  if (unit === 'mm') {
    const m = s.replace(/\s*mm$/i, '')
    if (!/^\d+(\.\d+)?$|^\.\d+$/.test(m)) return NaN
    return mmToInches(parseFloat(m))
  }
  const t = s.replace(/\s*("|in\.?|inches)$/i, '').trim()
  let m
  if ((m = t.match(/^(\d+(?:\.\d+)?|\.\d+)$/))) return parseFloat(m[1])
  if ((m = t.match(/^(\d+)\s*[- ]\s*(\d+)\s*\/\s*(\d+)$/))) {
    const den = parseInt(m[3], 10)
    if (den === 0) return NaN
    return parseInt(m[1], 10) + parseInt(m[2], 10) / den
  }
  if ((m = t.match(/^(\d+)\s*\/\s*(\d+)$/))) {
    const den = parseInt(m[2], 10)
    if (den === 0) return NaN
    return parseInt(m[1], 10) / den
  }
  return NaN
}
