import { afterEach, describe, expect, it, vi } from 'vitest'

import { submitQuestionnaire } from './client'

const answers = { factors: ['Rain', 'Coffee prices'], expectedEarnings: 20000 }
const file = new File(['date,revenue\n2026-01,1000'], 'financials.csv', { type: 'text/csv' })

describe('submitQuestionnaire', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('in mock mode, returns a report with one concern and one bet per factor', async () => {
    const report = await submitQuestionnaire(answers, file, { useMock: true, mockDelayMs: 0 })

    expect(report.concerns.map((concern) => concern.factor)).toEqual(['Rain', 'Coffee prices'])
    expect(report.bets).toHaveLength(2)
    expect(report.revenueSeries.length).toBeGreaterThan(0)
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
