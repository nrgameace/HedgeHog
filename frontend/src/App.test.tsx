import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('shows the Hedgehog homepage with a link to start the questionnaire', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /hedgehog/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /start/i })).toBeInTheDocument()
  })
})
