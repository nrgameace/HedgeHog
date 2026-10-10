import { afterEach, describe, expect, it, vi } from 'vitest'

import { iceCreamShop } from '../test/answers'
import { submitQuestionnaire } from './client'

const answers = iceCreamShop
const file = new File(['month,revenue\n2026-01,40000\n2026-02,40000'], 'financials.csv', { type: 'text/csv' })
const totalBets = (report: Awaited<ReturnType<typeof submitQuestionnaire>>) => report.bets.reduce((sum, bet) => sum + bet.amountUsd, 0)

describe('submitQuestionnaire', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('in mock mode, returns a report built from the answers', async () => {
    const report = await submitQuestionnaire(answers, null, { useMock: true, mockDelayMs: 0 })

    expect(report.bets.length).toBeGreaterThan(0)
    expect(report.revenueSeries.length).toBeGreaterThan(0)
  })

  it('in mock mode, sizes bets from the uploaded CSV revenue when there is one', async () => {
    const withoutCsv = await submitQuestionnaire(answers, null, { useMock: true, mockDelayMs: 0 })
    const withCsv = await submitQuestionnaire(answers, file, { useMock: true, mockDelayMs: 0 })

    expect(totalBets(withCsv)).toBeLessThanOrEqual(2000)
    expect(totalBets(withCsv)).toBeGreaterThan(totalBets(withoutCsv))
  })

  it('in real mode, posts the answers and the file to /analyze', async () => {
    const report = { concerns: [], bets: [], revenueSeries: [] }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(report), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' })

    const [url, init] = fetchMock.mock.calls[0]
    const body = init.body as FormData
    expect(url).toBe('http://api.test/analyze')
    expect(init.method).toBe('POST')
    expect(JSON.parse(body.get('answers') as string)).toEqual(answers)
    expect((body.get('financials') as File).name).toBe('financials.csv')
    expect(result).toEqual(report)
  })

  it('in real mode, throws when the backend returns an error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))

    await expect(submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' })).rejects.toThrow(/500/)
  })

  it('in real mode, sends only the answers when no file was uploaded', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await submitQuestionnaire(answers, null, { useMock: false, apiUrl: 'http://api.test' })

    const body = fetchMock.mock.calls[0][1].body as FormData
    expect(body.has('answers')).toBe(true)
    expect(body.has('financials')).toBe(false)
  })
})
