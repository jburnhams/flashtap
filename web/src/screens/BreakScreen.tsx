// The one question, the child's again: "What is the answer?", for a few rounds while something else waits. This is
// Play made to sit inside another app's frame (a video player that pauses for a break, configured there with this
// page's link): no nav, no choices on screen, everything from the URL, and when it is over it tells the page around it.
//
//   /break?learner=<id>&rounds=3            rounds chosen for that learner by the engine (?mode=next, the default)
//   /break?learner=<id>&mode=counting       rounds of one kind, recorded for the learner
//   /break?mode=counting                    rounds of one kind, recorded for nobody
//
// It ends after `rounds` rounds (default 3, counted on each Next, so the last "That's right" is seen), or sooner when the
// engine offers a break or ends the session: a sitting here is short, so the engine's own end is taken as the end.
// Then it posts `{ type: 'tubes:done' }` to its parent window (the message the embedding player waits for; Flashtap
// knows nothing else of it) and says it is over, which is what a person who opened the link on its own sees.
// The answers are kept and sent as on Play (the bare shell starts the queue), and a missing learner says so rather than
// playing unrecorded: a grown-up who set a learner's link meant those rounds to count.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { DataView, Done, EmptyState, format, useLoad, useSearchParam } from 'strata-react'
import { api, isPlayChoice, keys, newId, type LearnerRow, type PlayChoice, type Settings } from '../api'
import { RunningScore, ScoreRead, Scored } from '../score'
import { Game, NextAfter, Planned, RoundSkeleton, type Embedded } from './PlayScreen'

/** Rounds in a break when the link does not say. */
export const ROUNDS = 3
/** The message the page around this one is sent when the break is over. */
export const DONE = { type: 'tubes:done' }

/** The rounds the link asks for: a whole number from 1, else ROUNDS. */
export function roundsFrom(raw: string): number {
  const n = Number(raw)
  return Number.isInteger(n) && n >= 1 ? n : ROUNDS
}

/** Tells the page this one is framed in that the break is over; opened on its own, there is no one to tell. */
export function tellParent(win: Window = window) {
  if (win.parent !== win) win.parent.postMessage(DONE, '*')     // nothing private in it, and the parent may be on any origin
}

export function BreakScreen() {
  const settings = useLoad({ queryKey: keys.settings, queryFn: api.settings })
  const learners = useLoad({ queryKey: keys.learners, queryFn: api.learners })
  const both = settings.status !== 'ready' ? settings : learners.status !== 'ready' ? learners : { ...learners, data: { settings: settings.data, learners: learners.data } }
  return (
    <DataView state={both} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing to play">The server sent nothing.</EmptyState>}>
      {d => <Sitting settings={d.settings} learners={d.learners} />}
    </DataView>
  )
}

function Sitting({ settings, learners }: { settings: Settings; learners: LearnerRow[] }) {
  const [learner] = useSearchParam<string>('learner', { default: '' })
  const [mode] = useSearchParam<PlayChoice>('mode', { default: 'next', parse: isPlayChoice })
  const [rawRounds] = useSearchParam<string>('rounds', { default: '' })
  const rounds = roundsFrom(rawRounds)
  const [played, setPlayed] = useState(0)
  const [over, setOver] = useState(false)
  const [session] = useState(newId)
  const onPlayed = useCallback(() => setPlayed(n => n + 1), [])
  const onOver = useCallback(() => setOver(true), [])
  const embedded: Embedded = useMemo(() => ({ onPlayed, onOver }), [onPlayed, onOver])
  const finished = over || played >= rounds
  useEffect(() => { if (finished) tellParent() }, [finished])
  const who = learners.find(x => x.id === learner) ?? null
  if (finished) return <Done title={`Played ${format.count(played, 'round')}`} next="That’s the break over. Back to what you were watching." />
  if (learner && !who) return <EmptyState title="No such learner">This link names a learner Flashtap does not have, so there is nothing to record these rounds for. Check the link where the break is set up.</EmptyState>
  if (mode === 'next' && !who) return <EmptyState title="Choose who is playing">Rounds chosen for a learner come from what they have shown: add learner= to the link, or a kind of round with mode=.</EmptyState>
  // The same pace and running score as Play: a break is the same game, so the same score grows.
  return (
    <NextAfter.Provider value={settings.next_after}>
      <Scored learner={who}>
        <div className="grid gap-4">
          <RunningScore className="justify-self-end" />
          <ScoreRead skeleton={<RoundSkeleton />}>
            {mode === 'next' && who ? <Planned learner={who} embedded={embedded} /> : mode !== 'next' && <Game mode={mode} learner={who} session={who ? session : ''} rateEvery={settings.rate_every} embedded={embedded} />}
          </ScoreRead>
        </div>
      </Scored>
    </NextAfter.Provider>
  )
}
