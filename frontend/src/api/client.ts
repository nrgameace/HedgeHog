import { averageMonthlyRevenue } from '../csv/averageMonthlyRevenue'
import type { HedgeReport, QuestionnaireAnswers } from '../types'
import { buildMockReport } from './mockReport'

// Set VITE_USE_MOCK_API=false to call the real backend instead of returning mock data.
export const MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false'
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// Mock-mode revenue when no CSV (or no revenue column) is provided.
const DEMO_MONTHLY_REVENUE = 25000

type SubmitOptions = { useMock?: boolean; apiUrl?: string; mockDelayMs?: number }

export async function submitQuestionnaire(answers: QuestionnaireAnswers, file: File | null, options: SubmitOptions = {}): Promise<HedgeReport> {
  const { useMock = MOCK_API, apiUrl = API_URL, mockDelayMs = 1200 } = options
  if (useMock) {
    await new Promise((resolve) => setTimeout(resolve, mockDelayMs))
    const csvRevenue = file ? averageMonthlyRevenue(await file.text()) : null
    return buildMockReport(answers, csvRevenue ?? DEMO_MONTHLY_REVENUE)
  }
  const body = new FormData()
  body.append('answers', JSON.stringify(answers))
  if (file) body.append('financials', file)
  const response = await fetch(`${apiUrl}/analyze`, { method: 'POST', body })
  if (!response.ok) throw new Error(`The analysis failed (status ${response.status}).`)
  return response.json()
}
