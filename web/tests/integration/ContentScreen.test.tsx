import { describe, expect, it } from 'vitest'
import { contentEmpty, contentError, contentReviewed } from '../../src/mocks/handlers'
import { openApp, screen, within } from '../utils/render'
import { server } from '../utils/server'

/** The table's one row whose text holds `text`. */
function rowWith(table: HTMLElement, text: string) {
  const found = within(table).getAllByRole('row').filter(r => r.textContent?.includes(text))
  expect(found).toHaveLength(1)
  return found[0]
}

describe('Content', () => {
  it('leads with the drafts still to check, then the figures', async () => {
    openApp('/content')
    expect(await screen.findByRole('heading', { level: 1, name: 'Content' })).toBeInTheDocument()
    expect(screen.getByText('4 of 4 packs are drafts: written from the sources, not yet checked by a teacher.')).toBeInTheDocument()
    expect(screen.getByText('3 of 4')).toBeInTheDocument()
    expect(screen.getByText('3 played in a round today')).toBeInTheDocument()
  })

  it('gives the coverage when every pack is reviewed', async () => {
    server.use(contentReviewed)
    openApp('/content')
    expect(await screen.findByText('3 of 4 curriculum goals map to skills; the rest are set aside with a reason.')).toBeInTheDocument()
  })

  it('lists skills by strand, and a row opens to show its links, kept in the URL', async () => {
    const { user, router } = openApp('/content')
    const table = await screen.findByRole('grid', { name: 'Skills' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent("Find a word that starts with a letter's sound") // Literacy strands before Mathematics
    const objects = rowWith(table, 'Count a set of things')
    expect(objects).toHaveTextContent('EYFS')
    expect(objects).toHaveTextContent('counting')

    await user.click(within(table).getByRole('button', { name: 'Links of Count a set of things' }))
    expect(router.state.location.search).toBe('?open=maths.counting.objects')
    expect(await screen.findByText(/A learner who does not know|When the answer is a tapped numeral/)).toBeInTheDocument()
    expect(screen.getByText('Say the number names in order')).toBeInTheDocument()
  })

  it('shows a skill with nothing before it and its misconceptions', async () => {
    openApp('/content?open=maths.counting.one_to_one&open=maths.cardinality.last_number')
    expect(await screen.findByText('Counts again when asked how many')).toBeInTheDocument()
    expect(screen.getAllByText('None').length).toBeGreaterThan(0)
  })

  it('maps each curriculum goal to skills or says why it is out of scope', async () => {
    const { user, router } = openApp('/content')
    await user.click(await screen.findByRole('tab', { name: 'Curriculum' }))
    expect(router.state.location.search).toBe('?tab=curriculum')
    const table = screen.getByRole('grid', { name: 'Curriculum goals' })
    const writing = rowWith(table, 'Write recognisable letters')
    expect(within(writing).getByText('Out of scope')).toBeInTheDocument()
    const sounds = rowWith(table, 'Say a sound for each letter')
    expect(sounds).toHaveTextContent('Say the sound for the letters, Find the letters for a sound')
    expect(sounds).toHaveTextContent(/Saying needs speech input/)
  })

  it('lists the phonics sets in order with the words each makes readable', async () => {
    openApp('/content?tab=phonics')
    const table = await screen.findByRole('grid', { name: 'Letters and Sounds sets' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map(r => within(r).getByRole('rowheader').textContent)).toEqual(['Phase 2, set 1', 'Phase 2, set 2', 'Phase 2, set 3'])
    expect(rows[0]).toHaveTextContent('s /s/, a /æ/, t /t/, p /p/')
    expect(rows[1]).toHaveTextContent('map')
  })

  it('says when the server has no packs to show', async () => {
    server.use(contentEmpty)
    openApp('/content')
    expect(await screen.findByText('No content packs')).toBeInTheDocument()
  })

  it('says the server could not answer', async () => {
    server.use(contentError)
    openApp('/content')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503)')
  })
})
