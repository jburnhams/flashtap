// The one question, the child's: "What is the answer?" A round is a spoken prompt, perhaps a big
// picture, word or row of things, and an answer the server has checked is one and unmistakable
// (src/flashtap/mechanics.py). Its finding is the prompt itself.
//
// Two ways to answer, by the round's mechanic (src/flashtap/mechanics.py):
// - one tap (select one, fill the missing number, quick look, listen): strata-react's `ChoiceGrid`.
//   A wrong tap says what was tapped and greys that tile out; the right one says so and offers
//   Next. A quick look hides its picture after the round's `exposure_ms`, so the learner says how
//   many they saw, not how many they counted. Listen says a word the screen never prints.
// - an arrangement (give a number, put in order, match, sort): strata-react's `PlaceBoard`, two
//   taps to move a picture, then Check. A check marks each place right or "Not yet"; moving a
//   piece in or out of a place clears its mark.
//
// With a limit on tries (Settings), running out shows the answer: taps for a one-tap round, checks
// for an arrangement. There is no score and no streak: the spec asks for no streak pressure and no
// punishment for mistakes (§11, §17). The kind of round lives in the URL (?mode=counting), so a
// grown-up can bookmark one. It is a select, not a row of toggles: thirteen names do not fit.
import { useQueryClient } from '@tanstack/react-query'
import { Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button, ChoiceGrid, ChoiceGridSkeleton, DataView, EmptyState, Field, IconButton, NativeSelect, PageHeader, PlaceBoard, Skeleton, useLoad, type ChoiceState, type PlaceState } from 'strata-react'
import { api, isMode, keys, MODES, PLACE_MECHANICS, type Mode, type Option, type Round } from '../api'
import { arrangedRight, feedback, outcome, placeFeedback, placeOutcome, placeRight, solution, type Placement, type Turn } from '../play'
import { say } from '../speech'

export const modeLabels: Record<Mode, string> = {
  matching: 'Matching',
  colours: 'Colours',
  shapes: 'Shapes',
  letters: 'Letters',
  counting: 'Counting',
  missing: 'Missing number',
  quick_look: 'Quick look',
  listen: 'Listen',
  give: 'Give a number',
  order: 'Order',
  capitals: 'Capitals',
  sort_sounds: 'Sort by sound',
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
    <DataView state={round} isEmpty={r => r.options.length === 0 && r.pieces.length === 0} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing to play">The server sent a round with no pictures.</EmptyState>}>
      {r => <Board key={`${r.mode}-${r.seed}`} round={r} onNext={() => setN(x => x + 1)} />}
    </DataView>
  )
}

/** A round, answered by a tap or by an arrangement as its mechanic says. */
export function Board({ round, onNext }: { round: Round; onNext: () => void }) {
  const queryClient = useQueryClient()
  useEffect(() => { say(round.say) }, [round.say])
  const next = () => {
    // The round just played is not shown again: drop every round, this one too while it is still on
    // screen, so coming back to this kind of round (a new Game, counting from 0) asks the server afresh.
    queryClient.removeQueries({ queryKey: ['round'] })
    onNext()
  }
  return PLACE_MECHANICS.includes(round.mechanic) ? <Arrange round={round} onNext={next} /> : <Choose round={round} onNext={next} />
}

/** The heading every round shares: the prompt, Say it again, and once it is over what happened and Next. */
function RoundHeader({ round, over, onNext }: { round: Round; over: 'right' | 'missed' | null; onNext: () => void }) {
  return (
    <>
      <PageHeader
        title={round.prompt}
        actions={<IconButton icon={Volume2} label="Say it again" onClick={() => say(round.say)} />}
        finding={over ? { text: over === 'right' ? 'That’s right.' : 'The answer is shown below.', action: <Button variant="default" onClick={onNext} autoFocus>Next</Button> } : undefined}
      />
      <p id="prompt" className="sr-only">{round.prompt}</p>
    </>
  )
}

