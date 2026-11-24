import { afterEach, describe, expect, it } from 'vitest'
import { expectOneFilledButton, fakeMicrophone, installFakeSpeech } from 'strata-react/testing'
import { keepRecordingFails, voiceError } from '../../src/mocks/handlers'
import { openApp, screen, waitFor, within } from '../utils/render'
import { mock, server } from '../utils/server'

/** A sound's row, by its letters (the first column): the table names a sound by where it is heard, never by its IPA. */
const row = (letters: string) => screen.getByRole('row', { name: new RegExp(`^${letters}\\b`) })

describe('Sounds', () => {
  let speech: ReturnType<typeof installFakeSpeech> | undefined
  afterEach(() => speech?.uninstall())

  it('says how many consonants are still to record, and where each sound comes from', async () => {
    openApp('/sounds')
    expect(await screen.findByRole('heading', { level: 1, name: 'Sounds' })).toBeInTheDocument()
    expect(screen.getByText(/^21\ssounds to record\./)).toBeInTheDocument()
    expect(within(row('sh')).getByText('Recorded')).toBeInTheDocument()
    expect(within(row('sh')).getByText('sh')).toBeInTheDocument()
    expect(within(row('p')).getByText('To record')).toBeInTheDocument()
    expect(within(row('ai')).getByText('Not made yet')).toBeInTheDocument()
    expect(within(row('ee')).getByText('Made')).toBeInTheDocument()
  })

  it('plays a recorded sound from its clip, and describes one with no clip', async () => {
    speech = installFakeSpeech([{ lang: 'en-GB', name: 'Daniel' }])
    const { user } = openApp('/sounds')
    await user.click(await screen.findByRole('button', { name: 'Hear: the first sound in ship.' }))
    expect(speech.clips()).toEqual([mock.voice.clips['/ʃ/']])
    await user.click(screen.getByRole('button', { name: 'Hear: the first sound in pan.' }))
    expect(speech.said.at(-1)).toMatchObject({ text: 'the first sound in pan.', clip: null, voice: 'Daniel' })
  })

  it('records a sound, plays it back and keeps it', async () => {
    const { user } = openApp('/sounds', { microphone: fakeMicrophone({ speed: 50 }) })
    await user.click(await screen.findByRole('button', { name: 'Record the first sound in pan' }))
    const dialog = await screen.findByRole('dialog', { name: 'Record the first sound in pan' })
    expect(dialog).toHaveTextContent('no vowel after it')
    await user.click(within(dialog).getByRole('button', { name: 'Record' }))
    await user.click(await within(dialog).findByRole('button', { name: 'Stop' }))
    const keep = await within(dialog).findByRole('button', { name: 'Keep this recording' })
    expectOneFilledButton()
    await user.click(keep)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mock.recordings).toHaveLength(1)
    expect(mock.recordings[0]!.line).toBe('/p/')
    expect(mock.recordings[0]!.bytes).toBeGreaterThan(44)
    expect(await within(row('p')).findByText('Recorded')).toBeInTheDocument()
    expect(screen.getByText(/^20\ssounds to record\./)).toBeInTheDocument()
  })

  it('keeps the dialog open and says so when the recording is not kept', async () => {
    server.use(keepRecordingFails)
    const { user } = openApp('/sounds', { microphone: fakeMicrophone({ speed: 50 }) })
    await user.click(await screen.findByRole('button', { name: 'Record the first sound in net' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Record' }))
    await user.click(await within(dialog).findByRole('button', { name: 'Stop' }))
    await user.click(await within(dialog).findByRole('button', { name: 'Keep this recording' }))
    expect(await within(dialog).findByText(/The recording was not kept\./)).toBeInTheDocument()
    expect(mock.recordings).toEqual([])
  })

  it('says so when every consonant is recorded', async () => {
    for (const s of mock.voice.sounds) if (!s.vowel) Object.assign(s, { source: 'recorded', clip: `api/v1/voice/clips/r${s.phoneme}.wav` })
    openApp('/sounds')
    expect(await screen.findByText(/^Every consonant is recorded; \d+ of 45 sounds have a clip\./)).toBeInTheDocument()
  })

  it('says why nothing was recorded when the microphone is refused', async () => {
    const { user } = openApp('/sounds', { microphone: fakeMicrophone({ refuse: 'NotAllowedError' }) })
    await user.click(await screen.findByRole('button', { name: 'Record the first sound in net' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Record' }))
    expect(await within(dialog).findByText('Nothing was recorded')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /^Keep/ })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('says what failed when the sounds cannot be read', async () => {
    server.use(voiceError)
    openApp('/sounds')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503).')
  })
})
