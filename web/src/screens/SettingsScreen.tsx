// The grown-up's question: "What does a round look like by default?" Three tabs whose choice lives in
// the URL (?tab=appearance). Play is a form over the server's settings (the kind of round, how many
// choices, how many tries), started from what the server holds inside DataView's ready state and
// saved with one AsyncButton. Sessions holds the limits of a session the engine plans ("Chosen for
// them"): its rounds and minutes, how often a break is offered, and how often the learner picks
// between two activities or is asked how a round was (spec §11, §12: limits are the grown-up's, never
// traded against engagement). A session keeps the settings it started with, so a change applies from
// the next one. Appearance is Strata's ColorSchemeChoice, kept in this browser.
import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { AsyncButton, ColorSchemeChoice, DataView, EmptyState, Field, NativeSelect, NumberField, PageHeader, Skeleton, Tabs, useAsyncAction, useLoad } from 'strata-react'
import { api, keys, limits, MODES, type Mode, type ModeInfo, type Settings } from '../api'

const tabs = [
  { value: 'play', label: 'Play' },
  { value: 'sessions', label: 'Sessions' },
  { value: 'appearance', label: 'Appearance' },
]

export function SettingsScreen() {
  return (
    <>
      <PageHeader title="Settings" scope="Saved on the server, for every device that opens Flashtap" />
      <Tabs param="tab" items={tabs} label="Settings">
        {tab => (tab === 'appearance' ? <Appearance /> : tab === 'sessions' ? <Sessions /> : <General />)}
      </Tabs>
    </>
  )
}

function General() {
  const settings = useLoad({ queryKey: keys.settings, queryFn: api.settings })
  const modes = useLoad({ queryKey: keys.modes, queryFn: api.modes, staleTime: Infinity })
  return (
    <DataView state={settings} isEmpty={() => false} skeleton={<FormSkeleton />} empty={<EmptyState title="No settings">The server sent none.</EmptyState>}>
      {s => (
        <DataView state={modes} isEmpty={m => m.length === 0} skeleton={<FormSkeleton />} empty={<EmptyState title="No kinds of round">The server listed none.</EmptyState>}>
          {m => <SettingsForm current={s} modes={m} />}
        </DataView>
      )}
    </DataView>
  )
}

