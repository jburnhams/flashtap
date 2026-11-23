import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { installLayoutShims } from 'strata-react/testing'
import { handlers } from '../../src/mocks/handlers'
import { resetMock, server } from './server'

// jsdom does no layout and has no ResizeObserver: Strata's shims give measuring components (tables,
// virtual lists) a box to render into, and an in-memory localStorage where Node 25+ hides jsdom's.
// Real layout is checked by the visual suite in Chromium.
installLayoutShims()

// An endpoint without a handler fails the test, so a screen cannot quietly depend on a real server.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
// The app's handlers given back by name: a test that called `server.resetHandlers(x)` replaced the initial set, and a
// bare reset would keep that replacement for every later test in the file.
afterEach(() => { cleanup(); server.resetHandlers(...handlers); resetMock(); document.documentElement.classList.remove('dark') })
afterAll(() => server.close())
