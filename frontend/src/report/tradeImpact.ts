import type { Bet, ProfitPoint } from '../types'

export function profitWithTrades(profit: ProfitPoint[], monthlyNet: number[]): number[] {
  return profit.map((point, index) => point.actual + monthlyNet[index])
}

export function combinedNet(nets: number[][]): number[] {
  return nets[0].map((_, index) => nets.reduce((sum, net) => sum + net[index], 0))
}

// Size of the bad months: root-mean-square of how far profit fell below a normal year (good months count as zero).
function shortfall(profit: ProfitPoint[], actual: number[]): number {
  const squares = profit.map((point, index) => Math.max(point.expected - actual[index], 0) ** 2)
  return Math.sqrt(squares.reduce((sum, square) => sum + square, 0) / squares.length)
}

// Share of the bad-month shortfall the trades cover: 1 = fully covered, negative = their cost made bad months worse.
export function varianceMitigation(profit: ProfitPoint[], monthlyNet: number[]): number {
  const without = shortfall(profit, profit.map((point) => point.actual))
  return without === 0 ? 0 : 1 - shortfall(profit, profitWithTrades(profit, monthlyNet)) / without
}

export function stakedPerYear(bet: Pick<Bet, 'amountUsd' | 'tradeMonths'>): number {
  return bet.amountUsd * bet.tradeMonths.length
}
