// A skill's transfer check in words, for the Learner screen: its transfer kind is a second form of the skill held
// out of practice, and Generalised needs that check passed (src/flashtap/learners/transfer.py; spec §13).
import type { SkillReport } from './api'

/** How the skill has done in its transfer kind (a second form of it, held out of practice): what Generalised rests
 * on, said under the state. Empty while there is nothing to say: no transfer kind, or none tried and not yet due. */
export function transferNote(s: SkillReport): string {
  const t = s.transfer
  if (!t) return ''
  if (t.passed) return `Carries over: right in ${t.name}`
  if (t.tried > 0) return `${t.name}: ${t.right} of ${t.tried} right`
  return s.state === 'independent' ? `Not yet checked in ${t.name}` : ''
}
