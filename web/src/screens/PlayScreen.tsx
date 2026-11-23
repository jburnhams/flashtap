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
//
// Who is playing is the second select, also in the URL (?learner=<id>), so "Play as Fox" on the
// Learners screen is a link. With a learner chosen, each round is sent to the server once it ends
// (or once Next or a change of kind leaves it half done) with its first answer, how many tries it
// took and how it ended; the server rebuilds the round and judges the answer itself. With nobody
// chosen nothing is sent. A round the server did not take says so in one quiet line, never to the
// child in words.
//
// "Chosen for them" (?mode=next) hands the choice to the adaptive engine (src/flashtap/engine/): Play starts a
// session for the learner and asks for each decision by number, so a reload or a retry gets the same round back. A
// decision is a round (with a line for the grown-up saying why it was chosen), an offered break (keep playing or
// stop), or the end of the session, which the server calls once its rounds or minutes are up. It needs a learner:
// what comes next is chosen from what they have shown.
//
// Engagement, light (spec §11, §12; plan PR 6). Every few rounds (Settings, Sessions) the engine offers a choice of
// two instead of a round: two big picture tiles, their names said aloud, and the learner taps one; the pick is
// theirs and is recorded, then that round is played. And every few rounds the three faces ask how it was, under the
// finished round: optional (Next works without a face), never counted as an answer, never about right or wrong. A
// tile is a picture tile like any other (strata-react's ChoiceGrid), left open: neither a pick nor a face is right
// or wrong. With the grown-up choosing the kind, the faces still come every few rounds for a learner who is recorded.
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, ButtonLink, ChoiceGrid, ChoiceGridSkeleton, DataView, Done, EmptyState, format, Field, NativeSelect, PageHeader, PlaceBoard, SayAgain, Skeleton, speak, useLoad, useSearchParam, type ChoiceState, type Load, type PlaceState } from 'strata-react'
import { api, isPlayChoice, keys, MODES, newId, PLACE_MECHANICS, type AttemptIn, type Face, type LearnerRow, type Mode, type Next, type OfferOut, type Option, type PlayChoice, type Round, type SessionInfo, type Settings } from '../api'
import { arrangedRight, feedback, outcome, placeFeedback, placeOutcome, placeRight, solution, type Placement, type Turn } from '../play'
// Every prompt and answer is said aloud in UK English (the content's dialect): a learner who cannot read yet still
// needs the prompt. Browser voices cannot say an isolated sound such as /m/; recorded clips replace this for phonics
// (docs/implementation-plan.md, decision 4).
const LANG = 'en-GB'
const say = (text: string) => speak(text, { lang: LANG })

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
  const learners = useLoad({ queryKey: keys.learners, queryFn: api.learners })
  // One session per learner while this page is open: the server groups the rounds by it.
  const sessions = useRef(new Map<string, string>())
  const session = useCallback((id: string) => {
    let made = sessions.current.get(id)
    if (!made) sessions.current.set(id, (made = newId()))
    return made
  }, [])
  return (
    <DataView state={settings} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="No settings">The server sent none.</EmptyState>}>
      {s => <Choices settings={s} learners={learners} session={session} />}
    </DataView>
  )
}

/** The kind of round and who plays, both in the URL so a link or a reload keeps them; the saved kind is the default. */
function Choices({ settings, learners, session }: { settings: Settings; learners: Load<LearnerRow[]>; session: (id: string) => string }) {
  // The selects write the URL themselves (`param`); these read the same params back for the game.
  const [mode] = useSearchParam<PlayChoice>('mode', { default: settings.mode, parse: isPlayChoice })
  const [learner] = useSearchParam<string>('learner', { default: '' })
  const known = learners.status === 'ready' ? learners.data : []
  const playing = known.find(x => x.id === learner) ?? null
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap gap-4">
        <Field label="Kind of round" className="w-full max-w-xs">
          <NativeSelect param="mode" paramDefault={settings.mode}>
            <option value="next">Chosen for them</option>
            {MODES.map(m => <option key={m} value={m}>{modeLabels[m]}</option>)}
          </NativeSelect>
        </Field>
        <WhoPlays learners={known} recording={playing !== null} failed={learners.status === 'error'} />
      </div>
      {mode !== 'next' ? (
        <Game key={`${mode}-${playing?.id ?? ''}`} mode={mode} learner={playing} session={playing ? session(playing.id) : ''} rateEvery={settings.rate_every} />
      ) : playing ? (
        <Planned key={playing.id} learner={playing} />
      ) : (
        <EmptyState title="Choose who is playing">Rounds chosen for a learner come from what they have shown, so pick who is playing first, or pick a kind of round.</EmptyState>
      )}
    </div>
  )
}

