// The mock server: MSW handlers for every endpoint the app calls, answering like a healthy server.
// One set serves the jsdom tests (Node, tests/utils/server.ts), Storybook (a service worker,
// .storybook/preview.tsx) and the visual suite (Node, strata-visual.config.ts), so the app's real
// fetch, query and DataView code runs in all three and nothing is a module mock.
//
// The named handlers below each replace one route to put a test, story or screenshot into another
// state: `server.use(roundError)` in a test, `msw.use(roundError)` in a story's beforeEach,
// `states: { error: [roundError] }` in the visual config.
import { delay, http, HttpResponse } from 'msw'
import { isMode, paths, type AttemptIn, type LearnerRow, type Next, type OfferOut, type OverrideIn, type Round, type Settings, type Told } from '../api'
import { content } from './content'
import { defaultSettings, modes, rounds } from './fixtures'
import { countingEvidence, foxProfile, FOX, learners, owlProfile } from './learners'
import { voice } from './voice'

/** A round of a kind, a choice between two kinds (`pick:a/b`), a break or the end. `+rate` asks for the faces after it. */
type Plan = Round['mode'] | `${Round['mode']}+rate` | `pick:${Round['mode']}/${Round['mode']}` | 'break' | 'end'
const PLAN: Plan[] = ['counting', 'give', 'break', 'matching', 'end']

/** What the mock server holds. Writes change it, so a test can save a setting and see it used. */
export const mock = {
  settings: { ...defaultSettings } as Settings,
  tries: null as number | null,
  /** Rounds asked for since the last reset: a test can see a round fetched afresh rather than replayed from the cache. */
  roundRequests: 0,
  /** Requests for rounds to keep on the device (GET /api/rounds), and how many each asked for. */
  keptRequests: [] as number[],
  learners: [...learners] as LearnerRow[],
  /** Attempts the app sent, in order: a test reads what Play reported. */
  attempts: [] as AttemptIn[],
  /** Event ids struck out, with the reason. */
  struck: [] as { event_id: string; reason: string }[],
  /** What the engine decides, by number: a round of that kind, a break or the end; past the list, the end. */
  plan: [...PLAN] as Plan[],
  /** Decision numbers asked for, in order: a test sees a retry ask for the same number. */
  nextRequests: [] as number[],
  /** Picks from a choice of two, by decision number. */
  picks: {} as Record<number, number>,
  /** Faces sent, in order. */
  ratings: [] as { event_id: string; value: number }[],
  /** A grown-up's overrides sent, and the ids withdrawn. */
  told: [] as (OverrideIn & { learner_id: string })[],
  withdrawn: [] as string[],
  /** The recorded voice: the clips list and every sound. A kept recording changes it. */
  voice: structuredClone(voice),
  /** Recordings kept, in order: the sound and the WAV's size. */
  recordings: [] as { line: string; bytes: number }[],
}

/** Back to the healthy state: call between tests and stories. */
export function resetMock() {
  mock.settings = { ...defaultSettings }
  mock.tries = null
  mock.roundRequests = 0
  mock.keptRequests = []
  mock.learners = [...learners]
  mock.attempts = []
  mock.struck = []
  mock.plan = [...PLAN]
  mock.nextRequests = []
  mock.picks = {}
  mock.ratings = []
  mock.told = []
  mock.withdrawn = []
  mock.voice = structuredClone(voice)
  mock.recordings = []
}

/** A short silent PCM WAV (16-bit mono, 8 kHz), for every clip the mock voice serves: something real to play. */
export function silentWav(seconds = 0.2): ArrayBuffer {
  const frames = Math.round(8000 * seconds)
  const b = new DataView(new ArrayBuffer(44 + frames * 2))
  const text = (at: number, t: string) => { for (let i = 0; i < t.length; i++) b.setUint8(at + i, t.charCodeAt(i)) }
  text(0, 'RIFF'); b.setUint32(4, 36 + frames * 2, true); text(8, 'WAVE'); text(12, 'fmt ')
  b.setUint32(16, 16, true); b.setUint16(20, 1, true); b.setUint16(22, 1, true); b.setUint32(24, 8000, true)
  b.setUint32(28, 16000, true); b.setUint16(32, 2, true); b.setUint16(34, 16, true); text(36, 'data'); b.setUint32(40, frames * 2, true)
  return b.buffer
}

export const SESSION = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
const titles: Record<string, string> = { counting: 'Count a set of things', give: 'Give a number of things', matching: 'Find the picture for a spoken word', listen: 'Hear a sound and find its letter' }
const names: Record<string, string> = Object.fromEntries(modes.map(m => [m.mode, m.name]))
const pictures: Record<string, string> = { counting: '\u{1F522}', give: '\u{1F9FA}', matching: '\u{1F404}', listen: '\u{1F442}' }

function offerFor(mode: Round['mode']): OfferOut {
  const r = roundFor(mode)
  const skill = r.skills[0]?.skill ?? ''
  return { mode, title: names[mode] ?? mode, picture: pictures[mode] ?? '\u2753', skill, skill_title: titles[mode] ?? skill, round: r, why: `Practising: ${titles[mode] ?? skill}.` }
}

