import { describe, expect, it } from 'vitest'
import { editValue, formatAngle, formatInches, formatMm, parseLength } from './units.js'

describe('formatInches', () => {
  it('formats to the nearest 1/16 with reduced fractions', () => {
    expect(formatInches(81)).toBe('81"')
    expect(formatInches(40.5)).toBe('40 1/2"')
    expect(formatInches(44.8125)).toBe('44 13/16"')
    expect(formatInches(0.25)).toBe('1/4"')
    expect(formatInches(44.999)).toBe('45"')
  })
})

describe('formatMm / formatAngle', () => {
  it('formats mm to 0.1', () => {
    expect(formatMm(81)).toBe('2057.4 mm')
    expect(formatMm(100)).toBe('2540 mm')
  })
  it('formats angles to max 2 decimals', () => {
    expect(formatAngle(90)).toBe('90°')
    expect(formatAngle(116.3649)).toBe('116.36°')
    expect(formatAngle(89.999999)).toBe('90°')
  })
})

describe('parseLength', () => {
  it('parses inch forms', () => {
    expect(parseLength('81', 'in')).toBe(81)
    expect(parseLength('81.5', 'in')).toBe(81.5)
    expect(parseLength('44 13/16', 'in')).toBe(44.8125)
    expect(parseLength('44-13/16"', 'in')).toBe(44.8125)
    expect(parseLength('13/16', 'in')).toBe(0.8125)
  })
  it('parses mm into inches', () => {
    expect(parseLength('2540', 'mm')).toBe(100)
    expect(parseLength('25.4 mm', 'mm')).toBe(1)
  })
  it('returns NaN for anything else (never guesses)', () => {
    for (const s of ['', 'abc', '1/0', '12ft', '-5', '5 /']) {
      expect(parseLength(s, 'in')).toBeNaN()
    }
    expect(parseLength('1,5', 'mm')).toBeNaN()
  })
  it('round-trips the edit value', () => {
    expect(parseLength(editValue(44.8125, 'in'), 'in')).toBe(44.8125)
  })
})
