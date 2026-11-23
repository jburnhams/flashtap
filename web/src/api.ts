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
} as const

/** The query keys the screens share, so a write can invalidate every read it changes. */
export const keys = {
  settings: ['settings'],
  modes: ['modes'],
  content: ['content'],
  round: (mode: Mode, n: number) => ['round', mode, n],
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
}

// The server's own limits (src/flashtap/rounds.py), checked here too so the field says why before sending.
export const limits = { minChoices: 2, maxChoices: 8 } as const