/** Who the rounds are recorded for; Nobody records nothing. A failed list still lets the child play, unrecorded. */
function WhoPlays({ learners, recording, failed }: { learners: LearnerRow[]; recording: boolean; failed: boolean }) {
  return (
    <Field label="Who is playing" className="w-full max-w-xs" hint={failed ? 'The learners could not be loaded, so these rounds are not recorded.' : recording ? undefined : 'Nobody: rounds are not recorded.'}>
      <NativeSelect param="learner" paramDefault="">
        <option value="">Nobody</option>
        {learners.map(x => <option key={x.id} value={x.id}>{x.nickname}</option>)}
      </NativeSelect>
    </Field>
  )
}

/** What a round reports once it ends: the rest of an attempt comes from the round and who is playing. */
export type Answered = Pick<AttemptIn, 'first_answer' | 'tries' | 'outcome' | 'presented_at' | 'answered_at'>

/** One round after another in `mode`: each Next asks the server for a new one. Every `rateEvery`th round a recorded
 * learner is asked how it was. */
function Game({ mode, learner, session, rateEvery }: { mode: Mode; learner: LearnerRow | null; session: string; rateEvery: number }) {
  const [n, setN] = useState(0)
  const [unsaved, setUnsaved] = useState(false)
  const sent = useRef<Promise<string | null>>(Promise.resolve(null))
  const queryClient = useQueryClient()
  // A fresh round for every visit (a change of kind or of who is playing remounts this Game): a round left
  // half done and shown again with its answers forgotten would let a retry be recorded as a new first answer.
  const [visit] = useState(newId)
  const round = useLoad({ queryKey: keys.round(mode, visit, n), queryFn: ({ signal }) => api.round(mode, signal), staleTime: Infinity })
  const record = useCallback(
    (who: LearnerRow, r: Round, a: Answered) => {
      const id = newId()
      sent.current = api.recordAttempt({ event_id: id, learner_id: who.id, session_id: session, mode: r.mode, version: r.version, content: r.content, choices: r.choices, seed: r.seed, asked: mode, ...a }).then(
        () => {
          setUnsaved(false)
          void queryClient.invalidateQueries({ queryKey: ['learners'] })
          return id
        },
        () => {
          setUnsaved(true)
          return null
        },
      )
    },
    [session, mode, queryClient],
  )
  const asking = learner !== null && rateEvery > 0 && (n + 1) % rateEvery === 0
  return (
    <>
      <DataView state={round} isEmpty={r => r.options.length === 0 && r.pieces.length === 0} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing to play">The server sent a round with no pictures.</EmptyState>}>
        {r => <Board key={`${r.mode}-${r.seed}`} round={r} onNext={() => setN(x => x + 1)} onAnswered={learner ? a => record(learner, r, a) : undefined} onRated={asking ? v => rateAfter(sent.current, v) : undefined} />}
      </DataView>
      {unsaved && <p role="status" className="type-caption text-muted-foreground">The last round was not saved for {learner?.nickname}: the server did not take it.</p>}
    </>
  )
}

/** Sends a face once the round it rates has been saved; a round the server did not take is not rated. */
function rateAfter(saved: Promise<string | null>, value: Face): Promise<unknown> {
  return saved.then(id => (id ? api.rate(id, value) : Promise.reject(new Error('The round was not saved, so it cannot be rated.'))))
}

