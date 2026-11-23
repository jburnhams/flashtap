import { describe, expect, it, vi } from 'vitest'
import { expectOneFilledButton } from 'strata-react/testing'
import { deleteFails, profileError, strikeFails } from '../../src/mocks/handlers'
import { act, openApp, screen, waitFor, within } from '../utils/render'
import { mock, server } from '../utils/server'

const FOX = 'a'.repeat(32)
const OWL = 'b'.repeat(32)

describe('A learner', () => {
  it('leads with how many skills stand where, with both estimators per skill', async () => {
    openApp(`/learners/${FOX}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Fox' })).toBeInTheDocument()
    expect(screen.getByText(/1\sskill independent or beyond, 9 on the way, 3 not seen yet\./)).toBeInTheDocument()
    const table = screen.getByRole('grid', { name: 'Skills' })
    const counting = within(table).getByRole('row', { name: /Count a set of things/ })
    expect(within(counting).getByText('Independent')).toBeInTheDocument()
    expect(within(counting).getByText('5 of 5')).toBeInTheDocument()
    expect(within(table).queryByText('Not seen yet')).not.toBeInTheDocument() // the Seen tab
    expect(screen.getByRole('link', { name: 'Export' })).toHaveAttribute('href', `/api/learners/${FOX}/export`)
    expect(screen.getByText(/bkt@1: Bayesian knowledge tracing/)).toBeInTheDocument()
    expectOneFilledButton()
  })

  it('keeps unobserved apart from not mastered, on the All skills tab', async () => {
    const { user, router } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('tab', { name: 'All skills' }))
    expect(router.state.location.search).toBe('?show=all')
    expect(screen.getAllByText('Not seen yet')).toHaveLength(3)
  })

  it('opens a skill to the rounds behind it, and why each did or did not count', async () => {
    const { user, router } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('button', { name: 'Evidence for Count a set of things' }))
    expect(router.state.location.search).toContain('open=maths.counting.objects')
    const rounds = await screen.findByRole('grid', { name: /Rounds that touched/ })
    expect(within(rounds).getByText(/No: could be Find the numeral for a spoken number, not yet shown/)).toBeInTheDocument()
    expect(within(rounds).getByText(/No: struck out: someone else was playing/)).toBeInTheDocument()
    expect(within(rounds).getAllByText('Yes').length).toBeGreaterThan(3)
  })

  it('strikes a round out with Undo, then sends it', async () => {
    const { user } = openApp(`/learners/${FOX}?open=maths.counting.objects`)
    const rounds = await screen.findByRole('grid', { name: /Rounds that touched/ })
    const first = within(rounds).getAllByRole('button', { name: /^Strike out the Counting round/ })[0]
    await user.click(first)
    expect(await screen.findByText(/Struck out the Counting round from/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Undo' }))
    expect(mock.struck).toEqual([])
    await user.click(within(rounds).getAllByRole('button', { name: /^Strike out the Counting round/ })[0])
    await user.click(within(rounds).getAllByRole('button', { name: /^Strike out the Counting round/ })[0]) // a second commits the first
    await waitFor(() => expect(mock.struck).toHaveLength(1))
    expect(mock.struck[0].reason).toBe('struck out on the Learner screen')
    await user.click(screen.getByRole('button', { name: 'Undo' })) // nothing left to commit when the test unmounts the screen
  })

  it('says when a strike did not go through, once its Undo window closes', async () => {
    server.use(strikeFails)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { user } = openApp(`/learners/${FOX}?open=maths.counting.objects`, { user: { advanceTimers: vi.advanceTimersByTime } })
      const rounds = await screen.findByRole('grid', { name: /Rounds that touched/ })
      await user.click(within(rounds).getAllByRole('button', { name: /^Strike out the Counting round/ })[0])
      await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
      expect((await screen.findAllByText(/striking it out did not go through/)).length).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('deletes a learner only after a confirm, then goes back to the list', async () => {
    const { user, router } = openApp(`/learners/${OWL}`)
    expect(await screen.findByText(/No rounds recorded yet: choose Owl on Play/)).toBeInTheDocument()
    expect(screen.getByText('No skills seen yet')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    const dialog = await screen.findByRole('alertdialog', { name: 'Delete Owl and everything recorded?' })
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(mock.learners).toHaveLength(3)
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete Owl' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/learners'))
    expect(mock.learners.map(x => x.nickname)).toEqual(['Fox', 'Hare'])
  })

  it('keeps the dialog open with the reason when the delete fails', async () => {
    server.use(deleteFails)
    const { user } = openApp(`/learners/${OWL}`)
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    const dialog = await screen.findByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete Owl' }))
    expect(await within(dialog).findByText(/503|unavailable|down/i)).toBeInTheDocument()
  })

  it('says what happened when the learner is gone', async () => {
    server.use(profileError)
    openApp('/learners/nobody')
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('This learner could not be shown')).toBeInTheDocument()
    expect(within(alert).getByRole('link', { name: 'Learners' })).toHaveAttribute('href', '/learners')
  })
})
