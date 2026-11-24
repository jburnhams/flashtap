// The grown-up's question: "Which sounds can Flashtap say, and which do I still need to record?" The Sounds round
// says one phonics sound on its own ("hear /sh/, tap sh"). No browser voice can say one, and a speech model wraps a
// lone consonant in a vowel ("uh-sh-uh", the habit phonics teaching works to undo), so `flashtap voice build` makes
// only the vowel sounds and a person records the consonants here, once each (src/flashtap/voice.py). Until a sound
// has a clip, the browser describes it ("the first sound in ship"), so the round still works, less well.
//
// The finding is how many sounds still need a recording. Each row is one sound: its letters, a word it is heard
// in, where its clip came from, a play button and Record. A sound is named by where it is heard ("the first sound in
// ship"), never by its IPA: a grown-up does not read /θ/, and the app's face (Andika) is bundled without Greek. Recording is strata-react's recorder: Record, Stop,
// listen back and see the level, then Keep it (it replaces the made clip or an earlier recording). The take stays
// in the browser until it is kept, and is kept only on the server that runs Flashtap: a recording is a person's
// voice, so it is never in the repository (AGENTS.md rule 8).
import { useQueryClient } from '@tanstack/react-query'
import { Mic } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Alert, AsyncButton, Button, DataTable, DataView, Dialog, EmptyState, format, InputLevel, MediaPlayer, PageHeader, RowAction, SayAgain, Status, TableSkeleton, TakeLevel, useAsyncAction, useLoad, useRecorder, type Column, type Recording, type Tone } from 'strata-react'
import { api, keys, type SoundRow, type VoiceOut } from '../api'
import { LANG, useVoice } from '../voice'

/** The longest take the server keeps (src/flashtap/voice.py MAX_RECORDING_S): a sound is a second or two. */
const MAX_SECONDS = 10

export function SoundsScreen() {
  const voice = useLoad({ queryKey: keys.voice, queryFn: api.voice, staleTime: Infinity })
  const [recording, setRecording] = useState<SoundRow | null>(null)
  return (
    <>
      <DataView
        state={voice}
        isEmpty={v => v.sounds.length === 0}
        skeleton={<TableSkeleton rows={8} columns={5} />}
        empty={<EmptyState title="No phonics sounds">The content packs list no phonics sequence. Run flashtap content check on the server to see why.</EmptyState>}
      >
        {v => <Sounds v={v} onRecord={setRecording} />}
      </DataView>
      {recording && <RecordSound sound={recording} onClose={() => setRecording(null)} />}
    </>
  )
}

const needsRecording = (s: SoundRow) => !s.vowel && s.source !== 'recorded'

function Sounds({ v, onRecord }: { v: VoiceOut; onRecord: (s: SoundRow) => void }) {
  const toRecord = v.sounds.filter(needsRecording).length
  const withClip = v.sounds.filter(s => s.clip).length
  return (
    <>
      <PageHeader
        title="Sounds"
        scope="The phonics sounds Flashtap says on their own, and where each one's voice comes from"
        finding={{
          text: toRecord
            ? `${format.count(toRecord, 'sound')} to record. A speech model adds a vowel to a consonant on its own, so a person says those; the browser describes them until then.`
            : `Every consonant is recorded; ${withClip} of ${v.sounds.length} sounds have a clip.`,
        }}
      />
      <DataTable caption="Phonics sounds" columns={columns(onRecord)} rows={v.sounds} rowKey={s => s.line} />
    </>
  )
}

const status = (s: SoundRow): { tone: Tone; word: string } =>
  s.source === 'recorded' ? { tone: 'success', word: 'Recorded' }
    : s.source === 'generated' ? { tone: 'neutral', word: 'Made' }
      : s.vowel ? { tone: 'warning', word: 'Not made yet' }
        : { tone: 'warning', word: 'To record' }

const columns = (onRecord: (s: SoundRow) => void): Column<SoundRow>[] => [
  { key: 'graphemes', header: 'Letters', value: s => s.graphemes.join(', '), cell: s => s.graphemes.join(', ') },
  { key: 'example', header: 'Heard in', value: s => s.example, cell: s => s.example },
  { key: 'clip', header: 'Voice', value: s => status(s).word, cell: s => <Status tone={status(s).tone}>{status(s).word}</Status> },
  { key: 'listen', header: 'Listen', hideHeader: true, sort: false, cell: s => <Listen sound={s} /> },
  { key: 'record', header: 'Record', hideHeader: true, sort: false, cell: s => <RowAction label={s.source === 'recorded' ? 'Record again' : 'Record'} subject={s.describe} icon={Mic} onClick={() => onRecord(s)} /> },
]

/** Plays the sound as Play would: its clip, else the browser's description. */
function Listen({ sound }: { sound: SoundRow }) {
  const voice = useVoice()
  return <SayAgain text={voice.words(sound.line)} parts={voice.parts(sound.line)} lang={LANG} verb="Hear" />
}

/** Record one sound, listen back, keep it. */
function RecordSound({ sound, onClose }: { sound: SoundRow; onClose: () => void }) {
  const recorder = useRecorder({ maxSeconds: MAX_SECONDS })
  const [take, setTake] = useState<(Recording & { url: string }) | null>(null)
  useEffect(() => () => { if (take) URL.revokeObjectURL(take.url) }, [take])
  const record = async () => {
    const r = await recorder.start()
    if (r) setTake({ ...r, url: URL.createObjectURL(r.wav) })
  }
  const letters = sound.graphemes.join(', ')
  return (
    <Dialog
      open
      onOpenChange={onClose} // only ever asked to close: it is mounted open and unmounted to close
      title={`Record ${sound.describe}`}
      description={`The sound ${letters} makes, as in ${sound.example}: the sound alone, held for a moment if it can be ("sss"), with no vowel after it ("m", not "muh").`}
    >
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {recorder.recording
            ? <Button variant="default" onClick={recorder.stop}>Stop</Button>
            : <Button variant={take ? 'outline' : 'default'} onClick={() => void record()}>{take ? 'Record again' : 'Record'}</Button>}
          {take && !recorder.recording && <Keep sound={sound} take={take} onKept={onClose} />}
          <Button onClick={onClose}>Cancel</Button>
        </div>
        {recorder.state.phase === 'recording' && <InputLevel level={recorder.state.level} seconds={recorder.state.seconds} maxSeconds={MAX_SECONDS} />}
        {recorder.state.phase === 'failed' && <Alert tone="danger" title="Nothing was recorded" announce>{recorder.state.reason}</Alert>}
        {take && !recorder.recording && (
          <>
            <MediaPlayer label={`Your recording of ${sound.describe}`} kind="audio" src={take.url} />
            <TakeLevel peak={take.peak} lead={`Took ${format.runningTime(take.seconds)}`} />
          </>
        )}
      </div>
    </Dialog>
  )
}

/** Keep the take: it replaces the sound's clip on the server, and the clips list is read again. */
function Keep({ sound, take, onKept }: { sound: SoundRow; take: Recording; onKept: () => void }) {
  const queryClient = useQueryClient()
  const keep = useAsyncAction(async () => {
    await api.keepRecording(sound.line, take.wav)
    await queryClient.invalidateQueries({ queryKey: keys.voice })
    onKept()
  })
  return (
    <>
      <AsyncButton variant="default" phase={keep.phase} error={keep.error} onClick={() => void keep.run()} labels={{ idle: 'Keep this recording', pending: 'Keeping…', done: 'Kept' }} />
      {keep.phase === 'error' && <p className="basis-full type-body-sm text-danger">{keep.error} The recording was not kept.</p>}
    </>
  )
}
