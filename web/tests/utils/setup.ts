import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { installLayoutShims } from 'strata-react/testing'
import { answers } from '../../src/api'
import { handlers } from '../../src/mocks/handlers'
import { resetMock, server } from './server'
import { resetTalk } from '../../src/talk'

// jsdom does no layout and has no ResizeObserver: Strata's shims give measuring components (tables,
// virtual lists) a box to render into, and an in-memory localStorage where Node 25+ hides jsdom's.
// Real layout is checked by the visual suite in Chromium.
installLayoutShims()

// An endpoint without a handler fails the test, so a screen cannot quietly depend on a real server.
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
// The app's handlers given back by name: a test that called `server.resetHandlers(x)` replaced the initial set, and a
// bare reset would keep that replacement for every later test in the file.
// Answers still on their way are let land (or fail) before the mock is reset, so none arrives in the next test's mock;
// the queue is one per app, like the real one. Storage is emptied too (the answers waiting, the rounds kept), so no test
// starts with another's.
afterEach(async () => { cleanup(); await answers.flush(); window.localStorage.clear(); server.resetHandlers(...handlers); resetMock(); resetTalk(); document.documentElement.classList.remove('dark') })
afterAll(() => server.close())
