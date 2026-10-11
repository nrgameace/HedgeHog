import type { QuestionnaireAnswers } from '../types'
import financialsCsv from './two-scoops-creamery-financials.csv?raw'

// Two Scoops Creamery, the north-star demo business. Copies of demo-data/two-scoops-creamery/
// ("Demo answers" in background.md, and financials.csv); a test keeps them in sync.

export const TWO_SCOOPS_ANSWERS: QuestionnaireAnswers = {
  businessDescription:
    'Family-run ice cream shop with a walk-up window and outdoor patio seating. We also cater events, deliver pints, and wholesale pints to six local grocery stores.',
  customers:
    'Families, UT students, and tourists walking South Congress, mostly on warm evenings and weekends. When prices go up everywhere, people cut back on treats like ours first.',
  location: 'Austin, TX',
  operationalDependencies:
    'Freezers and refrigeration running 24/7, good patio weather, foot traffic, and our delivery van for pint deliveries and grocery runs.',
  keyMaterials:
    'Dairy (milk and cream) is our biggest cost, then sugar, cones and pint containers. Electricity for the freezers and gas for the van.',
  pastImpacts:
    'Rainy weekends empty the patio. May and June 2024 cost us about a third of our patio sales. Extreme heat waves keep people inside and our electric bill doubles. Winter Storm Uri closed us for 6 days. Gas spikes and our variable-rate van loan going up also hurt.',
  timeOfYear:
    'June through August is over a third of our year, so a bad summer is a bad year. Winter is slow. Spring and December are big for catering.',
  lockedInCosts: 'Our dairy is on a fixed-price contract with a co-op through December 2026.',
  riskBudget: 'About $800 a month.',
}

export const TWO_SCOOPS_FINANCIALS_FILENAME = 'two-scoops-creamery-financials.csv'

export function twoScoopsFinancialsFile(): File {
  return new File([financialsCsv], TWO_SCOOPS_FINANCIALS_FILENAME, { type: 'text/csv' })
}
