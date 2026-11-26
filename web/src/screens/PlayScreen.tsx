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
// Learners screen is a link. With a learner chosen, each round is kept once it ends (or once Next or
// a change of kind leaves it half done) with its first answer, how many tries it took and how it
// ended, and sent to the server, which rebuilds the round and judges the answer itself. With nobody
// chosen nothing is kept.
//
// Offline (spec §14). Answers and faces wait on the device until the server takes them (`answers` in api.ts; the
// Layout shows how many wait, never to the child in words). Play goes on without waiting for them. When a round
// cannot be fetched, Play plays one the server made earlier and the device kept (src/reserve.ts), and says so in one
// quiet line; the answer is judged by the server when it lands, like any other. "Chosen for them" cannot ask the
// engine while the server is away (each decision follows from the answer before it), so Play keeps the learner going
// with kept rounds of the kinds the engine chose this visit, recorded as the device's choice (asked "offline") in a
// sitting of their own, and asks the engine again after each one: once it answers, the session goes on from there.
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
import { Button, ButtonLink, isRefusal, ChoiceGrid, ChoiceGridSkeleton, DataView, Done, EmptyState, format, Field, NativeSelect, PageHeader, PlaceBoard, SayAgain, Skeleton, useLoad, useSearchParam, type ChoiceState, type Delivery, type Load, type PlaceState } from 'strata-react'
import { api, isMode, isPlayChoice, keepAttempt, keepRating, keys, MODES, newId, PLACE_MECHANICS, type AttemptIn, type Face, type LearnerRow, type Mode, type Next, type OfferOut, type Option, type PlayChoice, type Round, type SessionInfo, type Settings } from '../api'
import { LANG, useVoice } from '../voice'
import { refresh, take } from '../reserve'
import { arrangedRight, feedback, outcome, placeFeedback, placeOutcome, placeRight, solution, type Placement, type Turn } from '../play'
// Every prompt and answer is said aloud: a learner who cannot read yet still needs the prompt. It is said from the
// recorded clips where they cover it (../voice.ts), else in the browser's UK English voice. A prompt said unasked
// waits for the clips list (`voice.ready`), so the first one is in the same voice as the rest.

