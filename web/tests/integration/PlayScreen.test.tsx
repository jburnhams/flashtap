import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AttemptIn } from '../../src/api'
import { rounds } from '../../src/mocks/fixtures'
import { attemptFails, decisionFor, learnersError, nextChoice, nextError, pickFails, quickLookGoes, ratingFails, roundError, SESSION, sessionError } from '../../src/mocks/handlers'
import { openApp, screen, within } from '../utils/render'
import { mock, server } from '../utils/server'
import { expectOneFilledButton, installFakeSpeech } from 'strata-react/testing'

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
    let speech: ReturnType<typeof installFakeSpeech>
    afterEach(() => speech.uninstall())

    it('says the prompt, each tap and the prompt again on request, in a UK English voice', async () => {
      speech = installFakeSpeech([{ lang: 'en-US', name: 'Samantha' }, { lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/')
      await user.click(await screen.findByRole('row', { name: tile('pig') }))
      await user.click(screen.getByRole('button', { name: 'Say again: Find the cow.' }))
      await user.click(screen.getByRole('row', { name: tile('cow') }))
      expect(speech.said.map(s => s.text)).toEqual(['Find the cow.', 'No, that\u2019s a pig. Try again.', 'Find the cow.', 'Yes! You found the cow.'])
      expect(speech.said[0]).toMatchObject({ lang: 'en-GB', voice: 'Daniel', rate: 0.9 })
    })

    it('falls back to British English without a matching voice', async () => {
      speech = installFakeSpeech([{ lang: 'de-DE', name: 'Anna' }])
      openApp('/')
      await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })
      expect(speech.said[0]).toMatchObject({ text: 'Find the cow.', lang: 'en-GB', voice: null })
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
      'Chosen for them', 'Matching', 'Colours', 'Shapes', 'Letters', 'Counting', 'Missing number', 'Quick look', 'Listen', 'Give a number', 'Order', 'Capitals', 'Sort by sound', 'Mixed',
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
    let speech: ReturnType<typeof installFakeSpeech>
    afterEach(() => speech.uninstall())

    it('says the Listen word aloud without printing it', async () => {
      speech = installFakeSpeech([{ lang: 'en-GB', name: 'Daniel' }])
      const { user } = openApp('/?mode=listen')
      expect(await screen.findByRole('heading', { level: 1, name: 'Listen, then tap the letter it starts with.' })).toBeInTheDocument()
      expect(screen.queryByText(/dog/)).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: /^Say again: dog\./ }))
      expect(speech.said.map(s => s.text)).toEqual(['dog. Which letter does dog start with?', 'dog. Which letter does dog start with?'])
    })

    it('says how many were given when a basket is checked', async () => {
      speech = installFakeSpeech([{ lang: 'en-GB', name: 'Daniel' }])
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

describe('Play records rounds for the learner playing', () => {
  const FOX = 'a'.repeat(32)

  it('records nothing while nobody is chosen', async () => {
    const { user } = openApp('/')
    expect(await screen.findByRole('combobox', { name: 'Who is playing' })).toHaveValue('')
    expect(screen.getByText('Nobody: rounds are not recorded.')).toBeInTheDocument()
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByRole('row', { name: tile('pig') })
    expect(mock.attempts).toEqual([])
  })

  it('sends the first answer, the tries and how the round ended, once', async () => {
    const { user, router } = openApp('/')
    const who = await screen.findByRole('combobox', { name: 'Who is playing' })
    await screen.findByRole('option', { name: 'Fox' })
    await user.selectOptions(who, FOX)
    expect(router.state.location.search).toBe(`?learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('duck') }))
    expect(mock.attempts).toEqual([]) // still playing
    await user.click(screen.getByRole('row', { name: tile('cow') }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    const [a] = mock.attempts
    expect(a).toMatchObject({ learner_id: FOX, mode: 'matching', version: 1, content: rounds.matching.content, choices: 4, seed: 7, asked: 'mixed', first_answer: { option: 'duck' }, tries: 2, outcome: 'right' })
    expect(a.event_id).toMatch(/^[0-9a-f]{32}$/)
    expect(Date.parse(a.answered_at)).toBeGreaterThanOrEqual(Date.parse(a.presented_at))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByRole('row', { name: tile('pig') })
    await user.click(screen.getByRole('row', { name: tile('cow') }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(2))
    expect(mock.attempts[1]).toMatchObject({ first_answer: { option: 'cow' }, tries: 1, outcome: 'right', session_id: a.session_id })
    expect(mock.attempts[1].event_id).not.toBe(a.event_id)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Who is playing' }), '')
    expect(router.state.location.search).toBe('')
  })

  it('reports a round left half done, and a missed one', async () => {
    mock.tries = 1
    const { user } = openApp(`/?learner=${FOX}&mode=counting`)
    await user.click(await screen.findByRole('row', { name: tile('5') }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ mode: 'counting', asked: 'counting', outcome: 'missed', tries: 1 })
    mock.tries = null
    await user.selectOptions(screen.getByRole('combobox', { name: 'Kind of round' }), 'matching')
    await user.click(await screen.findByRole('row', { name: tile('pig') }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Kind of round' }), 'colours')
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(2))
    expect(mock.attempts[1]).toMatchObject({ mode: 'matching', first_answer: { option: 'pig' }, tries: 1, outcome: 'left' })
  })

  it('asks for a fresh round when who is playing changes, so a half-done round is not answered again', async () => {
    const { user } = openApp(`/?learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('duck') })) // wrong first answer
    const asked = mock.roundRequests
    const who = screen.getByRole('combobox', { name: 'Who is playing' })
    await user.selectOptions(who, '')
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ first_answer: { option: 'duck' }, outcome: 'left' })
    await user.selectOptions(who, FOX)
    await vi.waitFor(() => expect(mock.roundRequests).toBe(asked + 2))
    await screen.findByRole('row', { name: tile('pig') })
  })

  it('sends a placing round’s arrangement at its first check', async () => {
    mock.tries = 1
    const { user } = openApp(`/?learner=${FOX}&mode=order`)
    for (const [n, where] of [['1', 'first'], ['9', 'second']]) {
      await user.click(await screen.findByRole('button', { name: n }))
      await user.click(screen.getByRole('button', { name: `Put ${n} in ${where}` }))
    }
    await user.click(screen.getByRole('button', { name: 'Check' }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ mode: 'order', first_answer: { placement: { n1: 'first', n9: 'second' } }, tries: 1, outcome: 'missed' })
  })

  it('says quietly when the server did not take a round', async () => {
    server.use(attemptFails)
    const { user } = openApp(`/?learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    expect(await screen.findByText('The last round was not saved for Fox: the server did not take it.')).toBeInTheDocument()
  })

  it('lets the child play when the learners cannot be loaded', async () => {
    server.use(learnersError)
    const { user } = openApp(`/?learner=${FOX}`)
    expect(await screen.findByText('The learners could not be loaded, so these rounds are not recorded.')).toBeInTheDocument()
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(mock.attempts).toEqual([])
  })
})

describe('Play, chosen for them', () => {
  const FOX = 'a'.repeat(32)

  it('asks who is playing before choosing for them', async () => {
    openApp('/?mode=next')
    expect(await screen.findByText('Choose who is playing')).toBeInTheDocument()
    expect(mock.nextRequests).toEqual([])
  })

  it('plays the rounds the engine chooses, says why, and records each against its decision', async () => {
    const { user } = openApp(`/?mode=next&learner=${FOX}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'How many apples are there?' })).toBeInTheDocument()
    expect(screen.getByText('Why this round: Practising: Count a set of things.')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Kind of round' })).toHaveValue('next')
    await user.click(screen.getByRole('row', { name: tile('3') }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.attempts[0]).toMatchObject({ learner_id: FOX, session_id: SESSION, decision_id: 'd0'.padEnd(32, '0'), mode: 'counting', seed: 5, asked: 'next', first_answer: { option: 'n3' }, tries: 1, outcome: 'right' })
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Put 3 ducks in the basket.' })).toBeInTheDocument()
    expect(mock.nextRequests).toEqual([0, 1])
  })

  it('offers a break: keep playing asks for the next decision, stopping ends here', async () => {
    mock.plan = ['break', 'matching']
    const { user } = openApp(`/?mode=next&learner=${FOX}`)
    expect(await screen.findByRole('heading', { name: 'Time for a break?' })).toBeInTheDocument()
    expect(screen.getAllByRole('button').filter(b => b.getAttribute('data-variant') === 'default').map(b => b.textContent)).toEqual(['Keep playing'])
    await user.click(screen.getByRole('button', { name: 'Keep playing' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })).toBeInTheDocument()

    mock.plan = ['break']
    mock.nextRequests = []
    const again = openApp(`/?mode=next&learner=${FOX}`)
    await again.user.click(await screen.findByRole('button', { name: 'Stop for now' }))
    expect(await screen.findByRole('heading', { name: /^Played 0\srounds$/ })).toBeInTheDocument()
    expect(mock.nextRequests).toEqual([0])
  })

  it('ends when the engine says the session is over, with a way to see what was shown', async () => {
    mock.plan = ['matching', 'end']
    const { user, router } = openApp(`/?mode=next&learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('cow') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('heading', { name: /^Played 1\sround$/ })).toBeInTheDocument()
    expect(screen.getByText(/A session is 1 round at most\. The next session picks up/)).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'See what Fox has shown' }))
    expect(router.state.location.pathname).toBe(`/learners/${FOX}`)
  })

  it('asks for the next decision only once the answer is saved, so the engine knows it', async () => {
    let land = () => {}
    const landed = new Promise<void>(resolve => { land = resolve })
    server.use(http.post('*/api/attempts', async ({ request }) => {
      mock.attempts.push((await request.json()) as AttemptIn)
      await landed
      return HttpResponse.json({ event_id: 'x', first_correct: true, duplicate: false })
    }))
    const { user } = openApp(`/?mode=next&learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('3') }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
    expect(mock.nextRequests).toEqual([0])
    land()
    expect(await screen.findByRole('heading', { level: 1, name: 'Put 3 ducks in the basket.' })).toBeInTheDocument()
    expect(mock.nextRequests).toEqual([0, 1])
  })

  it('says quietly when the server did not take a chosen round', async () => {
    server.use(attemptFails)
    const { user } = openApp(`/?mode=next&learner=${FOX}`)
    await user.click(await screen.findByRole('row', { name: tile('3') }))
    expect(await screen.findByRole('status')).toHaveTextContent('The last round was not saved for Fox')
  })

  it('says the server could not start a session or choose a round', async () => {
    server.use(sessionError)
    openApp(`/?mode=next&learner=${FOX}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503)')
    server.resetHandlers(nextError)
    openApp(`/?mode=next&learner=${FOX}`)
    await vi.waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
  })

  describe('engagement', () => {
    const FOX = 'a'.repeat(32)
    const choices = () => within(screen.getByRole('grid', { name: 'Which one next?' })).getAllByRole('row')

    it('offers a choice of two, plays the one picked, and asks how it was', async () => {
      server.use(nextChoice)
      const { user } = openApp(`/?mode=next&learner=${FOX}`)
      expect(await screen.findByRole('heading', { level: 1, name: 'Which one next?' })).toBeInTheDocument()
      expect(choices().map(t => t.getAttribute('aria-label'))).toEqual(['Counting', 'Listen'])
      expect(choices().map(t => t.textContent)).toEqual(['🔢', '👂'])
      expect(screen.getByText(/^Why two: Two to pick from/)).toBeInTheDocument()
      await user.click(screen.getByRole('row', { name: 'Listen' }))
      expect(await screen.findByRole('heading', { level: 1, name: 'Listen, then tap the letter it starts with.' })).toBeInTheDocument()
      expect(mock.picks).toEqual({ 0: 1 })
      expect(screen.queryByRole('heading', { name: 'How was that one?' })).not.toBeInTheDocument() // not until it is over
      await user.click(screen.getByRole('row', { name: tile('d') }))
      await vi.waitFor(() => expect(mock.attempts).toHaveLength(1))
      expect(mock.attempts[0]).toMatchObject({ decision_id: 'd0'.padEnd(32, '0'), mode: 'listen', seed: 2 })
      expect(screen.getByRole('heading', { name: 'How was that one?' })).toBeInTheDocument()
      expectOneFilledButton() // Next stays the one filled button: the faces are optional
      await user.click(screen.getByRole('row', { name: 'Liked it' }))
      expect(await screen.findByText('Thank you.')).toBeInTheDocument()
      await vi.waitFor(() => expect(mock.ratings).toEqual([{ event_id: mock.attempts[0].event_id, value: 1 }]))
      await user.click(screen.getByRole('button', { name: 'Next' }))
      expect(await screen.findByRole('heading', { name: /^Played 1\sround$/ })).toBeInTheDocument()
      expect(mock.nextRequests).toEqual([0, 1])
    })

    it('says so when a pick does not reach the server, and the faces when one is not saved', async () => {
      server.use(nextChoice, pickFails)
      const { user } = openApp(`/?mode=next&learner=${FOX}`)
      await user.click(await screen.findByRole('row', { name: 'Counting' }))
      expect(await screen.findByRole('status')).toHaveTextContent('That pick did not reach the server: tap one again.')
      server.use(http.post('*/api/v1/sessions/:id/decisions/:seq/pick', async ({ params, request }) => {
        mock.picks[Number(params.seq)] = ((await request.json()) as { offer: number }).offer
        return HttpResponse.json(decisionFor(Number(params.seq)))
      }), ratingFails)
      await user.click(screen.getByRole('row', { name: 'Counting' }))
      await user.click(await screen.findByRole('row', { name: tile('3') }))
      await user.click(screen.getByRole('row', { name: 'Did not like it' }))
      expect(await screen.findByText('That face was not saved.')).toBeInTheDocument()
    })

    it('asks how it was every few rounds when the grown-up picks the kind, only for a recorded learner', async () => {
      mock.settings = { ...mock.settings, rate_every: 2 }
      const { user } = openApp(`/?learner=${FOX}`)
      await user.click(await screen.findByRole('row', { name: tile('cow') }))
      expect(screen.queryByRole('heading', { name: 'How was that one?' })).not.toBeInTheDocument() // round 1 of 2
      await user.click(screen.getByRole('button', { name: 'Next' }))
      await user.click(await screen.findByRole('row', { name: tile('cow') }))
      await user.click(await screen.findByRole('row', { name: 'It was all right' }))
      await vi.waitFor(() => expect(mock.ratings).toEqual([{ event_id: mock.attempts[1].event_id, value: 0 }]))

      mock.settings = { ...mock.settings, rate_every: 1 }
      const nobody = openApp('/')
      await nobody.user.click(await screen.findAllByRole('row', { name: tile('cow') }).then(r => r[r.length - 1]))
      expect(screen.queryAllByRole('heading', { name: 'How was that one?' })).toHaveLength(0)
    })

    it('asks how an arrangement was too, once it is checked', async () => {
      mock.plan = ['give+rate', 'end']
      const { user } = openApp(`/?mode=next&learner=${FOX}`)
      expect(await screen.findByRole('heading', { level: 1, name: 'Put 3 ducks in the basket.' })).toBeInTheDocument()
      for (let i = 0; i < 3; i++) {
        await user.click(within(screen.getByRole('group', { name: 'Pictures to place' })).getAllByRole('button')[0])
        await user.click(screen.getByRole('button', { name: 'Put duck in the basket' }))
      }
      expect(screen.queryByRole('heading', { name: 'How was that one?' })).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Check' }))
      await user.click(await screen.findByRole('row', { name: 'Liked it' }))
      await vi.waitFor(() => expect(mock.ratings).toHaveLength(1))
    })

    it('rates a round only once it is saved: a round the server did not take is not rated', async () => {
      mock.settings = { ...mock.settings, rate_every: 1 }
      server.use(attemptFails)
      const { user } = openApp(`/?learner=${FOX}`)
      await user.click(await screen.findByRole('row', { name: tile('cow') }))
      await user.click(screen.getByRole('row', { name: 'Liked it' }))
      expect(await screen.findByText('That face was not saved.')).toBeInTheDocument()
      expect(mock.ratings).toEqual([])
    })
  })
})
