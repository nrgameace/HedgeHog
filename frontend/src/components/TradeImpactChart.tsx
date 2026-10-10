import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { profitWithTrades } from '../report/tradeImpact'
import type { ProfitPoint } from '../types'

const formatUsd = (value: number) => `${value < 0 ? '−' : ''}$${Math.abs(value).toLocaleString()}`

type TradeImpactChartProps = { profit: ProfitPoint[]; monthlyNet: number[]; label: string }

function TradeImpactChart({ profit, monthlyNet, label }: TradeImpactChartProps) {
  const withTrades = profitWithTrades(profit, monthlyNet)
  const data = profit.map((point, index) => ({ ...point, withTrades: withTrades[index], tradeNet: monthlyNet[index] }))
  return (
    <figure className="chart" aria-label={`Monthly profit with and without ${label}`}>
      <ResponsiveContainer width="100%" height={320} initialDimension={{ width: 600, height: 320 }}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="period" stroke="var(--text)" />
          <YAxis stroke="var(--text)" tickFormatter={formatUsd} width={80} />
          <Tooltip formatter={(value) => formatUsd(Number(value))} />
          <Legend />
          <Bar dataKey="tradeNet" name="Trade payouts minus stakes" fill="var(--accent)" fillOpacity={0.35} />
          <Line type="monotone" dataKey="expected" name="Normal year" stroke="var(--text)" strokeDasharray="5 4" dot={false} />
          <Line type="monotone" dataKey="actual" name="Profit without trades" stroke="var(--unhedged)" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="withTrades" name={`Profit with ${label}`} stroke="var(--accent)" strokeWidth={3} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </figure>
  )
}

export default TradeImpactChart
