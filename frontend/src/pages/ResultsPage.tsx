import { Fragment, useState, type KeyboardEvent } from 'react'

import TradeImpactChart from '../components/TradeImpactChart'
import { explainTrade } from '../report/explainTrade'
import { combinedNet, stakedPerYear, varianceMitigation } from '../report/tradeImpact'
import type { Bet, HedgeReport } from '../types'

type ResultsPageProps = { report: HedgeReport; onStartOver: () => void }

const ALL_TRADES = -1
const COLUMN_COUNT = 8

const formatUsd = (value: number) => `$${Math.round(value).toLocaleString()}`
const formatSignedUsd = (value: number) => `${value < 0 ? '−' : '+'}$${Math.abs(Math.round(value)).toLocaleString()}`
function formatPercent(fraction: number) {
  const tenths = Math.round(fraction * 1000)
  return `${tenths < 0 ? '−' : ''}${(Math.abs(tenths) / 10).toFixed(1)}%`
}

const explanationId = (ticker: string) => `explain-${ticker}`

type ExplainToggleProps = { ticker: string; isOpen: boolean; onToggle: () => void }

function ExplainToggle({ ticker, isOpen, onToggle }: ExplainToggleProps) {
  return (
    <button
      type="button"
      className="explain-toggle"
      aria-expanded={isOpen}
      aria-controls={explanationId(ticker)}
      onClick={onToggle}
      // Keep Enter/Space on this button from also selecting the row.
      onKeyDown={(event) => event.stopPropagation()}
    >
      {isOpen ? 'Hide explanation' : 'What does this mean?'}
    </button>
  )
}

// Full-width row under a trade that spells it out in plain English.
function TradeExplanation({ bet, period }: { bet: Bet; period: string }) {
  return (
    <tr className="trade-explainer" id={explanationId(bet.ticker)}>
      <td colSpan={COLUMN_COUNT}>
        <dl>
          {explainTrade(bet, period).map(({ label, detail }) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{detail}</dd>
            </div>
          ))}
        </dl>
      </td>
    </tr>
  )
}

function HedgePlan({ report }: { report: HedgeReport }) {
  const [selected, setSelected] = useState(ALL_TRADES)
  const [explained, setExplained] = useState<string[]>([])
  const toggleExplanation = (ticker: string) =>
    setExplained(explained.includes(ticker) ? explained.filter((open) => open !== ticker) : [...explained, ticker])
  const totalNet = combinedNet(report.bets.map((bet) => bet.monthlyNetUsd))
  const sum = (values: number[]) => values.reduce((total, value) => total + value, 0)
  const selectedBet = report.bets[selected]

  const selectable = (index: number) => ({
    'aria-selected': selected === index,
    tabIndex: 0,
    className: selected === index ? 'selectable selected' : 'selectable',
    onClick: () => setSelected(index),
    onKeyDown: (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        setSelected(index)
      }
    },
  })

  return (
    <>
      <h2>Recommended Kalshi trades</h2>
      <p className="note">
        Simulated paper trades on your {report.simulatedPeriod} numbers. No real money moves. Click a trade to see its impact.
      </p>
      <div className="table-scroll">
        <table className="trades">
          <thead>
            <tr>
              <th>What could hurt your profit</th>
              <th>Kalshi market</th>
              <th>Side</th>
              <th>Amount per trade</th>
              <th>Frequency</th>
              <th>Why</th>
              <th>Net in {report.simulatedPeriod}</th>
              <th>Variance mitigation</th>
            </tr>
          </thead>
          <tbody>
            {report.bets.map((bet, index) => (
              <Fragment key={bet.ticker}>
                <tr {...selectable(index)}>
                  <td className="risk">
                    <strong>{bet.risk.factor}</strong>
                    <span>{bet.risk.explanation}</span>
                    <ExplainToggle ticker={bet.ticker} isOpen={explained.includes(bet.ticker)} onToggle={() => toggleExplanation(bet.ticker)} />
                  </td>
                  <td>{bet.market}</td>
                  <td>{bet.side}</td>
                  <td>{formatUsd(bet.amountUsd)}</td>
                  <td>{bet.frequency}</td>
                  <td>{bet.rationale}</td>
                  <td>{formatSignedUsd(sum(bet.monthlyNetUsd))}</td>
                  <td>{formatPercent(varianceMitigation(report.profitSeries, bet.monthlyNetUsd))}</td>
                </tr>
                {explained.includes(bet.ticker) && <TradeExplanation bet={bet} period={report.simulatedPeriod} />}
              </Fragment>
            ))}
          </tbody>
          <tfoot>
            <tr {...selectable(ALL_TRADES)}>
              <th scope="row">All trades</th>
              <td colSpan={2} />
              <td colSpan={3}>{`${formatUsd(sum(report.bets.map(stakedPerYear)))} staked per year`}</td>
              <td>{formatSignedUsd(sum(totalNet))}</td>
              <td>{formatPercent(varianceMitigation(report.profitSeries, totalNet))}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <h2>{selectedBet ? `Trade impact: ${selectedBet.market}` : 'Total trade impact'}</h2>
      <TradeImpactChart
        profit={report.profitSeries}
        monthlyNet={selectedBet ? selectedBet.monthlyNetUsd : totalNet}
        label={selectedBet ? 'this trade' : 'all trades'}
      />
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
