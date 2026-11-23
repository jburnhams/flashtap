// The grown-up's question: "What can Flashtap teach, and how much of the curriculum does that cover?"
// The finding is the coverage (goals mapped, goals set aside with a reason) and, while any pack is a
// draft, that a teacher has not yet checked it. Three tabs whose choice lives in the URL (?tab=):
// Skills (each skill with its strand, the curriculum stages that name it and the rounds that play
// it; a row opens in place to show its description, what it needs, what it leads to and its known misconceptions),
// Curriculum (each goal statement and the skills it maps to, or why it is out of scope) and
// Phonics (the sequence's sets in order, with the words each set makes readable). Stages are
// labels from the curriculum, never gates: nothing here says who may play what.
import { DataTable, DataView, EmptyState, format, Metric, MetricStrip, PageHeader, Status, TableSkeleton, Tabs, useExpanded, useLoad, type Column } from 'strata-react'
import { api, keys, type ContentSummary, type EdgeRow, type ObjectiveRow, type PhonicsSetRow, type SkillRow } from '../api'

const tabs = [
  { value: 'skills', label: 'Skills' },
  { value: 'curriculum', label: 'Curriculum' },
  { value: 'phonics', label: 'Phonics' },
]

export function ContentScreen() {
  const content = useLoad({ queryKey: keys.content, queryFn: api.content, staleTime: Infinity })
  return (
    <DataView
      state={content}
      isEmpty={c => c.skills.length === 0}
      skeleton={<TableSkeleton rows={8} columns={4} />}
      empty={<EmptyState title="No content packs">The server has no skills to show. Run flashtap content check on the server to see why.</EmptyState>}
    >
      {c => <Content c={c} />}
    </DataView>
  )
}

function Content({ c }: { c: ContentSummary }) {
  const mapped = c.objectives.filter(o => o.skills.length > 0).length
  const drafts = c.packs.filter(p => p.status === 'draft').length
  const played = c.skills.filter(s => s.modes.length > 0).length
  return (
    <>
      <PageHeader
        title="Content"
        scope="Skills, curriculum goals and phonics from the content packs"
        finding={{
          text: drafts
            ? `${drafts} of ${c.packs.length} packs are drafts: written from the sources, not yet checked by a teacher.`
            : `${mapped} of ${c.objectives.length} curriculum goals map to skills; the rest are set aside with a reason.`,
        }}
      />
      <MetricStrip label="Content at a glance">
        <Metric label="Skills" value={format.integer(c.skills.length)} note={`${played} played in a round today`} />
        <Metric label="Curriculum goals" value={`${mapped} of ${c.objectives.length}`} note="mapped to skills" />
        <Metric label="Phonics sets" value={format.integer(c.phonics.reduce((n, p) => n + p.sets.length, 0))} note="taught in order" />
      </MetricStrip>
      <Tabs param="tab" items={tabs} label="Content">
        {tab => (tab === 'curriculum' ? <Curriculum rows={c.objectives} /> : tab === 'phonics' ? <Phonics c={c} /> : <Skills rows={c.skills} />)}
      </Tabs>
    </>
  )
}

const list = (xs: string[]) => (xs.length ? xs.join(', ') : format.missing)

const skillColumns: Column<SkillRow>[] = [
  { key: 'title', header: 'Skill', value: s => s.title },
  { key: 'strand', header: 'Strand', value: s => `${s.domain}: ${s.strand}`, cell: s => <><span>{s.strand}</span><span className="block type-caption text-muted-foreground">{s.domain}</span></> },
  { key: 'stages', header: 'Curriculum', value: s => list(s.stages.map(x => x.toUpperCase())) },
  { key: 'modes', header: 'Played in', value: s => list(s.modes) },
]

function Skills({ rows }: { rows: SkillRow[] }) {
  const open = useExpanded({ param: 'open' })
  return (
    <DataTable
      caption="Skills"
      columns={skillColumns}
      rows={rows}
      rowKey={s => s.id}
      sortParam="sort"
      initialSort={{ key: 'strand', dir: 'ascending' }}
      expansion={{ ...open, rowLabel: s => `Links of ${s.title}`, detail: s => <SkillDetail s={s} /> }}
    />
  )
}

const relation: Record<string, string> = {
  prerequisite_strong: 'needed first',
  facilitates: 'helps',
  part_of: 'part of',
  related_to: 'related',
  confounded_by: 'errors may come from',
}

function Edges({ title, edges }: { title: string; edges: EdgeRow[] }) {
  return (
    <div className="grid content-start gap-1">
      <h3 className="type-label">{title}</h3>
      {edges.length === 0 ? (
        <p className="type-body-sm text-muted-foreground">None</p>
      ) : (
        <ul className="grid gap-1 type-body-sm">
          {edges.map(e => (
            <li key={`${e.relation}-${e.skill}`}>
              <span className="text-muted-foreground">{relation[e.relation]}:</span> {e.skill} <span className="text-muted-foreground">({e.confidence} confidence; {e.source})</span>
              {e.note && <span className="block type-caption text-muted-foreground">{e.note}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function SkillDetail({ s }: { s: SkillRow }) {
  return (
    <div className="grid gap-4 py-2 md:grid-cols-3">
      <p className="type-body-sm md:col-span-3">{s.description}</p>
      <Edges title="Builds on" edges={s.needs} />
      <Edges title="Leads to" edges={s.leads_to} />
      <div className="grid content-start gap-1">
        <h3 className="type-label">Known misconceptions</h3>
        <p className="type-body-sm">{list(s.misconceptions)}</p>
      </div>
    </div>
  )
}

const objectiveColumns: Column<ObjectiveRow>[] = [
  { key: 'goal', header: 'Goal', value: o => `${o.area}: ${o.goal}`, cell: o => <><span>{o.goal}</span><span className="block type-caption text-muted-foreground">{o.area}, {o.stage.toUpperCase()}</span></> },
  { key: 'text', header: 'Statement', value: o => o.text },
  {
    key: 'skills',
    header: 'Mapped to',
    sort: false,
    cell: o =>
      o.out_of_scope ? (
        <><Status tone="neutral">Out of scope</Status><span className="block type-caption text-muted-foreground">{o.out_of_scope}</span></>
      ) : (
        <><span>{o.skills.join(', ')}</span>{o.note && <span className="block type-caption text-muted-foreground">{o.note}</span>}</>
      ),
  },
]

function Curriculum({ rows }: { rows: ObjectiveRow[] }) {
  return <DataTable caption="Curriculum goals" columns={objectiveColumns} rows={rows} rowKey={o => o.id} />
}

const setColumns: Column<PhonicsSetRow>[] = [
  { key: 'title', header: 'Set', sort: false, cell: s => s.title },
  { key: 'gpcs', header: 'Letters and sounds', sort: false, cell: s => s.gpcs.map(g => `${g.grapheme} /${g.phoneme}/`).join(', ') },
  { key: 'words', header: 'Words now readable', sort: false, cell: s => list(s.words) },
]

function Phonics({ c }: { c: ContentSummary }) {
  return (
    <div className="grid gap-8">
      {c.phonics.map(p => (
        <section key={p.id} className="grid gap-3">
          <h2 className="type-heading">{p.title}</h2>
          <p className="type-body-sm text-muted-foreground">Taught in this order ({p.dialect}). Another programme is another sequence; a learner follows one.</p>
          <DataTable caption={`${p.title} sets`} columns={setColumns} rows={p.sets} rowKey={s => s.id} />
        </section>
      ))}
    </div>
  )
}
