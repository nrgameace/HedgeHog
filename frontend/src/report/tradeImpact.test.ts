import { describe, expect, it } from 'vitest'

import type { ProfitPoint } from '../types'
import { combinedNet, profitWithTrades, stakedPerYear, varianceMitigation } from './tradeImpact'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
// A normal year expects $10k profit a month; March came in $6k short.
const profit: ProfitPoint[] = MONTHS.map((period, index) => ({ period, expected: 10000, actual: index === 2 ? 4000 : 10000 }))
const net = (values: Record<number, number>) => MONTHS.map((_, index) => values[index] ?? 0)

describe('trade impact', () => {
  it('adds each month of trade results to profit', () => {
    expect(profitWithTrades(profit, net({ 2: 900 }))[2]).toBe(4900)
    expect(profitWithTrades(profit, net({ 0: -50 }))[0]).toBe(9950)
  })

  it('sums several trades month by month', () => {
    expect(combinedNet([net({ 0: -50, 2: 900 }), net({ 2: -100 })])).toEqual(net({ 0: -50, 2: 800 }))
  })

  it('measures variance mitigation as the share of the bad-month shortfall a trade covers', () => {
    expect(varianceMitigation(profit, net({ 2: 3000 }))).toBeCloseTo(0.5)
    expect(varianceMitigation(profit, net({ 2: 6000 }))).toBeCloseTo(1)
  })

  it('counts trades that cost money in a short month against mitigation, and ignores payouts in good months', () => {
    expect(varianceMitigation(profit, net({ 2: -600 }))).toBeCloseTo(-0.1)
    expect(varianceMitigation(profit, net({ 6: 5000 }))).toBe(0)
  })

  it('totals what a trade stakes over the year', () => {
    expect(stakedPerYear({ amountUsd: 100, tradeMonths: [3, 4, 5] })).toBe(300)
  })
})
