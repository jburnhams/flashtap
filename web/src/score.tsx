// The running score (asked for by the owner, 2026-11-27): for a learner who is recorded, every round they have ever
// answered, as a green count of first answers that were right and a red count of first answers that were wrong, on
// screen the whole time they play. First answers, as the server judges them (`first_correct`), because with no limit
// on tries every round ends found, so "found in the end" would never be red. All time, not per sitting: the number a
// child sees grow. Nobody playing is not recorded, so has no score.
//
// The total is the server's (GET /api/learners/{id}/score, the attempt log counted, struck rounds left out), read once
// when the learner sits down, plus each answer this visit keeps: those are counted the moment they are kept, whether
// the server has them yet or they wait on the device (api.ts `answers`), so an answer given offline counts at once.
// One the server refuses, at once or later, is taken off again. Reading the total again mid-visit would count this visit's answers twice
// (they reach the server one by one), so it is read once per visit (`keys.score`, outside ['learners'], which the
// shell refreshes on every send). An answer an earlier visit left waiting on the device joins the total once it lands
// and Play is opened again.
//
// The counts are big pills in the status roles (success, danger: pale tint, dark ink, each checked at 6:1 in
// styles/theme.css) with a tick and a cross, so the colour is never the only sign; each is read as "12 right".
import { Check, X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { cn, DataView, EmptyState, format, Skeleton, useLoad, useOutbox, type Load } from 'strata-react'
import { answers, api, keys, newId, type LearnerRow, type Score } from './api'

/** Counts one answer kept this visit, by its event id: right or wrong first time. */
export type Tally = (eventId: string, right: boolean) => void

type Running = { scored: boolean; tally: Tally; read: Load<Score>; added: Score }

const RunningContext = createContext<Running | null>(null)

/** What a kept answer is counted with. Every screen that plays is inside `Scored` (Play, Break), which gives one even
 * for nobody, whose answers are never kept, so never counted. */
export function useTally(): Tally {
  return (useContext(RunningContext) as Running).tally
}

type Sitting = { id: string; visit: string; counted: Record<string, boolean> }
const sitDown = (id: string): Sitting => ({ id, visit: newId(), counted: {} })

/** Keeps `learner`'s running score for the screen inside, read afresh whenever who is playing changes; for nobody,
 * none. Always the same element, so a change of learner does not remount the screen inside (its selects, its round). */
export function Scored({ learner, children }: { learner: LearnerRow | null; children: ReactNode }) {
  const id = learner?.id ?? ''
  // A sitting per learner: a fresh read of the total (a new visit key) and nothing added yet. Reset in render when the
  // learner changes, as React's docs do for state that follows a prop, so no frame shows one learner's score for another.
  const [sat, setSat] = useState(() => sitDown(id))
  if (sat.id !== id) setSat(sitDown(id))
  const read = useLoad({ queryKey: keys.score(id, sat.visit), queryFn: () => api.score(id), staleTime: Infinity, enabled: id !== '' })
  const visit = sat.visit
  // Added to the sitting it was answered in, so an answer given just before the learner changed is not another's.
  const tally = useCallback<Tally>((eventId, right) => setSat(x => (x.visit !== visit ? x : { ...x, counted: { ...x.counted, [eventId]: right } })), [visit])
  // An answer the server refuses (at once, or on a later try) is in the outbox's refused list: it never reaches the
  // total, so it comes off here, and stays off once the grown-up dismisses it from the list.
  const { refused } = useOutbox(answers)
  const gone = refused.filter(r => r.id in sat.counted).map(r => r.id)
  useEffect(() => {
    if (gone.length) setSat(x => ({ ...x, counted: Object.fromEntries(Object.entries(x.counted).filter(([e]) => !gone.includes(e))) }))
  }, [gone.join()]) // keyed by the ids, not by a fresh array each render
  const added = useMemo(() => {
    const kept = Object.entries(sat.counted).filter(([e]) => !gone.includes(e))
    return { right: kept.filter(([, r]) => r).length, wrong: kept.filter(([, r]) => !r).length }
  }, [sat.counted, gone.join()])
  const running = useMemo(() => ({ scored: id !== '', tally, read, added }), [id, tally, read, added])
  return <RunningContext.Provider value={running}>{children}</RunningContext.Provider>
}

/** The running score of the learner `Scored` keeps; nothing when nobody is scored. */
export function RunningScore({ className }: { className?: string }) {
  const running = useContext(RunningContext) as Running
  if (!running.scored) return null
  const { read, added } = running
  return (
    <DataView
      state={read}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-14 w-48" />}
      empty={<EmptyState title="No score">The server sent none.</EmptyState>}
      // The total could not be read: still count this visit, and say so for the grown-up (a child sees the pills).
      error={() => (
        <div className="grid gap-1">
          <ScorePills score={added} className={className} />
          <p className="type-caption text-muted-foreground">The total score could not be read, so this counts this visit only.</p>
        </div>
      )}
    >
      {s => <ScorePills score={{ right: s.right + added.right, wrong: s.wrong + added.wrong }} className={className} />}
    </DataView>
  )
}

/** Two big counts: green with a tick for right, red with a cross for wrong. */
export function ScorePills({ score, className }: { score: Score; className?: string }) {
  return (
    <ul aria-label="Score" className={cn('flex gap-3', className)}>
      <li className="inline-flex items-center gap-2 rounded-pill bg-success-subtle px-4 py-1 text-success type-figure tabular-nums">
        <Check aria-hidden className="size-8" strokeWidth={3} />
        {format.integer(score.right)}
        <span className="sr-only"> right</span>
      </li>
      <li className="inline-flex items-center gap-2 rounded-pill bg-danger-subtle px-4 py-1 text-danger type-figure tabular-nums">
        <X aria-hidden className="size-8" strokeWidth={3} />
        {format.integer(score.wrong)}
        <span className="sr-only"> wrong</span>
      </li>
    </ul>
  )
}
