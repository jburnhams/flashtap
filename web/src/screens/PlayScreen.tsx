// The one question, the child's: "Which one is it?" A round is a spoken prompt, a big picture, word
// or row of things to count, and two to eight tiles, exactly one of them right (the server checks
// every round: src/flashtap/rounds.py). Its finding is the prompt itself.
//
// A wrong tap says what was tapped and greys that tile out; the right one says so and offers Next.
// With a limit on tries (Settings), running out shows where the answer was. There is no score and no
// streak: the spec asks for no streak pressure and no punishment for mistakes (§11, §17).
// The kind of round lives in the URL (?mode=counting), so a grown-up can bookmark one. It is a
// select, not a row of toggles: six names do not fit across a phone.
import { useQueryClient } from '@tanstack/react-query'
import { Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button, ChoiceGrid, ChoiceGridSkeleton, DataView, EmptyState, Field, IconButton, NativeSelect, PageHeader, Skeleton, useLoad, type ChoiceState } from 'strata-react'
import { api, isMode, keys, MODES, type Mode, type Option, type Round } from '../api'
import { feedback, outcome, type Turn } from '../play'
import { say } from '../speech'

const modeLabels: Record<Mode, string> = {
  matching: 'Matching',
  colours: 'Colours',
  shapes: 'Shapes',
  letters: 'Letters',
  counting: 'Counting',
  mixed: 'Mixed',
}

export function PlayScreen() {
  const settings = useLoad({ queryKey: keys.settings, queryFn: api.settings })
  const [params, setParams] = useSearchParams()
  const asked = params.get('mode')
  return (
    <DataView state={settings} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="No settings">The server sent none.</EmptyState>}>
      {s => {
        const mode = isMode(asked) ? asked : s.mode
        return (
          <div className="grid gap-6">
            <Field label="Kind of round" className="max-w-xs">
              <NativeSelect value={mode} onChange={e => setParams(e.target.value === s.mode ? {} : { mode: e.target.value })}>
                {MODES.map(m => <option key={m} value={m}>{modeLabels[m]}</option>)}
              </NativeSelect>
            </Field>
            <Game key={mode} mode={mode} />
          </div>
        )
      }}
    </DataView>
  )
}

/** One round after another in `mode`: each Next asks the server for a new one. */
function Game({ mode }: { mode: Mode }) {
  const [n, setN] = useState(0)
  const round = useLoad({ queryKey: keys.round(mode, n), queryFn: ({ signal }) => api.round(mode, signal), staleTime: Infinity })
  return (
    <DataView state={round} isEmpty={r => r.options.length === 0} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing to play">The server sent a round with no pictures.</EmptyState>}>
      {r => <Board key={`${r.mode}-${r.seed}`} round={r} onNext={() => setN(x => x + 1)} />}
    </DataView>
  )
}

const marks = { wrong: 'Not this one', right: 'Right', answer: 'This one' }

export function Board({ round, onNext }: { round: Round; onNext: () => void }) {
  const queryClient = useQueryClient()
  const [turn, setTurn] = useState<Turn>({ tapped: [] })
  const state = outcome(round, turn)
  const done = state !== 'playing'

  useEffect(() => { say(round.prompt) }, [round.prompt])

  // ChoiceGrid draws the state and refuses a second tap on a closed tile; the answer key stays here.
  const tileState = (o: Option): ChoiceState =>
    turn.tapped.includes(o.id) ? (o.correct ? 'right' : 'wrong') : o.correct && done ? 'answer' : 'open'

  const tap = (id: string) => { // only an open tile reaches here: ChoiceGrid closes tapped tiles and, once answered, every tile
    const next = { tapped: [...turn.tapped, id] }
    setTurn(next)
    say(feedback(round, next))
  }

  const next = () => {
    // The round just played is not shown again: drop every round, this one too while it is still on
    // screen, so coming back to this kind of round (a new Game, counting from 0) asks the server afresh.
    queryClient.removeQueries({ queryKey: ['round'] })
    onNext()
  }

  return (
    <section aria-labelledby="prompt" className="grid gap-6">
      <PageHeader
        title={round.prompt}
        actions={<IconButton icon={Volume2} label="Say it again" onClick={() => say(round.prompt)} />}
        finding={done ? { text: state === 'right' ? 'That’s right.' : 'The answer is shown below.', action: <Button variant="default" onClick={next} autoFocus>Next</Button> } : undefined}
      />
      <p id="prompt" className="sr-only">{round.prompt}</p>
      <div className="type-picture break-words" aria-hidden>{round.show}</div>
      <ChoiceGrid
        label="Choices"
        items={round.options}
        itemKey={o => o.id}
        itemLabel={o => o.word}
        renderPicture={o => o.picture}
        state={tileState}
        marks={marks}
        onChoose={o => tap(o.id)}
      />
    </section>
  )
}

/** Mirrors a round: the heading, the big picture and four tiles. */
function RoundSkeleton() {
  return (
    <div className="grid gap-6" aria-hidden>
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-20 w-40" />
      <ChoiceGridSkeleton count={4} />
    </div>
  )
}
