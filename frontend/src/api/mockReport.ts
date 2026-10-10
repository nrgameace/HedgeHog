import type { Bet, HedgeReport, QuestionnaireAnswers, RevenuePoint } from '../types'

// MOCK DATA: stands in for the backend's /analyze response until the real pipeline exists.

const KNOWN_FACTORS: Record<string, { explanation: string; market: string; ticker: string }> = {
  rain: {
    explanation: 'Rainy days cut foot traffic, so wet weeks drag revenue down.',
    market: 'Will it rain more than 3 days this week?',
    ticker: 'MOCK-RAIN',
  },
  'gas prices': {
    explanation: 'Rising gas prices raise delivery and supply costs.',
    market: 'Will the national average gas price exceed $3.50 this month?',
    ticker: 'MOCK-GAS',
  },
  'gpu prices': {
    explanation: 'GPU price spikes make hardware and compute more expensive.',
    market: 'Will flagship GPU prices rise this quarter?',
    ticker: 'MOCK-GPU',
  },
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const UNHEDGED_SWINGS = [0.12, -0.18, 0.05, -0.22, 0.15, -0.08, 0.2, -0.15, 0.03, -0.2, 0.1, -0.05]

function describeFactor(factor: string) {
  return KNOWN_FACTORS[factor.toLowerCase()] ?? {
    explanation: `Changes in ${factor.toLowerCase()} move your revenue up and down.`,
    market: `Will ${factor.toLowerCase()} move against your business this month?`,
    ticker: `MOCK-${factor.toUpperCase().replace(/[^A-Z0-9]+/g, '-')}`,
  }
}

function buildRevenueSeries(expectedEarnings: number): RevenuePoint[] {
  return MONTHS.map((period, index) => ({
    period,
    unhedged: Math.round(expectedEarnings * (1 + UNHEDGED_SWINGS[index])),
    hedged: Math.round(expectedEarnings * (1 + UNHEDGED_SWINGS[index] * 0.3)),
  }))
}

export function buildMockReport(answers: QuestionnaireAnswers): HedgeReport {
  const amountUsd = Math.round((answers.expectedEarnings * 0.05) / answers.factors.length)
  const bets: Bet[] = answers.factors.map((factor) => {
    const { market, ticker } = describeFactor(factor)
    return { market, ticker, side: 'YES', amountUsd, rationale: `Pays out when ${factor.toLowerCase()} hurts your sales.` }
  })
  return {
    concerns: answers.factors.map((factor) => ({ factor, explanation: describeFactor(factor).explanation })),
    bets,
    revenueSeries: buildRevenueSeries(answers.expectedEarnings),
  }
}
