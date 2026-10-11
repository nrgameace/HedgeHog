import type { HedgeReport, QuestionnaireAnswers } from '../types'
import { twoScoopsReport } from './twoScoopsReport'

// Set VITE_USE_MOCK_API=true to show the simulated Two Scoops results instead of calling the backend.
export const MOCK_API = import.meta.env.VITE_USE_MOCK_API === 'true'
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// The analysis couldn't run at all (backend unreachable, no API key set up, or the model service failed),
// as opposed to a problem with what was entered. The page offers sample results instead.
export class AnalysisUnavailableError extends Error {}

type SubmitOptions = { useMock?: boolean; apiUrl?: string; mockDelayMs?: number }

export async function submitQuestionnaire(answers: QuestionnaireAnswers, file: File | null, options: SubmitOptions = {}): Promise<HedgeReport> {
  const { useMock = MOCK_API, apiUrl = API_URL, mockDelayMs = 1200 } = options
  if (useMock) {
    // Offline demo: whatever was entered, show the simulated Two Scoops results.
    await new Promise((resolve) => setTimeout(resolve, mockDelayMs))
    return twoScoopsReport()
  }
  const body = new FormData()
  body.append('answers', JSON.stringify(answers))
  if (file) body.append('financials', file)
  const response = await fetch(`${apiUrl}/analyze`, { method: 'POST', body }).catch(() => {
    throw new AnalysisUnavailableError("We couldn't reach the analysis service.")
  })
  if (response.status >= 500) throw new AnalysisUnavailableError(await failureMessage(response))
  if (!response.ok) throw new Error(await failureMessage(response))
  return response.json()
}

async function failureMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  return typeof body?.detail === 'string' ? body.detail : `The analysis failed (status ${response.status}).`
}
