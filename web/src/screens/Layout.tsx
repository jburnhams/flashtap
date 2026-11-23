// The frame every screen shares: product name, side nav (a scrolling row on phones) and the main
// region, from Strata's AppShell, inside the app's voice (../voice.ts: the clips list, read once). Play is the
// learner's screen; Learners, Content, Sounds and Settings are for the grown-up.
import { AudioLines, Gamepad2, Library, Settings, Users } from 'lucide-react'
import { Outlet } from 'react-router'
import { AppShell, type NavItem } from 'strata-react'
import { VoiceProvider } from '../voice'

export const nav: NavItem[] = [
  { to: '/', label: 'Play', icon: Gamepad2, end: true },
  { to: '/learners', label: 'Learners', icon: Users },
  { to: '/content', label: 'Content', icon: Library },
  { to: '/sounds', label: 'Sounds', icon: AudioLines },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const product = 'Flashtap'

export function Layout() {
  return (
    <VoiceProvider>
      <AppShell product={product} nav={nav}>
        <div className="grid max-w-5xl gap-8 pb-16">
          <Outlet />
        </div>
      </AppShell>
    </VoiceProvider>
  )
}
