import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { RevenuePoint } from '../types'

const formatUsd = (value: number) => `$${value.toLocaleString()}`

function RevenueVolatilityChart({ series }: { series: RevenuePoint[] }) {
  return (
    <figure className="chart" aria-label="Line chart of monthly revenue with and without hedging">
      <ResponsiveContainer width="100%" height={300} initialDimension={{ width: 600, height: 300 }}>
        <LineChart data={series} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="period" stroke="var(--text)" />
          <YAxis stroke="var(--text)" tickFormatter={formatUsd} width={80} />
          <Tooltip formatter={(value) => formatUsd(Number(value))} />
          <Legend />
          <Line type="monotone" dataKey="unhedged" name="Without hedging" stroke="var(--unhedged)" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="hedged" name="With hedging" stroke="var(--accent)" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}

export default RevenueVolatilityChart
