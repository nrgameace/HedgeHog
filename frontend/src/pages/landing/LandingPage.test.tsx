import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import LandingPage from './LandingPage'

describe('LandingPage', () => {
  it('uses no em dashes in its copy', () => {
    const { container } = render(<LandingPage onStart={() => {}} />)

    expect(container.textContent).not.toContain('\u2014')
  })

  it('uses the new landing page copy, with each line shown once', () => {
    const { container } = render(<LandingPage onStart={() => {}} />)
    const copy = [
      'A slow week shouldn’t put you behind on payroll. We help small and mid-sized businesses plan their margins so it doesn’t.',
      'Business doesn’t always go to plan.',
      'A rainy Saturday empties the patio. A spike in fuel prices raises the cost of every delivery. Neither is your fault, and both still cut into your cash flow.',
      'We help you even things out.',
      'Hedgehog identifies the outside factors that affect your revenue and sets up a small hedge for each one. If one of them causes a slow day, the hedge pays out to help cover the shortfall. It works like insurance: a small, predictable cost in exchange for protection when you need it.',
      'A few minutes to set up, and a plan built around your business.',
      'Let us know what affects your sales, such as weather, fuel prices or ingredient costs, and upload your recent financials.',
      'We identify the outside factors that pose the biggest risk to your revenue right now.',
      'We recommend small positions on Kalshi, sized to your business, that pay out when a slow stretch hits and help keep your cash flow steady.',
      'For businesses exposed to the real world.',
      'A café that loses its patio crowd when it rains. A farm that relies on the weather at harvest. A delivery service that pays more every time fuel prices rise. If outside factors move your revenue, Hedgehog can help.',
    ]

    for (const line of copy) expect(screen.getAllByText(line)).toHaveLength(1)
    for (const old of ['Some things are out of your hands.', 'Simple, from start to finish.', 'Built for businesses like yours.']) {
      expect(container.textContent).not.toContain(old)
    }
  })

  it('introduces hedgehog with its logo', () => {
    render(<LandingPage onStart={() => {}} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Hedgehog' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /hedgehog logo/i })).toBeInTheDocument()
  })

  it('starts the questionnaire from the hero and from the closing call to action', () => {
    const onStart = vi.fn()
    render(<LandingPage onStart={onStart} />)

    fireEvent.click(screen.getByRole('button', { name: /^start$/i }))
    fireEvent.click(screen.getByRole('button', { name: /let's begin/i }))

    expect(onStart).toHaveBeenCalledTimes(2)
  })

  it('answers the questions a careful owner would ask, without em dashes', () => {
    render(<LandingPage onStart={() => {}} />)

    expect(screen.getByRole('heading', { level: 2, name: /questions/i })).toBeInTheDocument()
    for (const question of [/is this gambling\?/i, /what is kalshi\?/i, /does hedgehog transfer money\?/i, /how much does it cost me\?/i]) {
      expect(screen.getByText(question)).toBeInTheDocument()
    }
    expect(screen.queryByText(/is my data saved\?/i)).not.toBeInTheDocument()
    expect(screen.getByText(/until you go to kalshi and place them yourself/i)).toBeInTheDocument()
  })

  it('tells the story of steadier cash flow for small and mid-sized businesses as you scroll', () => {
    render(<LandingPage onStart={() => {}} />)

    expect(screen.getAllByRole('heading', { level: 2 }).length).toBeGreaterThanOrEqual(3)
    expect(screen.getAllByText(/small and mid-sized businesses/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/cash flow/i).length).toBeGreaterThan(0)
  })
})
