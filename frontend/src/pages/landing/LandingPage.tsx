import type { CSSProperties } from 'react'

import hedgehogLogo from './assets/hedgehog-logo.png'
import FallingLeaves from './graphics/FallingLeaves'
import MainStreetGraphic from './graphics/MainStreetGraphic'
import RainyDayGraphic from './graphics/RainyDayGraphic'
import RollingHills from './graphics/RollingHills'
import ScrollTrail from './graphics/ScrollTrail'
import SteadyCashflowGraphic from './graphics/SteadyCashflowGraphic'
import { BalanceIcon, NotebookIcon, TrendLensIcon } from './graphics/StepIcons'
import StoryScene from './StoryScene'
import './landing.css'

type LandingPageProps = { onStart: () => void }

const STEPS = [
  { Icon: NotebookIcon, title: 'Tell us about your business', body: 'Share what moves your sales — weather, fuel, ingredients — and upload your recent financials.' },
  { Icon: TrendLensIcon, title: 'See what you can hedge', body: 'We spot the outside trends that are actually putting your revenue at risk right now.' },
  { Icon: BalanceIcon, title: 'Get a balanced plan', body: 'We suggest small, sized positions on Kalshi that pay off when a rough patch hits, keeping your cash flow even.' },
]

// Scroll-driven landing page. Styles are scoped under .landing so other pages are untouched.
function LandingPage({ onStart }: LandingPageProps) {
  return (
    <div className="landing">
      <div className="landing__backdrop" aria-hidden="true"><FallingLeaves /></div>

      <div className="landing__content">
        <header className="landing-hero">
          <div className="landing-hero__logo-wrap">
            <img className="landing-hero__logo" src={hedgehogLogo} alt="hedgehog logo" />
          </div>
          <h1>hedgehog</h1>
          <p className="landing-hero__tagline">Steady ground for growing businesses.</p>
          <p className="landing-hero__lede">
            We help small and mid-sized businesses balance their cash flow, so a rainy week or a jump in gas prices never decides how your month turns out.
          </p>
          <button type="button" className="landing-button" onClick={onStart}>Start</button>
          <p className="landing-hero__scroll-cue">Scroll to see how it works</p>
          <RollingHills />
        </header>

        <StoryScene eyebrow="The challenge" heading="Some things are out of your hands." graphic={<RainyDayGraphic />}>
          <p>A rainy Saturday empties the patio. A spike in fuel prices eats into every delivery. You built your business with care — the weather and the markets shouldn't get the final say.</p>
        </StoryScene>

        <StoryScene eyebrow="The idea" heading="So we help you even things out." graphic={<SteadyCashflowGraphic />} layout="reversed">
          <p>Hedgehog finds the outside forces that move your revenue and pairs each one with a small, offsetting position. When a tough day comes, your hedge helps cover it. When the sun is out, you do what you do best.</p>
        </StoryScene>

        <StoryScene
          eyebrow="How it works"
          heading="Simple, from start to finish."
          layout="stacked"
          graphic={(
            <ol className="landing-steps">
              {STEPS.map(({ Icon, title, body }, i) => (
                <li key={title} className="landing-steps__item" style={{ '--i': i } as CSSProperties}>
                  <Icon />
                  <h3>{title}</h3>
                  <p>{body}</p>
                </li>
              ))}
            </ol>
          )}
        >
          <p>A few minutes of your time, and a plan built around the business you actually run.</p>
        </StoryScene>

        <StoryScene eyebrow="Who it's for" heading="Built for businesses like yours." graphic={<MainStreetGraphic />} layout="stacked">
          <p>From the corner café to the family farm, hedgehog helps you plan ahead with confidence, season after season.</p>
          <button type="button" className="landing-button" onClick={onStart}>Let's begin</button>
        </StoryScene>
      </div>

      <ScrollTrail />
    </div>
  )
}

export default LandingPage
