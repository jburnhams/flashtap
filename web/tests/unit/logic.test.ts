import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { colorSchemeScript } from 'strata-react'
import { exportUrl, isMode, PLACE_MECHANICS } from '../../src/api'
import { rounds } from '../../src/mocks/fixtures'
import { roundFor } from '../../src/mocks/handlers'
import { arrangedRight, feedback, outcome, placeFeedback, placeOutcome, placeRight, solution } from '../../src/play'

describe('api helpers', () => {
  it('builds the export link under the base and knows the modes', () => {
    expect(exportUrl('ab12')).toBe('/api/learners/ab12/export')
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

  it('says what the round says before any tap, which may not be what it prints', () => {
    expect(feedback(cow, { tapped: [] })).toBe('Find the cow.')
    expect(feedback(rounds.listen, { tapped: [] })).toBe('dog. Which letter does dog start with?')
  })

  it('says only the tap on a malformed round with no right option', () => {
    const none = { ...cow, tries: 1, options: cow.options.map(o => ({ ...o, correct: false })) }
    expect(feedback(none, { tapped: ['pig'] })).toBe('No, that\u2019s a pig.')
  })
})

describe('an arrangement in play', () => {
  const give = rounds.give // 3 ducks from a pile of 5
  const sort = rounds.sort_sounds // bus and bell to b, dog and duck to d

  it('is right when every place holds exactly what it takes', () => {
    expect(arrangedRight(sort, { bus: 'sound_b', bell: 'sound_b', dog: 'sound_d', duck: 'sound_d' })).toBe(true)
    expect(arrangedRight(sort, { bus: 'sound_b', bell: 'sound_d', dog: 'sound_d', duck: 'sound_b' })).toBe(false)
    expect(arrangedRight(sort, { bus: 'sound_b', bell: 'sound_b', dog: 'sound_d' })).toBe(false) // duck still in the pile
    expect(placeRight(sort.places[0], { bus: 'sound_b', bell: 'sound_b' })).toBe(true)
  })

  it('takes any three ducks for three, and says how many were given when it is not', () => {
    expect(arrangedRight(give, { duck1: 'basket', duck4: 'basket', duck5: 'basket' })).toBe(true)
    const four = { duck1: 'basket', duck2: 'basket', duck3: 'basket', duck4: 'basket' }
    expect(placeFeedback(give, four, 1)).toBe('You put 4 in the basket. That’s too many. Try again.')
    expect(placeFeedback(give, { duck1: 'basket' }, 1)).toBe('You put 1 in the basket. That’s not enough. Try again.')
    expect(placeFeedback(give, solution(give), 1)).toBe('Yes! There are 3 ducks in the basket.')
  })

  it('is missed when the checks run out, and then the answer is shown', () => {
    const once = { ...sort, tries: 1 }
    expect(placeOutcome(once, 1, false)).toBe('missed')
    expect(placeOutcome(once, 1, true)).toBe('right')
    expect(placeOutcome(sort, 9, false)).toBe('playing')
    expect(placeFeedback(once, {}, 1)).toBe('Not yet. Here is the answer.')
    expect(placeFeedback(sort, {}, 1)).toBe('Not yet. Try again.')
    expect(solution(sort)).toEqual({ bus: 'sound_b', bell: 'sound_b', dog: 'sound_d', duck: 'sound_d' })
  })
})

describe('the mock server', () => {
  it('answers each mode with its fixed round, and Mixed with Matching', () => {
    expect(roundFor('letters').prompt).toBe('What starts with the letter D?')
    expect(roundFor('mixed')).toEqual(rounds.matching)
    expect(roundFor(null)).toEqual(rounds.matching)
  })

  it('keeps exactly one right option in every one-tap fixture and a solvable arrangement in every placing one', () => {
    for (const r of Object.values(rounds)) {
      if (PLACE_MECHANICS.includes(r.mechanic)) expect(arrangedRight(r, solution(r))).toBe(true)
      else expect(r.options.filter(o => o.correct).map(o => o.id)).toEqual([r.answer])
    }
  })
})

describe('index.html', () => {
  it('inlines Strata’s colour-scheme script, so a dark page does not flash light', () => {
    const html = readFileSync(new URL('../../index.html', import.meta.url), 'utf8')
    expect(html).toContain(colorSchemeScript())
  })
})
