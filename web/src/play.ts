// What happens when a tile is tapped, as plain functions so they are tested without a screen.

import type { Place, Round } from './api'

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
  if (!last) return round.say
  if (outcome(round, turn) === 'missed') {
    const right = round.options.find(o => o.correct)
    if (!right) return last.feedback
    return `${last.feedback} The right one was ${/^\d+$/.test(right.word) ? right.word : `the ${right.word}`}.`
  }
  return outcome(round, turn) === 'playing' ? `${last.feedback} Try again.` : last.feedback
}

// Placing rounds (give a number, order, match, sort): the learner arranges pieces, then checks.

/** Where each piece is: piece id to place id; a piece with no entry is in the pile. */
export type Placement = Readonly<Record<string, string | undefined>>

const inside = (placement: Placement, place: string) => Object.keys(placement).filter(k => placement[k] === place)

/** Whether a place holds exactly what it should: `holds` pieces, all of them ones it takes. */
export function placeRight(place: Place, placement: Placement) {
  const here = inside(placement, place.id)
  return here.length === place.holds && here.every(k => place.takes.includes(k))
}

/** The arrangement answers the round when every place is right (src/flashtap/mechanics.py `arranged_right`). */
export function arrangedRight(round: Pick<Round, 'places'>, placement: Placement) {
  return round.places.every(p => placeRight(p, placement))
}

/** The right arrangement: each place filled with the first pieces it takes. Shown once the checks run out. */
export function solution(round: Pick<Round, 'places'>): Placement {
  return Object.fromEntries(round.places.flatMap(p => p.takes.slice(0, p.holds).map(k => [k, p.id])))
}

/** Where a placing round stands after `checks` checks, the last of which was `right` or not. */
export function placeOutcome(round: Pick<Round, 'tries'>, checks: number, right: boolean): Outcome {
  if (right) return 'right'
  if (round.tries !== null && checks >= round.tries) return 'missed'
  return 'playing'
}

/** What to say after a check. Giving a number says how many were given, the skill being stopping at the number. */
export function placeFeedback(round: Round, placement: Placement, checks: number): string {
  if (arrangedRight(round, placement)) return round.done_feedback
  const missed = placeOutcome(round, checks, false) === 'missed'
  let said = 'Not yet.'
  if (round.mechanic === 'give_n') {
    const basket = round.places[0]
    const given = inside(placement, basket.id).length
    said = `You put ${given} in ${basket.word}. ${given > basket.holds ? 'That’s too many.' : 'That’s not enough.'}`
  }
  return missed ? `${said} Here is the answer.` : `${said} Try again.`
}
