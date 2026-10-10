import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PageHeader from './PageHeader'

describe('PageHeader', () => {
  it('shows the hedgehog logo and wordmark above the inner pages', () => {
    render(<PageHeader />)

    expect(screen.getByRole('banner')).toHaveTextContent('hedgehog')
    expect(screen.getByRole('img', { name: /hedgehog logo/i })).toBeInTheDocument()
  })
})
