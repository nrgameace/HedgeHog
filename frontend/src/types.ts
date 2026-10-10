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
  market: string
  ticker: string
  side: 'YES' | 'NO'
  amountUsd: number
  rationale: string
}

export type RevenuePoint = {
  period: string
  hedged: number
  unhedged: number
}

export type HedgeReport = {
  concerns: Concern[]
  bets: Bet[]
  revenueSeries: RevenuePoint[]
}
