// The grown-up's question: "What does a round look like by default?" Two tabs whose choice lives in
// the URL (?tab=appearance). Play is a form over the server's settings (the kind of round, how many
// choices, how many tries), started from what the server holds inside DataView's ready state and
// saved with one AsyncButton. Appearance is Strata's ColorSchemeChoice, kept in this browser.
import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { AsyncButton, ColorSchemeChoice, DataView, EmptyState, Field, NativeSelect, NumberField, PageHeader, Skeleton, Tabs, useAsyncAction, useLoad } from 'strata-react'
import { api, keys, limits, MODES, type Mode, type ModeInfo, type Settings } from '../api'

const tabs = [
  { value: 'play', label: 'Play' },
  { value: 'appearance', label: 'Appearance' },
]

export function SettingsScreen() {
  return (
    <>
      <PageHeader title="Settings" scope="Saved on the server, for every device that opens Flashtap" />
      <Tabs param="tab" items={tabs} label="Settings">
        {tab => (tab === 'appearance' ? <Appearance /> : <General />)}
      </Tabs>
    </>
  )
}

function General() {
  const settings = useLoad({ queryKey: keys.settings, queryFn: api.settings })
  const modes = useLoad({ queryKey: keys.modes, queryFn: api.modes, staleTime: Infinity })
  return (
    <DataView state={settings} isEmpty={() => false} skeleton={<FormSkeleton />} empty={<EmptyState title="No settings">The server sent none.</EmptyState>}>
      {s => <SettingsForm current={s} modes={modes.status === 'ready' ? modes.data : undefined} />}
    </DataView>
  )
}

/** Mirrors the form: three fields with hints, then the button. */
function FormSkeleton() {
  return (
    <div className="grid max-w-xl gap-6" aria-hidden>
      {[0, 1, 2].map(i => (
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

export function SettingsForm({ current, modes }: { current: Settings; modes?: ModeInfo[] }) {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>(current.mode)
  const [choices, setChoices] = useState<number | null>(Number(current.choices))
  const [tries, setTries] = useState<number | null>(Number(current.tries))

  const save = useAsyncAction(
    async () => {
      await api.saveSettings({ mode, choices: String(choices), tries: String(tries ?? 0) })
      await queryClient.invalidateQueries({ queryKey: keys.settings })
      queryClient.removeQueries({ queryKey: ['round'] }) // rounds already fetched were made with the old settings
    },
    { validate: () => (choices === null ? { choices: 'Enter how many choices a round offers.' } : undefined) },
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void save.run()
  }
  const described = modes?.find(m => m.mode === mode)?.description

  return (
    <form onSubmit={onSubmit} noValidate className="grid max-w-xl gap-6">
      <Field label="Kind of round" hint={described ?? 'Which kind of round Play starts with.'}>
        <NativeSelect value={mode} onChange={e => setMode(e.target.value as Mode)}>
          {MODES.map(m => <option key={m} value={m}>{modes?.find(i => i.mode === m)?.name ?? m}</option>)}
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

function Appearance() {
  return (
    <div className="grid max-w-xl gap-3">
      <ColorSchemeChoice legend="Colour scheme" />
      <p className="type-body-sm text-muted-foreground">Kept in this browser only.</p>
    </div>
  )
}