/** Decision `seq` of the mock session, in the server's shape (src/flashtap/engine/sessions.py `Next`). */
export function decisionFor(seq: number): Next {
  const planned = mock.plan[seq] ?? 'end'
  const rate = planned.endsWith('+rate')
  const step = planned.replace('+rate', '')
  const played = mock.plan.slice(0, seq).filter(p => p !== 'break' && p !== 'end').length
  const base = { id: `d${seq}`.padEnd(32, '0'), session_id: SESSION, seq, at: '2026-11-23T09:00:00Z', policy: 'utility@3', probability: 1, rounds_played: played, candidates: [], offers: null, picked: null, rate }
  if (step.startsWith('pick:')) {
    const offers = step.slice(5).split('/').map(m => offerFor(m as Round['mode']))
    const picked = mock.picks[seq] ?? null
    const o = picked === null ? null : offers[picked]
    return { ...base, action: 'choice', offers, picked, round: o?.round ?? null, skill: o?.skill ?? null, skill_title: o?.skill_title ?? null, rationale: ['offered_choice'], why: `Two to pick from, so they choose what comes next.${o ? ` ${o.why}` : ''}`, probability: 0.3, rate: true }
  }
  if (step === 'break') return { ...base, action: 'break', round: null, skill: null, skill_title: null, rationale: ['break_due'], why: `${played} round${played === 1 ? '' : 's'} played so far.` }
  if (step === 'end') return { ...base, action: 'end', round: null, skill: null, skill_title: null, rationale: ['session_cap_rounds'], why: `A session is ${played} round${played === 1 ? '' : 's'} at most.` }
  const r = roundFor(step)
  const skill = r.skills[0]?.skill ?? ''
  return { ...base, action: 'round', round: r, skill, skill_title: titles[step] ?? skill, rationale: ['practise'], why: `Practising: ${titles[step] ?? skill}.`, probability: 0.42 }
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
  http.get(at(paths.voice), () => HttpResponse.json(mock.voice)),
  http.get(at(`${paths.voice}/clips/:name`), () => new HttpResponse(silentWav(), { headers: { 'Content-Type': 'audio/wav' } })),
  http.put(at(`${paths.voice}/recordings`), async ({ request }) => {
    const line = new URL(request.url).searchParams.get('line') ?? ''
    const row = mock.voice.sounds.find(s => s.line === line)
    if (!row) return HttpResponse.json({ detail: `${line} is not a sound of the phonics inventory: only sounds are recorded here` }, { status: 400 })
    const bytes = (await request.arrayBuffer()).byteLength
    mock.recordings.push({ line, bytes })
    Object.assign(row, { source: 'recorded', clip: `api/v1/voice/clips/kept${mock.recordings.length}.wav` })
    mock.voice.clips[line] = row.clip!
    return HttpResponse.json(row)
  }),
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
  http.get(at(paths.rounds), ({ request }) => {
    const q = new URL(request.url).searchParams
    const count = Number(q.get('count') ?? 8)
    mock.keptRequests.push(count)
    // Kept rounds differ by seed, as the server's do, so a test can tell which one is on screen.
    return HttpResponse.json(Array.from({ length: count }, (_, i) => ({ ...roundFor(q.get('mode')), seed: 9000 + i })))
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
  http.post(at(paths.sessions), async ({ request }) => {
    const { learner_id } = (await request.json()) as { learner_id: string }
    return HttpResponse.json({ id: SESSION, learner_id, policy: 'utility@3', config: { choices: 4, tries: 0, max_rounds: 20, max_minutes: 15, break_every: 10, choice_every: 5, rate_every: 4 }, started_at: '2026-11-23T09:00:00Z' }, { status: 201 })
  }),
  http.post(at(`${paths.sessions}/:id/next`), async ({ request }) => {
    const { seq } = (await request.json()) as { seq: number }
    mock.nextRequests.push(seq)
    return HttpResponse.json(decisionFor(seq))
  }),
  http.post(at(`${paths.sessions}/:id/decisions/:seq/pick`), async ({ params, request }) => {
    const { offer } = (await request.json()) as { offer: number }
    const seq = Number(params.seq)
    const was = mock.picks[seq]
    if (was !== undefined && was !== offer) return HttpResponse.json({ detail: `Choice ${seq} was already answered with offer ${was}; a pick is never changed.` }, { status: 409 })
    mock.picks[seq] = offer
    return HttpResponse.json(decisionFor(seq))
  }),
  http.post(at(`${paths.attempts}/:id/strike`), async ({ params, request }) => {
    const { reason } = (await request.json()) as { reason: string }
    mock.struck.push({ event_id: String(params.id), reason })
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(at(`${paths.attempts}/:id/rating`), async ({ params, request }) => {
    const { value } = (await request.json()) as { value: number }
    mock.ratings.push({ event_id: String(params.id), value })
    return HttpResponse.json({ event_id: String(params.id), scale: 'enjoyment', value, duplicate: false })
  }),
  http.post(at(`${paths.overrides}/:id/overrides`), async ({ params, request }) => {
    const body = (await request.json()) as OverrideIn
    mock.told.push({ ...body, learner_id: String(params.id) })
    const made: Told = { id: String(mock.told.length).padStart(32, 'f'), ...body, note: body.note ?? '', at: '2026-11-23T09:00:00Z', withdrawn_at: null }
    return HttpResponse.json(made, { status: 201 })
  }),
  http.post(at(`${paths.overrides}/:id/overrides/:override/withdraw`), ({ params }) => {
    mock.withdrawn.push(String(params.override))
    return new HttpResponse(null, { status: 204 })
  }),
]

const down = () => HttpResponse.json({ detail: 'down' }, { status: 503 })

export const voiceError = http.get(at(paths.voice), down)
export const voiceLoading = http.get(at(paths.voice), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const voiceAllRecorded = http.get(at(paths.voice), () => {
  const sounds = voice.sounds.map(s => (s.vowel ? s : { ...s, source: 'recorded' as const, clip: `api/v1/voice/clips/r${s.phoneme}.wav` }))
  return HttpResponse.json({ sounds, clips: Object.fromEntries(sounds.filter(s => s.clip).map(s => [s.line, s.clip!])) })
})
export const keepRecordingFails = http.put(at(`${paths.voice}/recordings`), down)

export const settingsLoading = http.get(at(paths.settings), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const settingsError = http.get(at(paths.settings), down)
export const saveSettingsFails = http.put(at(paths.settings), down)
export const roundLoading = http.get(at(paths.round), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const roundError = http.get(at(paths.round), down)
/** No connection at all: the request fails before any answer (a dropped wifi), as against a server that answers 503. */
const unreachable = () => HttpResponse.error()
export const roundUnreachable = http.get(at(paths.round), unreachable)
export const attemptUnreachable = http.post(at(paths.attempts), unreachable)
export const nextUnreachable = http.post(at(`${paths.sessions}/:id/next`), unreachable)
/** The server refuses every answer (a pack changed since the round was made). */
export const attemptRefused = http.post(at(paths.attempts), () => HttpResponse.json({ detail: 'counting was made from words@1; the packs are now words@2 and the earlier ones are not kept.' }, { status: 400 }))
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
export const sessionError = http.post(at(paths.sessions), down)
export const nextLoading = http.post(at(`${paths.sessions}/:id/next`), async () => { await delay('infinite'); return HttpResponse.json(null) })
export const nextError = http.post(at(`${paths.sessions}/:id/next`), down)
/** The engine offers a break first, after 10 rounds (a story shows the offer without playing them). */
export const nextBreak = http.post(at(`${paths.sessions}/:id/next`), () => HttpResponse.json({ ...decisionFor(0), action: 'break', round: null, skill: null, skill_title: null, rationale: ['break_due'], why: '10 rounds played so far.', rounds_played: 10 }))
/** The engine ends the session at once, at 20 rounds. */
export const nextEnd = http.post(at(`${paths.sessions}/:id/next`), () => HttpResponse.json({ ...decisionFor(0), action: 'end', round: null, skill: null, skill_title: null, rationale: ['session_cap_rounds'], why: 'A session is 20 rounds at most.', rounds_played: 20 }))
/** A session the engine plans as `plan` says, whatever the mock held: for a story or a screenshot that starts there. */
const planned = (plan: Plan[]) => http.post(at(`${paths.sessions}/:id/next`), async ({ request }) => {
  const { seq } = (await request.json()) as { seq: number }
  mock.nextRequests.push(seq)
  mock.plan = plan
  return HttpResponse.json(decisionFor(seq))
})
/** A choice of two first, Counting or Listen, asking for the faces after the one picked; then the end. */
export const nextChoice = planned(['pick:counting/listen', 'end'])
/** A Matching round that asks how it was once it is over. */
export const nextRated = planned(['matching+rate', 'end'])
export const pickFails = http.post(at(`${paths.sessions}/:id/decisions/:seq/pick`), down)
export const ratingFails = http.post(at(`${paths.attempts}/:id/rating`), down)
/** The server refuses a face for good (one already given differently): it is never sent again. */
export const ratingRefused = http.post(at(`${paths.attempts}/:id/rating`), () => HttpResponse.json({ detail: 'This round is already rated 1; a rating is never rewritten.' }, { status: 409 }))
export const tellFails = http.post(at(`${paths.overrides}/:id/overrides`), down)
export const withdrawFails = http.post(at(`${paths.overrides}/:id/overrides/:override/withdraw`), down)
/** Fox with nothing in how they play that stands out. */
export const profileQuiet = http.get(at(`${paths.learners}/:id/profile`), () => HttpResponse.json({ ...foxProfile, engagement: { ...foxProfile.engagement, hypotheses: [] } }))