const marks = { wrong: 'Not this one', right: 'Right', answer: 'This one' }

function Choose({ round, onNext }: { round: Round; onNext: () => void }) {
  const [turn, setTurn] = useState<Turn>({ tapped: [] })
  const state = outcome(round, turn)
  const done = state !== 'playing'

  // ChoiceGrid draws the state and refuses a second tap on a closed tile; the answer key stays here.
  const tileState = (o: Option): ChoiceState =>
    turn.tapped.includes(o.id) ? (o.correct ? 'right' : 'wrong') : o.correct && done ? 'answer' : 'open'

  const tap = (id: string) => { // only an open tile reaches here: ChoiceGrid closes tapped tiles and, once answered, every tile
    const next = { tapped: [...turn.tapped, id] }
    setTurn(next)
    say(feedback(round, next))
  }

  return (
    <section aria-labelledby="prompt" className="grid gap-6">
      <RoundHeader round={round} over={done ? state : null} onNext={onNext} />
      {round.show && <Show round={round} />}
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

/** The big picture, word or row above the answer. A quick look hides it after `exposure_ms`, keeping its room so the tiles do not jump. */
function Show({ round }: { round: Round }) {
  const [hidden, setHidden] = useState(false)
  useEffect(() => {
    if (round.exposure_ms === null) return
    const t = setTimeout(() => setHidden(true), round.exposure_ms)
    return () => clearTimeout(t)
  }, [round.exposure_ms])
  if (!hidden) return <div className="type-picture break-words" aria-hidden>{round.show}</div>
  return (
    <div className="type-picture">
      <span aria-hidden>{'\u00a0'}</span>
      <span role="status" className="sr-only">The pictures have gone.</span>
    </div>
  )
}

const placeMarks = { held: 'Picked up', right: 'Right', wrong: 'Not yet' }

function Arrange({ round, onNext }: { round: Round; onNext: () => void }) {
  const [placement, setPlacement] = useState<Placement>({})
  const [checks, setChecks] = useState(0)
  // The arrangement at the last check: a place keeps its mark until what is in it changes.
  const [checked, setChecked] = useState<Placement | null>(null)
  const right = checked !== null && arrangedRight(round, checked)
  const state = placeOutcome(round, checks, right)
  const done = state !== 'playing'
  const shown = state === 'missed' ? solution(round) : placement

  const sameSince = (place: string) => {
    if (checked === null) return false
    const keys = new Set([...Object.keys(placement), ...Object.keys(checked)])
    return [...keys].every(k => (placement[k] === place) === (checked[k] === place))
  }
  const placeState = (p: Round['places'][number]): PlaceState =>
    state === 'missed' || !sameSince(p.id) ? 'open' : placeRight(p, placement) ? 'right' : 'wrong'

  const move = (piece: string, place: string | null) => setPlacement(m => ({ ...m, [piece]: place ?? undefined }))

  const check = () => {
    const n = checks + 1
    setChecks(n)
    setChecked(placement)
    say(placeFeedback(round, placement, n))
  }

  const placed = Object.values(placement).some(Boolean)
  return (
    <section aria-labelledby="prompt" className="grid gap-6">
      <RoundHeader round={round} over={done ? state : null} onNext={onNext} />
      <PlaceBoard
        label="Pictures and places"
        pieces={round.pieces}
        pieceKey={p => p.id}
        pieceLabel={p => p.word}
        renderPiece={p => p.picture}
        places={round.places}
        placeKey={p => p.id}
        placeLabel={p => p.word}
        renderPlace={round.places.some(p => p.picture) ? p => p.picture : undefined}
        placement={shown}
        onMove={move}
        pileLabel="Pictures to place"
        placeState={placeState}
        marks={placeMarks}
        locked={done}
      />
      {!done && (
        <Button variant="default" className="justify-self-start" onClick={check} disabled={!placed}>
          Check
        </Button>
      )}
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
