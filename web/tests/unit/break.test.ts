import { describe, expect, it, vi } from 'vitest'
import { DONE, ROUNDS, roundsFrom, tellParent } from '../../src/screens/BreakScreen'

describe('a break', () => {
  it('takes the rounds from the link, a whole number from 1', () => {
    expect(roundsFrom('5')).toBe(5)
    for (const raw of ['', '0', '-2', '1.5', 'three']) expect(roundsFrom(raw)).toBe(ROUNDS)
  })

  it('tells the page it is framed in, and no one when it is not framed', () => {
    const postMessage = vi.fn()
    tellParent({ parent: { postMessage } } as unknown as Window)
    expect(postMessage).toHaveBeenCalledWith(DONE, '*')
    const alone = { postMessage: vi.fn() } as unknown as Window & { postMessage: ReturnType<typeof vi.fn> }
    Object.assign(alone, { parent: alone })
    tellParent(alone)
    expect(alone.postMessage).not.toHaveBeenCalled()
  })
})
