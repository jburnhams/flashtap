// The FastAPI server's endpoints (src/flashtap/server/app.py) and their shapes. Reads go through
// strata-react's useLoad with the typed client below, which throws HttpError on a non-2xx answer; the
// screens never call fetch themselves. Every URL is built here, with the app's base in front, so the app
// works at the server's root and behind a reverse proxy at /<prefix>/.
import { createOutbox, createTypedApi, fetchJson, withBase, type Delivery } from 'strata-react'

// The shapes are generated from the server's OpenAPI schema (`api.generated.ts`, by strata-react's
// strata-api-types from `web/openapi.json`, which `flashtap openapi` writes), so they follow the Python
// models instead of being written again here. CI fails when either file is stale. What stays here is
// what the schema cannot say: the kinds of round as a list in their order, and the reporting states as
// a list ranked lowest first.
import type { paths as ApiPaths, Schema } from './api.generated'

export type Mode = Schema<'Mode'>
/** The kinds of round, as the server lists them (src/flashtap/mechanics.py `Mode`), Mixed last. */
// The kinds a grown-up picks from: the transfer kinds are left out, being held out of practice (0.13.0).
export const MODES = ['same_picture', 'same_colour', 'same_shape', 'same_letter', 'same_number', 'matching', 'colours', 'shapes', 'letters', 'counting', 'missing', 'quick_look', 'listen', 'give', 'order', 'capitals', 'sort_sounds', 'sounds', 'mixed'] as const satisfies readonly Mode[]
export const isMode = (v: string | null): v is Mode => (MODES as readonly (string | null)[]).includes(v)

/** `GET /api/settings`: the kind of round, and how many choices and tries, as numbers. */
export type Settings = Schema<'FlashtapSettings'>
/** How a round is answered. The first four by one tap (options), the rest by an arrangement (pieces into places). */
export type Mechanic = Schema<'Mechanic'>
export const PLACE_MECHANICS: readonly Mechanic[] = ['give_n', 'sequence', 'match_pairs', 'sort']
export type ModeInfo = Schema<'ModeInfo'>
/** One tile. `word` names it for a screen reader and is never printed: the tile would give the answer away. */
export type Option = Schema<'Option'>
export type Piece = Schema<'Piece'>
/** A place's answer: it must hold exactly `holds` pieces, all from `takes`. */
export type Place = Schema<'Place'>
/** `GET /api/round`: a checked round, rebuilt exactly from (mode, version, choices, seed). A one-tap round has
 * `options` with exactly one right; a placing round has `pieces` and `places`. `mode` is the kind actually played,
 * never Mixed (the server's type is the whole enum). */
export type Round = Omit<Schema<'Round'>, 'mode'> & { mode: Exclude<Mode, 'mixed'> }

/** An edge into or out of a skill, named by the other skill's title. */
export type EdgeRow = Schema<'EdgeRow'>
/** A skill from the content packs. `stages` are curriculum labels only: nothing is gated on them. */
export type SkillRow = Schema<'SkillRow'>
/** A curriculum statement: mapped to skills (their titles), or out of scope with the reason. */
export type ObjectiveRow = Schema<'ObjectiveRow'>
export type PhonicsSetRow = Schema<'PhonicsSetRow'>
/** `GET /api/content`: the content packs flattened into rows (src/flashtap/content/summary.py). */
export type ContentSummary = Schema<'ContentSummary'>

/** A learner: a random id and a nickname, nothing else (AGENTS.md rule 8). */
export type LearnerRow = Schema<'LearnerRow'>
/** A learner's running score, all time: rounds whose first answer was right, and wrong. */
export type Score = Schema<'RunningScore'>
export type SkillState = Schema<'State'>
/** Derived reporting states (src/flashtap/learners/report.py), lowest first. Unobserved is not "not mastered". */
export const SKILL_STATES = ['unobserved', 'introduced', 'emerging', 'independent', 'generalised', 'retained'] as const satisfies readonly SkillState[]
/** One estimator's number for a skill: `bkt@1` P(known), or `rule@1` the share right of the last five. */
export type Estimate = Schema<'Estimate'>
export type SkillReport = Schema<'SkillReport'>
/** `GET /api/learners/{id}/profile`. */
export type Profile = Schema<'Profile'>
/** How quickly right first answers come on a skill (src/flashtap/learners/fluency.py); never part of its state. */
export type Fluency = Schema<'Fluency'>
/** A misconception as the learner's wrong taps stand (src/flashtap/learners/misconceptions.py): a hypothesis. */
export type MisconceptionReport = Schema<'MisconceptionReport'>
export type MisconceptionStatus = Schema<'MisconceptionStatus'>
/** `GET /api/learners/{id}/skills/{skill}/evidence`: one attempt as it bears on one skill, newest first. */
export type EvidenceRow = Schema<'EvidenceRow'>
/** `POST /api/attempts`: one round answered. The server rebuilds the round and judges `first_answer` itself. */
export type AttemptIn = Omit<Schema<'AttemptIn'>, 'first_answer'> & { first_answer: { option: string } | { placement: Record<string, string> } }

