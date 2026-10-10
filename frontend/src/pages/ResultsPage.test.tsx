import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { HedgeReport } from '../types'
import ResultsPage from './ResultsPage'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const net = (values: Record<number, number>) => MONTHS.map((_, index) => values[index] ?? 0)

// Expected $10k profit a month; March came in $6k short.
const report: HedgeReport = {
  simulatedPeriod: '2024',
  bets: [
    {
      risk: { factor: 'Rain', explanation: 'Rainy days cut foot traffic.' },
      market: 'Will it rain in Austin this month?', ticker: 'MOCK-RAIN', side: 'YES', amountUsd: 100, frequency: 'Monthly, Feb–Mar',
      tradeMonths: [1, 2], rationale: 'Pays out on rain.', monthlyNetUsd: net({ 1: -100, 2: 900 }),
    },
    {
      risk: { factor: 'Gas prices', explanation: 'The van needs fuel.' },
      market: 'Will gas top $3.50?', ticker: 'MOCK-GAS', side: 'YES', amountUsd: 50, frequency: 'Once, in January',
      tradeMonths: [0], rationale: 'Pays out on pricey gas.', monthlyNetUsd: net({ 0: -50 }),
    },
  ],
  profitSeries: MONTHS.map((period, index) => ({ period, expected: 10000, actual: index === 2 ? 4000 : 10000 })),
}

const renderPage = () => render(<ResultsPage report={report} onStartOver={vi.fn()} />)
const row = (name: RegExp) => screen.getByRole('row', { name })

describe('ResultsPage', () => {
  it('shows what could hurt profit as part of each trade row, not as a separate list', () => {
    renderPage()

    const rain = within(row(/rain in austin/i))
    expect(rain.getByText('Rain')).toBeInTheDocument()
    expect(rain.getByText('Rainy days cut foot traffic.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /what could hurt your profit/i })).not.toBeInTheDocument()
    expect(screen.getAllByText('Rainy days cut foot traffic.')).toHaveLength(1)
  })

  it('lists each trade with its amount, frequency, reasoning, net result and variance mitigation', () => {
    renderPage()

    for (const column of ['What could hurt your profit', 'Kalshi market', 'Side', 'Amount per trade', 'Frequency', 'Why', 'Net in 2024', 'Variance mitigation']) {
      expect(screen.getByRole('columnheader', { name: column })).toBeInTheDocument()
    }
    const rain = within(row(/rain in austin/i))
    expect(rain.getByText('$100')).toBeInTheDocument()
    expect(rain.getByText('Monthly, Feb–Mar')).toBeInTheDocument()
    expect(rain.getByText('Pays out on rain.')).toBeInTheDocument()
    expect(rain.getByText('+$800')).toBeInTheDocument()
    expect(rain.getByText('15.0%')).toBeInTheDocument()
    expect(within(row(/gas top/i)).getByText('−$50')).toBeInTheDocument()
  })

  it('totals the trades at the bottom of the table', () => {
    renderPage()

    const totals = within(row(/all trades/i))
    expect(totals.getByText('$250 staked per year')).toBeInTheDocument()
    expect(totals.getByText('+$750')).toBeInTheDocument()
    expect(totals.getByText('15.0%')).toBeInTheDocument()
  })

  it('shows the total trade impact graph until a row is clicked, then that trade’s graph', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /total trade impact/i })).toBeInTheDocument()
    expect(row(/all trades/i)).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(row(/rain in austin/i))
    expect(screen.getByRole('heading', { name: /trade impact: will it rain in austin this month\?/i })).toBeInTheDocument()
    expect(row(/rain in austin/i)).toHaveAttribute('aria-selected', 'true')
    expect(row(/all trades/i)).toHaveAttribute('aria-selected', 'false')

    fireEvent.click(row(/all trades/i))
    expect(screen.getByRole('heading', { name: /total trade impact/i })).toBeInTheDocument()
  })

  it('lets keyboard users pick a row with Enter', () => {
    renderPage()

    fireEvent.keyDown(row(/gas top/i), { key: 'Enter' })

    expect(screen.getByRole('heading', { name: /trade impact: will gas top/i })).toBeInTheDocument()
  })

  it('starts over when asked', () => {
    const onStartOver = vi.fn()
    render(<ResultsPage report={report} onStartOver={onStartOver} />)

    fireEvent.click(screen.getByRole('button', { name: /start over/i }))

    expect(onStartOver).toHaveBeenCalled()
  })

  it('says so plainly when no clear hedges were found', () => {
    render(<ResultsPage report={{ ...report, bets: [] }} onStartOver={vi.fn()} />)

    expect(screen.getByText(/no clear hedges found/i)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
