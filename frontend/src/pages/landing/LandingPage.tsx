import type { CSSProperties } from 'react'

import hedgehogLogo from '../../assets/hedgehog-logo.png'
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
  { Icon: NotebookIcon, title: 'Tell us about your business', body: 'Let us know what affects your sales, such as weather, fuel prices or ingredient costs, and upload your recent financials.' },
  { Icon: TrendLensIcon, title: 'See what you can hedge', body: 'We identify the outside factors that pose the biggest risk to your revenue right now.' },
  { Icon: BalanceIcon, title: 'Get a balanced plan', body: 'We recommend small positions on Kalshi, sized to your business, that pay out when a slow stretch hits and help keep your cash flow steady.' },
]

// Scroll-driven landing page. Styles are scoped under .landing so other pages are untouched.
function LandingPage({ onStart }: LandingPageProps) {
  function start() {
    window.scrollTo(0, 0)
    onStart()
  }

  return (
    <div className="landing">
      <div className="landing__backdrop" aria-hidden="true"><FallingLeaves /></div>

      <div className="landing__content">
        <header className="landing-hero">
          <div className="landing-hero__logo-wrap">
            <img className="landing-hero__logo" src={hedgehogLogo} alt="hedgehog logo" />
          </div>
          <h1>Hedgehog</h1>
          <p className="landing-hero__tagline">Steady ground for growing businesses.</p>
          <p className="landing-hero__lede">
            A slow week shouldn’t put you behind on payroll. We help small and mid-sized businesses plan their margins so it doesn’t.
          </p>
          <button type="button" className="landing-button" onClick={start}>Start</button>
          <p className="landing-hero__scroll-cue">Scroll to see how it works</p>
          <RollingHills />
        </header>

        <StoryScene eyebrow="The challenge" heading="Business doesn’t always go to plan." graphic={<RainyDayGraphic />}>
          <p>A rainy Saturday empties the patio. A spike in fuel prices raises the cost of every delivery. Neither is your fault, and both still cut into your cash flow.</p>
        </StoryScene>

        <StoryScene eyebrow="The idea" heading="We help you even things out." graphic={<SteadyCashflowGraphic />} layout="reversed">
          <p>Hedgehog identifies the outside factors that affect your revenue and sets up a small hedge for each one. If one of them causes a slow day, the hedge pays out to help cover the shortfall. It works like insurance: a small, predictable cost in exchange for protection when you need it.</p>
        </StoryScene>

        <StoryScene
          eyebrow="How it works"
          heading="A few minutes to set up, and a plan built around your business."
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
        />

        <StoryScene eyebrow="Who it's for" heading="For businesses exposed to the real world." graphic={<MainStreetGraphic />} layout="stacked">
          <p>A café that loses its patio crowd when it rains. A farm that relies on the weather at harvest. A delivery service that pays more every time fuel prices rise. If outside factors move your revenue, Hedgehog can help.</p>
          <button type="button" className="landing-button" onClick={start}>Let's begin</button>
        </StoryScene>
      </div>

      <ScrollTrail />
    </div>
  )
}

export default LandingPage
