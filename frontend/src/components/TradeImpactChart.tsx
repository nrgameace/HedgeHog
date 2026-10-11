import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { ProfitPoint } from '../types'

// Two charts, not one. Profit runs to about $20,000 a month while a hedge's
// effect is in the hundreds, so putting both on a single axis made the thing the
// reader came for 4% of the axis height - the bars were a sliver and "profit with
// trades" sat invisibly on top of "profit without". Two measures of different
// scale get two charts.
//
// Chart 1 answers "did profit dip?" - the gap between the two lines is the hole,
// and at this scale a bad month is 40-60% of the axis, so it reads at a glance.
// Chart 2 answers "did the hedge fill it?" on its own scale, where a few hundred
// dollars against a twelve-thousand-dollar hole is visible and honestly small.
//
// Chart 2 is a meter, not a two-colour stack: covered and uncovered are one
// quantity split in two, so they take one hue light-to-dark. A categorical pair
// from this palette failed the contrast checks outright (normal-vision dE 11.1,
// below the floor of 15), and lightness ordering survives every kind of colour
// blindness anyway.

const COVERED = 'var(--accent)'
const UNCOVERED = 'var(--border)'
const WORSENED = 'var(--error)'

const formatUsd = (value: number) => `${value < 0 ? '−' : ''}$${Math.abs(Math.round(value)).toLocaleString()}`

// The open-gap fill is a pale tan that sits at 1.87:1 against the card - under
// the 3:1 the validator wants - so the bars carry their own figures rather than
// relying on colour or on a hover the reader may never try. Only the months big
// enough to matter are labelled; a number over every bar is its own noise.
const LABEL_THRESHOLD_SHARE = 0.15

export type ShortfallRow = {
  period: string
  shortfall: number
  covered: number
  uncovered: number
  worsened: number
}

/** Each month's hole and how much of it the hedge actually filled.
 *
 * A hole is profit below its seasonal normal; a surplus month has none. Cover is
 * clamped to the hole, because paying out more than the month was short is a
 * windfall rather than a hedge. A month where the premium went out and nothing
 * came back is shown below the line - the hedge cost money there, and hiding that
 * would overstate it.
 */
export function shortfallRows(profit: ProfitPoint[], monthlyNet: number[]): ShortfallRow[] {
  return profit.map((point, index) => {
    const net = monthlyNet[index] ?? 0
    const shortfall = Math.max(point.expected - point.actual, 0)
    const covered = Math.min(Math.max(net, 0), shortfall)
    return {
      period: point.period,
      shortfall,
      covered,
      uncovered: shortfall - covered,
      worsened: Math.min(net, 0),
    }
  })
}

export const totalCovered = (rows: ShortfallRow[]) => rows.reduce((sum, row) => sum + row.covered, 0)
export const totalShortfall = (rows: ShortfallRow[]) => rows.reduce((sum, row) => sum + row.shortfall, 0)

function ProfitAgainstNormal({ profit }: { profit: ProfitPoint[] }) {
  return (
    <figure className="chart">
      <figcaption>
        Monthly profit against a normal year. The gap is what the hedge is for.
      </figcaption>
      <ResponsiveContainer width="100%" height={260} initialDimension={{ width: 600, height: 260 }}>
        <LineChart data={profit} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="period" stroke="var(--text)" tickLine={false} />
          <YAxis stroke="var(--text)" tickFormatter={formatUsd} width={80} tickLine={false} />
          <Tooltip formatter={(value) => formatUsd(Number(value))} />
          <Legend />
          <Line isAnimationActive={false} type="linear" dataKey="expected" name="Normal year" stroke="var(--text)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
          <Line isAnimationActive={false} type="linear" dataKey="actual" name="What you made" stroke="var(--accent)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}

function ShortfallCoverage({ rows, label }: { rows: ShortfallRow[]; label: string }) {
  const covered = totalCovered(rows)
  const shortfall = totalShortfall(rows)
  const share = shortfall > 0 ? covered / shortfall : 0
  const anyWorsened = rows.some((row) => row.worsened < 0)
  const biggest = Math.max(...rows.map((row) => row.shortfall), 0)

  return (
    <figure className="chart">
      <figcaption>
        How much of each month's gap {label} covered —{' '}
        <strong>
          {formatUsd(covered)} of {formatUsd(shortfall)} ({(share * 100).toFixed(1)}%)
        </strong>{' '}
        across the year.
      </figcaption>
      <ResponsiveContainer width="100%" height={260} initialDimension={{ width: 600, height: 260 }}>
        <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 16 }} stackOffset="sign">
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="period" stroke="var(--text)" tickLine={false} />
          <YAxis stroke="var(--text)" tickFormatter={formatUsd} width={80} tickLine={false} />
          <Tooltip formatter={(value, name) => [formatUsd(Number(value)), name]} />
          <Legend />
          <ReferenceLine y={0} stroke="var(--text)" />
          {/* Covered sits at the baseline so the filled part of each month's
              meter is read against the axis, with the remaining gap stacked above it. */}
          <Bar isAnimationActive={false} dataKey="covered" name="Gap covered" stackId="gap" fill={COVERED} />
          <Bar isAnimationActive={false} dataKey="uncovered" name="Gap still open" stackId="gap" fill={UNCOVERED} radius={[4, 4, 0, 0]}>
            <LabelList
              dataKey="shortfall"
              position="top"
              fill="var(--text-h)"
              fontSize={12}
              formatter={(value) => (Number(value) >= biggest * LABEL_THRESHOLD_SHARE ? formatUsd(Number(value)) : '')}
            />
          </Bar>
          {anyWorsened && (
            <Bar isAnimationActive={false} dataKey="worsened" name="Premium paid, no payout" stackId="gap" fill={WORSENED} radius={[0, 0, 4, 4]}>
              {rows.map((row) => (
                <Cell key={row.period} fill={WORSENED} />
              ))}
            </Bar>
          )}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}

type TradeImpactChartProps = { profit: ProfitPoint[]; monthlyNet: number[]; label: string }

function TradeImpactChart({ profit, monthlyNet, label }: TradeImpactChartProps) {
  const rows = shortfallRows(profit, monthlyNet)
  return (
    <div className="charts" aria-label={`Monthly profit and the gap ${label} covered`}>
      <ProfitAgainstNormal profit={profit} />
      <ShortfallCoverage rows={rows} label={label} />
    </div>
  )
}

export default TradeImpactChart
