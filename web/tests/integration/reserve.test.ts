// The rounds a device keeps for when the server cannot be reached (src/reserve.ts), against the mock server's
// GET /api/rounds; jsdom gives the storage.
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { roundFor } from '../../src/mocks/handlers'
import { kept, refresh, RESERVE, take } from '../../src/reserve'
import { mock, server } from '../utils/server'

const counting = () => roundFor('counting')

describe('rounds kept on the device', () => {
  it('fills up in one request, gives each kept round once, and tops up only when fewer than half are left', async () => {
    expect(take('counting')).toBeNull()
    await refresh('counting', counting())
    expect(mock.keptRequests).toEqual([RESERVE])
    expect(kept('counting')).toBe(RESERVE)
    const seeds = Array.from({ length: RESERVE / 2 }, () => take('counting')?.seed)
    expect(seeds).toEqual([9000, 9001, 9002, 9003]) // oldest first, never twice
    await refresh('counting', counting())
    expect(mock.keptRequests).toEqual([RESERVE]) // half left: enough
    take('counting')
    await refresh('counting', counting())
    expect(mock.keptRequests).toEqual([RESERVE, RESERVE / 2 + 1])
    expect(kept('counting')).toBe(RESERVE)
  })

  it('drops kept rounds a fresh one shows are out of date, and keeps other kinds', async () => {
    await refresh('counting', counting())
    await refresh('mixed', roundFor('matching'))
    const moved = { ...counting(), content: { ...counting().content, words: 99 } }
    mock.keptRequests = []
    await refresh('counting', moved) // the server raised a pack: every kept counting round would be refused
    expect(mock.keptRequests).toEqual([RESERVE])
    expect(kept('mixed')).toBe(RESERVE)
  })

  it('keeps going when a top-up fails or storage holds something else', async () => {
    server.use(http.get('*/api/rounds', () => HttpResponse.error()))
    await refresh('counting', counting())
    expect(kept('counting')).toBe(0)
    window.localStorage.setItem('flashtap:reserve:counting', '{not json')
    expect(take('counting')).toBeNull()
    window.localStorage.setItem('flashtap:reserve:counting', '{"a": 1}')
    expect(kept('counting')).toBe(0)
  })

  it('asks once while a top-up is on its way', async () => {
    await Promise.all([refresh('counting', counting()), refresh('counting', counting())])
    expect(mock.keptRequests).toEqual([RESERVE])
  })
})
