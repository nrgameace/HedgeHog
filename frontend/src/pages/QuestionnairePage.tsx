import { useState, type FormEvent } from 'react'

import { validateFinancialsFile } from '../csv/validateFinancialsFile'
import type { HedgeReport, QuestionnaireAnswers } from '../types'

type Question = { id: keyof QuestionnaireAnswers; label: string; example: string; multiline?: boolean }

// Only things the financials CSV can't tell us: what the business depends on, and why revenue moves.
const QUESTIONS: Question[] = [
  { id: 'businessDescription', label: 'What does your business do?', example: 'Ice cream shop with outdoor seating' },
  { id: 'customers', label: 'Who are your customers?', example: 'Mostly tourists and families in summer' },
  { id: 'location', label: 'Where is your business located?', example: 'Austin, TX' },
  { id: 'operationalDependencies', label: 'What does your business rely on to operate day to day?', example: 'Refrigeration, a delivery van, foot traffic', multiline: true },
  { id: 'keyMaterials', label: 'What materials or services do you use the most?', example: 'Dairy, sugar, electricity, gas for the van', multiline: true },
  { id: 'pastImpacts', label: 'What outside events have hurt your business before, or worry you most?', example: 'Rainy weekends, heat waves, gas price spikes', multiline: true },
  { id: 'timeOfYear', label: 'What times of year matter most to your business, and why?', example: 'June–August is tourist season; winter is slow', multiline: true },
  {
    id: 'lockedInCosts',
    label: 'Are any of your costs locked in at a set price, like a fixed-price supplier contract, a fixed-rate loan or a long-term lease?',
    example: 'Milk is on a fixed-price contract through 2027; our lease is fixed through 2028',
    multiline: true,
  },
  { id: 'riskBudget', label: 'How much budget would you have for risk mitigation?', example: '$500 a month' },
]

const EMPTY_ANSWERS = Object.fromEntries(QUESTIONS.map((question) => [question.id, ''])) as QuestionnaireAnswers

type QuestionnairePageProps = {
  submit: (answers: QuestionnaireAnswers, file: File | null) => Promise<HedgeReport>
  onComplete: (report: HedgeReport) => void
  requireFinancials: boolean
}

type ProgressProps = { answered: number; total: number }

// Sticky bar so ten questions feel short: fills as answers (and the CSV) come in.
function QuestionnaireProgress({ answered, total }: ProgressProps) {
  const label = `${answered} of ${total} answered`
  return (
    <div className="questionnaire-progress" role="progressbar" aria-label="Questions answered" aria-valuemin={0} aria-valuemax={total} aria-valuenow={answered} aria-valuetext={label}>
      <div className="questionnaire-progress__track">
        <div className="questionnaire-progress__fill" style={{ width: `${(answered / total) * 100}%` }} />
      </div>
      <span className="questionnaire-progress__label">{label}</span>
    </div>
  )
}

type TextQuestionProps = { question: Question; value: string; onChange: (value: string) => void }

function TextQuestion({ question, value, onChange }: TextQuestionProps) {
  const inputProps = { id: question.id, value, placeholder: `e.g. ${question.example}`, onChange: (event: { target: { value: string } }) => onChange(event.target.value) }
  return (
    <div className="field">
      <label htmlFor={question.id}>{question.label}</label>
      {question.multiline ? <textarea rows={2} {...inputProps} /> : <input {...inputProps} />}
    </div>
  )
}

function QuestionnairePage({ submit, onComplete, requireFinancials }: QuestionnairePageProps) {
  const [answers, setAnswers] = useState<QuestionnaireAnswers>(EMPTY_ANSWERS)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const answeredCount = QUESTIONS.filter((question) => answers[question.id].trim()).length + (file ? 1 : 0)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = Object.fromEntries(Object.entries(answers).map(([id, value]) => [id, value.trim()])) as QuestionnaireAnswers
    // No question is required; the backend needs the financials CSV to simulate trades.
    const uploadError = validateFinancialsFile(file, requireFinancials)
    setFileError(uploadError)
    setSubmitError(null)
    if (uploadError) return
    setIsSubmitting(true)
    try {
      onComplete(await submit(trimmed, file))
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Something went wrong. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <form className="questionnaire" onSubmit={handleSubmit} noValidate>
      <h1>About your business</h1>
      <p>Tell us how your business works so we can find what's worth protecting.</p>
      <QuestionnaireProgress answered={answeredCount} total={QUESTIONS.length + 1} />

      {QUESTIONS.map((question) => (
        <TextQuestion
          key={question.id}
          question={question}
          value={answers[question.id]}
          onChange={(value) => setAnswers({ ...answers, [question.id]: value })}
        />
      ))}

      <div className="field">
        <label htmlFor="financials">
          Upload your financials (CSV, max 5 MB)
        </label>
        <input id="financials" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        {fileError && <p className="field-error">{fileError}</p>}
      </div>

      {submitError && <p className="field-error" role="alert">{submitError}</p>}

      <button type="submit" className="primary" disabled={isSubmitting}>
        {isSubmitting ? 'Analyzing…' : 'Analyze my risks'}
      </button>
    </form>
  )
}

export default QuestionnairePage
