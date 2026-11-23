// The mock server: MSW handlers for every endpoint the app calls, answering like a healthy server.
// One set serves the jsdom tests (Node, tests/utils/server.ts), Storybook (a service worker,
// .storybook/preview.tsx) and the visual suite (Node, strata-visual.config.ts), so the app's real
// fetch, query and DataView code runs in all three and nothing is a module mock.
//
// The named handlers below each replace one route to put a test, story or screenshot into another
// state: `server.use(roundError)` in a test, `msw.use(roundError)` in a story's beforeEach,
// `states: { error: [roundError] }` in the visual config.
import { delay, http, HttpResponse } from 'msw'
import { isMode, paths, type AttemptIn, type LearnerRow, type Round, type Settings } from '../api'
import { content } from './content'
import { defaultSettings, modes, rounds } from './fixtures'
import { countingEvidence, foxProfile, FOX, learners, owlProfile } from './learners'

/** What the mock server holds. Writes change it, so a test can save a setting and see it used. */
export const mock = {
  settings: { ...defaultSettings } as Settings,
  tries: null as number | null,
  /** Rounds asked for since the last reset: a test can see a round fetched afresh rather than replayed from the cache. */
  roundRequests: 0,
  learners: [...learners] as LearnerRow[],
  /** Attempts the app sent, in order: a test reads what Play reported. */
  attempts: [] as AttemptIn[],
  /** Event ids struck out, with the reason. */
  struck: [] as { event_id: string; reason: string }[],
}

/** Back to the healthy state: call between tests and stories. */
export function resetMock() {
  mock.settings = { ...defaultSettings }
  mock.tries = null
  mock.roundRequests = 0
  mock.learners = [...learners]
  mock.attempts = []
  mock.struck = []
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
    const choices = body.choices ?? mock.settings.choices
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
  http.get(at(paths.learners), () => HttpResponse.json(mock.learners)),
  http.post(at(paths.learners), async ({ request }) => {
    const { nickname } = (await request.json()) as { nickname: string }
    const name = nickname.trim()
    if (mock.learners.some(x => x.nickname.toLowerCase() === name.toLowerCase())) return HttpResponse.json({ detail: `There is already a learner called ${name}.` }, { status: 409 })
    const made = { id: String(mock.learners.length + 1).padStart(32, 'c'), nickname: name, created_at: '2026-11-23T09:00:00Z', attempts: 0, last_played: null }
    mock.learners = [...mock.learners, made]
    return HttpResponse.json(made, { status: 201 })
  }),
  http.delete(at(`${paths.learners}/:id`), ({ params }) => {
    mock.learners = mock.learners.filter(x => x.id !== params.id)
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(at(`${paths.learners}/:id/profile`), ({ params }) => {
    const who = mock.learners.find(x => x.id === params.id)
    if (!who) return HttpResponse.json({ detail: `No learner ${String(params.id)}: removed, or never added.` }, { status: 404 })
    return HttpResponse.json(who.id === FOX ? foxProfile : { ...owlProfile, learner: who })
  }),
  http.get(at(`${paths.learners}/:id/skills/:skill/evidence`), ({ params }) => HttpResponse.json(params.id === FOX && params.skill === 'maths.counting.objects' ? countingEvidence : [])),
  http.post(at(paths.attempts), async ({ request }) => {
    const a = (await request.json()) as AttemptIn
    mock.attempts.push(a)
    return HttpResponse.json({ event_id: a.event_id, first_correct: 'option' in a.first_answer && a.tries === 1 && a.outcome === 'right', duplicate: false })
  }),
  http.post(at(`${paths.attempts}/:id/strike`), async ({ params, request }) => {
    const { reason } = (await request.json()) as { reason: string }
    mock.struck.push({ event_id: String(params.id), reason })
    return new HttpResponse(null, { status: 204 })
  }),
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
export const learnersLoading = http.get(at(paths.learners), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const learnersError = http.get(at(paths.learners), down)
export const learnersNone = http.get(at(paths.learners), () => HttpResponse.json([]))
/** Learners added but none has played yet. */
export const learnersUnplayed = http.get(at(paths.learners), () => HttpResponse.json(learners.map(x => ({ ...x, attempts: 0, last_played: null }))))
export const profileLoading = http.get(at(`${paths.learners}/:id/profile`), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const profileError = http.get(at(`${paths.learners}/:id/profile`), down)
export const evidenceLoading = http.get(at(`${paths.learners}/:id/skills/:skill/evidence`), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const attemptFails = http.post(at(paths.attempts), down)
export const strikeFails = http.post(at(`${paths.attempts}/:id/strike`), down)
export const deleteFails = http.delete(at(`${paths.learners}/:id`), down)
