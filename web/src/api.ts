// The FastAPI server's endpoints (src/flashtap/server/app.py) and their shapes. Reads go through
// strata-react's useLoad with fetchJson, which throws HttpError on a non-2xx answer; the screens
// never call fetch themselves. Every URL is built here, through withBase, so the app works at the
// server's root and behind a reverse proxy at /<prefix>/.
import { fetchJson } from 'strata-react'

// The kinds of round, as the server lists them (src/flashtap/mechanics.py `Mode`), Mixed last.
export const MODES = ['matching', 'colours', 'shapes', 'letters', 'counting', 'missing', 'quick_look', 'listen', 'give', 'order', 'capitals', 'sort_sounds', 'mixed'] as const
export type Mode = (typeof MODES)[number]
export const isMode = (v: string | null): v is Mode => MODES.includes(v as Mode)

/** `GET /api/settings`. strata-python keeps every value as a canonical string. */
export interface Settings { mode: Mode; choices: string; tries: string }
/** How a round is answered. The first four by one tap (options), the rest by an arrangement (pieces into places). */
export type Mechanic = 'select_one' | 'fill_missing' | 'brief_exposure' | 'audio_respond' | 'give_n' | 'sequence' | 'match_pairs' | 'sort'
export const PLACE_MECHANICS: readonly Mechanic[] = ['give_n', 'sequence', 'match_pairs', 'sort']
export interface ModeInfo { mode: Mode; name: string; description: string; mechanic: Mechanic | null }
/** One tile. `word` names it for a screen reader and is never printed: the tile would give the answer away. */
export interface Option { id: string; picture: string; word: string; correct: boolean; feedback: string; distractor: string }
export interface Piece { id: string; picture: string; word: string }
/** A place's answer: it must hold exactly `holds` pieces, all from `takes`. */
export interface Place { id: string; picture: string; word: string; takes: string[]; holds: number }
/** `GET /api/round`: a checked round, rebuilt exactly from (mode, version, choices, seed). A one-tap round has
 * `options` with exactly one right; a placing round has `pieces` and `places`. */
export interface Round {
  mode: Exclude<Mode, 'mixed'>
  version: number
  choices: number
  seed: number
  mechanic: Mechanic
  skills: { skill: string; role: 'primary' | 'secondary' | 'confound' }[]
  /** Shown as the heading. */
  prompt: string
  /** Said aloud; differs from `prompt` where printing it would give the answer to a reader (Listen). */
  say: string
  /** The big picture or word above the answer; empty for none. */
  show: string
  /** A brief exposure: `show` is hidden after this long. */
  exposure_ms: number | null
  options: Option[]
  answer: string
  pieces: Piece[]
  places: Place[]
  /** A placing round: said when the arrangement is right. */
  done_feedback: string
  /** Taps (one-tap rounds) or checks (placing rounds) before the round counts as missed; null for no limit. */
  tries: number | null
}

/** An edge into or out of a skill, named by the other skill's title. */
export interface EdgeRow { skill: string; relation: string; confidence: string; source: string; note: string }
/** A skill from the content packs. `stages` are curriculum labels only: nothing is gated on them. */
export interface SkillRow {
  id: string
  title: string
  description: string
  domain: string
  strand: string
  stages: string[]
  modes: string[]
  needs: EdgeRow[]
  leads_to: EdgeRow[]
  misconceptions: string[]
}
/** A curriculum statement: mapped to skills (their titles), or out of scope with the reason. */
export interface ObjectiveRow { id: string; curriculum: string; stage: string; area: string; goal: string; text: string; skills: string[]; out_of_scope: string; note: string }
export interface PhonicsSetRow { id: string; title: string; gpcs: { grapheme: string; phoneme: string; example: string }[]; words: string[] }
/** `GET /api/content`: the content packs flattened into rows (src/flashtap/content/summary.py). */
export interface ContentSummary {
  packs: { id: string; version: number; title: string; status: 'draft' | 'reviewed' }[]
  skills: SkillRow[]
  objectives: ObjectiveRow[]
  phonics: { id: string; title: string; dialect: string; sets: PhonicsSetRow[] }[]
}

