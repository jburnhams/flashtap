// Rounds kept on the device for when the server cannot be reached, so a learner whose connection drops keeps playing
// (spec §14: "client should render deterministic validated item payloads and queue events offline"). The server still
// owns the truth: each kept round is one it made and checked (`GET /api/rounds`), carrying its (mode, version,
// choices, seed, content), and an answer to it is judged by the server rebuilding it from those when the answer lands
// (src/flashtap/learners/store.py). Nothing here judges or makes a round.
//
// - Kept per kind asked for (`flashtap:reserve:<mode>`, Mixed apart), RESERVE rounds each, topped up in one request
//   whenever a fresh round arrives and fewer than half are left, so it costs one request in every few rounds.
// - A kept round is played once and then gone: a round shown again would let a second try be recorded as a first
//   answer.
// - A fresh round whose template or pack versions differ from a kept round of the same kind means the server moved on
//   (a deploy, a pack raised): those kept rounds would be refused when answered, so they are dropped and refilled.
// - Storage that throws (a private window) keeps nothing: offline play then has no rounds, and says so.
import { api, type Mode, type Round } from './api'

export const RESERVE = 8
const key = (mode: Mode) => `flashtap:reserve:${mode}`

function read(mode: Mode): Round[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(key(mode)) ?? '[]') as unknown
    return Array.isArray(raw) ? (raw as Round[]) : []
  } catch {
    return []
  }
}

function write(mode: Mode, kept: Round[]) {
  try {
    window.localStorage.setItem(key(mode), JSON.stringify(kept))
  } catch {
    // no storage: nothing is kept
  }
}

const sameMake = (a: Round, b: Round) => a.version === b.version && JSON.stringify(a.content) === JSON.stringify(b.content)

/** How many rounds of `mode` are kept. */
export function kept(mode: Mode): number {
  return read(mode).length
}

/** Takes the oldest kept round of `mode` (it will not be given again), or null when none is kept. */
export function take(mode: Mode): Round | null {
  const [first, ...rest] = read(mode)
  if (!first) return null
  write(mode, rest)
  return first
}

const filling = new Map<Mode, Promise<void>>()

/** After a fresh round of `mode` from the server: drop kept rounds it shows are out of date, and top up when low. */
export function refresh(mode: Mode, fresh: Round): Promise<void> {
  const now = read(mode).filter(r => r.mode !== fresh.mode || sameMake(r, fresh))
  write(mode, now)
  if (now.length >= RESERVE / 2 || filling.has(mode)) return filling.get(mode) ?? Promise.resolve()
  const run = api
    .rounds(mode, RESERVE - now.length)
    .then(more => write(mode, [...read(mode), ...more].slice(0, RESERVE)))
    .catch(() => {}) // the reserve is a convenience: a failed top-up is tried again after the next round
    .finally(() => filling.delete(mode))
  filling.set(mode, run)
  return run
}
