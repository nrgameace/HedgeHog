import { useState, type FormEvent } from 'react'

import { validateFinancialsFile } from '../csv/validateFinancialsFile'
import type { HedgeReport, QuestionnaireAnswers } from '../types'

type QuestionnairePageProps = {
  submit: (answers: QuestionnaireAnswers, file: File | null) => Promise<HedgeReport>
  onComplete: (report: HedgeReport) => void
}

type FieldErrors = { factors?: string; earnings?: string; file?: string }

function QuestionnairePage({ submit, onComplete }: QuestionnairePageProps) {
  const [factors, setFactors] = useState<string[]>([])
  const [newFactor, setNewFactor] = useState('')
  const [earnings, setEarnings] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function addFactor() {
    const factor = newFactor.trim()
    if (factor && !factors.includes(factor)) setFactors([...factors, factor])
    setNewFactor('')
  }

  function removeFactor(factor: string) {
    setFactors(factors.filter((f) => f !== factor))
  }

  function validate(): FieldErrors {
    const found: FieldErrors = {}
    if (factors.length === 0) found.factors = 'Add at least one factor.'
    if (!(Number(earnings) > 0)) found.earnings = 'Enter your expected earnings as a positive number.'
    const fileError = validateFinancialsFile(file)
    if (fileError) found.file = fileError
    return found
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    setSubmitError(null)
    if (Object.keys(found).length > 0) return
    setIsSubmitting(true)
    try {
      onComplete(await submit({ factors, expectedEarnings: Number(earnings) }, file))
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Something went wrong. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <form className="questionnaire" onSubmit={handleSubmit} noValidate>
      <h1>About your business</h1>

      <div className="field">
        <label htmlFor="new-factor">What factors do you believe impact your business?</label>
        <div className="add-factor">
          <input
            id="new-factor"
            value={newFactor}
            onChange={(event) => setNewFactor(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addFactor()
              }
            }}
          />
          <button type="button" onClick={addFactor}>Add</button>
        </div>
        {factors.length > 0 && (
          <ul className="factor-list">
            {factors.map((factor) => (
              <li key={factor}>
                {factor}
                <button type="button" aria-label={`Remove ${factor}`} onClick={() => removeFactor(factor)}>×</button>
              </li>
            ))}
          </ul>
        )}
        {errors.factors && <p className="field-error">{errors.factors}</p>}
      </div>

      <div className="field">
        <label htmlFor="earnings">Expected monthly earnings ($)</label>
        <input id="earnings" type="number" min="0" inputMode="decimal" value={earnings} onChange={(event) => setEarnings(event.target.value)} />
        {errors.earnings && <p className="field-error">{errors.earnings}</p>}
      </div>

      <div className="field">
        <label htmlFor="financials">Upload your financials (optional, CSV, max 5 MB)</label>
        <input id="financials" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <a href="/sample-financials.csv" download>Download a sample CSV</a>
        {errors.file && <p className="field-error">{errors.file}</p>}
      </div>

      {submitError && <p className="field-error" role="alert">{submitError}</p>}

      <button type="submit" className="primary" disabled={isSubmitting}>
        {isSubmitting ? 'Analyzing…' : 'Analyze my risks'}
      </button>
    </form>
  )
}

export default QuestionnairePage
