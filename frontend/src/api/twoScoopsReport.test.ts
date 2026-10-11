import { describe, expect, it } from 'vitest'

import { combinedNet, varianceMitigation } from '../report/tradeImpact'
import { twoScoopsReport } from './twoScoopsReport'

const report = twoScoopsReport()
const bet = (ticker: string) => report.bets.find((b) => b.ticker === ticker)!

describe('twoScoopsReport', () => {
  it('finds a trade for every risk, so nothing is left without a market', () => {
    expect(report.unhedgedRisks).toEqual([])
  })

  it("hedges Two Scoops Creamery's risks, but not its locked-in dairy", () => {
    expect(report.bets.map((b) => b.ticker)).toEqual(['MOCK-RAIN', 'MOCK-HEAT', 'MOCK-POWER', 'MOCK-GAS', 'MOCK-FED', 'MOCK-CPI'])
    expect(bet('MOCK-RAIN').market).toContain('Austin, TX')
    expect(report.bets.map((b) => b.risk.factor)).toEqual(['Rain', 'Extreme heat', 'Energy costs', 'Gas prices', 'Interest rates', 'Inflation'])
  })

  it('never stakes more than its $800 monthly budget in any month', () => {
    for (let month = 0; month < 12; month++) {
      const staked = report.bets.filter((b) => b.tradeMonths.includes(month)).reduce((sum, b) => sum + b.amountUsd, 0)
      expect(staked).toBeLessThanOrEqual(800)
    }
  })

  it("is simulated on Two Scoops' real 2024 profit, when rain wrecked May and June", () => {
    expect(report.profitSeries).toHaveLength(12)
    expect(report.profitSeries[4]).toMatchObject({ period: 'May', actual: 4724 })
    expect(report.profitSeries[5].actual).toBeLessThan(report.profitSeries[5].expected / 2)
  })

  it('has the rain trade pay out in May and June and cost its stake in the other traded months', () => {
    const rain = bet('MOCK-RAIN')

    expect(rain.monthlyNetUsd[4]).toBeGreaterThan(2000)
    expect(rain.monthlyNetUsd[5]).toBeGreaterThan(2000)
    expect(rain.monthlyNetUsd[3]).toBe(-rain.amountUsd)
    expect(rain.monthlyNetUsd[0]).toBe(0)
  })

  it('covers a meaningful share of the bad-month shortfall overall, mostly through rain', () => {
    const total = varianceMitigation(report.profitSeries, combinedNet(report.bets.map((b) => b.monthlyNetUsd)))

    expect(total).toBeGreaterThan(0.1)
    expect(varianceMitigation(report.profitSeries, bet('MOCK-RAIN').monthlyNetUsd)).toBeGreaterThan(0.1)
  })
})
