import RevenueVolatilityChart from '../components/RevenueVolatilityChart'
import type { HedgeReport } from '../types'

type ResultsPageProps = { report: HedgeReport; onStartOver: () => void }

function ResultsPage({ report, onStartOver }: ResultsPageProps) {
  return (
    <section className="results">
      <h1>Your hedging plan</h1>

      <h2>What could hurt your revenue</h2>
      <ul className="concerns">
        {report.concerns.map((concern) => (
          <li key={concern.factor}>
            <strong>{concern.factor}</strong>
            <p>{concern.explanation}</p>
          </li>
        ))}
      </ul>

      <h2>Recommended Kalshi bets</h2>
      <p className="note">Simulated paper trades. No real money moves.</p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>Side</th>
              <th>Amount</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {report.bets.map((bet) => (
              <tr key={bet.ticker}>
                <td>{bet.market}</td>
                <td>{bet.side}</td>
                <td>{`$${bet.amountUsd.toLocaleString()}`}</td>
                <td>{bet.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Hedged vs. unhedged revenue</h2>
      <RevenueVolatilityChart series={report.revenueSeries} />

      <button type="button" onClick={onStartOver}>Start over</button>
    </section>
  )
}

export default ResultsPage
