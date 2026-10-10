import type { ReactNode } from 'react'

import { useRevealOnScroll } from './useRevealOnScroll'

type StorySceneProps = { eyebrow: string, heading: string, graphic: ReactNode, children: ReactNode, layout?: 'side' | 'reversed' | 'stacked' }

// One scroll "chapter": its text and graphic fade/slide in the first time it enters view.
function StoryScene({ eyebrow, heading, graphic, children, layout = 'side' }: StorySceneProps) {
  const [sceneRef, isRevealed] = useRevealOnScroll<HTMLElement>()

  return (
    <section ref={sceneRef} className={`landing-scene landing-scene--${layout}${isRevealed ? ' is-revealed' : ''}`}>
      <div className="landing-scene__text">
        <p className="landing-eyebrow">{eyebrow}</p>
        <h2>{heading}</h2>
        {children}
      </div>
      <div className="landing-scene__graphic">{graphic}</div>
    </section>
  )
}

export default StoryScene
