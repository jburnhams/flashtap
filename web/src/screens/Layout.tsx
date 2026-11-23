// The frame every screen shares: product name, side nav (a scrolling row on phones) and the main
// region, from Strata's AppShell. Play is the learner's screen; Learners, Content and Settings are for the grown-up.
// Answers waiting on this device (the server out of reach, or refusing one) are said above every screen, in words for
// the grown-up, so they can check before closing the tab; the queue starts here, so what an earlier visit left is sent
// whichever screen opens first.
import { Gamepad2, Library, Settings, Users } from 'lucide-react'
import { Outlet } from 'react-router'
import { AppShell, type NavItem } from 'strata-react'
import { answers } from '../api'
import { OutboxStatus, useOutboxStarted } from '../outbox'

export const nav: NavItem[] = [
  { to: '/', label: 'Play', icon: Gamepad2, end: true },
  { to: '/learners', label: 'Learners', icon: Users },
  { to: '/content', label: 'Content', icon: Library },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const product = 'Flashtap'

export function Layout() {
  useOutboxStarted(answers)
  return (
    <AppShell product={product} nav={nav}>
      <div className="grid max-w-5xl gap-8 pb-16">
        <OutboxStatus outbox={answers} noun="answer" />
        <Outlet />
      </div>
    </AppShell>
  )
}
