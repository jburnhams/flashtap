// The FastAPI server's endpoints (src/flashtap/server/app.py) and their shapes. Reads go through
// strata-react's useLoad with fetchJson, which throws HttpError on a non-2xx answer; the screens
// never call fetch themselves. Every URL is built here, through withBase, so the app works at the
// server's root and behind a reverse proxy at /<prefix>/.
import { fetchJson } from 'strata-react'

export const MODES = ['matching', 'colours', 'shapes', 'letters', 'counting', 'mixed'] as const
export type Mode = (typeof MODES)[number]
export const isMode = (v: string | null): v is Mode => MODES.includes(v as Mode)

/** `GET /api/settings`. strata-python keeps every value as a canonical string. */
export interface Settings { mode: Mode; choices: string; tries: string }
export interface ModeInfo { mode: Mode; name: string; description: string }
/** One tile. `word` names it for a screen reader and is never printed: the tile would give the answer away. */
export interface Option { id: string; picture: string; word: string; correct: boolean; feedback: string }
/** `GET /api/round`: a checked round with exactly one right option, rebuilt exactly from (mode, choices, seed). */
export interface Round {
  mode: Exclude<Mode, 'mixed'>
  seed: number
  prompt: string
  show: string
  options: Option[]
  answer: string
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
