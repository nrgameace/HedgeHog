import { useEffect, useRef, useState } from 'react'

const canObserve = () => typeof IntersectionObserver !== 'undefined'

// Flips to true the first time the element scrolls into view, then stops watching.
export function useRevealOnScroll<T extends Element>(threshold = 0.25) {
  const ref = useRef<T>(null)
  const [isRevealed, setIsRevealed] = useState(() => !canObserve())

  useEffect(() => {
    if (isRevealed || !ref.current) return
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      setIsRevealed(true)
      observer.disconnect()
    }, { threshold })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [isRevealed, threshold])

  return [ref, isRevealed] as const
}
