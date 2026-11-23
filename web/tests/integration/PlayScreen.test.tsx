import { afterEach, describe, expect, it } from 'vitest'
import { quickLookGoes, roundError } from '../../src/mocks/handlers'
import { openApp, screen, within } from '../utils/render'
import { mock, server } from '../utils/server'
import { installSpeech } from '../utils/speech'

const tiles = () => within(screen.getByRole('grid', { name: 'Choices' })).getAllByRole('row')
// A tile is named by what it shows, then its mark once it has one ("duck, not this one").
const tile = (word: string) => new RegExp(`^${word}(,|$)`)

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
    await user.click(await screen.findByRole('row', { name: tile('duck') }))
    const duck = screen.getByRole('row', { name: tile('duck') })
    expect(duck).toHaveAttribute('aria-disabled', 'true')
    expect(within(duck).getByText('Not this one')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('row', { name: tile('cow') }))
    expect(within(screen.getByRole('row', { name: tile('cow') })).getByText('Right')).toBeInTheDocument()
    expect(screen.getByText('That’s right.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument()
  })

  it('asks for a new round, not the one just played, after Next and a change of kind and back', async () => {
    const { user } = openApp('/')
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByRole('row', { name: tile('pig') })
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
    await user.click(await screen.findByRole('row', { name: tile('lion') }))
    expect(within(screen.getByRole('row', { name: tile('cow') })).getByText('This one')).toBeInTheDocument()
    expect(screen.getByText('The answer is shown below.')).toBeInTheDocument()
    await user.click(screen.getByRole('row', { name: tile('pig') })) // the round is over: nothing changes
    expect(screen.queryByText('Not this one', { selector: '*' })).toBeInTheDocument()
    expect(within(screen.getByRole('row', { name: tile('pig') })).queryByText('Not this one')).not.toBeInTheDocument()
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
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    expect(screen.getAllByRole('button').filter(b => b.getAttribute('data-variant') === 'default')).toHaveLength(1)
  })

  describe('spoken aloud', () => {
    let speech: ReturnType<typeof installSpeech>
    afterEach(() => speech.remove())

    it('says the prompt, each tap and the prompt again on request, in a UK English voice', async () => {
      speech = installSpeech([{ lang: 'en-US', name: 'Samantha' }, { lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/')
      await user.click(await screen.findByRole('row', { name: tile('pig') }))
      await user.click(screen.getByRole('button', { name: 'Say it again' }))
      await user.click(screen.getByRole('row', { name: tile('cow') }))
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

const piece = (name: string | RegExp) => screen.getByRole('button', { name })
const place = (name: string | RegExp) => screen.getByRole('button', { name })

describe('Play, the new kinds of round', () => {
  it('lists every kind, by name', async () => {
    openApp('/')
    const kind = await screen.findByRole('combobox', { name: 'Kind of round' })
    expect(within(kind).getAllByRole('option').map(o => o.textContent)).toEqual([
      'Matching', 'Colours', 'Shapes', 'Letters', 'Counting', 'Missing number', 'Quick look', 'Listen', 'Give a number', 'Order', 'Capitals', 'Sort by sound', 'Mixed',
    ])
  })

  it('shows a run with a gap and takes the missing number', async () => {
    const { user } = openApp('/?mode=missing')
    expect(await screen.findByRole('heading', { level: 1, name: 'Which number is missing?' })).toBeInTheDocument()
    expect(screen.getByText('4 5 ? 7 8')).toBeInTheDocument()
    await user.click(screen.getByRole('row', { name: tile('6') }))
    expect(screen.getByText('That’s right.')).toBeInTheDocument()
  })

  it('hides a quick look’s pictures after a moment, keeping the tiles', async () => {
    server.use(quickLookGoes)
    openApp('/?mode=quick_look')
    expect(await screen.findByText('🦆 🦆 🦆')).toBeInTheDocument()
    expect(await screen.findByRole('status')).toHaveTextContent('The pictures have gone.')
    expect(screen.queryByText('🦆 🦆 🦆')).not.toBeInTheDocument()
    expect(tiles()).toHaveLength(4)
  })

  describe('spoken', () => {
    let speech: ReturnType<typeof installSpeech>
    afterEach(() => speech.remove())

    it('says the Listen word aloud without printing it', async () => {
      speech = installSpeech([{ lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/?mode=listen')
      expect(await screen.findByRole('heading', { level: 1, name: 'Listen, then tap the letter it starts with.' })).toBeInTheDocument()
      expect(screen.queryByText(/dog/)).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Say it again' }))
      expect(speech.said.map(s => s.text)).toEqual(['dog. Which letter does dog start with?', 'dog. Which letter does dog start with?'])
    })

    it('says how many were given when a basket is checked', async () => {
      speech = installSpeech([{ lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/?mode=give')
      await screen.findByRole('heading', { level: 1, name: 'Put 3 ducks in the basket.' })
      for (let i = 0; i < 4; i++) {
        await user.click(within(screen.getByRole('group', { name: 'Pictures to place' })).getAllByRole('button')[0])
        await user.click(place('Put duck in the basket'))
      }
      await user.click(screen.getByRole('button', { name: 'Check' }))
      expect(speech.said.at(-1)?.text).toBe('You put 4 in the basket. That’s too many. Try again.')
      // The mark is in the place's name too, not only drawn inside it.
      expect(place('the basket, not yet')).toHaveTextContent('Not yet')
      // Taking one out clears the mark; three is right.
      await user.click(within(screen.getByRole('group', { name: 'In the basket' })).getAllByRole('button')[0])
      await user.click(screen.getByRole('button', { name: 'Put duck back' }))
      expect(place('the basket')).not.toHaveTextContent('Not yet')
      await user.click(screen.getByRole('button', { name: 'Check' }))
      expect(speech.said.at(-1)?.text).toBe('Yes! There are 3 ducks in the basket.')
      expect(place('the basket, right')).toHaveTextContent('Right')
      expect(screen.queryByRole('button', { name: 'Check' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    })
  })

  it('cannot be checked before anything is placed', async () => {
    openApp('/?mode=order')
    await screen.findByRole('heading', { level: 1, name: 'Put the numbers in order, smallest first.' })
    expect(screen.getByRole('button', { name: 'Check' })).toBeDisabled()
  })

  it('marks the places that are right and the ones that are not yet, then takes the order', async () => {
    const { user } = openApp('/?mode=order') // 1 4 7 9
    await screen.findByRole('heading', { level: 1, name: 'Put the numbers in order, smallest first.' })
    const put = async (n: string, where: string) => {
      await user.click(piece(n))
      await user.click(place(`Put ${n} in ${where}`))
    }
    await put('1', 'first')
    await put('7', 'second')
    await user.click(screen.getByRole('button', { name: 'Check' }))
    expect(place('first, right')).toHaveTextContent('Right')
    expect(place('second, not yet')).toHaveTextContent('Not yet')
    expect(place('third, not yet')).toHaveTextContent('Not yet') // empty, so not right either
    await user.click(piece('7'))
    await user.click(place('Put 7 in third, not yet'))
    await put('4', 'second')
    await put('9', 'fourth, not yet') // checked while empty: its mark stays until something goes in
    await user.click(screen.getByRole('button', { name: 'Check' }))
    expect(screen.getByText('That’s right.')).toBeInTheDocument()
    expect(screen.getAllByRole('button').filter(b => b.getAttribute('data-variant') === 'default')).toHaveLength(1)
  })

  it('shows the answer in place once the checks run out', async () => {
    mock.tries = 1
    const { user } = openApp('/?mode=capitals')
    await screen.findByRole('heading', { level: 1, name: 'Put each small letter on its capital.' })
    await user.click(piece('small b'))
    await user.click(place('Put small b in capital D'))
    await user.click(screen.getByRole('button', { name: 'Check' }))
    expect(screen.getByText('The answer is shown below.')).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'In capital B' })).getByRole('button', { name: 'small b' })).toBeDisabled()
    expect(place('capital D')).not.toHaveTextContent('Not yet')
  })

  it('sorts pictures under the letters they start with', async () => {
    const { user } = openApp('/?mode=sort_sounds')
    await screen.findByRole('heading', { level: 1, name: 'Put each picture with the letter it starts with.' })
    for (const [word, letter] of [['bus', 'b'], ['bell', 'b'], ['dog', 'd'], ['duck', 'd']]) {
      await user.click(piece(word))
      await user.click(place(`Put ${word} in ${letter}`))
    }
    await user.click(screen.getByRole('button', { name: 'Check' }))
    expect(screen.getByText('That’s right.')).toBeInTheDocument()
  })
})
