// The visual suite, run by strata-react's own runner (`strata-visual`, from strata-react/visual):
// Playwright Chromium screenshots, light and dark, compared with committed baselines in
// tests/visual/baselines/ by pixelmatch. Two targets:
//
// - storybook: every story of the built Storybook (each screen in each server state);
// - app: the production build served as the Python server would (history fallback), each route at
//   a wide and a phone viewport, with every request answered in Node by the same MSW handlers the
//   jsdom tests use. Route states here are the ones a story cannot reach without a tap: a wrong
//   tile greyed out, the right one found, and a field's error.
//
// `npm run test:visual` builds both and compares; `npm run test:visual:update` writes new
// baselines. Look at a diff in tests/visual/output/ before accepting it.
import { defineVisualConfig } from 'strata-react/visual'
import { handlers } from './src/mocks/handlers'

export default defineVisualConfig({
  storybook: 'storybook-static',
  app: {
    dir: 'dist-visual',
    handlers,
    viewports: ['wide', 'phone'],
    routes: [
      {
        name: 'play',
        path: '/',
        states: {
          ready: [],
          wrong: {
            setup: async page => {
              await page.getByRole('button', { name: 'duck' }).click()
              await page.getByText('Not this one').waitFor()
            },
          },
          right: {
            setup: async page => {
              await page.getByRole('button', { name: 'cow' }).click()
              await page.getByRole('button', { name: 'Next' }).waitFor()
            },
          },
        },
      },
      { name: 'counting', path: '/?mode=counting' },
      { name: 'settings', path: '/settings', states: { play: [], appearance: { path: '/settings?tab=appearance' } } },
    ],
  },
})
