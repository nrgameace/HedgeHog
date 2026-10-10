import type { Bet, HedgeReport } from '../types'

// MOCK DATA: until the backend exists, the results page always shows Two Scoops Creamery
// (demo-data/two-scoops-creamery), simulating its trades against its real 2024 profit.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
// financials.csv operating_income: 2024 as it happened; "expected" = average of 2023 and 2025.
const ACTUAL_2024 = [1156, 3349, 10124, 12539, 4724, 3230, 20550, 16561, 13003, 9943, 4895, 4542]
const EXPECTED = [188, 3012, 8328, 12638, 13097, 18326, 18792, 19722, 14530, 12162, 4408, 7206]
const FOMC_MEETINGS_2024 = [0, 2, 4, 5, 6, 8, 10, 11]

type TradePlan = Omit<Bet, 'monthlyNetUsd'> & {
  // Market price of a YES contract (its implied probability); a hit pays amountUsd / price.
  price: number
  // Months of 2024 in which the event happened, so the trade paid out.
  hitMonths: number[]
}

const TRADES: TradePlan[] = [
  {
    risk: { factor: 'Rain', explanation: 'Rainy days empty the patio; May–June 2024 cut profit by more than half.' },
    ticker: 'MOCK-RAIN', market: 'Will Austin, TX get more than 10 rainy days this month?', side: 'YES', amountUsd: 400,
    frequency: 'Monthly, Apr–Jun and Sep–Oct (patio season)', tradeMonths: [3, 4, 5, 8, 9], price: 0.15, hitMonths: [4, 5],
    rationale: 'A rainy month empties the patio. This pays out when it happens, as it did in May and June 2024.',
  },
  {
    risk: { factor: 'Extreme heat', explanation: '100°F+ days keep evening crowds home and send the electric bill up.' },
    ticker: 'MOCK-HEAT', market: 'Will Austin, TX hit 105°F this month?', side: 'YES', amountUsd: 200,
    frequency: 'Monthly, Jun–Aug', tradeMonths: [5, 6, 7], price: 0.3, hitMonths: [7],
    rationale: 'Extreme heat keeps evening crowds home and doubles the electric bill.',
  },
  {
    risk: { factor: 'Energy costs', explanation: 'Freezers and AC run all summer, so electricity prices hit hard.' },
    ticker: 'MOCK-POWER', market: 'Will Texas retail electricity prices rise this month?', side: 'YES', amountUsd: 100,
    frequency: 'Monthly, Jun–Sep', tradeMonths: [5, 6, 7, 8], price: 0.35, hitMonths: [5, 7],
    rationale: 'Freezers run 24/7. Covers summer electricity price jumps.',
  },
  {
    risk: { factor: 'Gas prices', explanation: 'The delivery van and wholesale runs depend on fuel.' },
    ticker: 'MOCK-GAS', market: 'Will the U.S. average gas price be above $3.50 at quarter end?', side: 'YES', amountUsd: 50,
    frequency: 'Quarterly', tradeMonths: [0, 3, 6, 9], price: 0.3, hitMonths: [],
    rationale: 'The delivery van and grocery runs get pricier when gas spikes.',
  },
  {
    risk: { factor: 'Interest rates', explanation: 'The van loan has a variable rate (prime + 2.75%).' },
    ticker: 'MOCK-FED', market: 'Will the Fed raise interest rates at this meeting?', side: 'YES', amountUsd: 30,
    frequency: 'Every Fed meeting (8 a year)', tradeMonths: FOMC_MEETINGS_2024, price: 0.1, hitMonths: [],
    rationale: 'The van loan has a variable rate. Pays out if a hike raises the payments.',
  },
  {
    risk: { factor: 'Inflation', explanation: 'Ice cream is a treat: customers cut back first when prices rise.' },
    ticker: 'MOCK-CPI', market: 'Will monthly CPI inflation come in above 0.3%?', side: 'YES', amountUsd: 50,
    frequency: 'Monthly', tradeMonths: MONTHS.map((_, index) => index), price: 0.4, hitMonths: [0, 2, 3],
    rationale: 'When prices rise everywhere, customers cut back on treats first.',
  },
]

function simulate({ price, hitMonths, ...bet }: TradePlan): Bet {
  const monthlyNetUsd = MONTHS.map((_, month) => {
    const stake = bet.tradeMonths.includes(month) ? bet.amountUsd : 0
    const payout = hitMonths.includes(month) ? Math.round(bet.amountUsd / price) : 0
    return payout - stake
  })
  return { ...bet, monthlyNetUsd }
}

export function twoScoopsReport(): HedgeReport {
  return {
    simulatedPeriod: '2024',
    bets: TRADES.map(simulate),
    profitSeries: MONTHS.map((period, index) => ({ period, expected: EXPECTED[index], actual: ACTUAL_2024[index] })),
  }
}
