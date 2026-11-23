// The mock server: MSW handlers for every endpoint the app calls, answering like a healthy server.
// One set serves the jsdom tests (Node, tests/utils/server.ts), Storybook (a service worker,
// .storybook/preview.tsx) and the visual suite (Node, strata-visual.config.ts), so the app's real
// fetch, query and DataView code runs in all three and nothing is a module mock.
//
// The named handlers below each replace one route to put a test, story or screenshot into another
// state: `server.use(roundError)` in a test, `msw.use(roundError)` in a story's beforeEach,
// `states: { error: [roundError] }` in the visual config.
import { delay, http, HttpResponse } from 'msw'
import { isMode, paths, type Round, type Settings } from '../api'
import { content } from './content'
import { defaultSettings, modes, rounds } from './fixtures'

/** What the mock server holds. Writes change it, so a test can save a setting and see it used. */
export const mock = {
  settings: { ...defaultSettings } as Settings,
  tries: null as number | null,
  /** Rounds asked for since the last reset: a test can see a round fetched afresh rather than replayed from the cache. */
  roundRequests: 0,
}

/** Back to the healthy state: call between tests and stories. */
export function resetMock() {
  mock.settings = { ...defaultSettings }
  mock.tries = null
  mock.roundRequests = 0
}

// Matched as paths, so they answer whatever origin and base the app runs under.
const at = (path: string) => `*${path}`

/** The fixed round for a mode; Mixed plays Matching, so it is the same picture every time. */
export function roundFor(mode: string | null): Round {
  const m = isMode(mode) ? mode : mock.settings.mode
  const tries = mock.tries ?? (Number(mock.settings.tries) || null)
  return { ...rounds[m === 'mixed' ? 'matching' : m], tries }
}

export const handlers = [
  http.get(at(paths.health), () => HttpResponse.json({ ok: true, version: '0.2.0' })),
  http.get(at(paths.settings), () => HttpResponse.json(mock.settings)),
  http.put(at(paths.settings), async ({ request }) => {
    const body = (await request.json()) as Partial<Settings>
    const choices = Number(body.choices ?? mock.settings.choices)
    if (!(choices >= 2 && choices <= 8)) return HttpResponse.json({ detail: 'choices: must be a whole number from 2 to 8' }, { status: 400 })
    mock.settings = { ...mock.settings, ...body }
    return HttpResponse.json(mock.settings)
  }),
  http.get(at(paths.modes), () => HttpResponse.json(modes)),
  http.get(at(paths.round), ({ request }) => {
    mock.roundRequests += 1
    return HttpResponse.json(roundFor(new URL(request.url).searchParams.get('mode')))
  }),
  http.get(at(paths.content), () => HttpResponse.json(content)),
]

const down = () => HttpResponse.json({ detail: 'down' }, { status: 503 })

export const settingsLoading = http.get(at(paths.settings), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const settingsError = http.get(at(paths.settings), down)
export const saveSettingsFails = http.put(at(paths.settings), down)
export const roundLoading = http.get(at(paths.round), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const roundError = http.get(at(paths.round), down)
/** A server that describes only some kinds of round (an older one): the rest keep their plain names. */
export const modesFew = http.get(at(paths.modes), () => HttpResponse.json(modes.filter(m => m.mode === 'matching' || m.mode === 'counting')))
export const modesError = http.get(at(paths.modes), down)
export const modesLoading = http.get(at(paths.modes), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const contentLoading = http.get(at(paths.content), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const contentError = http.get(at(paths.content), down)
/** A server with no packs to show (a fresh install whose packs failed to ship). */
export const contentEmpty = http.get(at(paths.content), () => HttpResponse.json({ ...content, skills: [], objectives: [], phonics: [] }))
/** Every pack reviewed: the header's warning goes. */
export const contentReviewed = http.get(at(paths.content), () => HttpResponse.json({ ...content, packs: content.packs.map(p => ({ ...p, status: 'reviewed' })) }))
/** A quick look whose pictures go at once (a test need not wait 1.5 s), and one whose pictures stay (a screenshot of them). */
export const quickLookGoes = http.get(at(paths.round), () => HttpResponse.json({ ...roundFor('quick_look'), exposure_ms: 10 }))
export const quickLookStays = http.get(at(paths.round), () => HttpResponse.json({ ...roundFor('quick_look'), exposure_ms: 3_600_000 }))
