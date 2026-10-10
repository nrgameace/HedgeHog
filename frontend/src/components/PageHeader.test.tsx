import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import PageHeader from './PageHeader'

describe('PageHeader', () => {
  it('shows the hedgehog logo and wordmark above the inner pages', () => {
    render(<PageHeader onHome={vi.fn()} />)

    expect(screen.getByRole('banner')).toHaveTextContent('hedgehog')
    expect(screen.getByRole('img', { name: /hedgehog logo/i })).toBeInTheDocument()
  })

  it('goes back to the home page when the logo is pressed', () => {
    const onHome = vi.fn()
    render(<PageHeader onHome={onHome} />)

    fireEvent.click(screen.getByRole('button', { name: /back to home/i }))

    expect(onHome).toHaveBeenCalledOnce()
  })
})