/** A session the engine plans for `learner`: started once per visit, then one decision after another. */
function Planned({ learner }: { learner: LearnerRow }) {
  const [visit] = useState(newId)
  const session = useLoad({ queryKey: keys.session(learner.id, visit), queryFn: () => api.startSession(learner.id), staleTime: Infinity })
  return (
    <DataView state={session} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="No session">The server started none.</EmptyState>}>
      {s => <Decisions session={s} learner={learner} />}
    </DataView>
  )
}

/** Decision `seq` of the session, asked for by number so a retry returns the same one; each Next asks for the one after. */
function Decisions({ session, learner }: { session: SessionInfo; learner: LearnerRow }) {
  const [seq, setSeq] = useState(0)
  const [unsaved, setUnsaved] = useState(false)
  const queryClient = useQueryClient()
  const decision = useLoad({ queryKey: keys.next(session.id, seq), queryFn: () => api.next(session.id, seq), staleTime: Infinity })
  // The answer being saved, if any: the next decision is asked for only once it has landed (or failed), so the
  // engine chooses knowing it; asked too soon, a third miss would not yet show and no break would be offered.
  const saving = useRef<Promise<string | null>>(Promise.resolve(null))
  // A face is sent after its round is saved; the next decision waits for both, so the engine sees the face too.
  const rating = useRef<Promise<unknown>>(Promise.resolve())
  const onward = () => { void Promise.allSettled([saving.current, rating.current]).then(() => setSeq(n => n + 1)) }
  const record = (d: Next, r: Round, a: Answered) => {
    const id = newId()
    saving.current = api.recordAttempt({ event_id: id, learner_id: learner.id, session_id: session.id, decision_id: d.id, mode: r.mode, version: r.version, content: r.content, choices: r.choices, seed: r.seed, asked: 'next', ...a }).then(
      () => {
        setUnsaved(false)
        void queryClient.invalidateQueries({ queryKey: ['learners'] })
        return id
      },
      () => {
        setUnsaved(true)
        return null
      },
    )
  }
  const rate = (v: Face) => (rating.current = rateAfter(saving.current, v))
  const picked = (n: Next) => queryClient.setQueryData(keys.next(session.id, n.seq), n)
  return (
    <>
      <DataView state={decision} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing chosen">The server chose nothing.</EmptyState>}>
        {d =>
          (d.action === 'round' || d.action === 'choice') && d.round ? (
            <div className="grid gap-4">
              <Board key={d.id} round={d.round} onNext={onward} onAnswered={a => record(d, d.round as Round, a)} onRated={d.rate ? rate : undefined} />
              <p className="type-caption text-muted-foreground">Why this round: {d.why}</p>
            </div>
          ) : d.action === 'choice' && d.offers ? (
            <PickOne decision={d} offers={d.offers} onPicked={picked} />
          ) : d.action === 'break' ? (
            <BreakOffer decision={d} onContinue={onward} />
          ) : (
            <SessionOver learner={learner} decision={d} />
          )
        }
      </DataView>
      {unsaved && <p role="status" className="type-caption text-muted-foreground">The last round was not saved for {learner.nickname}: the server did not take it.</p>}
    </>
  )
}

/** A choice of two: the learner taps the one they want to play next; the server keeps the pick, then it is played. */
function PickOne({ decision, offers, onPicked }: { decision: Next; offers: OfferOut[]; onPicked: (n: Next) => void }) {
  const [failed, setFailed] = useState(false)
  const question = `Which one next? ${offers.map(o => o.title).join(' or ')}?`
  useEffect(() => { say(question) }, [question])
  const choose = (o: OfferOut) => {
    setFailed(false)
    api.pick(decision.session_id, decision.seq, offers.indexOf(o)).then(onPicked, () => setFailed(true))
  }
  return (
    <section aria-labelledby="pick" className="grid gap-6">
      <PageHeader title="Which one next?" actions={<SayAgain text={question} lang={LANG} verb="Say again" />} />
      <p id="pick" className="sr-only">{question}</p>
      <ChoiceGrid label="Which one next?" items={offers} itemKey={o => o.mode} itemLabel={o => o.title} renderPicture={o => o.picture} state={() => 'open'} marks={pickMarks} onChoose={choose} size="lg" />
      {failed && <p role="status" className="type-caption text-muted-foreground">That pick did not reach the server: tap one again.</p>}
      <p className="type-caption text-muted-foreground">Why two: {decision.why} {offers.map(o => `${o.title}: ${o.why}`).join(' ')}</p>
    </section>
  )
}

