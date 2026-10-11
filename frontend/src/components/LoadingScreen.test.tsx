import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import LoadingScreen from './LoadingScreen'

describe('LoadingScreen', () => {
  it('announces that it is loading', () => {
    render(<LoadingScreen />)

    expect(screen.getByRole('status')).toHaveAccessibleName('Loading')
    expect(screen.getByRole('status')).toHaveTextContent(/^Loading\.\.\.$/)
  })

  it('shows a curled-up hedgehog that spins like a loading wheel', () => {
    render(<LoadingScreen />)

    expect(screen.getByRole('img', { name: /curled-up hedgehog/i })).toHaveClass('loading-hedgehog')
  })

  it('reveals the dots one at a time', () => {
    const { container } = render(<LoadingScreen />)

    expect(container.querySelectorAll('.loading-dots span')).toHaveLength(3)
  })
})
