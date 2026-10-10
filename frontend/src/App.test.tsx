import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { buildMockReport } from './api/mockReport'

vi.mock('./api/client', () => ({
  submitQuestionnaire: vi.fn((answers) => Promise.resolve(buildMockReport(answers, 30000))),
}))

describe('App', () => {
  it('shows the Hedgehog homepage with a button to start the questionnaire', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /hedgehog/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument()
  })

  it('goes from home, through the questionnaire (no CSV needed), to the results and back home', async () => {
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /start/i }))
    fireEvent.change(screen.getByLabelText(/what does your business do/i), { target: { value: 'Ice cream shop' } })
    fireEvent.change(screen.getByLabelText(/where is your business located/i), { target: { value: 'Austin, TX' } })
    fireEvent.change(screen.getByLabelText(/what outside events/i), { target: { value: 'Rainy weekends' } })
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('heading', { name: /your hedging plan/i })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /rain.*austin, tx/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /start over/i }))
    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument()
  })
})
