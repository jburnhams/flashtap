import { describe, expect, it, vi } from 'vitest'
import { expectOneFilledButton } from 'strata-react/testing'
import { deleteFails, profileError, profileQuiet, profileUnchecked, strikeFails, tellFails, withdrawFails } from '../../src/mocks/handlers'
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
    // The Seen tab: skills with evidence, and the one a grown-up has spoken for, still Not seen yet by the rounds.
    const rhyme = within(table).getByRole('row', { name: /Hear which words rhyme/ })
    expect(within(rhyme).getByText('Not seen yet')).toBeInTheDocument()
    expect(within(rhyme).getByText('Can do it, says a parent')).toBeInTheDocument()
    expect(within(table).getAllByText('Not seen yet')).toHaveLength(1)
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

  it('records what a grown-up has seen, labelled with who they are', async () => {
    const { user } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('button', { name: 'Say what Fox can do: Count a set of things' }))
    const dialog = await screen.findByRole('dialog', { name: 'What have you seen Fox do?' })
    await user.click(within(dialog).getByRole('radio', { name: /Not yet/ }))
    await user.click(within(dialog).getByRole('radio', { name: /A teacher/ }))
    await user.type(within(dialog).getByRole('textbox', { name: /Note/ }), 'Skips a few when counting')
    expectOneFilledButton(dialog)
    await user.click(within(dialog).getByRole('button', { name: 'Save what you saw' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mock.told).toEqual([{ learner_id: FOX, skill: 'maths.counting.objects', says: 'not_yet', observer: 'teacher', note: 'Skips a few when counting' }])
  })

  it('keeps the dialog open with the reason when saving fails, and Cancel closes it', async () => {
    server.use(tellFails)
    const { user } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('button', { name: 'Say what Fox can do: Count a set of things' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Save what you saw' }))
    expect(await within(dialog).findByText(/Nothing was saved\./)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Say what Fox can do: Count a set of things' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mock.told).toEqual([])
  })

  it('starts the dialog from what was said before, and shows a word left without a note', async () => {
    const { user } = openApp(`/learners/${FOX}`)
    const row = await screen.findByRole('row', { name: /Touch or tag each thing once/ })
    expect(within(row).getByText('Not yet, says a teacher')).toBeInTheDocument()
    expect(within(row).getByText(/^\d+ Nov 2026$/)).toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: 'Say what Fox can do: Touch or tag each thing once' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('radio', { name: /Not yet/ })).toBeChecked()
    expect(within(dialog).getByRole('radio', { name: /A teacher/ })).toBeChecked()
  })

  it('withdraws what was said with Undo, then sends it once the bar goes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { user } = openApp(`/learners/${FOX}`, { user: { advanceTimers: vi.advanceTimersByTime } })
      await user.click(await screen.findByRole('button', { name: 'Withdraw what was said about Hear which words rhyme' }))
      expect(await screen.findByText(/Withdrew “Can do it” for Hear which words rhyme\./)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Withdraw what was said about Hear which words rhyme' })).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Undo' }))
      expect(mock.withdrawn).toEqual([])
      await user.click(screen.getByRole('button', { name: 'Withdraw what was said about Hear which words rhyme' }))
      await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
      expect(mock.withdrawn).toEqual(['f0000000000000000000000000000001'])
    } finally {
      vi.useRealTimers()
    }
  })

  it('says when a withdrawal did not go through', async () => {
    server.use(withdrawFails)
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const { user } = openApp(`/learners/${FOX}`, { user: { advanceTimers: vi.advanceTimersByTime } })
      await user.click(await screen.findByRole('button', { name: 'Withdraw what was said about Hear which words rhyme' }))
      await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
      expect((await screen.findAllByText(/withdrawing it did not go through/)).length).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('shows how they engage as numbers and hypotheses, on its own tab', async () => {
    const { user, router } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('tab', { name: 'Engagement' }))
    expect(router.state.location.search).toBe('?show=engagement')
    const kinds = screen.getByRole('grid', { name: 'Kinds of round' })
    const letters = within(kinds).getByRole('row', { name: /Letters/ })
    expect(within(letters).getByText('0 of 2')).toBeInTheDocument()
    expect(within(letters).getByText(/16\.2\ss/)).toBeInTheDocument()
    expect(within(kinds).getByRole('row', { name: /Give a number/ })).toHaveTextContent('Not offered')
    expect(within(kinds).getByRole('row', { name: /Listen/ })).toHaveTextContent('0 of 2') // offered, never played
    expect(screen.getByText('Letters: rated with the sad face 2 of 3 times.')).toBeInTheDocument()
    expect(screen.getAllByText(/^Could be:/)).toHaveLength(2)
  })

  it('shows how quick each skill is, and a skill held back by a suspected mix-up, without moving either estimate', async () => {
    openApp(`/learners/${FOX}`)
    const table = await screen.findByRole('grid', { name: 'Skills' })
    const counting = within(table).getByRole('row', { name: /Count a set of things/ })
    expect(within(counting).getByText(/^3\.4\ss$/)).toBeInTheDocument()
    expect(within(counting).getByText(/2\.9–4\.2\ss, getting quicker/)).toBeInTheDocument()
    const numerals = within(table).getByRole('row', { name: /Find the numeral for a spoken number/ })
    expect(within(numerals).getByText('Emerging')).toBeInTheDocument()
    expect(within(numerals).getByText('Held back: Confuses 6 and 9')).toBeInTheDocument()
    expect(within(counting).getByText('Which group: 1 of 1 right')).toBeInTheDocument() // its transfer check so far
    expect(within(table).getByRole('row', { name: /See how many without counting/ })).toHaveTextContent(/4\.8\ss1\sanswer/)
    expect(within(table).getAllByText('Not timed yet').length).toBeGreaterThan(0)
  })

  it('says what each wrong answer was and how long each took', async () => {
    openApp(`/learners/${FOX}?open=maths.counting.objects`)
    const rounds = await screen.findByRole('grid', { name: /Rounds that touched/ })
    expect(within(rounds).getByText('a number close to it')).toBeInTheDocument()
    expect(within(rounds).getByText(/^7\.4\ss$/)).toBeInTheDocument()
  })

  it('lists the mix-ups as hypotheses, each with what it rests on and how to check it', async () => {
    const { user, router } = openApp(`/learners/${FOX}`)
    await user.click(await screen.findByRole('tab', { name: 'Mix-ups' }))
    expect(router.state.location.search).toBe('?show=mixups')
    const list = screen.getByRole('list', { name: 'Mix-ups' })
    const items = within(list).getAllByRole('listitem')
    expect(items.map(i => within(i).getByText(/^(Suspected|Could be chance|Cleared|Not seen)$/).textContent)).toEqual(['Suspected', 'Could be chance', 'Cleared', 'Not seen'])
    expect(items[0]).toHaveTextContent(/Offered in 6\srounds; 4 of 4 wrong answers were this one, where luck would give about 1\.3\. Last /)
    expect(items[0]).toHaveTextContent(/To check by hand: 6 and 9 both offered/)
    expect(items[0]).toHaveTextContent(/Rounds Flashtap chooses for Fox offer this mix-up among the choices/)
    expect(items[2]).toHaveTextContent(/Right every time since, with it on offer\./)
    expect(items[2]).not.toHaveTextContent(/To check/)
    expect(items[3]).toHaveTextContent(/Offered in 2\srounds, never chosen\./)
  })

  it('does not claim the rounds check a mix-up no kind of round can offer', async () => {
    server.use(profileUnchecked)
    openApp(`/learners/${FOX}?show=mixups`)
    const items = within(await screen.findByRole('list', { name: 'Mix-ups' })).getAllByRole('listitem')
    expect(items[1]).toHaveTextContent(/To check by hand:/)
    expect(items[1]).not.toHaveTextContent(/Rounds Flashtap chooses/)
  })

  it('says there is nothing to look for yet on the Mix-ups tab of a new learner', async () => {
    openApp(`/learners/${OWL}?show=mixups`)
    expect(await screen.findByText('No mix-ups to look for yet')).toBeInTheDocument()
  })

  it('says nothing has been played yet on the Engagement tab of a new learner', async () => {
    openApp(`/learners/${OWL}?show=engagement`)
    expect(await screen.findByText('Nothing played yet')).toBeInTheDocument()
  })

  it('says no pattern stands out when none does', async () => {
    server.use(profileQuiet)
    openApp(`/learners/${FOX}?show=engagement`)
    expect(await screen.findByText(/No pattern stands out yet\./)).toBeInTheDocument()
  })
})
