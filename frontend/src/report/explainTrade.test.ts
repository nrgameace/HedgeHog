import { describe, expect, it } from 'vitest'

import type { Bet } from '../types'
import { explainTrade } from './explainTrade'

const MONTHS = 12
const net = (values: Record<number, number>) => Array.from({ length: MONTHS }, (_, index) => values[index] ?? 0)

const rainBet: Bet = {
  risk: { factor: 'Rain', explanation: 'Rainy days cut foot traffic.' },
  market: 'Will it rain in Austin this month?', ticker: 'MOCK-RAIN', side: 'YES', amountUsd: 100, frequency: 'Monthly, Feb–Mar',
  tradeMonths: [1, 2], rationale: 'Pays out on rain.', monthlyNetUsd: net({ 1: -100, 2: 900 }),
}

const text = (bet: Bet) => explainTrade(bet, '2024').map(({ label, detail }) => `${label}: ${detail}`).join('\n')

describe('explainTrade', () => {
  it('walks through the stake, what happens either way, and how it went last period', () => {
    expect(explainTrade(rainBet, '2024').map(({ label }) => label)).toEqual(['The trade', 'If it happens', 'If it doesn’t', 'In 2024'])
    const explanation = text(rainBet)

    expect(explanation).toContain('You put $100 on YES for “Will it rain in Austin this month?”')
    expect(explanation).toContain('pays out about $1,000')
    expect(explanation).toContain('You lose the $100 stake')
    expect(explanation).toContain('paid out in 1 month')
    expect(explanation).toContain('staked $200 in total and come out +$800 overall')
  })

  it('flips the outcomes for a NO position', () => {
    const labels = explainTrade({ ...rainBet, side: 'NO' }, '2024').map(({ label }) => label)

    expect(labels).toEqual(['The trade', 'If it doesn’t happen', 'If it does', 'In 2024'])
  })

  it('frames a trade that never paid out as the cost of being covered', () => {
    const explanation = text({ ...rainBet, monthlyNetUsd: net({ 1: -100, 2: -100 }) })

    expect(explanation).toContain('It never paid out in 2024')
    expect(explanation).toContain('$200')
    expect(explanation).not.toContain('pays out about')
  })

  it('uses no em dashes', () => {
    expect(text(rainBet)).not.toContain('\u2014')
  })
})
