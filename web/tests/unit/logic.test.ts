import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { colorSchemeScript } from 'strata-react'
import { isMode, roundUrl, withBase } from '../../src/api'
import { rounds } from '../../src/mocks/fixtures'
import { roundFor } from '../../src/mocks/handlers'
import { feedback, outcome } from '../../src/play'
import { pickVoice, say } from '../../src/speech'

describe('api helpers', () => {
  it('builds URLs under the base and knows the modes', () => {
    expect(withBase('/api/health')).toBe('/api/health')
    expect(withBase('relative')).toBe('relative')
    expect(roundUrl('counting')).toBe('/api/round?mode=counting')
    expect(isMode('letters')).toBe(true)
    expect(isMode('spelling')).toBe(false)
    expect(isMode(null)).toBe(false)
  })
})

describe('a round in play', () => {
  const cow = rounds.matching

  it('is right once the answer is tapped, and says so', () => {
    const turn = { tapped: ['pig', 'cow'] }
    expect(outcome(cow, turn)).toBe('right')
    expect(feedback(cow, turn)).toBe('Yes! You found the cow.')
  })

  it('asks to try again after a wrong tap while tries remain', () => {
    expect(outcome(cow, { tapped: ['pig'] })).toBe('playing')
    expect(feedback(cow, { tapped: ['pig'] })).toBe('No, that’s a pig. Try again.')
    expect(outcome({ ...cow, tries: 2 }, { tapped: ['pig'] })).toBe('playing')
  })

  it('is missed when the tries run out, and names the answer', () => {
    const one = { ...cow, tries: 1 }
    expect(outcome(one, { tapped: ['duck'] })).toBe('missed')
    expect(feedback(one, { tapped: ['duck'] })).toBe('No, that’s a duck. The right one was the cow.')
    expect(feedback({ ...rounds.counting, tries: 1 }, { tapped: ['n5'] })).toBe('No, that’s 5. The right one was 3.')
  })

  it('says the prompt before any tap', () => {
    expect(feedback(cow, { tapped: [] })).toBe('Find the cow.')
  })

  it('says only the tap on a malformed round with no right option', () => {
    const none = { ...cow, tries: 1, options: cow.options.map(o => ({ ...o, correct: false })) }
    expect(feedback(none, { tapped: ['pig'] })).toBe('No, that\u2019s a pig.')
  })
})

describe('speech', () => {
  it('says nothing where the browser has no speech', () => {
    expect(say('Hello')).toBe(false)
  })

  it('prefers a UK English voice, then any English one', () => {
    const us = { lang: 'en-US', name: 'US' }
    const gb = { lang: 'en-GB', name: 'GB' }
    const fr = { lang: 'fr-FR', name: 'FR' }
    expect(pickVoice([fr, us, gb])).toBe(gb)
    expect(pickVoice([fr, us])).toBe(us)
    expect(pickVoice([fr])).toBeUndefined()
  })
})

describe('the mock server', () => {
  it('answers each mode with its fixed round, and Mixed with Matching', () => {
    expect(roundFor('letters').prompt).toBe('What starts with the letter D?')
    expect(roundFor('mixed')).toEqual(rounds.matching)
    expect(roundFor(null)).toEqual(rounds.matching)
  })

  it('keeps exactly one right option in every fixture, as the server guarantees', () => {
    for (const r of Object.values(rounds)) expect(r.options.filter(o => o.correct).map(o => o.id)).toEqual([r.answer])
  })
})

describe('index.html', () => {
  it('inlines Strata’s colour-scheme script, so a dark page does not flash light', () => {
    const html = readFileSync(new URL('../../index.html', import.meta.url), 'utf8')
    expect(html).toContain(colorSchemeScript())
  })
})
