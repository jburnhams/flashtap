// The grown-up's question: "Who plays here, and what has each of them done?" The finding is how many
// learners there are and when one last played. A learner is a nickname and nothing else: no age,
// birth date, year group, school or photo is asked for or kept (AGENTS.md rule 8, spec §17), and
// what comes next for them is decided by evidence of ability, never by age.
//
// Adding is a one-field form (Field action=, the view's one filled button). Each row opens that
// learner's screen; "Play as" opens Play with the learner chosen, so their rounds are recorded.
// Removing a learner deletes everything held about them and cannot be undone, so it lives on the
// learner's own screen behind a confirm, not as a quick row action here.
import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { AsyncButton, DataTable, DataView, EmptyState, Field, format, Input, PageHeader, Skeleton, TableSkeleton, useAsyncAction, useLoad, type Column } from 'strata-react'
import { api, keys, type LearnerRow } from '../api'

export function LearnersScreen() {
  const learners = useLoad({ queryKey: keys.learners, queryFn: api.learners })
  return (
    <DataView state={learners} isEmpty={() => false} skeleton={<LearnersSkeleton />} empty={null}>
      {rows => (
        <>
          <PageHeader title="Learners" scope="Each learner is a nickname; nothing else about them is kept" finding={{ text: finding(rows) }} />
          <AddLearner />
          {rows.length === 0 ? (
            <EmptyState title="No learners yet">Add a nickname above. Rounds played as that learner are then recorded, and their screen shows what the evidence says for each skill.</EmptyState>
          ) : (
            <DataTable caption="Learners" columns={columns} rows={rows} rowKey={x => x.id} sortParam="sort" initialSort={{ key: 'nickname', dir: 'ascending' }} />
          )}
        </>
      )}
    </DataView>
  )
}

/** Mirrors the screen: the heading and finding, the one-field form, the table. */
function LearnersSkeleton() {
  return (
    <div className="grid gap-8" aria-hidden>
      <div className="grid gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-80" />
      </div>
      <Skeleton className="h-16 w-full max-w-xl" />
      <TableSkeleton rows={3} columns={4} />
    </div>
  )
}

function finding(rows: LearnerRow[]) {
  if (rows.length === 0) return 'Nobody yet: add a learner to start recording rounds.'
  const played = rows.filter(x => x.last_played).sort((a, b) => String(b.last_played).localeCompare(String(a.last_played)))
  const who = format.count(rows.length, 'learner')
  return played.length ? `${who}; ${played[0].nickname} played last, ${format.dateTime(played[0].last_played)}.` : `${who}; no rounds recorded yet.`
}

const columns: Column<LearnerRow>[] = [
  { key: 'nickname', header: 'Learner', value: x => x.nickname, cell: x => <Link to={`/learners/${x.id}`} className="text-primary underline underline-offset-4">{x.nickname}</Link> },
  { key: 'attempts', header: 'Rounds recorded', numeric: true, value: x => x.attempts, cell: x => format.integer(x.attempts) },
  { key: 'last_played', header: 'Last played', value: x => (x.last_played ? new Date(x.last_played) : null), cell: x => format.dateTime(x.last_played), missing: 'Never' },
  { key: 'play', header: 'Play', hideHeader: true, sort: false, cell: x => <Link to={`/?learner=${x.id}`} className="type-label text-primary underline underline-offset-4">Play as {x.nickname}</Link> },
]

function AddLearner() {
  const queryClient = useQueryClient()
  const [nickname, setNickname] = useState('')
  const add = useAsyncAction(
    async (name: string) => {
      await api.addLearner(name)
      setNickname('')
      await queryClient.invalidateQueries({ queryKey: keys.learners })
    },
    { validate: name => (name.trim() ? undefined : { nickname: 'Type a nickname first.' }) },
  )
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void add.run(nickname)
  }
  return (
    <form onSubmit={onSubmit} noValidate className="max-w-xl">
      <Field
        label="Nickname"
        hint="Up to 40 characters. Use a nickname, not a full name."
        error={add.fieldErrors.nickname ?? (add.phase === 'error' ? add.error : undefined)}
        action={<AsyncButton type="submit" variant="default" phase={add.phase} labels={{ idle: 'Add learner', pending: 'Adding…', done: 'Added' }} error={add.error} />}
      >
        <Input value={nickname} maxLength={40} onChange={e => { setNickname(e.target.value); add.clearFieldError('nickname') }} />
      </Field>
    </form>
  )
}