/** What Play is asked for: a kind of round, or `next`, the adaptive engine choosing each one for the learner. */
export type PlayChoice = Mode | 'next'
export const isPlayChoice = (v: string | null): v is PlayChoice => v === 'next' || isMode(v)
/** `POST /api/v1/sessions`: a session the engine plans, with the settings it runs with. */
export type SessionInfo = Schema<'SessionInfo'>
/** One of the two rounds a choice offers, with its picture and name for the learner. */
export type OfferOut = Omit<Schema<'OfferOut'>, 'round'> & { round: Round }
/** `POST /api/v1/sessions/{id}/next`: a round, a choice of two, an offered break or the end, with why
 * (src/flashtap/engine/policy.py). A choice's `round` is the picked offer's once it is picked. */
export type Next = Omit<Schema<'Next'>, 'round' | 'offers'> & { round: Round | null; offers: OfferOut[] | null }
/** The three faces after a round: liked it, all right, did not. */
export type Face = 1 | 0 | -1
/** A grown-up's observation of one skill, labelled with who said it (src/flashtap/learners/evidence.py `Told`). */
export type Told = Schema<'Told'>
export type OverrideIn = Schema<'OverrideIn'>
/** How a learner engages, as hypotheses (src/flashtap/learners/engagement.py). */
export type Engagement = Schema<'Engagement'>
export type KindRow = Schema<'KindRow'>
export type Hypothesis = Schema<'Hypothesis'>

/** `GET /api/v1/voice`: the clip of each line that has one (line -> URL under the app's base), and every phonics sound. */
export type VoiceOut = Schema<'VoiceOut'>
/** A phonics sound: its letters, how the browser describes it, and its clip (made from IPA for a vowel, recorded for a consonant). */
export type SoundRow = Schema<'SoundRow'>

/** A random 32-hex-digit id for an event or a session. Not `crypto.randomUUID`: that needs a secure context, and the
 * app is often served over plain http on a home network; `getRandomValues` works anywhere. */
export function newId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')
}

/** The endpoints, as paths under the server's root. Mock handlers (src/mocks/handlers.ts) match the same paths. */
export const paths = {
  health: '/api/health',
  settings: '/api/settings',
  modes: '/api/modes',
  round: '/api/round',
  rounds: '/api/rounds',
  content: '/api/content',
  learners: '/api/learners',
  attempts: '/api/attempts',
  sessions: '/api/v1/sessions',
  overrides: '/api/v1/learners',
  voice: '/api/v1/voice',
} as const

/** The query keys the screens share, so a write can invalidate every read it changes. */
export const keys = {
  settings: ['settings'],
  modes: ['modes'],
  content: ['content'],
  round: (mode: Mode, visit: string, n: number) => ['round', mode, visit, n],
  session: (learner: string, visit: string) => ['session', learner, visit],
  next: (session: string, seq: number) => ['next', session, seq],
  learners: ['learners'],
  profile: (id: string) => ['learners', id, 'profile'],
  // Not under ['learners']: the shell refreshes those on every answer sent, and Play adds this visit's answers to the
  // score it read when the learner sat down (src/score.tsx), so reading it again mid-visit would count them twice.
  score: (id: string, visit: string) => ['score', id, visit],
  evidence: (id: string, skill: string) => ['learners', id, 'evidence', skill],
  voice: ['voice'],
} as const

// Every request goes through strata-react's typed client over the generated `paths`: it puts the app's base
// in front (the page's <base href>, which the server gives every page, so one build works at the root and
// behind a reverse proxy), sends JSON bodies, fills and escapes `{learner_id}`, and checks each path, body and
// answer against the schema. `fetchJson` underneath throws HttpError with the server's reason.
const http = createTypedApi<ApiPaths>()

