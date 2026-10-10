import type { HedgeReport, QuestionnaireAnswers, RevenuePoint } from '../types'

// MOCK DATA: stands in for the backend's /analyze response until the real pipeline exists.
// Keyword rules fake what the model will do: spot hedgeable dependencies in the free-text answers.

type HedgeWording = {
  explanation: string
  market: (place: string) => string
  rationale: string
}

type HedgeRule = HedgeWording & {
  ticker: string
  factor: string
  keywords: RegExp
  // Alternate wording when the answers show the risk runs the other way.
  reversed?: HedgeWording & { keywords: RegExp }
}

const HEDGE_RULES: HedgeRule[] = [
  {
    ticker: 'MOCK-RAIN', factor: 'Rain', keywords: /\b(rain\w*|storms?|stormy|wet)\b/i,
    explanation: 'Rainy days keep customers away, so wet stretches drag revenue down.',
    market: (place) => `Will it rain in ${place} on more than 8 days this month?`,
    rationale: 'Pays out in a rainy month, when foot traffic drops.',
  },
  {
    ticker: 'MOCK-HEAT', factor: 'Extreme heat', keywords: /\b(heat|heat ?waves?|hot)\b/i,
    explanation: 'Heat waves change how many people come out and raise cooling costs.',
    market: (place) => `Will ${place} hit 100°F this month?`,
    rationale: 'Pays out in a heat wave, offsetting lost sales and higher bills.',
  },
  {
    ticker: 'MOCK-SNOW', factor: 'Snow and cold', keywords: /\b(snow\w*|blizzards?|freezing|frost|cold (snaps?|weather))\b/i,
    explanation: 'Snow and cold snaps keep customers home and can shut operations down.',
    market: (place) => `Will ${place} get more than 6 inches of snow this month?`,
    rationale: 'Pays out in a snowy month, when business slows.',
  },
  {
    ticker: 'MOCK-GAS', factor: 'Gas prices', keywords: /\b(gas|gasoline|fuel|diesel|vans?|trucks?|deliver\w*|driving)\b/i,
    explanation: 'Rising gas prices make deliveries and driving more expensive.',
    market: () => 'Will the U.S. average gas price be above $3.50 at month end?',
    rationale: 'Pays out when gas gets expensive, covering higher fuel costs.',
  },
  {
    ticker: 'MOCK-POWER', factor: 'Energy costs', keywords: /\b(electric\w*|power|energy|refrigerat\w*|freezers?|air condition\w*)\b/i,
    explanation: 'Higher electricity prices raise the cost of running equipment.',
    market: () => 'Will U.S. electricity prices rise this month?',
    rationale: 'Pays out when energy prices climb, offsetting bigger bills.',
  },
  {
    ticker: 'MOCK-FED', factor: 'Interest rates', keywords: /\b(loans?|interest|credit|debt|mortgage)\b/i,
    explanation: 'If rates go up, a variable-rate loan or credit line costs more each month.',
    market: () => 'Will the Fed raise interest rates at its next meeting?',
    rationale: 'Pays out if rates rise, covering higher loan payments.',
    reversed: {
      keywords: /\b(rate cuts?|t-?bills?|treasur\w*|interest on our cash)\b/i,
      explanation: 'Your cash earns interest, so every rate cut shrinks that income.',
      market: () => 'Will the Fed cut interest rates at its next meeting?',
      rationale: 'Pays out if rates fall, offsetting lower interest on your cash.',
    },
  },
  {
    ticker: 'MOCK-CPI', factor: 'Inflation', keywords: /\b(inflation|recession|economy|cut(ting)? back|spend(ing)? less)\b/i,
    explanation: 'When prices rise everywhere, customers cut back on extras.',
    market: () => 'Will monthly CPI inflation come in above 0.3%?',
    rationale: 'Pays out when inflation runs hot and customers spend less.',
  },
  {
    ticker: 'MOCK-AI-REG', factor: 'AI regulation', keywords: /\b(regulat\w*|legislation|liability bill|ai[- ]liability)\b/i,
    explanation: 'New AI rules can make customers pause purchases or cancel while they assess liability.',
    market: () => 'Will a state pass an AI liability law this year?',
    rationale: 'Pays out if the law passes, offsetting lost and delayed deals.',
  },
  {
    ticker: 'MOCK-FUNDING', factor: 'Funding market', keywords: /\b(fundrais\w*|funding market|series [a-c]|venture capital|nasdaq|stock market)\b/i,
    explanation: 'A tech selloff makes the next funding round smaller, later, or both.',
    market: () => 'Will the Nasdaq fall more than 10% this quarter?',
    rationale: 'Pays out in a selloff, when raising money gets harder.',
  },
  ...commodityRules([
    ['MOCK-DAIRY', 'Dairy prices', /\b(dairy|milk|cream|cheese|butter)\b/i],
    ['MOCK-COFFEE', 'Coffee prices', /\bcoffee\b/i],
    ['MOCK-SUGAR', 'Sugar prices', /\bsugar\b/i],
    ['MOCK-WHEAT', 'Wheat and flour prices', /\b(wheat|flour)\b/i],
    ['MOCK-BEEF', 'Beef prices', /\b(beef|meat)\b/i],
    ['MOCK-EGGS', 'Egg prices', /\beggs?\b/i],
    ['MOCK-COCOA', 'Cocoa prices', /\b(cocoa|chocolate)\b/i],
    ['MOCK-LUMBER', 'Lumber prices', /\b(lumber|wood)\b/i],
    ['MOCK-GPU', 'GPU prices', /\b(gpus?|graphics cards?)\b/i],
  ]),
]

