// A stand-in for the browser's speech (window.speechSynthesis): jsdom has none, and it is a true
// external (the device's voices), so the tests record what would have been said instead.
export function installSpeech(voices: { lang: string; name: string }[] = [{ lang: 'en-GB', name: 'Daniel' }]) {
  const said: { text: string; lang: string; voice?: string }[] = []
  class Utterance { text: string; lang = ''; rate = 1; voice?: { name: string }; constructor(text: string) { this.text = text } }
  const synth = {
    cancel: () => {},
    getVoices: () => voices,
    speak: (u: Utterance) => { said.push({ text: u.text, lang: u.lang, voice: u.voice?.name }) },
  }
  Object.defineProperty(window, 'speechSynthesis', { value: synth, configurable: true })
  Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', { value: Utterance, configurable: true, writable: true })
  return {
    said,
    remove: () => {
      Reflect.deleteProperty(window, 'speechSynthesis')
      Reflect.deleteProperty(globalThis, 'SpeechSynthesisUtterance')
    },
  }
}
