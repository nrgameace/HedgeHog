import { afterEach, describe, expect, it, vi } from 'vitest'

import { blankAnswers, iceCreamShop } from '../test/answers'
import { AnalysisUnavailableError, submitQuestionnaire } from './client'
import { twoScoopsReport } from './twoScoopsReport'

const answers = iceCreamShop
const file = new File(['month,revenue\n2026-01,40000\n2026-02,40000'], 'financials.csv', { type: 'text/csv' })

describe('submitQuestionnaire', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('in mock mode, always shows the simulated Two Scoops Creamery results, whatever was entered', async () => {
    expect(await submitQuestionnaire(blankAnswers, null, { useMock: true, mockDelayMs: 0 })).toEqual(twoScoopsReport())
    expect(await submitQuestionnaire(answers, file, { useMock: true, mockDelayMs: 0 })).toEqual(twoScoopsReport())
  })

  it('in real mode, posts the answers and the file to /analyze', async () => {
    const report = { bets: [], unhedgedRisks: [], profitSeries: [], simulatedPeriod: '' }
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

  it('in real mode, throws the backend\'s explanation when it gives one', async () => {
    const body = JSON.stringify({ detail: 'The financials CSV needs a profit column.' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 400 })))

    await expect(submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' })).rejects.toThrow('The financials CSV needs a profit column.')
  })

  it('in real mode, reports the service as unavailable when the backend is unreachable or broken', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' })).rejects.toBeInstanceOf(AnalysisUnavailableError)

    const misconfigured = new Response(JSON.stringify({ detail: 'the analysis service is misconfigured' }), { status: 500 })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(misconfigured))
    await expect(submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' })).rejects.toThrow(AnalysisUnavailableError)
  })

  it('in real mode, treats a rejected upload as a normal error, not an unavailable service', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'bad csv' }), { status: 400 })))

    const error = await submitQuestionnaire(answers, file, { useMock: false, apiUrl: 'http://api.test' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(Error)
    expect(error).not.toBeInstanceOf(AnalysisUnavailableError)
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
