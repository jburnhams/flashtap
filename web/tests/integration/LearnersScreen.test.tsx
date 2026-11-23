import { describe, expect, it } from 'vitest'
import { expectOneFilledButton } from 'strata-react/testing'
import { learnersError, learnersNone, learnersUnplayed } from '../../src/mocks/handlers'
import { openApp, screen, within } from '../utils/render'
import { mock, server } from '../utils/server'

const FOX = 'a'.repeat(32)

describe('Learners', () => {
  it('lists each learner with their rounds, last play and a way to play as them', async () => {
    openApp('/learners')
    expect(await screen.findByRole('heading', { level: 1, name: 'Learners' })).toBeInTheDocument()
    expect(screen.getByText(/3\slearners; Fox played last/)).toBeInTheDocument()
    const table = screen.getByRole('grid', { name: 'Learners' })
    expect(within(table).getByRole('link', { name: 'Fox' })).toHaveAttribute('href', `/learners/${FOX}`)
    expect(within(table).getByRole('link', { name: 'Play as Fox' })).toHaveAttribute('href', `/?learner=${FOX}`)
    expect(within(table).getByText('Never')).toBeInTheDocument()
    expectOneFilledButton()
  })

  it('adds a learner, refuses an empty or taken nickname, and says nothing else is kept', async () => {
    const { user } = openApp('/learners')
    const field = await screen.findByRole('textbox', { name: 'Nickname' })
    await user.click(screen.getByRole('button', { name: 'Add learner' }))
    expect(await screen.findByText('Type a nickname first.')).toBeInTheDocument()
    await user.type(field, 'fox')
    await user.click(screen.getByRole('button', { name: 'Add learner' }))
    expect((await screen.findAllByText(/already a learner called fox/)).length).toBeGreaterThan(0)
    await user.clear(field)
    await user.type(field, 'Hedgehog{Enter}')
    expect(await screen.findByRole('link', { name: 'Hedgehog' })).toBeInTheDocument()
    expect(field).toHaveValue('')
    expect(mock.learners.map(x => x.nickname)).toEqual(['Fox', 'Owl', 'Hare', 'Hedgehog'])
    expect(screen.getByText('Each learner is a nickname; nothing else about them is kept')).toBeInTheDocument()
  })

  it('teaches the next step when there is nobody yet', async () => {
    server.use(learnersNone)
    openApp('/learners')
    expect(await screen.findByText('No learners yet')).toBeInTheDocument()
    expect(screen.getByText('Nobody yet: add a learner to start recording rounds.')).toBeInTheDocument()
  })

  it('says when nobody has played yet', async () => {
    server.use(learnersUnplayed)
    openApp('/learners')
    expect(await screen.findByText(/3\slearners; no rounds recorded yet\./)).toBeInTheDocument()
  })

  it('says when the learners cannot be read', async () => {
    server.use(learnersError)
    openApp('/learners')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
