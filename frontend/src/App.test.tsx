import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { twoScoopsReport } from './api/twoScoopsReport'

vi.mock('./api/client', () => ({
  submitQuestionnaire: vi.fn(() => Promise.resolve(twoScoopsReport())),
}))

describe('App', () => {
  it('shows the Hedgehog homepage with a button to start the questionnaire', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /hedgehog/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument()
  })

  it('goes from home, through the questionnaire (nothing required), to the simulated Two Scoops results and back home', async () => {
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /start/i }))
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('heading', { name: /your hedging plan/i })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /austin, tx.*rainy days/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /start over/i }))
    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument()
  })
})
