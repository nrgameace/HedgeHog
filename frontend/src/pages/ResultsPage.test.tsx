import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { HedgeReport } from '../types'
import ResultsPage from './ResultsPage'

const report: HedgeReport = {
  concerns: [{ factor: 'Rain', explanation: 'Rainy days cut foot traffic.' }],
  bets: [{ market: 'Will it rain this week?', ticker: 'MOCK-RAIN', side: 'YES', amountUsd: 500, rationale: 'Pays out on rain.' }],
  revenueSeries: [{ period: 'Jan', hedged: 20000, unhedged: 18000 }],
}

describe('ResultsPage', () => {
  it('shows the concerns, the recommended bets and the revenue chart', () => {
    render(<ResultsPage report={report} onStartOver={vi.fn()} />)

    expect(screen.getByText('Rainy days cut foot traffic.')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Will it rain this week?' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '$500' })).toBeInTheDocument()
    expect(screen.getByText(/simulated/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /hedged vs\. unhedged revenue/i })).toBeInTheDocument()
  })

  it('starts over when asked', () => {
    const onStartOver = vi.fn()
    render(<ResultsPage report={report} onStartOver={onStartOver} />)

    fireEvent.click(screen.getByRole('button', { name: /start over/i }))

    expect(onStartOver).toHaveBeenCalled()
  })

  it('says so plainly when no clear hedges were found', () => {
    render(<ResultsPage report={{ concerns: [], bets: [], revenueSeries: [] }} onStartOver={vi.fn()} />)

    expect(screen.getByText(/no clear hedges found/i)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /start over/i })).toBeInTheDocument()
  })
})
