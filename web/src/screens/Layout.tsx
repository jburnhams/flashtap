// The frame every screen shares: product name, side nav (a scrolling row on phones) and the main
// region, from Strata's AppShell, inside the app's voice (../voice.ts: the clips list, read once). Play is the
// learner's screen; Learners, Content, Sounds and Settings are for the grown-up.
// Answers waiting on this device (the server out of reach, or refusing one) are said above every screen, in words for
// the grown-up, so they can check before closing the tab; the queue starts here, so what an earlier visit left is sent
// whichever screen opens first. Every answer the server takes, whenever it goes (at once, on a retry, or left by an
// earlier visit), refreshes the learners' records, so a report never lags behind what was sent.
import { useQueryClient } from '@tanstack/react-query'
import { AudioLines, Gamepad2, Library, Settings, Users } from 'lucide-react'
import { useEffect } from 'react'
import { Outlet } from 'react-router'
import { AppShell, type NavItem } from 'strata-react'
import { answers } from '../api'
import { OutboxStatus, useOutboxStarted } from '../outbox'
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
  useOutboxStarted(answers)
  const queryClient = useQueryClient()
  useEffect(() => answers.onSent(() => void queryClient.invalidateQueries({ queryKey: ['learners'] })), [queryClient])
  return (
    <VoiceProvider>
      <AppShell product={product} nav={nav}>
        <div className="grid max-w-5xl gap-8 pb-16">
          <OutboxStatus outbox={answers} noun="answer" />
          <Outlet />
        </div>
      </AppShell>
    </VoiceProvider>
  )
}
