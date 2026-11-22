import { afterEach, describe, expect, it } from 'vitest'
import { roundError } from '../../src/mocks/handlers'
import { openApp, screen, within } from '../utils/render'
import { mock, server } from '../utils/server'
import { installSpeech } from '../utils/speech'

const tiles = () => within(screen.getByRole('list', { name: 'Choices' })).getAllByRole('button')

describe('Play', () => {
  it('shows the round in the saved mode, with no names printed on the tiles', async () => {
    openApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })).toBeInTheDocument()
    expect(tiles().map(t => t.getAttribute('aria-label'))).toEqual(['pig', 'cow', 'duck', 'lion'])
    expect(tiles().map(t => t.textContent)).toEqual(['🐖', '🐄', '🦆', '🦁'])
    expect(screen.getByRole('combobox', { name: 'Kind of round' })).toHaveValue('mixed')
  })

  it('greys out a wrong tile and keeps playing, then marks the right one and offers Next', async () => {
    const { user } = openApp('/')
    await user.click(await screen.findByRole('button', { name: 'duck' }))
    const duck = screen.getByRole('button', { name: 'duck' })
    expect(duck).toHaveAttribute('aria-disabled', 'true')
    expect(within(duck).getByText('Not this one')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'cow' }))
    expect(within(screen.getByRole('button', { name: 'cow' })).getByText('Right')).toBeInTheDocument()
    expect(screen.getByText('That’s right.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument()
  })

  it('asks for a new round, not the one just played, after Next and a change of kind and back', async () => {
    const { user } = openApp('/')
    await user.click(await screen.findByRole('button', { name: 'cow' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByRole('button', { name: 'pig' })
    const asked = mock.roundRequests
    const kind = screen.getByRole('combobox', { name: 'Kind of round' })
    await user.selectOptions(kind, 'colours')
    await screen.findByRole('heading', { level: 1, name: 'Which one is yellow?' })
    await user.selectOptions(kind, 'mixed')
    await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })
    expect(mock.roundRequests).toBe(asked + 2)
  })

  it('shows where the answer was once the tries run out', async () => {
    mock.tries = 1
    const { user } = openApp('/')
    await user.click(await screen.findByRole('button', { name: 'lion' }))
    expect(within(screen.getByRole('button', { name: 'cow' })).getByText('This one')).toBeInTheDocument()
    expect(screen.getByText('The answer is shown below.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'pig' })) // the round is over: nothing changes
    expect(screen.queryByText('Not this one', { selector: '*' })).toBeInTheDocument()
    expect(within(screen.getByRole('button', { name: 'pig' })).queryByText('Not this one')).not.toBeInTheDocument()
  })

  it('keeps the kind of round in the URL', async () => {
    const { user, router } = openApp('/')
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Kind of round' }), 'counting')
    expect(router.state.location.search).toBe('?mode=counting')
    expect(await screen.findByRole('heading', { level: 1, name: 'How many apples are there?' })).toBeInTheDocument()
    expect(tiles().map(t => t.textContent)).toEqual(['5', '3', '9', '2'])
    await user.selectOptions(screen.getByRole('combobox', { name: 'Kind of round' }), 'mixed')
    expect(router.state.location.search).toBe('') // the saved mode needs no parameter
  })

  it('opens on a kind of round from a link', async () => {
    openApp('/?mode=letters')
    expect(await screen.findByRole('heading', { level: 1, name: 'What starts with the letter D?' })).toBeInTheDocument()
  })

  it('says the server could not answer', async () => {
    server.use(roundError)
    openApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503)')
  })

  it('has one filled button at most', async () => {
    const { user } = openApp('/')
    await user.click(await screen.findByRole('button', { name: 'cow' }))
    expect(screen.getAllByRole('button').filter(b => b.getAttribute('data-variant') === 'default')).toHaveLength(1)
  })

  describe('spoken aloud', () => {
    let speech: ReturnType<typeof installSpeech>
    afterEach(() => speech.remove())

    it('says the prompt, each tap and the prompt again on request, in a UK English voice', async () => {
      speech = installSpeech([{ lang: 'en-US', name: 'Samantha' }, { lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/')
      await user.click(await screen.findByRole('button', { name: 'pig' }))
      await user.click(screen.getByRole('button', { name: 'Say it again' }))
      await user.click(screen.getByRole('button', { name: 'cow' }))
      expect(speech.said.map(s => s.text)).toEqual(['Find the cow.', 'No, that\u2019s a pig. Try again.', 'Find the cow.', 'Yes! You found the cow.'])
      expect(speech.said[0]).toMatchObject({ lang: 'en-GB', voice: 'Daniel' })
    })

    it('falls back to British English without a matching voice', async () => {
      speech = installSpeech([{ lang: 'de-DE', name: 'Anna' }])
      openApp('/')
      await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })
      expect(speech.said[0]).toEqual({ text: 'Find the cow.', lang: 'en-GB', voice: undefined })
    })
  })
})
