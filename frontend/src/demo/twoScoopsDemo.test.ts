/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { TWO_SCOOPS_ANSWERS, TWO_SCOOPS_FINANCIALS_FILENAME, twoScoopsFinancialsFile } from './twoScoopsDemo'

// The north-star files live outside frontend/, so read them from disk rather than importing them.
// Tests run from frontend/.
const northStar = (name: string) => readFileSync(join(process.cwd(), '..', 'demo-data', 'two-scoops-creamery', name), 'utf8')
const background = northStar('background.md')
const northStarCsv = northStar('financials.csv')

describe('Two Scoops demo data', () => {
  it('uses the demo answers from demo-data/two-scoops-creamery/background.md', () => {
    for (const answer of Object.values(TWO_SCOOPS_ANSWERS)) {
      expect(background).toContain(`| ${answer} |`)
    }
  })

  it('attaches an exact copy of demo-data/two-scoops-creamery/financials.csv', async () => {
    const file = twoScoopsFinancialsFile()

    expect(file.name).toBe(TWO_SCOOPS_FINANCIALS_FILENAME)
    expect(file.type).toBe('text/csv')
    expect(await file.text()).toBe(northStarCsv)
  })
})