export const modeLabels: Record<Mode, string> = {
  same_picture: 'Same picture',
  same_colour: 'Same colour',
  same_letter: 'Same letter',
  same_number: 'Same number',
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
  sounds: 'Sounds',
  hear_find: 'Hear and find',
  colour_box: 'Colour box',
  shape_box: 'Shape box',
  which_group: 'Which group',
  quick_dots: 'Quick dots',
  one_more: 'One more, one less',
  biggest: 'Biggest number',
  number_card: 'Number card',
  small_letters: 'Small letters',
  letter_box: 'Letter box',
  same_sound: 'Same first sound',
  first_sounds: 'First sounds',
  picture_twins: 'Picture twins',
  colour_twins: 'Colour twins',
  letter_twins: 'Letter twins',
  number_twins: 'Number twins',
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

/** A round to play: fresh from the server, or one the device kept for when the server cannot be reached. */
type Played = { round: Round; kept: boolean }

/** A fresh round of `mode`, topping up the kept ones; when the server cannot be reached (not when it refuses), a kept one. */
async function freshOrKept(mode: Mode): Promise<Played> {
  try {
    const round = await api.round(mode)
    void refresh(mode, round)
    return { round, kept: false }
  } catch (e) {
    const round = isRefusal(e) ? null : take(mode)
    if (round) return { round, kept: true }
    throw e
  }
}

const KEPT = 'The server can’t be reached, so this round is one kept on this device. Answers are sent when it is back.'

/** Keeps a learner’s answer to send (the shell refreshes the learners’ records whenever one is sent). */
function keep(who: LearnerRow, attempt: Omit<AttemptIn, 'learner_id' | 'event_id'>): { id: string; delivered: Promise<Delivery> } {
  const id = newId()
  return { id, delivered: keepAttempt({ ...attempt, event_id: id, learner_id: who.id }, `${who.nickname}, ${modeLabels[attempt.mode]}`) }
}

/** Keeps a face for the answer `eventId`; a face the server refused says so under the faces. */
function rate(who: LearnerRow, eventId: string, value: Face): Promise<unknown> {
  return keepRating(eventId, value, `${who.nickname}, a face`).then(d => (d === 'refused' ? Promise.reject(new Error('refused')) : d))
}

/** What a game embedded elsewhere (the Break screen) is told: each round played (on its Next), and the engine ending
 * the sitting (a break offered or the session over), which an embedded game takes as its end instead of asking. */
export type Embedded = { onPlayed: () => void; onOver: () => void }

/** One round after another in `mode`: each Next asks the server for a new one. Every `rateEvery`th round a recorded
 * learner is asked how it was. */
export function Game({ mode, learner, session, rateEvery, embedded }: { mode: Mode; learner: LearnerRow | null; session: string; rateEvery: number; embedded?: Embedded }) {
  const [n, setN] = useState(0)
  const last = useRef('') // the last answer kept: a face is offered only after one
  // A fresh round for every visit (a change of kind or of who is playing remounts this Game): a round left
  // half done and shown again with its answers forgotten would let a retry be recorded as a new first answer.
  const [visit] = useState(newId)
  const round = useLoad({ queryKey: keys.round(mode, visit, n), queryFn: () => freshOrKept(mode), staleTime: Infinity })
  const record = (who: LearnerRow, r: Round, a: Answered) => {
    last.current = keep(who, { session_id: session, mode: r.mode, version: r.version, content: r.content, choices: r.choices, seed: r.seed, level: r.level, asked: mode, ...a }).id
  }
  const asking = learner !== null && rateEvery > 0 && (n + 1) % rateEvery === 0
  return (
    <DataView state={round} isEmpty={p => p.round.options.length === 0 && p.round.pieces.length === 0} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing to play">The server sent a round with no pictures.</EmptyState>}>
      {({ round: r, kept }) => (
        <div className="grid gap-4">
          <Board key={`${r.mode}-${r.seed}`} round={r} onNext={() => { setN(x => x + 1); embedded?.onPlayed() }} onAnswered={learner ? a => record(learner, r, a) : undefined} onRated={asking && learner ? v => rate(learner, last.current, v) : undefined} />
          {kept && <p className="type-caption text-muted-foreground">{KEPT}</p>}
        </div>
      )}
    </DataView>
  )
}

/** A session the engine plans for `learner`: started once per visit, then one decision after another. */
export function Planned({ learner, embedded }: { learner: LearnerRow; embedded?: Embedded }) {
  const [visit] = useState(newId)
  const session = useLoad({ queryKey: keys.session(learner.id, visit), queryFn: () => api.startSession(learner.id), staleTime: Infinity })
  return (
    <DataView state={session} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="No session">The server started none.</EmptyState>}>
      {s => <Decisions session={s} learner={learner} embedded={embedded} />}
    </DataView>
  )
}

/** The engine could not be reached for a decision: Play goes on with kept rounds until it can. */
type Away = { action: 'away' }
const AWAY: Away = { action: 'away' }

/** Decision `seq`, or Away when the server cannot be reached (a refusal is still an error). */
function nextOrAway(session: string, seq: number): Promise<Next | Away> {
  return api.next(session, seq).catch((e: unknown) => {
    if (isRefusal(e)) throw e
    return AWAY
  })
}

