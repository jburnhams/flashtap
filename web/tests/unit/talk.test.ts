import { beforeEach, describe, expect, it } from 'vitest'
import { rounds } from '../../src/mocks/fixtures'
import { talkFixed, talkWritten } from '../../src/mocks/handlers'
import { feedback, placeFeedback, solution, type Words } from '../../src/play'
import { FIXED, resetTalk, rotate, startVisit, talkOf } from '../../src/talk'

const words = (right: string, retry: string, missed: string): Words => ({ right: () => right, retry: () => retry, missed: () => missed })

describe('the words around a reply', () => {
  const cow = rounds.matching
  const w = words('Brilliant, Fox!', 'Have another look.', 'Good try.')

  it('puts the cheer in place of Yes, and another go in place of Try again', () => {
    expect(feedback(cow, { tapped: ['cow'] }, w)).toBe('Brilliant, Fox! You found the cow.')
    expect(feedback(cow, { tapped: ['pig'] }, w)).toBe('No, that’s a pig. Have another look.')
  })

  it('says the missed line before where the answer was, and nothing extra without one', () => {
    const once = { ...cow, tries: 1 }
    expect(feedback(once, { tapped: ['pig'] }, w)).toBe('No, that’s a pig. Good try. The right one was the cow.')
    expect(feedback(once, { tapped: ['pig'] })).toBe('No, that’s a pig. The right one was the cow.')
  })

  it('does the same for a placing round', () => {
    const give = rounds.give
    expect(placeFeedback(give, solution(give), 1, w)).toBe('Brilliant, Fox! There are 3 ducks in the basket.')
    expect(placeFeedback(give, {}, 1, w)).toBe('You put 0 in the basket. That’s not enough. Have another look.')
    expect(placeFeedback({ ...give, tries: 1 }, {}, 1, w)).toBe('You put 0 in the basket. That’s not enough. Good try. Here is the answer.')
  })

  it('leaves a right reply that does not open with Yes as it is', () => {
    const plain = { ...cow, options: cow.options.map(o => (o.correct ? { ...o, feedback: 'You found the cow.' } : o)) }
    expect(feedback(plain, { tapped: ['cow'] }, w)).toBe('You found the cow.')
  })

  it('asks a pool for a line only when it is said', () => {
    let asked = 0
    const counting: Words = { right: () => { asked += 1; return 'Yes!' }, retry: () => 'Try again.', missed: () => '' }
    feedback(cow, { tapped: ['pig'] }, counting)
    expect(asked).toBe(0)
    feedback(cow, { tapped: ['cow'] }, counting)
    expect(asked).toBe(1)
  })
})

describe('talk', () => {
  beforeEach(resetTalk)
  const pools = { lines: { ...talkFixed.lines, right: ['Yes!', 'Brilliant!', 'Well done, Fox!'], 'intro.counting': ['Now for some counting.'] } }

  it('goes round a pool from where it starts, so a line comes back only after the rest', () => {
    expect([0, 1, 2, 3].map(n => rotate(['a', 'b', 'c'], 1, n))).toEqual(['b', 'c', 'a', 'b'])
    const t = talkOf('fox', pools, () => 0.5)
    expect([t.right(), t.right(), t.right(), t.right()]).toEqual(['Brilliant!', 'Well done, Fox!', 'Yes!', 'Brilliant!'])
  })

  it('carries on across a new Talk for the same learner (a round remounted), and apart for another', () => {
    expect(talkOf('fox', pools, () => 0).right()).toBe('Yes!')
    expect(talkOf('fox', pools, () => 0.9).right()).toBe('Brilliant!')
    expect(talkOf('owl', pools, () => 0).right()).toBe('Yes!')
  })

  it('says hello once a visit, then an intro only when the kind changes', () => {
    const t = talkOf('fox', talkWritten, () => 0)
    expect(t.opening('counting')).toBe('Hello, Fox! Let’s play. Now for some counting.')
    expect(t.opening('counting')).toBe('')
    expect(t.opening('give')).toBe('Time to fill the basket.')
    expect(t.opening('letters')).toBe('') // no pool for it: nothing is said
  })

  it('says the fixed lines with no pools, and nothing more', () => {
    const t = talkOf('fox', undefined)
    expect([t.right(), t.retry(), t.missed(), t.opening('counting'), t.pick(), t.break()]).toEqual([FIXED.right, FIXED.retry, '', '', FIXED.pick, FIXED.break])
  })
})

describe('a new visit', () => {
  beforeEach(resetTalk)

  it('says hello again and introduces its first kind, carrying on round each pool', () => {
    const pools = { lines: { ...talkWritten.lines, right: ['Yes!', 'Brilliant!'] } }
    const t = talkOf('fox', pools, () => 0)
    expect(t.opening('counting')).not.toBe('')
    expect(t.right()).toBe('Yes!')
    startVisit('fox')
    const again = talkOf('fox', pools, () => 0)
    expect(again.opening('counting')).toBe('Hello, Fox! Let’s play. Now for some counting.')
    expect(again.right()).toBe('Brilliant!')
  })
})
