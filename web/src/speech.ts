// Prompts and feedback said aloud with the browser's own speech (ported from the library's
// audioService.ts). A learner who cannot read yet still needs the prompt, so every round is spoken, and Replay
// says it again. Browser voices differ by device and cannot say an isolated sound such as /m/;
// recorded UK English clips replace this for phonics (docs/implementation-plan.md, decision 4).

/** The voice to use: UK English first (the spec's default dialect), then any English voice. */
export function pickVoice(voices: readonly Pick<SpeechSynthesisVoice, 'lang' | 'name'>[]) {
  return voices.find(v => v.lang === 'en-GB') ?? voices.find(v => v.lang.startsWith('en'))
}

/** Say `text`, cutting off anything still being said. Does nothing where the browser has no speech (jsdom, some kiosks). */
export function say(text: string) {
  const synth = typeof window === 'undefined' ? undefined : window.speechSynthesis
  if (!synth || typeof SpeechSynthesisUtterance === 'undefined') return false
  synth.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const voice = pickVoice(synth.getVoices())
  if (voice) u.voice = voice as SpeechSynthesisVoice
  u.lang = voice?.lang ?? 'en-GB'
  u.rate = 0.9 // a little slower than conversation, for early readers and listeners
  synth.speak(u)
  return true
}
