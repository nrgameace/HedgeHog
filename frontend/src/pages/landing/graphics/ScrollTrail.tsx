import { useEffect, useRef } from 'react'

import hedgehogLogo from '../../../assets/hedgehog-logo.png'
import { scrollProgress } from '../scrollProgress'

// A little hedgehog that trots along the bottom of the screen as the reader scrolls.
function ScrollTrail() {
  const trailRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let frame = 0
    const update = () => {
      const { scrollHeight } = document.documentElement
      const progress = scrollProgress(window.scrollY, scrollHeight, window.innerHeight)
      trailRef.current?.style.setProperty('--hh-progress', String(progress))
      frame = 0
    }
    const onScroll = () => { frame ||= requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])

  return (
    <div ref={trailRef} className="hh-trail" aria-hidden="true">
      <img className="hh-trail__hedgehog" src={hedgehogLogo} alt="" />
    </div>
  )
}

export default ScrollTrail
