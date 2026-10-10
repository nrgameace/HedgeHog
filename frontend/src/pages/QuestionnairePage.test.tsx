import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { HedgeReport } from '../types'
import QuestionnairePage from './QuestionnairePage'

const report: HedgeReport = { concerns: [], bets: [], revenueSeries: [] }
const csvFile = new File(['date,revenue\n2026-01,1000'], 'financials.csv', { type: 'text/csv' })

function renderPage(submit = vi.fn().mockResolvedValue(report), onComplete = vi.fn()) {
  render(<QuestionnairePage submit={submit} onComplete={onComplete} />)
  return { submit, onComplete }
}

function addFactor(factor: string) {
  fireEvent.change(screen.getByLabelText(/what factors do you believe impact your business/i), { target: { value: factor } })
  fireEvent.click(screen.getByRole('button', { name: /^add$/i }))
}

function enterEarnings(value: string) {
  fireEvent.change(screen.getByLabelText(/expected monthly earnings/i), { target: { value } })
}

describe('QuestionnairePage', () => {
  it('asks what factors impact the business without suggesting any', () => {
    renderPage()

    expect(screen.getByLabelText('What factors do you believe impact your business?')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('lists each factor the owner adds, and lets them remove one', () => {
    renderPage()

    addFactor('Rain')
    addFactor('Coffee prices')
    expect(screen.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      expect.stringContaining('Rain'),
      expect.stringContaining('Coffee prices'),
    ])

    fireEvent.click(screen.getByRole('button', { name: 'Remove Rain' }))
    expect(screen.queryByText('Rain')).not.toBeInTheDocument()
  })

  it('ignores blank and duplicate factors', () => {
    renderPage()

    addFactor('   ')
    addFactor('Rain')
    addFactor('Rain')

    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('shows errors and does not submit without a factor or earnings', () => {
    const { submit } = renderPage()

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(screen.getByText(/add at least one factor/i)).toBeInTheDocument()
    expect(screen.getByText(/enter your expected earnings/i)).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
  })

  it('submits without a CSV, since the upload is optional', async () => {
    const { submit, onComplete } = renderPage()
    addFactor('Rain')
    enterEarnings('20000')

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith({ factors: ['Rain'], expectedEarnings: 20000 }, null)
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(report))
  })

  it('passes along a CSV when one is uploaded', () => {
    const { submit } = renderPage()
    addFactor('Rain')
    enterEarnings('20000')
    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [csvFile] } })

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(submit).toHaveBeenCalledWith({ factors: ['Rain'], expectedEarnings: 20000 }, csvFile)
  })

  it('still rejects an uploaded file that is not a CSV', () => {
    const { submit } = renderPage()
    addFactor('Rain')
    enterEarnings('20000')
    const textFile = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    fireEvent.change(screen.getByLabelText(/upload your financials/i), { target: { files: [textFile] } })

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(screen.getByText(/must be a csv/i)).toBeInTheDocument()
    expect(submit).not.toHaveBeenCalled()
  })

  it('shows the error when the analysis fails', async () => {
    renderPage(vi.fn().mockRejectedValue(new Error('The analysis failed (status 500).')))
    addFactor('Rain')
    enterEarnings('20000')

    fireEvent.click(screen.getByRole('button', { name: /analyze/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/status 500/)
  })
})
