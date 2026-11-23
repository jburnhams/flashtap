import { describe, expect, it } from 'vitest'
import { modesError, modesFew, modesLoading, saveSettingsFails, settingsError } from '../../src/mocks/handlers'
import { openApp, screen, waitFor } from '../utils/render'
import { mock, server } from '../utils/server'

describe('Settings', () => {
  it('starts the form from what the server holds and saves a change', async () => {
    const { user } = openApp('/settings')
    const mode = await screen.findByRole('combobox', { name: 'Kind of round' })
    expect(mode).toHaveValue('mixed')
    expect(await screen.findByRole('option', { name: 'Counting' })).toBeInTheDocument()
    await user.selectOptions(mode, 'counting')
    expect(mode).toHaveAccessibleDescription('Count the pictures and tap the number')
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('Saved', { selector: '[role=status]' })).toBeInTheDocument()
    expect(mock.settings.mode).toBe('counting')
  })

  it('needs a number of choices before saving', async () => {
    const { user } = openApp('/settings')
    const choices = await screen.findByRole('textbox', { name: 'Choices' })
    await user.clear(choices)
    await user.tab()
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('Enter how many choices a round offers.')).toBeInTheDocument()
    expect(mock.settings.choices).toBe(4)
  })

  it('saves an empty Tries as no limit', async () => {
    mock.settings.tries = 2
    const { user } = openApp('/settings')
    const tries = await screen.findByRole('textbox', { name: 'Tries' })
    await user.clear(tries)
    await user.tab()
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('Saved', { selector: '[role=status]' })).toBeInTheDocument()
    expect(mock.settings.tries).toBe(0)
  })

  it('says what happened when saving fails', async () => {
    server.use(saveSettingsFails)
    const { user } = openApp('/settings')
    await user.click(await screen.findByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText(/The settings were not changed\.$/)).toBeInTheDocument()
  })

  it('keeps the tab in the URL, and the colour scheme choice changes the page', async () => {
    const { user, router } = openApp('/settings')
    await user.click(screen.getByRole('tab', { name: 'Appearance' }))
    expect(router.state.location.search).toBe('?tab=appearance')
    await user.click(screen.getByRole('radio', { name: 'Dark' }))
    await waitFor(() => expect(document.documentElement).toHaveClass('dark'))
  })

  it('says the server could not answer', async () => {
    server.use(settingsError)
    openApp('/settings')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503)')
  })

  it('waits for the list of kinds of round before showing the form', async () => {
    server.use(modesLoading)
    openApp('/settings')
    await screen.findByRole('tabpanel')
    expect(screen.queryByRole('combobox', { name: 'Kind of round' })).not.toBeInTheDocument()
  })

  it('names a kind of round the server did not describe by its plain name', async () => {
    server.use(modesFew)
    openApp('/settings')
    const mode = await screen.findByRole('combobox', { name: 'Kind of round' })
    expect(mode).toHaveAccessibleDescription('Which kind of round Play starts with.')
    expect(screen.getByRole('option', { name: 'colours' })).toBeInTheDocument()
  })

  it('says so when the list of kinds of round cannot be read', async () => {
    server.use(modesError)
    openApp('/settings')
    expect(await screen.findByRole('alert')).toHaveTextContent('The server could not answer (503)')
    expect(screen.queryByRole('combobox', { name: 'Kind of round' })).not.toBeInTheDocument()
  })
})
