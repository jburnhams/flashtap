// A path the app has no screen for, such as an old bookmark. It says so and offers the way back,
// rather than showing an empty frame.
import { useLocation } from 'react-router'
import { EmptyState, PageHeader, TextLink } from 'strata-react'

export function NotFoundScreen() {
  const { pathname } = useLocation()
  return (
    <>
      <PageHeader title="No such page" />
      <EmptyState title={`There is nothing at ${pathname}`} action={<TextLink to="/" className="type-label">Go and play</TextLink>}>
        The link may be from an older version of the app. Every screen is in the menu.
      </EmptyState>
    </>
  )
}
