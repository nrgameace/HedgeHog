import RevenueVolatilityChart from '../components/RevenueVolatilityChart'
import type { HedgeReport } from '../types'

type ResultsPageProps = { report: HedgeReport; onStartOver: () => void }

function HedgePlan({ report }: { report: HedgeReport }) {
  return (
    <>
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
    </>
  )
}

function ResultsPage({ report, onStartOver }: ResultsPageProps) {
  return (
    <section className="results">
      <h1>Your hedging plan</h1>
      {report.bets.length > 0 ? (
        <HedgePlan report={report} />
      ) : (
        <p className="empty-plan">
          No clear hedges found. Nothing you described lines up with a market we can bet on. Try adding more detail about
          what your business relies on and what has hurt it before.
        </p>
      )}
      <button type="button" onClick={onStartOver}>Start over</button>
    </section>
  )
}

export default ResultsPage
