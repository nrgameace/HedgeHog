import './App.css'
import LandingPage from './pages/landing/LandingPage'

function App() {
  return <LandingPage onStart={() => window.location.assign('/questionnaire')} />
}

export default App
