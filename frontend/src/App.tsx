import { useState } from 'react'

import './App.css'
import { submitQuestionnaire } from './api/client'
import HomePage from './pages/HomePage'
import QuestionnairePage from './pages/QuestionnairePage'
import ResultsPage from './pages/ResultsPage'
import type { HedgeReport } from './types'

type Screen = 'home' | 'questionnaire' | 'results'

// Screens live in memory only: refreshing the page starts over, matching the no-persistence design.
function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [report, setReport] = useState<HedgeReport | null>(null)

  function showResults(newReport: HedgeReport) {
    setReport(newReport)
    setScreen('results')
  }

  function startOver() {
    setReport(null)
    setScreen('home')
  }

  return (
    <main>
      {screen === 'home' && <HomePage onStart={() => setScreen('questionnaire')} />}
      {screen === 'questionnaire' && <QuestionnairePage submit={submitQuestionnaire} onComplete={showResults} />}
      {screen === 'results' && report && <ResultsPage report={report} onStartOver={startOver} />}
    </main>
  )
}

export default App
