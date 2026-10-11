import { useEffect, useState } from 'react'

import './App.css'
import { MOCK_API, submitQuestionnaire } from './api/client'
import PageHeader from './components/PageHeader'
import LandingPage from './pages/landing/LandingPage'
import QuestionnairePage from './pages/QuestionnairePage'
import ResultsPage from './pages/ResultsPage'
import type { HedgeReport } from './types'

type Screen = 'home' | 'questionnaire' | 'results'

// Screens live in memory only: refreshing the page starts over, matching the no-persistence design.
function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [report, setReport] = useState<HedgeReport | null>(null)

  // Each screen opens at its top, not wherever the previous one was scrolled to.
  useEffect(() => { window.scrollTo(0, 0) }, [screen])

  function showResults(newReport: HedgeReport) {
    setReport(newReport)
    setScreen('results')
  }

  function startOver() {
    setReport(null)
    setScreen('home')
  }

  // The landing page is full-bleed, so it renders outside the narrow <main> column.
  if (screen === 'home') return <LandingPage onStart={() => setScreen('questionnaire')} />

  return (
    <>
      <PageHeader onHome={startOver} />
      <main>
        {screen === 'questionnaire' && <QuestionnairePage submit={submitQuestionnaire} onComplete={showResults} requireFinancials={!MOCK_API} />}
        {screen === 'results' && report && <ResultsPage report={report} onStartOver={startOver} />}
      </main>
    </>
  )
}

export default App