/** Decision `seq` of the session, asked for by number so a retry returns the same one; each Next asks for the one after. */
function Decisions({ session, learner, embedded }: { session: SessionInfo; learner: LearnerRow; embedded?: Embedded }) {
  const [seq, setSeq] = useState(0)
  const queryClient = useQueryClient()
  const decision = useLoad({ queryKey: keys.next(session.id, seq), queryFn: () => nextOrAway(session.id, seq), staleTime: Infinity })
  // The kinds the engine chose this visit, newest first: what Play falls back on while the server is away.
  const [chosen, setChosen] = useState<Mode[]>([])
  // The answer and face being sent, if any: the next decision is asked for only once their first try is over, so the
  // engine chooses knowing them; asked too soon, a third miss would not yet show and no break would be offered. A try
  // that found the server away does not hold Play up: the next decision then finds it away too.
  const sending = useRef<Promise<unknown>[]>([])
  const onward = () => { void Promise.allSettled(sending.current).then(() => setSeq(n => n + 1)) }
  const last = useRef('') // the last answer kept: a face is offered only after one
  const record = (d: Next, r: Round, a: Answered) => {
    const kept = keep(learner, { session_id: session.id, decision_id: d.id, mode: r.mode, version: r.version, content: r.content, choices: r.choices, seed: r.seed, level: r.level, asked: 'next', ...a })
    last.current = kept.id
    sending.current = [kept.delivered]
  }
  const rated = (v: Face) => {
    const p = rate(learner, last.current, v)
    sending.current = [...sending.current, p]
    return p
  }
  const back = (n: Next) => queryClient.setQueryData(keys.next(session.id, n.seq), n)
  return (
    <DataView state={decision} isEmpty={() => false} skeleton={<RoundSkeleton />} empty={<EmptyState title="Nothing chosen">The server chose nothing.</EmptyState>}>
      {d =>
        d.action === 'away' ? (
          <AwayRounds key={seq} session={session} seq={seq} learner={learner} kinds={chosen} onBack={back} onPlayed={embedded?.onPlayed} />
        ) : (d.action === 'round' || d.action === 'choice') && d.round ? (
          <div className="grid gap-4">
            <Chosen round={d.round} onChosen={m => setChosen(k => [m, ...k.filter(x => x !== m)])} />
            <Board key={d.id} round={d.round} onNext={() => { onward(); embedded?.onPlayed() }} onAnswered={a => record(d, d.round as Round, a)} onRated={d.rate ? rated : undefined} />
            <p className="type-caption text-muted-foreground">Why this round: {d.why}</p>
          </div>
        ) : d.action === 'choice' && d.offers ? (
          <PickOne decision={d} offers={d.offers} onPicked={back} />
        ) : embedded && (d.action === 'break' || d.action === 'end') ? (
          <Over onOver={embedded.onOver} />
        ) : d.action === 'break' ? (
          <BreakOffer decision={d} onContinue={onward} />
        ) : (
          <SessionOver learner={learner} decision={d} />
        )
      }
    </DataView>
  )
}

/** The engine ended the sitting in an embedded game: told once, drawn by the embedding screen. */
function Over({ onOver }: { onOver: () => void }) {
  const latest = useRef(onOver)
  useEffect(() => { latest.current() }, [])
  return null
}

/** Notes a kind the engine chose and tops up the rounds kept of it, so they are there if the server goes. */
function Chosen({ round, onChosen }: { round: Round; onChosen: (m: Mode) => void }) {
  const latest = useRef(onChosen)
  useEffect(() => { latest.current = onChosen })
  useEffect(() => {
    // A transfer kind (held out of practice, so not among the kinds a grown-up picks) is never kept or played away:
    // rounds of it played offline would be practice, and their answers would pass the check the engine is making.
    if (!isMode(round.mode)) return
    latest.current(round.mode)
    void refresh(round.mode, round)
  }, [round])
  return null
}

/** The first kept round of the kinds the engine chose, newest kind first. */
function takeKept(kinds: readonly Mode[]): Round | null {
  for (const k of kinds) {
    const r = take(k)
    if (r) return r
  }
  return null
}

/**
 * While the engine cannot be reached: kept rounds of the kinds it chose this visit, answered into a sitting of their
 * own as the device's choice (asked "offline", no decision), and after each Next the engine is asked again for the
 * decision Play was waiting for. Once it answers, `onBack` puts that decision on screen and the session goes on.
 */
function AwayRounds({ session, seq, learner, kinds, onBack, onPlayed }: { session: SessionInfo; seq: number; learner: LearnerRow; kinds: readonly Mode[]; onBack: (n: Next) => void; onPlayed?: () => void }) {
  const [sitting] = useState(newId)
  const [round, setRound] = useState<Round | null>(() => takeKept(kinds))
  const [asking, setAsking] = useState(false)
  const again = () => {
    setAsking(true)
    api.next(session.id, seq).then(onBack, () => {
      setAsking(false)
      setRound(takeKept(kinds))
    })
  }
  const record = (r: Round, a: Answered) => { keep(learner, { session_id: sitting, mode: r.mode, version: r.version, content: r.content, choices: r.choices, seed: r.seed, level: r.level, asked: 'offline', ...a }) }
  if (!round)
    return (
      <EmptyState title="No rounds kept on this device" action={<Button variant="default" onClick={again} disabled={asking}>Try the server again</Button>}>
        The server can’t be reached, and the rounds this device keeps for that have all been played. Answers already given are kept here and sent when it is back.
      </EmptyState>
    )
  return (
    <div className="grid gap-4">
      <Board key={`${round.mode}-${round.seed}`} round={round} onNext={() => { again(); onPlayed?.() }} onAnswered={a => record(round, a)} />
      <p className="type-caption text-muted-foreground">{KEPT}</p>
    </div>
  )
}