function commodityRules(commodities: [string, string, RegExp][]): HedgeRule[] {
  return commodities.map(([ticker, factor, keywords]) => {
    const name = factor.replace(/ prices$/, '')
    const item = /^[A-Z]{2,}\b/.test(name) ? name : name.toLowerCase()
    return {
      ticker, factor, keywords,
      explanation: `You rely on ${item}, so a price jump squeezes your margins.`,
      market: () => `Will ${item} prices rise this month?`,
      rationale: `Pays out when ${item} gets more expensive.`,
    }
  })
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const UNHEDGED_SWINGS = [0.12, -0.18, 0.05, -0.22, 0.15, -0.08, 0.2, -0.15, 0.03, -0.2, 0.1, -0.05]
const HEDGE_BUDGET_SHARE = 0.05

// Reads the first dollar amount in the owner's budget answer ("$800 a month", "2k", "$12,000 a year") as a monthly figure.
function parseMonthlyBudget(text: string): number | null {
  const match = text.replace(/,/g, '').match(/(\d+(?:\.\d+)?)\s*(k|m)?\b/i)
  if (!match) return null
  const multiplier = { k: 1_000, m: 1_000_000 }[match[2]?.toLowerCase() as 'k' | 'm'] ?? 1
  const amount = Number(match[1]) * multiplier
  const monthly = /\b(year|yearly|yr|annual\w*)\b/i.test(text) ? amount / 12 : amount
  return monthly > 0 ? monthly : null
}

function buildRevenueSeries(monthlyRevenue: number, hedged: boolean): RevenuePoint[] {
  const damping = hedged ? 0.3 : 1
  return MONTHS.map((period, index) => ({
    period,
    unhedged: Math.round(monthlyRevenue * (1 + UNHEDGED_SWINGS[index])),
    hedged: Math.round(monthlyRevenue * (1 + UNHEDGED_SWINGS[index] * damping)),
  }))
}

export function buildMockReport(answers: QuestionnaireAnswers, monthlyRevenue: number): HedgeReport {
  const { lockedInCosts, location, riskBudget, ...otherAnswers } = answers
  const text = Object.values(otherAnswers).join(' ')
  const rules = HEDGE_RULES.filter((rule) => rule.keywords.test(text) && !rule.keywords.test(lockedInCosts))
  const place = location.trim() || 'your area'
  const budget = parseMonthlyBudget(riskBudget) ?? monthlyRevenue * HEDGE_BUDGET_SHARE
  const amountUsd = rules.length ? Math.floor(budget / rules.length) : 0
  const wording = (rule: HedgeRule): HedgeWording => (rule.reversed?.keywords.test(text) ? rule.reversed : rule)
  return {
    concerns: rules.map((rule) => ({ factor: rule.factor, explanation: wording(rule).explanation })),
    bets: rules.map((rule) => ({ market: wording(rule).market(place), ticker: rule.ticker, side: 'YES', amountUsd, rationale: wording(rule).rationale })),
    revenueSeries: buildRevenueSeries(monthlyRevenue, rules.length > 0),
  }
}
