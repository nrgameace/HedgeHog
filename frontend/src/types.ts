// Free-text answers: the backend's model reads them to find hedgeable dependencies.
// Nothing the financials CSV already reports (earnings, costs) is asked here.
export type QuestionnaireAnswers = {
  businessDescription: string
  customers: string
  location: string
  operationalDependencies: string
  keyMaterials: string
  pastImpacts: string
  timeOfYear: string
  lockedInCosts: string
  riskBudget: string
}

export type Concern = {
  factor: string
  explanation: string
}

export type Bet = {
  // What could hurt profit, which this trade protects against.
  risk: Concern
  market: string
  ticker: string
  side: 'YES' | 'NO'
  // Stake each time the trade is placed.
  amountUsd: number
  frequency: string
  // Months (0 = Jan) in which the trade is placed.
  tradeMonths: number[]
  rationale: string
  // Payouts minus stakes for each month of the simulated year.
  monthlyNetUsd: number[]
}

export type ProfitPoint = {
  period: string
  // Profit in a normal year, and what the business actually made.
  expected: number
  actual: number
}

// A risk the analysis found that no open Kalshi market can hedge, and why.
export type UnhedgedRisk = {
  factor: string
  explanation: string
  reason: string
}

export type HedgeReport = {
  bets: Bet[]
  unhedgedRisks: UnhedgedRisk[]
  profitSeries: ProfitPoint[]
  simulatedPeriod: string
}
