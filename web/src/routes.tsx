// The app's route tree, in its own module so the app (main.tsx), the jsdom tests (renderRoutes from
// strata-react/testing) and the stories build their routers from the same objects.
//
// Routes are real paths (/settings?tab=appearance), not #hashes: the server answers every page path
// with the app (src/flashtap/server/app.py), so a reload or a shared link opens that screen.
import type { RouteObject } from 'react-router'
import { Layout } from './screens/Layout'
import { NotFoundScreen } from './screens/NotFoundScreen'
import { PlayScreen } from './screens/PlayScreen'
import { SettingsScreen } from './screens/SettingsScreen'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <PlayScreen /> },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <NotFoundScreen /> },
    ],
  },
]
