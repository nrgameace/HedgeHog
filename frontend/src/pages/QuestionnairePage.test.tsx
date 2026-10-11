import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AnalysisUnavailableError } from '../api/client'
import { twoScoopsReport } from '../api/twoScoopsReport'
import { TWO_SCOOPS_ANSWERS, TWO_SCOOPS_FINANCIALS_FILENAME } from '../demo/twoScoopsDemo'
import { blankAnswers } from '../test/answers'
import type { HedgeReport } from '../types'
import QuestionnairePage from './QuestionnairePage'

const report: HedgeReport = { bets: [], unhedgedRisks: [], profitSeries: [], simulatedPeriod: '' }
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

function renderPage(submit = vi.fn().mockResolvedValue(report), onComplete = vi.fn(), requireFinancials = false) {
  render(<QuestionnairePage submit={submit} onComplete={onComplete} requireFinancials={requireFinancials} />)
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

  it('shows how many of the ten questions are answered, counting the CSV upload', () => {
    renderPage()
    const progress = screen.getByRole('progressbar', { name: /questions answered/i })
    expect(progress).toHaveAttribute('aria-valuenow', '0')
    expect(progress).toHaveAttribute('aria-valuemax', '10')
    expect(screen.getByText('0 of 10 answered')).toBeInTheDocument()

    answer(/what does your business do/i, 'Ice cream shop')
    answer(/who are your customers/i, '   ')
    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [csvFile] } })

    expect(progress).toHaveAttribute('aria-valuenow', '2')
    expect(screen.getByText('2 of 10 answered')).toBeInTheDocument()
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

  it('swaps the form for the spinning hedgehog loading screen while the analysis runs', () => {
    renderPage(vi.fn(() => new Promise<HedgeReport>(() => {})))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(screen.getByRole('status')).toHaveAccessibleName('Loading')
    expect(screen.queryByRole('heading', { name: /about your business/i })).not.toBeInTheDocument()
  })

  it('brings the form back with the answers kept if the analysis fails', async () => {
    renderPage(vi.fn().mockRejectedValue(new Error('The analysis failed (status 500).')))
    answerRequired()

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/where is your business located/i)).toHaveValue('Austin, TX')
  })

  it('fills every question and attaches the ice cream shop financials with one click', () => {
    const { submit } = renderPage(undefined, undefined, true)

    fireEvent.click(screen.getByRole('button', { name: /^fill in demo data$/i }))

    expect(screen.getByLabelText(/what does your business do/i)).toHaveValue(TWO_SCOOPS_ANSWERS.businessDescription)
    expect(screen.getByLabelText(/where is your business located/i)).toHaveValue('Austin, TX')
    expect(screen.getByLabelText(/budget would you have for risk mitigation/i)).toHaveValue(TWO_SCOOPS_ANSWERS.riskBudget)
    expect(screen.getByText(TWO_SCOOPS_FINANCIALS_FILENAME)).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuetext', '10 of 10 answered')

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith(TWO_SCOOPS_ANSWERS, expect.objectContaining({ name: TWO_SCOOPS_FINANCIALS_FILENAME }))
  })

  it('offers the sample ice cream shop results when the analysis service is unavailable', async () => {
    const { onComplete } = renderPage(vi.fn().mockRejectedValue(new AnalysisUnavailableError('the analysis service is misconfigured')))

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))
    fireEvent.click(await screen.findByRole('button', { name: /see sample results/i }))

    expect(screen.getByRole('alert')).toHaveTextContent(/misconfigured/)
    expect(onComplete).toHaveBeenCalledWith(twoScoopsReport())
  })

  it('scrolls the error into view, since it sits below all the questions', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    renderPage(vi.fn().mockRejectedValue(new AnalysisUnavailableError("We couldn't reach the analysis service.")))

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    await screen.findByRole('alert')
    expect(scrollIntoView).toHaveBeenCalled()
  })

  it('does not offer sample results when the problem is with what was entered', async () => {
    renderPage(vi.fn().mockRejectedValue(new Error('The financials CSV needs a month column.')))

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/month column/)
    expect(screen.queryByRole('button', { name: /see sample results/i })).not.toBeInTheDocument()
  })

  it('asks for the CSV before submitting when the real backend needs it', () => {
    const { submit } = renderPage(undefined, undefined, true)

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(screen.getByText('Upload your financials CSV so we can simulate your trades.')).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
  })

  it('submits with the CSV when the real backend needs it', () => {
    const { submit } = renderPage(undefined, undefined, true)

    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [csvFile] } })
    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith(blankAnswers, csvFile)
  })
})