const pickMarks = { wrong: 'Not this one', right: 'Picked', answer: 'Picked' }

const FACES: { value: Face; picture: string; word: string }[] = [
  { value: 1, picture: '\u{1F600}', word: 'Liked it' },
  { value: 0, picture: '\u{1F610}', word: 'It was all right' },
  { value: -1, picture: '\u{1F641}', word: 'Did not like it' },
]

/** The three faces after a round. Optional: Next stays the filled button, and a face can be left untapped. */
function HowWasIt({ onRated }: { onRated: (v: Face) => Promise<unknown> }) {
  const [said, setSaid] = useState<'no' | 'sent' | 'failed'>('no')
  const rate = (v: Face) => {
    setSaid('sent')
    onRated(v).catch(() => setSaid('failed'))
  }
  if (said === 'sent') return <p role="status" className="type-body text-muted-foreground">Thank you.</p>
  return (
    <section aria-labelledby="how" className="grid gap-3">
      <div className="flex items-center gap-2">
        <h2 id="how" className="type-heading">How was that one?</h2>
        <SayAgain text="How was that one?" lang={LANG} verb="Say" />
      </div>
      <ChoiceGrid label="How was that one?" items={FACES} itemKey={f => String(f.value)} itemLabel={f => f.word} renderPicture={f => f.picture} state={() => 'open'} marks={pickMarks} onChoose={f => rate(f.value)} />
      {said === 'failed' && <p role="status" className="type-caption text-muted-foreground">That face was not saved.</p>}
    </section>
  )
}

/** An offered break: keeping on is the filled button (a break is offered, never forced), stopping ends the session here. */
function BreakOffer({ decision, onContinue }: { decision: Next; onContinue: () => void }) {
  const [stopped, setStopped] = useState(false)
  useEffect(() => { say('Time for a break?') }, [])
  if (stopped) return <Done title={`Played ${format.count(decision.rounds_played, 'round')}`} next="Come back later: the next session picks up from these rounds." />
  return (
    <PageHeader
      title="Time for a break?"
      finding={{ text: decision.why, action: <Button variant="default" onClick={onContinue} autoFocus>Keep playing</Button> }}
      actions={<Button onClick={() => setStopped(true)}>Stop for now</Button>}
    />
  )
}

/** The session's end, at its rounds or minutes: what was played and that the next one starts afresh. */
function SessionOver({ learner, decision }: { learner: LearnerRow; decision: Next }) {
  return (
    <Done
      title={`Played ${format.count(decision.rounds_played, 'round')}`}
      next={`${decision.why} The next session picks up from these rounds.`}
      actions={<ButtonLink to={`/learners/${learner.id}`}>See what {learner.nickname} has shown</ButtonLink>}
    />
  )
}

/**
 * Keeps one round's attempt: when it was shown, the first answer and when, and the tries. `ended`
 * reports it once; leaving the round half done (Next is not offered then, but a change of kind or
 * of page is) reports it as left, as long as there was a first answer. The report function is read
 * through a ref, so a new one on each render does not count as leaving.
 */