/** A learner: a random id and a nickname, nothing else (AGENTS.md rule 8). */
export interface LearnerRow { id: string; nickname: string; created_at: string; attempts: number; last_played: string | null }
/** Derived reporting states (src/flashtap/learners/report.py), lowest first. Unobserved is not "not mastered". */
export const SKILL_STATES = ['unobserved', 'introduced', 'emerging', 'independent', 'generalised', 'retained'] as const
export type SkillState = (typeof SKILL_STATES)[number]
/** One estimator's number for a skill: `bkt@1` P(known), or `rule@1` the share right of the last five. */
export interface Estimate { model: string; p: number; used: number }
export interface SkillReport {
  skill: string
  title: string
  domain: string
  strand: string
  state: SkillState
  /** BKT first; empty while unobserved (a prior is not evidence). */
  estimates: Estimate[]
  counted: number
  right: number
  /** Attempts that touched the skill but did not count, each with its reason in the evidence. */
  held: number
  mechanics: Mechanic[]
  last_seen: string | null
}
/** `GET /api/learners/{id}/profile`. */
export interface Profile { learner: LearnerRow; sessions: number; struck: number; models: { model: string; description: string }[]; skills: SkillReport[] }
/** `GET /api/learners/{id}/skills/{skill}/evidence`: one attempt as it bears on one skill, newest first. */
export interface EvidenceRow {
  event_id: string
  at: string
  mode: Exclude<Mode, 'mixed'>
  version: number
  choices: number
  seed: number
  role: 'primary' | 'secondary' | 'confound'
  /** The first answer in words. */
  answer: string
  correct: boolean
  counted: boolean
  /** Why it did not count; empty when it did. */
  why: string
  struck: boolean
  tries: number
  outcome: 'right' | 'missed' | 'left'
}
/** `POST /api/attempts`: one round answered. The server rebuilds the round and judges `first_answer` itself. */
export interface AttemptIn {
  event_id: string
  learner_id: string
  session_id: string
  mode: Exclude<Mode, 'mixed'>
  version: number
  choices: number
  seed: number
  /** The kind the grown-up picked: mixed, or the kind itself. */
  asked: Mode
  presented_at: string
  answered_at: string
  first_answer: { option: string } | { placement: Record<string, string> }
  tries: number
  outcome: 'right' | 'missed' | 'left'
}

/** A random 32-hex-digit id for an event or a session. Not `crypto.randomUUID`: that needs a secure context, and the
 * app is often served over plain http on a home network; `getRandomValues` works anywhere. */
export function newId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')
}

// Where the app is served from: '' at the server's own root, '/prefix' behind a reverse proxy. Read
// from the page's base URL: the server gives every page a relative <base> back to its root, and
// assets are relative (vite.config.ts base './'), so one build works in both places.
export const BASE = typeof document === 'undefined' ? '' : new URL('.', document.baseURI).pathname.replace(/\/$/, '')
export const withBase = (u: string) => (u.startsWith('/') ? BASE + u : u)

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
  round: (mode: Mode, n: number) => ['round', mode, n],
  learners: ['learners'],
  profile: (id: string) => ['learners', id, 'profile'],
  evidence: (id: string, skill: string) => ['learners', id, 'evidence', skill],
} as const

export function roundUrl(mode: Mode) {
  return withBase(`${paths.round}?${new URLSearchParams({ mode })}`)
}

const send = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  settings: () => fetchJson<Settings>(withBase(paths.settings)),
  saveSettings: (s: Partial<Settings>) => fetchJson<Settings>(withBase(paths.settings), send('PUT', s)),
  modes: () => fetchJson<ModeInfo[]>(withBase(paths.modes)),
  round: (mode: Mode, signal?: AbortSignal) => fetchJson<Round>(roundUrl(mode), { signal }),
  content: () => fetchJson<ContentSummary>(withBase(paths.content)),
  learners: () => fetchJson<LearnerRow[]>(withBase(paths.learners)),
  addLearner: (nickname: string) => fetchJson<LearnerRow>(withBase(paths.learners), send('POST', { nickname })),
  deleteLearner: (id: string) => fetchJson<undefined>(withBase(`${paths.learners}/${id}`), { method: 'DELETE' }),
  profile: (id: string) => fetchJson<Profile>(withBase(`${paths.learners}/${id}/profile`)),
  evidence: (id: string, skill: string) => fetchJson<EvidenceRow[]>(withBase(`${paths.learners}/${id}/skills/${skill}/evidence`)),
  recordAttempt: (a: AttemptIn) => fetchJson<{ event_id: string; first_correct: boolean; duplicate: boolean }>(withBase(paths.attempts), send('POST', a)),
  strike: (eventId: string, reason: string) => fetchJson<undefined>(withBase(`${paths.attempts}/${eventId}/strike`), send('POST', { reason })),
}

/** The export download: a plain link, so the browser saves the file the server names. */
export const exportUrl = (id: string) => withBase(`${paths.learners}/${id}/export`)

// The server's own limits (src/flashtap/rounds.py), checked here too so the field says why before sending.
export const limits = { minChoices: 2, maxChoices: 8 } as const
