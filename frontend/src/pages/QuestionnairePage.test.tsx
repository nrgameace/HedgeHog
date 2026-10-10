import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { blankAnswers } from '../test/answers'
import type { HedgeReport } from '../types'
import QuestionnairePage from './QuestionnairePage'

const report: HedgeReport = { concerns: [], bets: [], revenueSeries: [] }
const csvFile = new File(['month,revenue\n2026-01,1000'], 'financials.csv', { type: 'text/csv' })

const QUESTIONS = [
  'What does your business do?',
  'Who are your customers?',
  'Where is your business located?',
  'What does your business rely on to operate day to day?',
  'What materials or services do you use the most?',
  'What outside events have hurt your business before, or worry you most?',
  'What times of year matter most to your business, and why?',
  'Are any of your costs locked in at a set price, like a fixed-price supplier contract, a fixed-rate loan or a long-term lease?',
  'How much budget would you have for risk mitigation?',
]

function renderPage(submit = vi.fn().mockResolvedValue(report), onComplete = vi.fn()) {
  render(<QuestionnairePage submit={submit} onComplete={onComplete} />)
  return { submit, onComplete }
}

function answer(question: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(question), { target: { value } })
}

function answerRequired() {
  answer(/what does your business do/i, 'Ice cream shop')
  answer(/where is your business located/i, 'Austin, TX')
  answer(/what outside events/i, 'Rainy weekends')
}

const requiredAnswers = { ...blankAnswers, businessDescription: 'Ice cream shop', location: 'Austin, TX', pastImpacts: 'Rainy weekends' }

describe('QuestionnairePage', () => {
  it('asks all nine questions and nothing the CSV already covers', () => {
    renderPage()

    for (const question of QUESTIONS) {
      expect(screen.getByLabelText(new RegExp(question.replace(/[?,]/g, '.')))).toBeInTheDocument()
    }
    expect(screen.queryByLabelText(/earnings/i)).not.toBeInTheDocument()
  })

  it('has no sample-CSV download link (demo CSVs live in demo-data/)', () => {
    renderPage()

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('does not label anything as optional', () => {
    renderPage()

    expect(screen.queryByText(/optional/i)).not.toBeInTheDocument()
  })

  it('lets the owner submit without answering anything while we use simulated data', () => {
    const { submit } = renderPage()

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith(blankAnswers, null)
  })

  it('submits all the answers, trimmed, without needing a CSV', async () => {
    const { submit, onComplete } = renderPage()
    answerRequired()
    answer(/who are your customers/i, '  Tourists  ')
    answer(/are any of your costs locked in/i, 'Fixed-rate loan')
    answer(/budget would you have for risk mitigation/i, ' $500 a month ')

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith({ ...requiredAnswers, customers: 'Tourists', lockedInCosts: 'Fixed-rate loan', riskBudget: '$500 a month' }, null)
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(report))
  })

  it('passes along a CSV when one is uploaded', () => {
    const { submit } = renderPage()
    answerRequired()
    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [csvFile] } })

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith(requiredAnswers, csvFile)
  })

  it('still rejects an uploaded file that is not a CSV', () => {
    const { submit } = renderPage()
    answerRequired()
    const textFile = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [textFile] } })

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(screen.getByText(/must be a csv/i)).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
  })

  it('shows the error when the analysis fails', async () => {
    renderPage(vi.fn().mockRejectedValue(new Error('The analysis failed (status 500).')))
    answerRequired()

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/status 500/)
  })
})
