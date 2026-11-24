// The app's route tree, in its own module so the app (main.tsx), the jsdom tests (renderRoutes from
// strata-react/testing) and the stories build their routers from the same objects.
//
// Routes are real paths (/settings?tab=appearance), not #hashes: the server answers every page path
// with the app (src/flashtap/server/app.py), so a reload or a shared link opens that screen.
import type { RouteObject } from 'react-router'
import { ContentScreen } from './screens/ContentScreen'
import { BreakScreen } from './screens/BreakScreen'
import { Bare, Layout } from './screens/Layout'
import { LearnerScreen } from './screens/LearnerScreen'
import { LearnersScreen } from './screens/LearnersScreen'
import { NotFoundScreen } from './screens/NotFoundScreen'
import { PlayScreen } from './screens/PlayScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { SoundsScreen } from './screens/SoundsScreen'

export const routes: RouteObject[] = [
  // Play inside another app's frame (a video player's break): no nav, ends by telling the parent page.
  { path: 'break', element: <Bare />, children: [{ index: true, element: <BreakScreen /> }] },
  {
    element: <Layout />,
    children: [
      { index: true, element: <PlayScreen /> },
      { path: 'learners', element: <LearnersScreen /> },
      { path: 'learners/:id', element: <LearnerScreen /> },
      { path: 'content', element: <ContentScreen /> },
      { path: 'sounds', element: <SoundsScreen /> },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <NotFoundScreen /> },
    ],
  },
]
