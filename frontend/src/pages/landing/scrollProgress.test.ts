import { describe, expect, it } from 'vitest'

import { scrollProgress } from './scrollProgress'

describe('scrollProgress', () => {
  it('reports how far down the page the reader has scrolled, from 0 to 1', () => {
    expect(scrollProgress(0, 3000, 1000)).toBe(0)
    expect(scrollProgress(1000, 3000, 1000)).toBe(0.5)
    expect(scrollProgress(2000, 3000, 1000)).toBe(1)
  })

  it('stays within 0 and 1 during overscroll bounce', () => {
    expect(scrollProgress(-40, 3000, 1000)).toBe(0)
    expect(scrollProgress(2100, 3000, 1000)).toBe(1)
  })

  it('treats a page too short to scroll as not scrolled', () => {
    expect(scrollProgress(0, 800, 1000)).toBe(0)
  })
})
