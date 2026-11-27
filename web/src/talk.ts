// Talk (src/flashtap/talk.py): the lines around a round, varied and with the learner's name, so a right answer is not
// "Yes!" every time and a new kind of round is said to be coming. The server writes the pools ahead of time (a
// language model, with `{name}` filled in on the server) and the voice build makes their clips, so every line here
// is normally said in the recorded voice; one with no clip yet is said by the browser, as any line is.
//
// Each pool is gone round in order from a random place, so a line comes back only after every other one in its pool
// has been said. Where each pool stands is kept per learner for as long as the page is open (a module-level map, not
// state: a round's Board remounts each round, and the rotation must carry on across them, and across visits). A visit
// (each mount of a Game or a planned session) says hello again and introduces its first kind. Without a learner, or
// until the pools arrive, or if they fail, the fixed lines are said, which is what Play said before (0.16.0): this is
// never drawn, so it has no DataView, like the clips list (voice.ts).
import { useQueryClient } from '@tanstack/react-query'
import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLoad } from 'strata-react'
import { api, keys, type TalkOut } from './api'

/** What Play says at each moment (`MOMENTS` in src/flashtap/talk.py; `intro.<kind>` for each kind of round). */
export type Talk = {
  /** The opening of a right answer's sentence, in place of its "Yes!". */
  right: () => string
  /** After a miss with a go left, in place of "Try again.". */
  retry: () => string
  /** Before the answer is shown after the last go; empty with no pools. */
  missed: () => string
  /** Said before a round of `mode`: the visit's hello before its first round, then a word whenever the kind changes. */
  opening: (mode: string) => string
  /** Asks which of two kinds to play next (their names follow it). */
  pick: () => string
  /** Offers a break. */
  break: () => string
}

/** The lines Play said before there were pools: what it says with none. */
export const FIXED = { right: 'Yes!', retry: 'Try again.', pick: 'Which one next?', break: 'Time for a break?' } as const

type Where = { turns: Map<string, number>; starts: Map<string, number>; lastMode: string | null; greeted: boolean }

const where = new Map<string, Where>()

/** A new visit for `learner` (a Game or a planned session mounted): hello again, and the next kind is introduced.
 * Where each pool stands carries on, so the lines just heard are not the first ones again. */
export function startVisit(learner: string) {
  const w = where.get(learner)
  if (w) Object.assign(w, { greeted: false, lastMode: null })
}

/** Forgets where every pool stands (tests start each case afresh). */
export function resetTalk() {
  where.clear()
}

/** The `n`th line of a pool gone round from `start`. */
export function rotate(pool: readonly string[], start: number, n: number): string {
  return pool[(start + n) % pool.length]
}

/** A Talk over `out`'s pools for `learner`, carrying on where this page left it. `random` picks each pool's start. */
export function talkOf(learner: string, out: TalkOut | undefined, random: () => number = Math.random): Talk {
  const w = where.get(learner) ?? { turns: new Map<string, number>(), starts: new Map<string, number>(), lastMode: null, greeted: false }
  where.set(learner, w)
  const starts = w.starts
  const line = (key: string, fallback: string) => {
    const pool = out?.lines[key]
    if (!pool?.length) return fallback
    const n = w.turns.get(key) ?? 0
    w.turns.set(key, n + 1)
    const start = starts.get(key) ?? Math.floor(random() * pool.length)
    starts.set(key, start)
    return rotate(pool, start, n)
  }
  return {
    right: () => line('right', FIXED.right),
    retry: () => line('retry', FIXED.retry),
    missed: () => line('missed', ''),
    opening: mode => {
      if (!out) return ''
      const changed = w.lastMode !== mode
      w.lastMode = mode
      const hello = w.greeted ? '' : line('start', '')
      w.greeted = true
      return [hello, changed ? line(`intro.${mode}`, '') : ''].filter(Boolean).join(' ')
    },
    pick: () => line('pick', FIXED.pick),
    break: () => line('break', FIXED.break),
  }
}

const plain: Talk = talkOf('', undefined) // no pools: the fixed lines, whoever asks

const TalkContext = createContext<Talk>(plain)

/** Reads `learner`'s pools once a visit and gives the rounds under it `useTalk()`. With no learner, the fixed lines. */
export function TalkProvider({ learner, children }: { learner: string | null; children: ReactNode }) {
  if (learner === null) return children
  return createElement(Pools, { learner, children })
}

function Pools({ learner, children }: { learner: string; children: ReactNode }) {
  useState(() => startVisit(learner)) // once per mount: each mount is a visit
  // The clips list is kept for the session (voice.ts), but a learner added since it was read has had their name lines
  // made by a later build: each visit reads it again, so their clips are used without a reload.
  const queryClient = useQueryClient()
  useEffect(() => { void queryClient.invalidateQueries({ queryKey: keys.voice }) }, [queryClient])
  const load = useLoad({ queryKey: keys.talk(learner), queryFn: () => api.talk(learner), staleTime: Infinity })
  const data = load.status === 'ready' ? load.data : undefined
  const talk = useMemo(() => talkOf(learner, data), [learner, data])
  return createElement(TalkContext.Provider, { value: talk }, children)
}

/** What to say around a round: `useTalk().right()`. Outside a TalkProvider, the fixed lines. */
export function useTalk(): Talk {
  return useContext(TalkContext)
}