/** A choice of two: the learner taps the one they want to play next; the server keeps the pick, then it is played. */
function PickOne({ decision, offers, onPicked }: { decision: Next; offers: OfferOut[]; onPicked: (n: Next) => void }) {
  const [failed, setFailed] = useState(false)
  const voice = useVoice()
  const question = `Which one next? ${offers.map(o => o.title).join(' or ')}?`
  useEffect(() => { if (voice.ready) voice.say(question) }, [question, voice])
  const choose = (o: OfferOut) => {
    setFailed(false)
    api.pick(decision.session_id, decision.seq, offers.indexOf(o)).then(onPicked, () => setFailed(true))
  }
  return (
    <section aria-labelledby="pick" className="grid gap-6">
      <PageHeader title="Which one next?" actions={<Say text={question} verb="Say again" />} />
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
        <Say text="How was that one?" verb="Say" />
      </div>
      <ChoiceGrid label="How was that one?" items={FACES} itemKey={f => String(f.value)} itemLabel={f => f.word} renderPicture={f => f.picture} state={() => 'open'} marks={pickMarks} onChoose={f => rate(f.value)} />
      {said === 'failed' && <p role="status" className="type-caption text-muted-foreground">That face was not saved.</p>}
    </section>
  )
}

/** An offered break: keeping on is the filled button (a break is offered, never forced), stopping ends the session here. */
function BreakOffer({ decision, onContinue }: { decision: Next; onContinue: () => void }) {
  const [stopped, setStopped] = useState(false)
  const voice = useVoice()
  useEffect(() => { if (voice.ready) voice.say('Time for a break?') }, [voice])
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

/** Say it again, from the clips where they cover it: named by the words it says (a sound by its description). */
function Say({ text, verb }: { text: string; verb: string }) {
  const voice = useVoice()
  return <SayAgain text={voice.words(text)} parts={voice.parts(text)} lang={LANG} verb={verb} />
}

/** A round, answered by a tap or by an arrangement as its mechanic says. */
export function Board({ round, onNext, onAnswered, onRated }: { round: Round; onNext: () => void; onAnswered?: (a: Answered) => void; onRated?: (v: Face) => Promise<unknown> }) {
  const queryClient = useQueryClient()
  const voice = useVoice()
  // Said once per round, when the clips list is known; `voice` changes only then, so a later re-render never repeats it.
  useEffect(() => { if (voice.ready) voice.say(round.say) }, [round.say, voice])
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
        actions={<Say text={round.say} verb="Say again" />}
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

  const voice = useVoice()
  const tap = (id: string) => { // only an open tile reaches here: ChoiceGrid closes tapped tiles and, once answered, every tile
    const next = { tapped: [...turn.tapped, id] }
    setTurn(next)
    voice.say(feedback(round, next))
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

  const voice = useVoice()
  const check = () => {
    const n = checks + 1
    setChecks(n)
    setChecked(placement)
    voice.say(placeFeedback(round, placement, n))
    attempt.answered({ placement: Object.fromEntries(Object.entries(placement).filter((e): e is [string, string] => e[1] !== undefined)) })
    const after = placeOutcome(round, n, arrangedRight(round, placement))
    if (after !== 'playing') attempt.ended(after)
  }

  const placed = Object.values(placement).some(Boolean)
  return (
    <section aria-labelledby="prompt" className="grid gap-6">
      <RoundHeader round={round} over={done ? state : null} onNext={onNext} />
      {round.show && <Show round={round} />}
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
export function RoundSkeleton() {
  return (
    <div className="grid gap-6" aria-hidden>
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-20 w-40" />
      <ChoiceGridSkeleton count={4} />
    </div>
  )
}