function useAttempt(report: ((a: Answered) => void) | undefined) {
  const latest = useRef(report)
  useEffect(() => { latest.current = report })
  // One mutable record per round, made once when the round appears (a lazy state initialiser, not a ref read in render).
  const [log] = useState(() => ({ presented: new Date().toISOString(), first: null as { answer: AttemptIn['first_answer']; at: string } | null, tries: 0, sent: false }))
  const ended = useCallback((outcome: AttemptIn['outcome']) => {
    const x = log
    if (x.sent || !x.first) return
    x.sent = true
    latest.current?.({ first_answer: x.first.answer, tries: x.tries, outcome, presented_at: x.presented, answered_at: x.first.at })
  }, [log])
  useEffect(() => () => ended('left'), [ended])
  const answered = (answer: AttemptIn['first_answer']) => {
    const x = log
    x.tries += 1
    x.first ??= { answer, at: new Date().toISOString() }
  }
  return { answered, ended }
}

/** A round, answered by a tap or by an arrangement as its mechanic says. */
export function Board({ round, onNext, onAnswered, onRated }: { round: Round; onNext: () => void; onAnswered?: (a: Answered) => void; onRated?: (v: Face) => Promise<unknown> }) {
  const queryClient = useQueryClient()
  useEffect(() => { say(round.say) }, [round.say])
  const next = () => {
    // The round just played is not shown again: drop every round, this one too while it is still on
    // screen, so coming back to this kind of round (a new Game, counting from 0) asks the server afresh.
    queryClient.removeQueries({ queryKey: ['round'] })
    onNext()
  }
  return PLACE_MECHANICS.includes(round.mechanic) ? <Arrange round={round} onNext={next} onAnswered={onAnswered} onRated={onRated} /> : <Choose round={round} onNext={next} onAnswered={onAnswered} onRated={onRated} />
}

/** The heading every round shares: the prompt, Say it again, and once it is over what happened and Next. */
function RoundHeader({ round, over, onNext }: { round: Round; over: 'right' | 'missed' | null; onNext: () => void }) {
  return (
    <>
      <PageHeader
        title={round.prompt}
        actions={<SayAgain text={round.say} lang={LANG} verb="Say again" />}
        finding={over ? { text: over === 'right' ? 'That’s right.' : 'The answer is shown below.', action: <Button variant="default" onClick={onNext} autoFocus>Next</Button> } : undefined}
      />
      <p id="prompt" className="sr-only">{round.prompt}</p>
    </>
  )
}

const marks = { wrong: 'Not this one', right: 'Right', answer: 'This one' }

function Choose({ round, onNext, onAnswered, onRated }: { round: Round; onNext: () => void; onAnswered?: (a: Answered) => void; onRated?: (v: Face) => Promise<unknown> }) {
  const [turn, setTurn] = useState<Turn>({ tapped: [] })
  const attempt = useAttempt(onAnswered)
  const state = outcome(round, turn)
  const done = state !== 'playing'

  // ChoiceGrid draws the state and refuses a second tap on a closed tile; the answer key stays here.
  const tileState = (o: Option): ChoiceState =>
    turn.tapped.includes(o.id) ? (o.correct ? 'right' : 'wrong') : o.correct && done ? 'answer' : 'open'

  const tap = (id: string) => { // only an open tile reaches here: ChoiceGrid closes tapped tiles and, once answered, every tile
    const next = { tapped: [...turn.tapped, id] }
    setTurn(next)
    say(feedback(round, next))
    attempt.answered({ option: id })
    const after = outcome(round, next)
    if (after !== 'playing') attempt.ended(after)
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
      {done && onRated && <HowWasIt onRated={onRated} />}
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

function Arrange({ round, onNext, onAnswered, onRated }: { round: Round; onNext: () => void; onAnswered?: (a: Answered) => void; onRated?: (v: Face) => Promise<unknown> }) {
  const [placement, setPlacement] = useState<Placement>({})
  const attempt = useAttempt(onAnswered)
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
    attempt.answered({ placement: Object.fromEntries(Object.entries(placement).filter((e): e is [string, string] => e[1] !== undefined)) })
    const after = placeOutcome(round, n, arrangedRight(round, placement))
    if (after !== 'playing') attempt.ended(after)
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
      {done && onRated && <HowWasIt onRated={onRated} />}
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
