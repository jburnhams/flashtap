import { afterEach, describe, expect, it } from 'vitest'
import { installFakeSpeech, renderWithStrata } from 'strata-react/testing'
import { screen } from '@testing-library/react'
import { useVoice } from '../../src/voice'

// Outside the app's VoiceProvider (a story of one part, a screen rendered alone) the voice is the browser's: no clips
// list is read, and a sound is described, never spelled out.
function Probe() {
  const voice = useVoice()
  return <button onClick={() => voice.say('Listen. /ʃ/')}>{voice.words('Listen. /ʃ/')} {voice.parts('Try again.')[0]?.clip ?? 'no clip'}</button>
}

describe('useVoice outside the app', () => {
  let speech: ReturnType<typeof installFakeSpeech>
  afterEach(() => speech.uninstall())

  it('speaks with the browser alone', () => {
    speech = installFakeSpeech([{ lang: 'en-GB', name: 'Daniel' }])
    renderWithStrata(<Probe />)
    const b = screen.getByRole('button', { name: 'Listen. a sound. no clip' })
    b.click()
    expect(speech.said).toMatchObject([{ text: 'Listen. a sound.', clip: null, lang: 'en-GB' }])
  })
})
