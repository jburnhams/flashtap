// The grown-up's question: "What can this learner do, and what is that based on?" The finding counts
// skills by reporting state: how many are independent or beyond, how many emerging, how many not yet
// seen. "Not seen yet" is its own state, never "not mastered" (spec §13).
//
// Each skill row shows the two estimators side by side (BKT's chance the skill is known, and the
// rule baseline's share right of the last five counted answers) and opens in place to its evidence:
// every attempt that touched it, whether it counted and, when not, why (only a first answer counts;
// a wrong answer may be held back while a confounding skill is unseen; a struck-out round counts for
// nothing). That list is the provenance the spec asks a profile to carry (§15). A round played by
// someone else can be struck out there, with Undo while the bar shows.
//
// A grown-up can say what they have seen of a skill ("Can do it" or "Not yet", as a parent or a
// teacher; spec §13 "manual overrides with source-labelled evidence"): it shows beside the state,
// labelled with who said it and when, moves BKT's estimate and what the engine offers, and never
// counts as an answer, so it cannot make a state alone. Withdrawing it is reversible until the Undo
// bar goes, like a strike.
//
// Speed is shown beside each skill (the typical time to a right first answer, and whether it is
// getting quicker against their own earlier answers on the same kind of round) and never moves its
// state: §10, speed is not mastery. Under an Independent skill, how it has done in its transfer kind
// (a second form of it, held out of practice): Generalised needs that check passed (§13). A suspected mix-up (a misconception: wrong taps landing on the
// option it predicts more often than luck would) holds its skills at Emerging, and the State cell
// says which. The Mix-ups tab lists every misconception a round has offered, each as a hypothesis
// with what it rests on and the round that would tell it from a slip.
//
// The Engagement tab is how they play, kept apart from what they know (§11): each kind of round
// with how it went, the faces and the picks, and the patterns worth a look, each worded as what it
// could be and what to try, never as a label about the learner.
//
// Export saves everything held about the learner as one JSON file (§17); `flashtap learners
// rebuild` checks the estimates in it against its own events. Delete removes the learner and every
// round for good, so it is the one action behind a confirm.
import { useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router'
import { AlertDialog, AsyncButton, Button, ButtonLink, ChoiceGroup, DataTable, DataView, Dialog, EmptyState, Field, format, Input, Metric, MetricStrip, PageHeader, RowAction, Skeleton, Status, TableSkeleton, Tabs, TextLink, UndoBar, useAsyncAction, useExpanded, useLoad, useUndoable, type Column, type Tone, type Undoable } from 'strata-react'
import { api, exportUrl, keys, SKILL_STATES, type Engagement, type EvidenceRow, type Fluency, type KindRow, type MisconceptionReport, type MisconceptionStatus, type OverrideIn, type Profile, type SkillReport, type SkillState, type Told } from '../api'
import { modeLabels } from './PlayScreen'
import { transferNote } from '../transfer'

export const stateWords: Record<SkillState, { word: string; tone: Tone }> = {
  unobserved: { word: 'Not seen yet', tone: 'neutral' },
  introduced: { word: 'Introduced', tone: 'info' },
  emerging: { word: 'Emerging', tone: 'info' },
  independent: { word: 'Independent', tone: 'success' },
  generalised: { word: 'Generalised', tone: 'success' },
  retained: { word: 'Retained', tone: 'success' },
}

const tabs = [
  { value: 'seen', label: 'Seen' },
  { value: 'all', label: 'All skills' },
  { value: 'mixups', label: 'Mix-ups' },
  { value: 'engagement', label: 'Engagement' },
]

export const mixupWords: Record<MisconceptionStatus, { word: string; tone: Tone }> = {
  suspected: { word: 'Suspected', tone: 'warning' },
  unclear: { word: 'Could be chance', tone: 'info' },
  cleared: { word: 'Cleared', tone: 'success' },
  not_seen: { word: 'Not seen', tone: 'neutral' },
}

const trendWords: Record<NonNullable<Fluency['trend']>, string> = { quicker: 'getting quicker', steady: 'about the same', slower: 'getting slower' }

export const saysWords: Record<Told['says'], string> = { can: 'Can do it', not_yet: 'Not yet' }
const observerWords: Record<Told['observer'], string> = { parent: 'a parent', teacher: 'a teacher' }

export function LearnerScreen() {
  const { id = '' } = useParams()
  const profile = useLoad({ queryKey: keys.profile(id), queryFn: () => api.profile(id) })
  return (
    <DataView
      state={profile}
      isEmpty={() => false}
      skeleton={<LearnerSkeleton />}
      empty={null}
      error={({ message, retry }) => (
        <EmptyState title="This learner could not be shown" action={<Button onClick={retry}>Try again</Button>}>
          {message} If the learner was deleted, choose another on <TextLink to="/learners">Learners</TextLink>.
        </EmptyState>
      )}
    >
      {p => <Learner p={p} />}
    </DataView>
  )
}

const rank = (s: SkillState) => SKILL_STATES.indexOf(s)

function finding(p: Profile) {
  const at = (states: SkillState[]) => p.skills.filter(s => states.includes(s.state)).length
  if (p.learner.attempts === 0) return `No rounds recorded yet: choose ${p.learner.nickname} on Play and their rounds are kept here.`
  return `${format.count(at(['independent', 'generalised', 'retained']), 'skill')} independent or beyond, ${format.integer(at(['introduced', 'emerging']))} on the way, ${format.integer(at(['unobserved']))} not seen yet.`
}

function Learner({ p }: { p: Profile }) {
  const navigate = useNavigate()
  // Held here, not in a skill's evidence: closing the row must not take the Undo bar (or a failure) with it.
  const undoable = useUndoable()
  const [telling, setTelling] = useState<SkillReport | null>(null)
  const queryClient = useQueryClient()
  const name = p.learner.nickname
  const remove = async () => {
    await api.deleteLearner(p.learner.id)
    queryClient.removeQueries({ queryKey: keys.profile(p.learner.id) })
    await queryClient.invalidateQueries({ queryKey: keys.learners })
    void navigate('/learners')
  }
  return (
    <>
      <PageHeader
        title={name}
        scope={`${format.count(p.learner.attempts, 'round')} recorded over ${format.count(p.sessions, 'session')}`}
        actions={
          <>
            <ButtonLink to={`/?learner=${encodeURIComponent(p.learner.id)}`} variant="default">{`Play as ${name}`}</ButtonLink>
            <ButtonLink href={exportUrl(p.learner.id)} download icon={Download}>Export</ButtonLink>
            <AlertDialog
              title={`Delete ${name} and everything recorded?`}
              description={`This removes ${name}, ${format.count(p.learner.attempts, 'round')} and every estimate made from them, for good. Export first to keep a copy.`}
              confirm={`Delete ${name}`}
              onConfirm={remove}
              trigger={<Button><Trash2 aria-hidden className="size-4" />Delete</Button>}
            />
          </>
        }
        finding={{ text: finding(p) }}
      />
      <MetricStrip label={`${name} at a glance`}>
        <Metric label="Rounds recorded" value={format.integer(p.learner.attempts)} note={p.learner.last_played ? `last ${format.dateTime(p.learner.last_played)}` : 'none yet'} />
        <Metric label="Skills seen" value={`${p.skills.filter(s => s.state !== 'unobserved').length} of ${p.skills.length}`} note="with any evidence" />
        <Metric label="Struck out" value={format.integer(p.struck)} note="rounds that count for nothing" />
      </MetricStrip>
      <Tabs param="show" items={tabs} label="Skills">
        {tab =>
          tab === 'engagement' ? (
            <EngagementView e={p.engagement} name={name} />
          ) : tab === 'mixups' ? (
            <Mixups rows={p.misconceptions} name={name} />
          ) : (
            <Skills learner={p.learner.id} name={name} undoable={undoable} onTell={setTelling} rows={tab === 'all' ? p.skills : p.skills.filter(s => s.state !== 'unobserved' || s.told)} />
          )
        }
      </Tabs>
      <UndoBar undoable={undoable} />
      {telling && <Tell learner={p.learner.id} name={name} skill={telling} onClose={() => setTelling(null)} />}
      <section className="grid gap-1 type-caption text-muted-foreground">
        <h2 className="type-label text-foreground">How these are worked out</h2>
        {p.models.map(m => <p key={m.model}>{m.model}: {m.description}.</p>)}
        <p>Only a first answer counts. The states are labels drawn from those numbers; their thresholds are first guesses, to be fitted once there are real rounds to fit them to.</p>
        <p>What a grown-up says sets BKT's estimate when it is said, and the rounds after it move it on; it is never counted as an answer.</p>
        <p>Speed is the typical time to a right first answer, from rounds early in a session, against their own earlier rounds of the same kind and step. It never changes a state: a slow right answer is still right.</p>
      </section>
    </>
  )
}

const estimate = (s: SkillReport, model: string) => s.estimates.find(e => e.model === model)

function toldText(t: Told) {
  return `${saysWords[t.says]}, says ${observerWords[t.observer]}`
}

/** What a grown-up said, who they are, when, and their note when they left one. */
function ToldCell({ t }: { t: Told }) {
  return (
    <>
      <span>{toldText(t)}</span>
      <span className="block type-caption text-muted-foreground">{[format.date(t.at), t.note].filter(Boolean).join(': ')}</span>
    </>
  )
}

/** The typical time, its spread and, once there are enough, how it is moving. */
function SpeedCell({ f }: { f: Fluency }) {
  const spread = f.used > 1 ? `${format.decimal(f.low)}–${format.decimal(f.high)}\u00a0s` : format.count(f.used, 'answer')
  return (
    <>
      <span>{format.withUnit(f.seconds, 's', format.decimal)}</span>
      <span className="block type-caption text-muted-foreground">{f.trend ? `${spread}, ${trendWords[f.trend]}` : spread}</span>
    </>
  )
}

const skillColumns: Column<SkillReport>[] = [
  { key: 'title', header: 'Skill', value: s => s.title, cell: s => <><span>{s.title}</span><span className="block type-caption text-muted-foreground">{s.strand}</span></> },
  {
    key: 'state',
    header: 'State',
    value: s => rank(s.state),
    cell: s => (
      <>
        <Status tone={stateWords[s.state].tone}>{stateWords[s.state].word}</Status>
        {s.suspected.length > 0 && <span className="block type-caption text-muted-foreground">Held back: {s.suspected.join(', ')}</span>}
        {transferNote(s) && <span className="block type-caption text-muted-foreground">{transferNote(s)}</span>}
      </>
    ),
  },
  { key: 'known', header: 'Known (BKT)', numeric: true, value: s => estimate(s, 'bkt@1')?.p ?? null, cell: s => format.share(estimate(s, 'bkt@1')?.p) },
  {
    key: 'recent',
    header: 'Last answers',
    numeric: true,
    value: s => estimate(s, 'rule@1')?.p ?? null,
    // Drawn only for a row with a value (an unobserved skill shows the missing dash), so the estimate is there.
    cell: s => s.estimates.filter(e => e.model === 'rule@1').map(r => `${Math.round(r.p * r.used)} of ${r.used}`),
  },
  { key: 'counted', header: 'Counted', numeric: true, value: s => s.counted, cell: s => (s.held ? `${format.integer(s.counted)} (+${format.integer(s.held)} not)` : format.integer(s.counted)) },
  {
    key: 'speed',
    header: 'Speed',
    numeric: true,
    value: s => s.fluency?.seconds ?? null,
    // Drawn only for a row with a value, so the fluency is there.
    cell: s => <SpeedCell f={s.fluency as Fluency} />,
    missing: 'Not timed yet',
  },
  { key: 'last_seen', header: 'Last seen', value: s => (s.last_seen ? new Date(s.last_seen) : null), cell: s => format.dateTime(s.last_seen), missing: 'Never' },
]

function Skills({ learner, name, undoable, onTell, rows }: { learner: string; name: string; undoable: Undoable; onTell: (s: SkillReport) => void; rows: SkillReport[] }) {
  const open = useExpanded({ param: 'open' })
  const queryClient = useQueryClient()
  if (rows.length === 0) return <EmptyState title="No skills seen yet">Every skill is still unobserved: nothing is known either way. Open All skills to see the list, or to say what you have seen.</EmptyState>
  const withdraw = (s: SkillReport, t: Told) =>
    undoable.schedule({
      id: t.id,
      message: `Withdrew “${saysWords[t.says]}” for ${s.title}.`,
      failure: `“${saysWords[t.says]}” for ${s.title} is back: withdrawing it did not go through.`,
      commit: async () => {
        await api.withdraw(learner, t.id)
        await queryClient.invalidateQueries({ queryKey: ['learners', learner] })
      },
    })
  const columns: Column<SkillReport>[] = [
    ...skillColumns,
    {
      key: 'told',
      header: 'A grown-up says',
      value: s => (s.told && !undoable.isRemoved(s.told.id) ? s.told.says : null),
      // Drawn only for a row with a value, so the override is there.
      cell: s => <ToldCell t={s.told as Told} />,
      missing: 'Nothing yet',
    },
    {
      key: 'tell',
      header: 'Say what you have seen',
      hideHeader: true,
      sort: false,
      cell: s => (
        <span className="flex flex-wrap gap-1">
          <RowAction label="Say" subject={`what ${name} can do: ${s.title}`} onClick={() => onTell(s)} />
          {s.told && !undoable.isRemoved(s.told.id) && <RowAction label="Withdraw" subject={`what was said about ${s.title}`} onClick={() => withdraw(s, s.told as Told)} />}
        </span>
      ),
    },
  ]
  return (
    <DataTable
      caption="Skills"
      columns={columns}
      rows={rows}
      rowKey={s => s.skill}
      sortParam="sort"
      initialSort={{ key: 'state', dir: 'descending' }}
      expansion={{ ...open, rowLabel: s => `Evidence for ${s.title}`, isExpandable: s => s.state !== 'unobserved', detail: s => <Evidence learner={learner} skill={s} undoable={undoable} /> }}
    />
  )
}

const roleWords = { primary: 'Assessed', secondary: 'Also used', confound: 'Needed' }

function Evidence({ learner, skill, undoable }: { learner: string; skill: SkillReport; undoable: Undoable }) {
  const queryClient = useQueryClient()
  const rows = useLoad({ queryKey: keys.evidence(learner, skill.skill), queryFn: () => api.evidence(learner, skill.skill) })
  const strike = (r: EvidenceRow) =>
    undoable.schedule({
      id: r.event_id,
      message: `Struck out the ${modeLabels[r.mode]} round from ${format.dateTime(r.at)}.`,
      failure: `The ${modeLabels[r.mode]} round is back: striking it out did not go through.`,
      commit: async () => {
        await api.strike(r.event_id, 'struck out on the Learner screen')
        await queryClient.invalidateQueries({ queryKey: ['learners', learner] })
      },
    })
  const columns: Column<EvidenceRow>[] = [
    { key: 'at', header: 'When', sort: false, cell: r => format.dateTime(r.at) },
    { key: 'round', header: 'Round', sort: false, cell: r => <><span>{modeLabels[r.mode]}</span><span className="block type-caption text-muted-foreground">v{r.version}, {r.choices} choices, seed {r.seed}</span></> },
    { key: 'role', header: 'Role', sort: false, cell: r => roleWords[r.role] },
    {
      key: 'answer',
      header: 'First answer',
      sort: false,
      cell: r => (
        <>
          {r.answer} <span className="text-muted-foreground">({r.correct ? 'right' : 'not right'})</span>
          {r.mistake && <span className="block type-caption text-muted-foreground">{r.mistake}</span>}
        </>
      ),
    },
    { key: 'seconds', header: 'Time', numeric: true, sort: false, cell: r => format.withUnit(r.seconds, 's', format.decimal) },
    {
      key: 'counted',
      header: 'Counted',
      sort: false,
      // A round struck out here shows as struck at once; the refetch after the commit says the same.
      cell: r => (undoable.isRemoved(r.event_id) ? <span className="text-muted-foreground">No: struck out</span> : r.counted ? 'Yes' : <span className="text-muted-foreground">No: {r.why}</span>),
    },
    { key: 'strike', header: 'Strike out', hideHeader: true, sort: false, cell: r => (r.struck || undoable.isRemoved(r.event_id) ? null : <RowAction label="Strike out" subject={`the ${modeLabels[r.mode]} round from ${format.dateTime(r.at)}`} onClick={() => strike(r)} />) },
  ]
  return (
    <div className="grid gap-2 py-2">
      <DataView state={rows} isEmpty={r => r.length === 0} skeleton={<TableSkeleton rows={3} columns={5} />} empty={<EmptyState title="No rounds touched this skill">Its evidence will show here once one does.</EmptyState>}>
        {r => <DataTable caption={`Rounds that touched ${skill.title}`} columns={columns} rows={r} rowKey={x => x.event_id} />}
      </DataView>
    </div>
  )
}

/** What a grown-up has seen of one skill: can do it or not yet, who they are to the learner, and a note. */
function Tell({ learner, name, skill, onClose }: { learner: string; name: string; skill: SkillReport; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [says, setSays] = useState<OverrideIn['says']>(skill.told?.says ?? 'can')
  const [observer, setObserver] = useState<OverrideIn['observer']>(skill.told?.observer ?? 'parent')
  const [note, setNote] = useState('')
  const save = useAsyncAction(async () => {
    await api.tell(learner, { skill: skill.skill, says, observer, note })
    await queryClient.invalidateQueries({ queryKey: ['learners', learner] })
    onClose()
  })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void save.run()
  }
  return (
    <Dialog
      open
      onOpenChange={onClose} // only ever asked to close: it is mounted open and unmounted to close
      title={`What have you seen ${name} do?`}
      description={`${skill.title}. It sets the estimate now and the rounds after it move it on; it never counts as an answer.`}
    >
      <form id="tell" onSubmit={onSubmit} noValidate className="grid gap-5">
        <ChoiceGroup legend={`${name}…`} name="says" value={says} onChange={v => setSays(v as OverrideIn['says'])} choices={[{ value: 'can', label: 'Can do it', detail: 'Seen doing it, without help.' }, { value: 'not_yet', label: 'Not yet', detail: 'Tried, and it is not there yet.' }]} />
        <ChoiceGroup legend="You are" name="observer" value={observer} onChange={v => setObserver(v as OverrideIn['observer'])} choices={[{ value: 'parent', label: 'A parent' }, { value: 'teacher', label: 'A teacher' }]} />
        <Field label="Note" hint="Optional: what you saw, up to 200 characters. No names.">
          <Input value={note} maxLength={200} onChange={e => setNote(e.target.value)} />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <AsyncButton type="submit" variant="default" phase={save.phase} error={save.error} labels={{ idle: 'Save what you saw', pending: 'Saving…', done: 'Saved' }} />
          <Button onClick={onClose}>Cancel</Button>
          {save.phase === 'error' && <p className="type-body-sm text-danger">{save.error} Nothing was saved.</p>}
        </div>
      </form>
    </Dialog>
  )
}

/** What the wrong taps say, misconception by misconception, each as a hypothesis with the round that would check it. */
function Mixups({ rows, name }: { rows: MisconceptionReport[]; name: string }) {
  if (rows.length === 0) return <EmptyState title="No mix-ups to look for yet">Some rounds offer the answer a common mix-up would give (a 9 for six, a d for b). Once {name} has played some, what their wrong answers say shows here.</EmptyState>
  return (
    <ul className="grid gap-3" aria-label="Mix-ups">
      {rows.map(m => (
        <li key={m.id} className="grid gap-1 rounded-surface border border-border p-4">
          <p className="flex flex-wrap items-center gap-2 type-body">
            <span>{m.title}</span>
            <Status tone={mixupWords[m.status].tone}>{mixupWords[m.status].word}</Status>
          </p>
          <p className="type-body-sm text-muted-foreground">{mixupText(m)}</p>
          {open(m) && m.probe && <p className="type-body-sm text-muted-foreground">To check by hand: {m.probe}</p>}
          {open(m) && m.checks && <p className="type-body-sm text-muted-foreground">Rounds Flashtap chooses for {name} offer this mix-up among the choices, to tell it from a slip.</p>}
        </li>
      ))}
    </ul>
  )
}

const open = (m: MisconceptionReport) => m.status === 'suspected' || m.status === 'unclear'

function mixupText(m: MisconceptionReport) {
  const offered = `Offered in ${format.count(m.offered, 'round')}`
  if (m.shown === 0) return `${offered}, never chosen.`
  const shown = `${offered}; ${format.integer(m.shown)} of ${format.integer(m.wrong)} wrong answers were this one, where luck would give about ${format.decimal(m.expected)}`
  return m.status === 'cleared' ? `${shown}. Right every time since, with it on offer.` : `${shown}. Last ${format.dateTime(m.last_shown)}.`
}

const facesText = (k: KindRow) => `${k.liked} \u{1F600} · ${k.okay} \u{1F610} · ${k.disliked} \u{1F641}`
// A cell is drawn only for a row whose `value` is not null (the table prints the missing word otherwise), so each
// cell can take its number as there. A kind can be offered in a choice without being played yet: no rounds.
const kindColumns: Column<KindRow>[] = [
  { key: 'title', header: 'Kind of round', value: k => k.title, cell: k => k.title },
  { key: 'rounds', header: 'Rounds', numeric: true, value: k => k.rounds, cell: k => format.integer(k.rounds) },
  { key: 'right', header: 'Right first time', numeric: true, value: k => (k.rounds ? k.right_first / k.rounds : null), cell: k => format.share(k.right_first / k.rounds) },
  { key: 'seconds', header: 'Typical first answer', numeric: true, value: k => k.median_seconds, cell: k => format.withUnit(k.median_seconds as number, 's', format.decimal) },
  { key: 'tries', header: 'Tries', numeric: true, value: k => k.mean_tries, cell: k => format.decimal(k.mean_tries as number) },
  { key: 'faces', header: 'Faces', value: k => (k.liked + k.okay + k.disliked ? k.liked - k.disliked : null), cell: k => facesText(k), missing: 'None' },
  { key: 'picked', header: 'Picked', numeric: true, value: k => (k.offered ? k.picked / k.offered : null), cell: k => `${k.picked} of ${k.offered}`, missing: 'Not offered' },
]

/** How they play: each kind with its numbers, then the patterns worth a look, as hypotheses. */
function EngagementView({ e, name }: { e: Engagement; name: string }) {
  if (e.kinds.length === 0) return <EmptyState title="Nothing played yet">Once {name} plays, how each kind of round goes, the faces and the picks show here.</EmptyState>
  return (
    <div className="grid gap-6">
      <DataTable caption="Kinds of round" columns={kindColumns} rows={e.kinds} rowKey={k => k.mode} sortParam="ksort" initialSort={{ key: 'rounds', dir: 'descending' }} />
      <section className="grid gap-3" aria-labelledby="patterns">
        <h2 id="patterns" className="type-heading">Worth a look</h2>
        {e.hypotheses.length === 0 ? (
          <p className="type-body-sm text-muted-foreground">No pattern stands out yet. Patterns are named only over enough rounds, and only as what they could be.</p>
        ) : (
          <ul className="grid gap-3">
            {e.hypotheses.map(h => (
              <li key={h.seen} className="grid gap-1 rounded-surface border border-border p-4">
                <p className="type-body">{h.seen}</p>
                <p className="type-body-sm text-muted-foreground">Could be: {h.could_be}</p>
                <p className="type-body-sm text-muted-foreground">To try: {h.try_}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Mirrors the screen: heading, three metrics, the tabs and the table. */
function LearnerSkeleton() {
  return (
    <div className="grid gap-8" aria-hidden>
      <div className="grid gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map(i => <Skeleton key={i} className="h-20" />)}
      </div>
      <TableSkeleton rows={6} columns={6} />
    </div>
  )
}
