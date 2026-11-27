import { describe, expect, it, vi } from 'vitest'
import { learnersError, nextUnreachable } from '../../src/mocks/handlers'
import { openApp, screen } from '../utils/render'
import { mock, server } from '../utils/server'

const FOX = 'a'.repeat(32)
const tile = (word: string) => new RegExp(`^${word}(,|$)`)
const over = (n: string) => screen.findByRole('heading', { name: new RegExp(`^Played ${n}$`) })

describe('Break, Play inside another app', () => {
  it('plays the rounds chosen for the learner, with no nav, and ends after the rounds asked for', async () => {
    const { user } = openApp(`/break?learner=${FOX}&rounds=1`)
    expect(await screen.findByRole('heading', { level: 1, name: 'How many apples are there?' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Kind of round' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('row', { name: tile('3') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await over('1\\sround')).toBeInTheDocument()
    expect(screen.getByText(/Back to what you were watching/)).toBeInTheDocument()
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ learner_id: FOX, asked: 'next' })
  })

  it('ends when the engine offers a break or ends the session', async () => {
    mock.plan = ['break']
    openApp(`/break?learner=${FOX}`)
    expect(await over('0\\srounds')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Keep playing' })).not.toBeInTheDocument()
    mock.plan = ['matching', 'end']
    const { user } = openApp(`/break?learner=${FOX}&rounds=5`)
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await over('1\\sround')).toBeInTheDocument()
  })

  it('counts kept rounds played while the engine cannot be reached', async () => {
    const { user } = openApp(`/break?learner=${FOX}&rounds=2`)
    await screen.findByRole('heading', { level: 1, name: 'How many apples are there?' })
    await vi.waitFor(() => expect(mock.keptRequests).toEqual([8]))
    server.use(nextUnreachable)
    await user.click(screen.getByRole('row', { name: tile('3') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText(/one kept on this device/)).toBeInTheDocument()
    await user.click(screen.getByRole('row', { name: tile('3') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await over('2\\srounds')).toBeInTheDocument()
  })

  it('plays one kind of round, for nobody, when the link names a kind and no learner', async () => {
    const { user } = openApp('/break?mode=matching&rounds=1')
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await over('1\\sround')).toBeInTheDocument()
    expect(mock.attempts).toEqual([])
  })

  it('records one kind of round for the learner named', async () => {
    const { user } = openApp(`/break?learner=${FOX}&mode=matching&rounds=1`)
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await over('1\\sround')).toBeInTheDocument()
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ learner_id: FOX, asked: 'matching' })
  })

  it('shows the learner’s running score, the same one Play shows, and goes on by itself as Play does', async () => {
    mock.settings = { ...mock.settings, next_after: 1 }
    const { user } = openApp(`/break?learner=${FOX}&mode=matching&rounds=1`)
    const score = () => screen.getByRole('list', { name: 'Score' }).textContent
    await vi.waitFor(() => expect(score()).toBe('12 right3 wrong'))
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    expect(score()).toBe('13 right3 wrong')
    expect(await over('1\\sround')).toBeInTheDocument() // no tap on Next: it counted down
  })

  it('shows no score for nobody', async () => {
    openApp('/break?mode=matching')
    await screen.findByRole('row', { name: tile('cow') })
    expect(screen.queryByRole('list', { name: 'Score' })).not.toBeInTheDocument()
  })

  it('says what is missing from the link', async () => {
    openApp('/break')
    expect(await screen.findByText('Choose who is playing')).toBeInTheDocument()
    openApp(`/break?learner=${'f'.repeat(32)}`)
    expect(await screen.findByText('No such learner')).toBeInTheDocument()
  })

  it('says when the learners cannot be read', async () => {
    server.use(learnersError)
    openApp(`/break?learner=${FOX}`)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
