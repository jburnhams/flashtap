// What happens when a tile is tapped, as plain functions so they are tested without a screen.

import type { Round } from './api'

export interface Turn {
  /** Ids tapped so far, in order. */
  tapped: string[]
}

export type Outcome = 'playing' | 'right' | 'missed'

/** Where a round stands after `turn`: right once the answer is tapped, missed once the tries run out without it. */
export function outcome(round: Pick<Round, 'answer' | 'tries'>, turn: Turn): Outcome {
  if (turn.tapped.includes(round.answer)) return 'right'
  if (round.tries !== null && turn.tapped.length >= round.tries) return 'missed'
  return 'playing'
}

/** What to say after the last tap: the option's own sentence, then, when the round is missed, where the answer was. */
export function feedback(round: Round, turn: Turn): string {
  const last = round.options.find(o => o.id === turn.tapped.at(-1))
  if (!last) return round.prompt
  if (outcome(round, turn) === 'missed') {
    const right = round.options.find(o => o.correct)
    if (!right) return last.feedback
    return `${last.feedback} The right one was ${/^\d+$/.test(right.word) ? right.word : `the ${right.word}`}.`
  }
  return outcome(round, turn) === 'playing' ? `${last.feedback} Try again.` : last.feedback
}
