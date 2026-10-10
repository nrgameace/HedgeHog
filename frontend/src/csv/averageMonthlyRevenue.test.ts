import { describe, expect, it } from 'vitest'

import { averageMonthlyRevenue } from './averageMonthlyRevenue'

describe('averageMonthlyRevenue', () => {
  it('averages the revenue column', () => {
    expect(averageMonthlyRevenue('month,revenue,payroll\n2026-01,1000,5\n2026-02,3000,5\n')).toBe(2000)
  })

  it('finds the revenue column regardless of case or position, and skips bad cells', () => {
    expect(averageMonthlyRevenue('Month,Total Revenue\n2026-01,"1,000"\n2026-02,n/a\n2026-03,2000')).toBe(1500)
  })

  it('prefers the total_revenue column over partial revenue columns', () => {
    expect(averageMonthlyRevenue('month,in_store_revenue,total_revenue\n2026-01,100,1000\n2026-02,300,3000')).toBe(2000)
  })

  it('returns null when there is no revenue column', () => {
    expect(averageMonthlyRevenue('month,payroll\n2026-01,5')).toBeNull()
  })
})
