import curledHedgehog from '../assets/hedgehog-curled.webp'

// Shown while the analysis runs: a curled-up hedgehog spinning like a loading wheel.
function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="loading-hedgehog-stage">
        <img className="loading-hedgehog" src={curledHedgehog} alt="Curled-up hedgehog" />
        <div className="loading-hedgehog__shadow" aria-hidden="true" />
      </div>
      <p className="loading-text" role="status" aria-label="Loading">
        Loading
        <span className="loading-dots" aria-hidden="true">
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </span>
      </p>
    </div>
  )
}

export default LoadingScreen
