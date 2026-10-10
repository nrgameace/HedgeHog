import { describe, expect, it } from 'vitest'

import { blankAnswers, iceCreamShop, quillstackAi, twoScoopsCreamery } from '../test/answers'
import { buildMockReport } from './mockReport'

const tickers = (answers: Parameters<typeof buildMockReport>[0]) => buildMockReport(answers, 30000).bets.map((bet) => bet.ticker)

// The "What Hedgehog should find" checklists in demo-data/*/background.md.
describe('buildMockReport on the north-star demo businesses', () => {
  it('Two Scoops Creamery: weather, energy, gas, rates and spending — but not its locked-in dairy', () => {
    const found = tickers(twoScoopsCreamery)

    expect(found).toEqual(expect.arrayContaining(['MOCK-RAIN', 'MOCK-HEAT', 'MOCK-POWER', 'MOCK-GAS', 'MOCK-FED', 'MOCK-CPI']))
    expect(found).not.toContain('MOCK-DAIRY')
    expect(buildMockReport(twoScoopsCreamery, 60000).bets[0].market).toContain('Austin, TX')
  })

  it('Quillstack AI: regulation, GPUs, rates and the funding market — and no weather', () => {
    const found = tickers(quillstackAi)

    expect(found).toEqual(expect.arrayContaining(['MOCK-AI-REG', 'MOCK-GPU', 'MOCK-FED', 'MOCK-FUNDING']))
    for (const weather of ['MOCK-RAIN', 'MOCK-HEAT', 'MOCK-SNOW']) expect(found).not.toContain(weather)
  })

  it('bets on rate cuts for Quillstack (cash in T-bills) but on hikes for Two Scoops (variable loan)', () => {
    const fedMarket = (answers: Parameters<typeof buildMockReport>[0]) =>
      buildMockReport(answers, 30000).bets.find((bet) => bet.ticker === 'MOCK-FED')?.market

    expect(fedMarket(quillstackAi)).toMatch(/cut/i)
    expect(fedMarket(twoScoopsCreamery)).toMatch(/raise/i)
  })

  it('keeps acronyms like GPU in capitals', () => {
    const gpuBet = buildMockReport(quillstackAi, 30000).bets.find((bet) => bet.ticker === 'MOCK-GPU')

    expect(gpuBet?.market).toContain('GPU prices')
    expect(gpuBet?.rationale).toContain('GPU')
  })
})

const totalBets = (answers: Parameters<typeof buildMockReport>[0]) =>
  buildMockReport(answers, 30000).bets.reduce((sum, bet) => sum + bet.amountUsd, 0)

describe('buildMockReport risk budget', () => {
  it('spends the monthly budget the owner gives instead of 5% of revenue', () => {
    expect(totalBets({ ...iceCreamShop, riskBudget: 'About $800 a month.' })).toBeLessThanOrEqual(800)
    expect(totalBets({ ...iceCreamShop, riskBudget: 'About $800 a month.' })).toBeGreaterThan(790)
  })

  it('understands thousands and yearly budgets', () => {
    expect(totalBets({ ...iceCreamShop, riskBudget: '$6,000' })).toBeGreaterThan(5990)
    expect(totalBets({ ...iceCreamShop, riskBudget: '2k per month' })).toBeGreaterThan(1990)
    expect(totalBets({ ...iceCreamShop, riskBudget: '$12,000 a year' })).toBeLessThanOrEqual(1000)
    expect(totalBets({ ...iceCreamShop, riskBudget: '$12,000 a year' })).toBeGreaterThan(990)
  })

  it('falls back to 5% of revenue when no amount is given', () => {
    expect(totalBets({ ...iceCreamShop, riskBudget: 'not sure yet' })).toBeGreaterThan(1490)
  })
})

describe('buildMockReport', () => {
  it('turns rain worries into a weather bet for the business location', () => {
    const report = buildMockReport({ ...blankAnswers, location: 'Austin, TX', pastImpacts: 'Rainy weekends' }, 30000)

    expect(report.bets).toHaveLength(1)
    expect(report.bets[0].market).toMatch(/rain/i)
    expect(report.bets[0].market).toContain('Austin, TX')
  })

  it('finds dependencies mentioned in any answer', () => {
    expect(tickers({ ...blankAnswers, operationalDependencies: 'gas for the van' })).toContain('MOCK-GAS')
    expect(tickers({ ...blankAnswers, keyMaterials: 'electricity for the freezers' })).toContain('MOCK-POWER')
    expect(tickers({ ...blankAnswers, keyMaterials: 'Coffee beans and milk' })).toEqual(expect.arrayContaining(['MOCK-COFFEE', 'MOCK-DAIRY']))
  })

  it('does not hedge a cost the owner already has locked in', () => {
    const report = buildMockReport({ ...blankAnswers, keyMaterials: 'Dairy', lockedInCosts: 'Fixed-price dairy contract' }, 30000)

    expect(report.bets.map((bet) => bet.ticker)).not.toContain('MOCK-DAIRY')
  })

  it('builds one concern per bet and spends about 5% of monthly revenue in total', () => {
    const report = buildMockReport(iceCreamShop, 30000)
    const total = report.bets.reduce((sum, bet) => sum + bet.amountUsd, 0)

    expect(report.concerns).toHaveLength(report.bets.length)
    expect(total).toBeGreaterThan(1400)
    expect(total).toBeLessThanOrEqual(1500)
  })

  it('returns no concerns or bets when nothing hedgeable is mentioned', () => {
    const report = buildMockReport({ ...blankAnswers, businessDescription: 'Accounting firm', location: 'Denver, CO', pastImpacts: 'Losing clients' }, 30000)

    expect(report.concerns).toEqual([])
    expect(report.bets).toEqual([])
  })
})
