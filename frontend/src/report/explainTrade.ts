import type { Bet } from '../types'
import { stakedPerYear } from './tradeImpact'

export type ExplanationLine = { label: string; detail: string }

const formatUsd = (value: number) => `$${Math.round(Math.abs(value)).toLocaleString()}`
const formatSignedUsd = (value: number) => `${value < 0 ? '−' : '+'}${formatUsd(value)}`
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`

// Plain-English walk-through of one trade for owners who don't speak "prediction market".
export function explainTrade(bet: Bet, period: string): ExplanationLine[] {
  const paidMonths = bet.monthlyNetUsd.filter((net) => net > 0)
  // In a month it paid, net = payout − stake, so the payout is the best month plus the stake.
  const payout = paidMonths.length ? Math.max(...paidMonths) + bet.amountUsd : 0
  const staked = stakedPerYear(bet)
  const totalNet = bet.monthlyNetUsd.reduce((sum, net) => sum + net, 0)
  const [winLabel, loseLabel] = bet.side === 'YES' ? ['If it happens', 'If it doesn’t'] : ['If it doesn’t happen', 'If it does']

  return [
    { label: 'The trade', detail: `You put ${formatUsd(bet.amountUsd)} on ${bet.side} for “${bet.market}” each time it’s placed.` },
    {
      label: winLabel,
      detail: payout
        ? `The trade pays out about ${formatUsd(payout)}. That money lands in the same month your business takes the hit, so it helps cover the shortfall.`
        : 'The trade pays out. That money lands in the same month your business takes the hit, so it helps cover the shortfall.',
    },
    { label: loseLabel, detail: `You lose the ${formatUsd(bet.amountUsd)} stake. That usually means business went fine, so think of it like an insurance premium.` },
    {
      label: `In ${period}`,
      detail: paidMonths.length
        ? `It paid out in ${plural(paidMonths.length, 'month')}. You’d have staked ${formatUsd(staked)} in total and come out ${formatSignedUsd(totalNet)} overall.`
        : `It never paid out in ${period}. The ${formatUsd(staked)} it cost was the price of being covered, like insurance you didn’t end up needing.`,
    },
  ]
}
