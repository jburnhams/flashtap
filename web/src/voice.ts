// The recorded voice (src/flashtap/voice.py): every sentence and phonics sound Flashtap says, made once in one UK
// voice by strata-models, or recorded by a grown-up on the Sounds screen. A sentence is cut into lines exactly as
// the server cuts it (`segments`, both tested against tests/fixtures/voice-segments.json), each line's clip is
// looked up by its text, and strata-react's `speak(parts)` plays them; when any line has no clip the browser's
// voice says the whole sentence (one voice per prompt). A sound with no clip is described ("the first sound in
// ship"), since no browser voice can say /ʃ/ on its own and its letters would give the answer away.
//
// The clips list is one read for the whole app, kept for the session (`staleTime: Infinity`) and refreshed when
// a recording is kept. It is not drawn, so it has no DataView: until it arrives, or if it fails, the browser
// speaks, which is what the app did before there were clips. `ready` lets a screen wait for it before saying a
// round's prompt on its own, so the first prompt is not in a different voice from the rest.
import { createContext, createElement, useContext, useMemo, type ReactNode } from 'react'
import { speak, textOf, useLoad, withBase, type SpeechPart } from 'strata-react'
import { api, keys, type VoiceOut } from './api'

/** Every prompt and answer is said in UK English, the content's dialect. */
export const LANG = 'en-GB'

const SOUND = /(\/[^/\s]+\/)/
const IS_SOUND = /^\/[^/\s]+\/$/
const SENTENCE_END = /(?<=[.?!])\s+/
const EDGE = /^[\s.,;:!?]+|\s+$/g
const NUMBER_LIST = /^\d+(?:, \d+)* and \d+[.?!]$/

/** The lines of a sentence, in order: each `/IPA/` sound alone, the rest cut into sentences, a list of numbers into its numbers. */
export function segments(text: string): string[] {
  const out: string[] = []
  for (const piece of text.split(SOUND)) {
    if (IS_SOUND.test(piece)) {
      out.push(piece)
      continue
    }
    for (const sentence of piece.split(SENTENCE_END)) {
      let s = sentence.split(/\s+/).filter(Boolean).join(' ')
      if (!s.replace(EDGE, '')) continue // a lone "." left between two sounds is not a line
      s = s.replace(/^[ .,;:]+/, '')
      if (NUMBER_LIST.test(s)) out.push(...Array.from(s.matchAll(/\d+/g), m => m[0]))
      else out.push(s)
    }
  }
  return out
}

/** The parts strata-react's `speak` plays: each line with its clip (through the app's base), a sound with no clip described. */
export function partsOf(text: string, voice: VoiceOut | undefined): SpeechPart[] {
  return segments(text).map(line => {
    const clip = voice?.clips[line]
    // a sound's description is a sentence of its own, so the browser pauses after it as it does after a sentence
    const words = IS_SOUND.test(line) ? `${voice?.sounds.find(s => s.line === line)?.describe ?? 'a sound'}.` : line
    return { text: words, clip: clip ? withBase(clip) : null }
  })
}

export type Voice = {
  /** The clips list has arrived, or failed (then the browser speaks): a screen waits for this before speaking unasked. */
  ready: boolean
  parts: (text: string) => SpeechPart[]
  /** Says it now, from the clips when every line has one, else with the browser's voice. */
  say: (text: string) => boolean
  /** The words a sentence is said as, for a button's name: a sound is its description, not /ʃ/. */
  words: (text: string) => string
}

const fallback: Voice = {
  ready: true,
  parts: text => partsOf(text, undefined),
  say: text => speak(partsOf(text, undefined), { lang: LANG }),
  words: text => textOf(partsOf(text, undefined)),
}

const VoiceContext = createContext<Voice>(fallback)

/** Reads the clips list once and gives every screen under it `useVoice()`. */
export function VoiceProvider({ children }: { children: ReactNode }) {
  const load = useLoad({ queryKey: keys.voice, queryFn: api.voice, staleTime: Infinity })
  const data = load.status === 'ready' ? load.data : undefined
  const ready = load.status !== 'loading'
  const voice = useMemo<Voice>(() => ({
    ready,
    parts: text => partsOf(text, data),
    say: text => speak(partsOf(text, data), { lang: LANG }),
    words: text => textOf(partsOf(text, data)),
  }), [data, ready])
  return createElement(VoiceContext.Provider, { value: voice }, children)
}

/** The app's voice: `const voice = useVoice(); voice.say(round.say)`. Outside a VoiceProvider it is the browser's alone. */
export function useVoice(): Voice {
  return useContext(VoiceContext)
}
