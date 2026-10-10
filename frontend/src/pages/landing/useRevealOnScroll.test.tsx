import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useRevealOnScroll } from './useRevealOnScroll'

function RevealProbe() {
  const [ref, isRevealed] = useRevealOnScroll<HTMLDivElement>()
  return <div ref={ref} data-testid="probe" data-revealed={isRevealed} />
}

type ObserverCallback = (entries: Array<{ isIntersecting: boolean }>) => void

function installFakeIntersectionObserver() {
  const observer = { callback: null as ObserverCallback | null, disconnect: vi.fn() }
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: ObserverCallback) { observer.callback = callback }
    observe() {}
    disconnect() { observer.disconnect() }
  })
  return observer
}

describe('useRevealOnScroll', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('reveals immediately when the browser cannot observe scrolling', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    render(<RevealProbe />)

    expect(screen.getByTestId('probe')).toHaveAttribute('data-revealed', 'true')
  })

  it('stays hidden until scrolled into view, then stays revealed', () => {
    const observer = installFakeIntersectionObserver()
    render(<RevealProbe />)
    expect(screen.getByTestId('probe')).toHaveAttribute('data-revealed', 'false')

    act(() => observer.callback?.([{ isIntersecting: true }]))

    expect(screen.getByTestId('probe')).toHaveAttribute('data-revealed', 'true')
    expect(observer.disconnect).toHaveBeenCalled()
  })
})
