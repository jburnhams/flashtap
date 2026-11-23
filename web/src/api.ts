// The FastAPI server's endpoints (src/flashtap/server/app.py) and their shapes. Reads go through
// strata-react's useLoad with the typed client below, which throws HttpError on a non-2xx answer; the
// screens never call fetch themselves. Every URL is built here, with the app's base in front, so the app
// works at the server's root and behind a reverse proxy at /<prefix>/.
import { createTypedApi, withBase } from 'strata-react'

// The shapes are generated from the server's OpenAPI schema (`api.generated.ts`, by strata-react's
// strata-api-types from `web/openapi.json`, which `flashtap openapi` writes), so they follow the Python
// models instead of being written again here. CI fails when either file is stale. What stays here is
// what the schema cannot say: the kinds of round as a list in their order, and the reporting states as
// a list ranked lowest first.
import type { paths as ApiPaths, Schema } from './api.generated'

export type Mode = Schema<'Mode'>
/** The kinds of round, as the server lists them (src/flashtap/mechanics.py `Mode`), Mixed last. */
export const MODES = ['matching', 'colours', 'shapes', 'letters', 'counting', 'missing', 'quick_look', 'listen', 'give', 'order', 'capitals', 'sort_sounds', 'mixed'] as const satisfies readonly Mode[]
export const isMode = (v: string | null): v is Mode => MODES.includes(v as Mode)

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
export type SkillState = Schema<'State'>
/** Derived reporting states (src/flashtap/learners/report.py), lowest first. Unobserved is not "not mastered". */
export const SKILL_STATES = ['unobserved', 'introduced', 'emerging', 'independent', 'generalised', 'retained'] as const satisfies readonly SkillState[]
/** One estimator's number for a skill: `bkt@1` P(known), or `rule@1` the share right of the last five. */
export type Estimate = Schema<'Estimate'>
export type SkillReport = Schema<'SkillReport'>
/** `GET /api/learners/{id}/profile`. */
export type Profile = Schema<'Profile'>
/** `GET /api/learners/{id}/skills/{skill}/evidence`: one attempt as it bears on one skill, newest first. */
export type EvidenceRow = Schema<'EvidenceRow'>
/** `POST /api/attempts`: one round answered. The server rebuilds the round and judges `first_answer` itself. */
export type AttemptIn = Omit<Schema<'AttemptIn'>, 'first_answer'> & { first_answer: { option: string } | { placement: Record<string, string> } }

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
  content: '/api/content',
  learners: '/api/learners',
  attempts: '/api/attempts',
} as const

/** The query keys the screens share, so a write can invalidate every read it changes. */
export const keys = {
  settings: ['settings'],
  modes: ['modes'],
  content: ['content'],
  round: (mode: Mode, visit: string, n: number) => ['round', mode, visit, n],
  learners: ['learners'],
  profile: (id: string) => ['learners', id, 'profile'],
  evidence: (id: string, skill: string) => ['learners', id, 'evidence', skill],
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
  content: () => http.get('/api/content'),
  learners: () => http.get('/api/learners'),
  addLearner: (nickname: string) => http.post('/api/learners', { json: { nickname } }),
  deleteLearner: (id: string) => http.delete('/api/learners/{learner_id}', { path: { learner_id: id } }),
  profile: (id: string) => http.get('/api/learners/{learner_id}/profile', { path: { learner_id: id } }),
  evidence: (id: string, skill: string) => http.get('/api/learners/{learner_id}/skills/{skill}/evidence', { path: { learner_id: id, skill } }),
  recordAttempt: (a: AttemptIn) => http.post('/api/attempts', { json: a }),
  strike: (eventId: string, reason: string) => http.post('/api/attempts/{event_id}/strike', { path: { event_id: eventId }, json: { reason } }),
}

/** The export download: a plain link, so the browser saves the file the server names. */
export const exportUrl = (id: string) => withBase(`${paths.learners}/${encodeURIComponent(id)}/export`)

// The server's own limits (src/flashtap/rounds.py), checked here too so the field says why before sending.
export const limits = { minChoices: 2, maxChoices: 8 } as const