export const api = {
  settings: () => http.get('/api/settings'),
  saveSettings: (s: Partial<Settings>) => http.put('/api/settings', { json: s }),
  modes: () => http.get('/api/modes'),
  // The server answers the kind actually played (never Mixed), which the schema's whole-enum `mode` cannot say.
  round: (mode: Mode, signal?: AbortSignal) => http.get('/api/round', { query: { mode }, signal }) as Promise<Round>,
  /** Fresh rounds for the device to keep for when it cannot reach the server (src/reserve.ts). */
  rounds: (mode: Mode, count: number) => http.get('/api/rounds', { query: { mode, count } }) as Promise<Round[]>,
  content: () => http.get('/api/content'),
  voice: () => http.get('/api/v1/voice'),
  // A recording is a WAV body, not JSON, which the typed client only sends: fetchJson with the same base and errors.
  keepRecording: (line: string, wav: Blob) =>
    fetchJson<SoundRow>(withBase(`${paths.voice}/recordings?line=${encodeURIComponent(line)}`), { method: 'PUT', body: wav, headers: { 'Content-Type': 'audio/wav' } }),
  learners: () => http.get('/api/learners'),
  addLearner: (nickname: string) => http.post('/api/learners', { json: { nickname } }),
  deleteLearner: (id: string) => http.delete('/api/learners/{learner_id}', { path: { learner_id: id } }),
  profile: (id: string) => http.get('/api/learners/{learner_id}/profile', { path: { learner_id: id } }),
  score: (id: string) => http.get('/api/learners/{learner_id}/score', { path: { learner_id: id } }),
  evidence: (id: string, skill: string) => http.get('/api/learners/{learner_id}/skills/{skill}/evidence', { path: { learner_id: id, skill } }),
  startSession: (learnerId: string) => http.post('/api/v1/sessions', { json: { learner_id: learnerId } }),
  // The server answers a round's played kind (never Mixed), as for `round` above.
  next: (sessionId: string, seq: number) => http.post('/api/v1/sessions/{session_id}/next', { path: { session_id: sessionId }, json: { seq } }) as Promise<Next>,
  pick: (sessionId: string, seq: number, offer: number) => http.post('/api/v1/sessions/{session_id}/decisions/{seq}/pick', { path: { session_id: sessionId, seq }, json: { offer } }) as Promise<Next>,
  tell: (learnerId: string, body: OverrideIn) => http.post('/api/v1/learners/{learner_id}/overrides', { path: { learner_id: learnerId }, json: body }),
  withdraw: (learnerId: string, overrideId: string) => http.post('/api/v1/learners/{learner_id}/overrides/{override_id}/withdraw', { path: { learner_id: learnerId, override_id: overrideId } }),
  strike: (eventId: string, reason: string) => http.post('/api/attempts/{event_id}/strike', { path: { event_id: eventId }, json: { reason } }),
}

/** The export download: a plain link, so the browser saves the file the server names. */
export const exportUrl = (id: string) => withBase(`${paths.learners}/${encodeURIComponent(id)}/export`)

// The server's own limits (src/flashtap/rounds.py), checked here too so the field says why before sending.
export const limits = { minChoices: 2, maxChoices: 8, maxNextAfter: 10 } as const

// Answers and faces wait on the device until the server takes them (spec §14: "queue events offline; server
// reconciles idempotently"). Every attempt carries its own event id, which the server dedupes on, so an answer sent
// twice (its acknowledgement lost) is logged once; a face names the answer it follows, so it is sent after it and is
// not sent at all if the answer was refused. The queue outlives the page: what a closed tab left is sent the next time
// the app opens (Layout starts it). STAND-IN: src/outbox.tsx until strata-react's release.
export const answers = createOutbox({ name: 'flashtap-answers' })

/** Keeps an answered round to send; `delivered` says how its first try went, so Play goes on without the server. */
export function keepAttempt(a: AttemptIn, label: string): Promise<Delivery> {
  return answers.add({ method: 'POST', path: paths.attempts, json: a, id: a.event_id, label }).delivered
}

/** Keeps a face to send after the answer it rates. */
export function keepRating(eventId: string, value: Face, label: string): Promise<Delivery> {
  return answers.add({ method: 'POST', path: `${paths.attempts}/${encodeURIComponent(eventId)}/rating`, json: { value, scale: 'enjoyment' }, after: eventId, label }).delivered
}
