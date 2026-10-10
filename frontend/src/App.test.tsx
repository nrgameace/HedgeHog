import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('shows the hedgehog landing page with a button to start the questionnaire', () => {
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: /hedgehog/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^start$/i })).toBeInTheDocument()
  })
})
