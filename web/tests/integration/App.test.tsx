import { describe, expect, it } from 'vitest'
import { openApp, screen, within } from '../utils/render'

describe('the app frame', () => {
  it('marks the current screen in the menu and moves between screens by link', async () => {
    const { user, router } = openApp('/')
    const menu = screen.getByRole('navigation', { name: 'Main' })
    expect(within(menu).getByRole('link', { name: 'Play' })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('heading', { level: 1, name: 'Find the cow.' })).toBeInTheDocument()

    await user.click(within(menu).getByRole('link', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/settings')
  })

  it('says when a path has no screen, with the way back', async () => {
    const { user, router } = openApp('/old/bookmark')
    expect(screen.getByRole('heading', { level: 1, name: 'No such page' })).toBeInTheDocument()
    expect(screen.getByText('There is nothing at /old/bookmark')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Go and play' }))
    expect(router.state.location.pathname).toBe('/')
  })

  it('renders in the dark scheme', async () => {
    openApp('/settings', { colorScheme: 'dark' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })
})
