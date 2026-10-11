import { describe, expect, it } from 'vitest'

import { MAX_CSV_BYTES, validateFinancialsFile } from './validateFinancialsFile'

const csvFile = (content: string, name = 'financials.csv') => new File([content], name, { type: 'text/csv' })

describe('validateFinancialsFile', () => {
  it('allows no file when the upload is not required (mock mode)', () => {
    expect(validateFinancialsFile(null, false)).toBeNull()
  })

  it('asks for the CSV when the upload is required (real backend)', () => {
    expect(validateFinancialsFile(null, true)).toBe('Upload your financials CSV so we can simulate your trades.')
  })

  it('accepts a CSV when the upload is required', () => {
    expect(validateFinancialsFile(csvFile('month,operating_income\n2024-01,1'), true)).toBeNull()
  })

  it('rejects files that are not CSVs', () => {
    expect(validateFinancialsFile(csvFile('a,b', 'financials.txt'), false)).toMatch(/csv/i)
  })

  it('rejects empty files', () => {
    expect(validateFinancialsFile(csvFile(''), false)).toMatch(/empty/i)
  })

  it('caps uploads at 4 MB, under the hosting request limit', () => {
    expect(MAX_CSV_BYTES).toBe(4 * 1024 * 1024)
  })

  it('rejects files over 4 MB', () => {
    expect(validateFinancialsFile(csvFile('a'.repeat(MAX_CSV_BYTES + 1)), false)).toMatch(/4 MB/)
  })

  it('accepts a CSV of exactly 4 MB', () => {
    expect(validateFinancialsFile(csvFile('a'.repeat(MAX_CSV_BYTES)), false)).toBeNull()
  })

  it('accepts a CSV with an uppercase extension', () => {
    expect(validateFinancialsFile(csvFile('date,revenue\n2026-01,1000', 'FINANCIALS.CSV'), false)).toBeNull()
  })
})
