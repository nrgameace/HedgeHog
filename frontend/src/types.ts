export type QuestionnaireAnswers = {
  factors: string[]
  expectedEarnings: number
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
