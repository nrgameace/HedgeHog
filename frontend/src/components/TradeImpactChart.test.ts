import { describe, expect, it } from 'vitest'

import { shortfallRows, totalCovered, totalShortfall } from './TradeImpactChart'
import type { ProfitPoint } from '../types'

const point = (period: string, expected: number, actual: number): ProfitPoint => ({ period, expected, actual })

describe('shortfallRows', () => {
  it('reads a month below its normal as a gap', () => {
    const [row] = shortfallRows([point('Jun', 15_753, 3_230)], [0])

    expect(row.shortfall).toBe(12_523)
    expect(row.uncovered).toBe(12_523)
    expect(row.covered).toBe(0)
  })

  it('counts a surplus month as no gap at all', () => {
    const [row] = shortfallRows([point('Jul', 18_113, 20_550)], [0])

    expect(row.shortfall).toBe(0)
    expect(row.uncovered).toBe(0)
  })

  it('splits a gap into the part covered and the part left open', () => {
    const [row] = shortfallRows([point('Jun', 15_753, 3_230)], [769])

    expect(row.covered).toBe(769)
    expect(row.uncovered).toBe(11_754)
    expect(row.covered + row.uncovered).toBe(row.shortfall)
  })

  it('clamps cover to the gap, since paying out more is a windfall not a hedge', () => {
    const [row] = shortfallRows([point('Dec', 5_431, 4_542)], [10_000])

    expect(row.shortfall).toBe(889)
    expect(row.covered).toBe(889)
    expect(row.uncovered).toBe(0)
  })

  it('credits no cover in a month that had no gap', () => {
    const [row] = shortfallRows([point('Jul', 18_113, 20_550)], [500])

    expect(row.covered).toBe(0)
  })

  it('shows a premium that paid nothing back as below the line', () => {
    const [row] = shortfallRows([point('Mar', 7_524, 10_124)], [-400])

    expect(row.worsened).toBe(-400)
    expect(row.covered).toBe(0)
  })

  it('never reports a positive net as worsening', () => {
    const [row] = shortfallRows([point('Jun', 15_753, 3_230)], [769])

    expect(row.worsened).toBe(0)
  })

  it('tolerates a short net array', () => {
    const rows = shortfallRows([point('Jan', 100, 50), point('Feb', 100, 50)], [10])

    expect(rows[1].covered).toBe(0)
    expect(rows).toHaveLength(2)
  })

  it('keeps one row per month in order', () => {
    const rows = shortfallRows([point('Jan', 1, 1), point('Feb', 1, 1), point('Mar', 1, 1)], [0, 0, 0])

    expect(rows.map((row) => row.period)).toEqual(['Jan', 'Feb', 'Mar'])
  })
})

describe('year totals', () => {
  const profit = [point('May', 12_773, 4_724), point('Jun', 15_753, 3_230), point('Jul', 18_113, 20_550)]
  const rows = shortfallRows(profit, [769, 769, 0])

  it('adds up the gaps, ignoring surplus months', () => {
    expect(totalShortfall(rows)).toBe(8_049 + 12_523)
  })

  it('adds up what was covered', () => {
    expect(totalCovered(rows)).toBe(1_538)
  })

  it('gives the share of the year s gap that was covered', () => {
    // The honest headline: a few hundred a month against twenty thousand of holes.
    expect(totalCovered(rows) / totalShortfall(rows)).toBeCloseTo(0.0748, 3)
  })
})
