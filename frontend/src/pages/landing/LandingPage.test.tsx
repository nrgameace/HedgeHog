import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LandingPage from './LandingPage'

describe('LandingPage', () => {
  beforeEach(() => vi.spyOn(window, 'scrollTo').mockImplementation(() => {}))
  afterEach(() => vi.restoreAllMocks())

  it('uses no em dashes in its copy', () => {
    const { container } = render(<LandingPage onStart={() => {}} />)

    expect(container.textContent).not.toContain('\u2014')
  })

  it('introduces hedgehog with its logo', () => {
    render(<LandingPage onStart={() => {}} />)

    expect(screen.getByRole('heading', { level: 1, name: 'hedgehog' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /hedgehog logo/i })).toBeInTheDocument()
  })

  it('starts the questionnaire from the hero and from the closing call to action', () => {
    const onStart = vi.fn()
    render(<LandingPage onStart={onStart} />)

    fireEvent.click(screen.getByRole('button', { name: /^start$/i }))
    fireEvent.click(screen.getByRole('button', { name: /let's begin/i }))

    expect(onStart).toHaveBeenCalledTimes(2)
  })

  it('returns the reader to the top of the page when they start, so the next screen opens at its beginning', () => {
    render(<LandingPage onStart={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: /let's begin/i }))

    expect(window.scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('tells the story of steadier cash flow for small and mid-sized businesses as you scroll', () => {
    render(<LandingPage onStart={() => {}} />)

    expect(screen.getAllByRole('heading', { level: 2 }).length).toBeGreaterThanOrEqual(3)
    expect(screen.getAllByText(/small and mid-sized businesses/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/cash flow/i).length).toBeGreaterThan(0)
  })
})
