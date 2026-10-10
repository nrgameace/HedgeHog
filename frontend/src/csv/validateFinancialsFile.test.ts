import { describe, expect, it } from 'vitest'

import { MAX_CSV_BYTES, validateFinancialsFile } from './validateFinancialsFile'

const csvFile = (content: string, name = 'financials.csv') => new File([content], name, { type: 'text/csv' })

describe('validateFinancialsFile', () => {
  it('allows no file, since the upload is optional while we use simulated data', () => {
    expect(validateFinancialsFile(null)).toBeNull()
  })

  it('rejects files that are not CSVs', () => {
    expect(validateFinancialsFile(csvFile('a,b', 'financials.txt'))).toMatch(/csv/i)
  })

  it('rejects empty files', () => {
    expect(validateFinancialsFile(csvFile(''))).toMatch(/empty/i)
  })

  it('rejects files over 5 MB', () => {
    expect(validateFinancialsFile(csvFile('a'.repeat(MAX_CSV_BYTES + 1)))).toMatch(/5 MB/)
  })

  it('accepts a CSV of exactly 5 MB', () => {
    expect(validateFinancialsFile(csvFile('a'.repeat(MAX_CSV_BYTES)))).toBeNull()
  })

  it('accepts a CSV with an uppercase extension', () => {
    expect(validateFinancialsFile(csvFile('date,revenue\n2026-01,1000', 'FINANCIALS.CSV'))).toBeNull()
  })
})