/** Mirrors the form: `fields` fields with hints, then the button. */
function FormSkeleton({ fields = 3 }: { fields?: number }) {
  return (
    <div className="grid max-w-xl gap-6" aria-hidden>
      {Array.from({ length: fields }, (_, i) => (
        <div key={i} className="grid gap-1.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ))}
      <Skeleton className="h-9 w-32" />
    </div>
  )
}

export function SettingsForm({ current, modes }: { current: Settings; modes: ModeInfo[] }) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>(current.mode)
  const [choices, setChoices] = useState<number | null>(current.choices)
  const [tries, setTries] = useState<number | null>(current.tries)

  const save = useAsyncAction(
    async () => {
      await api.saveSettings({ mode, choices: choices as number, tries: tries ?? 0 }) // not null: validate refused that before this runs
      await queryClient.invalidateQueries({ queryKey: keys.settings })
      queryClient.removeQueries({ queryKey: ['round'] }) // rounds already fetched were made with the old settings
    },
    { validate: () => (choices === null ? { choices: 'Enter how many choices a round offers.' } : undefined) },
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void save.run()
  }
  const described = modes.find(m => m.mode === mode)?.description

  return (
    <form onSubmit={onSubmit} noValidate className="grid max-w-xl gap-6">
      <Field label="Kind of round" hint={described ?? 'Which kind of round Play starts with.'}>
        <NativeSelect value={mode} onChange={e => setMode(e.target.value as Mode)}>
          {MODES.map(m => <option key={m} value={m}>{modes.find(i => i.mode === m)?.name ?? m}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Choices" hint={`Pictures or numbers in a round, ${limits.minChoices} to ${limits.maxChoices}. Fewer is easier.`} error={save.fieldErrors.choices}>
        <NumberField value={choices} onChange={v => { setChoices(v); save.clearFieldError('choices') }} min={limits.minChoices} max={limits.maxChoices} step={1} />
      </Field>
      <Field label="Tries" hint="Taps before a round shows the answer. 0 means keep trying until it is found.">
        <NumberField value={tries} onChange={setTries} min={0} max={limits.maxChoices - 1} step={1} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <AsyncButton type="submit" variant="default" phase={save.phase} error={save.error} labels={{ idle: 'Save settings', pending: 'Saving…', done: 'Saved' }} />
        {save.phase === 'error' && <p className="type-body-sm text-danger">{save.error} The settings were not changed.</p>}
      </div>
    </form>
  )
}

function Sessions() {
  const settings = useLoad({ queryKey: keys.settings, queryFn: api.settings })
  return (
    <DataView state={settings} isEmpty={() => false} skeleton={<FormSkeleton fields={5} />} empty={<EmptyState title="No settings">The server sent none.</EmptyState>}>
      {s => <SessionsForm current={s} />}
    </DataView>
  )
}

type SessionKey = 'session_rounds' | 'session_minutes' | 'break_every' | 'choice_every' | 'rate_every'

/** Each field: its label, hint and range; 0 means never where it is allowed. */
const sessionFields: { key: SessionKey; label: string; hint: string; min: number; max: number }[] = [
  { key: 'session_rounds', label: 'Rounds in a session', hint: 'The session ends after this many, 1 to 100.', min: 1, max: 100 },
  { key: 'session_minutes', label: 'Minutes in a session', hint: 'Or after this many minutes, 1 to 120, whichever comes first.', min: 1, max: 120 },
  { key: 'break_every', label: 'Break every', hint: 'Rounds between offered breaks. 0 for none: a break is still offered after three misses in a row.', min: 0, max: 100 },
  { key: 'choice_every', label: 'Their choice every', hint: 'Rounds between picking one of two activities themselves. 0 for never.', min: 0, max: 20 },
  { key: 'rate_every', label: 'Ask how it was every', hint: 'Rounds between the three faces after a round, which they can leave. 0 for never.', min: 0, max: 20 },
]

export function SessionsForm({ current }: { current: Settings }) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<SessionKey, number | null>>(() => ({
    session_rounds: current.session_rounds,
    session_minutes: current.session_minutes,
    break_every: current.break_every,
    choice_every: current.choice_every,
    rate_every: current.rate_every,
  }))
  const save = useAsyncAction(
    async () => {
      await api.saveSettings(values as Record<SessionKey, number>) // not null: validate refused that before this runs
      await queryClient.invalidateQueries({ queryKey: keys.settings })
    },
    { validate: () => {
      const missing = sessionFields.filter(f => values[f.key] === null)
      return missing.length ? Object.fromEntries(missing.map(f => [f.key, `Enter ${f.label.toLowerCase()}.`])) : undefined
    } },
  )
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void save.run()
  }
  return (
    <form onSubmit={onSubmit} noValidate className="grid max-w-xl gap-6">
      <p className="type-body-sm text-muted-foreground">For sessions chosen for them. A session keeps the settings it started with, so a change applies from the next one.</p>
      {sessionFields.map(f => (
        <Field key={f.key} label={f.label} hint={f.hint} error={save.fieldErrors[f.key]}>
          <NumberField value={values[f.key]} onChange={v => { setValues(x => ({ ...x, [f.key]: v })); save.clearFieldError(f.key) }} min={f.min} max={f.max} step={1} />
        </Field>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <AsyncButton type="submit" variant="default" phase={save.phase} error={save.error} labels={{ idle: 'Save session settings', pending: 'Saving…', done: 'Saved' }} />
        {save.phase === 'error' && <p className="type-body-sm text-danger">{save.error} The settings were not changed.</p>}
      </div>
    </form>
  )
}

function Appearance() {
  return (
    <div className="grid max-w-xl gap-3">
      <ColorSchemeChoice legend="Colour scheme" />
      <p className="type-body-sm text-muted-foreground">Kept in this browser only.</p>
    </div>
  )
}
