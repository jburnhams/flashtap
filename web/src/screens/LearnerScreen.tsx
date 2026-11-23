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
// Export saves everything held about the learner as one JSON file (§17); `flashtap learners
// rebuild` checks the estimates in it against its own events. Delete removes the learner and every
// round for good, so it is the one action behind a confirm.
import { useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import { AlertDialog, Button, buttonVariants, DataTable, DataView, EmptyState, format, Metric, MetricStrip, PageHeader, RowAction, Skeleton, Status, TableSkeleton, Tabs, UndoBar, useExpanded, useLoad, useUndoable, type Column, type Tone, type Undoable } from 'strata-react'
import { api, exportUrl, keys, SKILL_STATES, type EvidenceRow, type Profile, type SkillReport, type SkillState } from '../api'
import { modeLabels } from './PlayScreen'

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
]

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
          {message} If the learner was deleted, choose another on <Link to="/learners" className="text-primary underline underline-offset-4">Learners</Link>.
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
            <Link to={`/?learner=${p.learner.id}`} data-variant="default" className={buttonVariants({ variant: 'default' })}>Play as {name}</Link>
            <a href={exportUrl(p.learner.id)} download data-variant="outline" className={buttonVariants({ variant: 'outline' })}><Download aria-hidden className="size-4" />Export</a>
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
        {tab => <Skills learner={p.learner.id} undoable={undoable} rows={tab === 'all' ? p.skills : p.skills.filter(s => s.state !== 'unobserved')} />}
      </Tabs>
      <UndoBar undoable={undoable} />
      <section className="grid gap-1 type-caption text-muted-foreground">
        <h2 className="type-label text-foreground">How these are worked out</h2>
        {p.models.map(m => <p key={m.model}>{m.model}: {m.description}.</p>)}
        <p>Only a first answer counts. The states are labels drawn from those numbers; their thresholds are first guesses, to be fitted once there are real rounds to fit them to.</p>
      </section>
    </>
  )
}

const estimate = (s: SkillReport, model: string) => s.estimates.find(e => e.model === model)

const skillColumns: Column<SkillReport>[] = [
  { key: 'title', header: 'Skill', value: s => s.title, cell: s => <><span>{s.title}</span><span className="block type-caption text-muted-foreground">{s.strand}</span></> },
  { key: 'state', header: 'State', value: s => rank(s.state), cell: s => <Status tone={stateWords[s.state].tone}>{stateWords[s.state].word}</Status> },
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
  { key: 'last_seen', header: 'Last seen', value: s => (s.last_seen ? new Date(s.last_seen) : null), cell: s => format.dateTime(s.last_seen), missing: 'Never' },
]

function Skills({ learner, undoable, rows }: { learner: string; undoable: Undoable; rows: SkillReport[] }) {
  const open = useExpanded({ param: 'open' })
  if (rows.length === 0) return <EmptyState title="No skills seen yet">Every skill is still unobserved: nothing is known either way. Open All skills to see the list.</EmptyState>
  return (
    <DataTable
      caption="Skills"
      columns={skillColumns}
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
    { key: 'answer', header: 'First answer', sort: false, cell: r => <>{r.answer} <span className="text-muted-foreground">({r.correct ? 'right' : 'not right'})</span></> },
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
