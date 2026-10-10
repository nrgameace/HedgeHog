import type { QuestionnaireAnswers } from '../types'

export const blankAnswers: QuestionnaireAnswers = {
  businessDescription: '',
  customers: '',
  location: '',
  operationalDependencies: '',
  keyMaterials: '',
  pastImpacts: '',
  timeOfYear: '',
  lockedInCosts: '',
  riskBudget: '',
}

// North-star demo answers, copied from demo-data/*/background.md ("Demo answers"). Keep in sync.
export const twoScoopsCreamery: QuestionnaireAnswers = {
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
    'Rainy weekends empty the patio — May and June 2024 cost us about a third of our patio sales. Extreme heat waves keep people inside and our electric bill doubles. Winter Storm Uri closed us for 6 days. Gas spikes and our variable-rate van loan going up also hurt.',
  timeOfYear:
    'June through August is over a third of our year, so a bad summer is a bad year. Winter is slow. Spring and December are big for catering.',
  lockedInCosts: 'Our dairy is on a fixed-price contract with a co-op through December 2026.',
  riskBudget: 'About $800 a month.',
}

export const quillstackAi: QuestionnaireAnswers = {
  businessDescription:
    'AI software that reviews contracts for law firms — it flags risky clauses and suggests edits. We charge a monthly subscription plus usage-based API fees.',
  customers: 'About 80 mid-size US law firms, from 20 to 300 lawyers. One national firm is our biggest account.',
  location: 'San Francisco, CA',
  operationalDependencies:
    'Rented GPUs, LLM APIs from model providers, AWS hosting, our engineering team, and a $1.5M venture loan plus the cash from our seed round sitting in T-bills.',
  keyMaterials: 'LLM API tokens are our biggest cost, then GPU hours and AWS hosting.',
  pastImpacts:
    'GPU prices spiked in late 2024 and cut our margin to 40%. Fed rate cuts shrank the interest on our cash. A proposed state AI-liability regulation made firms pause purchases and we lost our largest customer for two months. A weak funding market or a Nasdaq selloff would make our Series A much harder.',
  timeOfYear: 'Law firms freeze spending in December and buy in Q1 when new budgets open. We need to raise our Series A in early 2027.',
  lockedInCosts: 'Our office lease is fixed through February 2027.',
  riskBudget: 'Up to $6,000 a month.',
}

export const iceCreamShop: QuestionnaireAnswers = {
  businessDescription: 'Ice cream shop with outdoor seating',
  customers: 'Tourists and families',
  location: 'Austin, TX',
  operationalDependencies: 'Refrigeration and a delivery van',
  keyMaterials: 'Dairy and sugar',
  pastImpacts: 'Rainy weekends',
  timeOfYear: 'Summer is our busy season',
  lockedInCosts: '',
  riskBudget: '',
}
