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
import { defaultSettings, modes, rounds } from './fixtures'

/** What the mock server holds. Writes change it, so a test can save a setting and see it used. */
export const mock = {
  settings: { ...defaultSettings } as Settings,
  tries: null as number | null,
}

/** Back to the healthy state: call between tests and stories. */
export function resetMock() {
  mock.settings = { ...defaultSettings }
  mock.tries = null
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
  http.get(at(paths.round), ({ request }) => HttpResponse.json(roundFor(new URL(request.url).searchParams.get('mode')))),
]

const down = () => HttpResponse.json({ detail: 'down' }, { status: 503 })

export const settingsLoading = http.get(at(paths.settings), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const settingsError = http.get(at(paths.settings), down)
export const saveSettingsFails = http.put(at(paths.settings), down)
export const roundLoading = http.get(at(paths.round), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const roundError = http.get(at(paths.round), down)
export const modesLoading = http.get(at(paths.modes), async () => { await delay('infinite'); return HttpResponse.json(null) })
