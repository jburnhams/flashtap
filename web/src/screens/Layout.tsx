// The frame every screen shares: product name, side nav (a scrolling row on phones) and the main
// region, from Strata's AppShell, inside the app's voice (../voice.ts: the clips list, read once). Play is the
// learner's screen; Learners, Content, Sounds and Settings are for the grown-up. `Bare` is the frame of the Break
// screen, shown inside another app: the voice and the answers' queue, nothing else.
// Answers waiting on this device (the server out of reach, or refusing one) are said above every screen, in words for
// the grown-up, so they can check before closing the tab; the queue starts here, so what an earlier visit left is sent
// whichever screen opens first. Every answer the server takes, whenever it goes (at once, on a retry, or left by an
// earlier visit), refreshes the learners' records, so a report never lags behind what was sent.
import { useQueryClient } from '@tanstack/react-query'
import { AudioLines, Gamepad2, Library, Settings, Users } from 'lucide-react'
import { useEffect } from 'react'
import { Outlet } from 'react-router'
import { AppShell, OutboxStatus, useOutboxStarted, type NavItem } from 'strata-react'
import { answers } from '../api'
import { VoiceProvider } from '../voice'

export const nav: NavItem[] = [
  { to: '/', label: 'Play', icon: Gamepad2, end: true },
  { to: '/learners', label: 'Learners', icon: Users },
  { to: '/content', label: 'Content', icon: Library },
  { to: '/sounds', label: 'Sounds', icon: AudioLines },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export const product = 'Flashtap'

/** Starts the answers' queue, and reads the learners again whenever one is sent: every shell does this. */
function useAnswers() {
  useOutboxStarted(answers)
  const queryClient = useQueryClient()
  useEffect(() => answers.onSent(() => void queryClient.invalidateQueries({ queryKey: ['learners'] })), [queryClient])
}

export function Layout() {
  useAnswers()
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

/** The shell of a page framed in another app (the Break screen): the voice and the answers' queue, no product name or nav,
 * and no word about waiting answers (that is for the grown-up, on the other screens). */
export function Bare() {
  useAnswers()
  return (
    <VoiceProvider>
      <main className="grid min-h-dvh content-start gap-8 bg-background p-6 text-foreground">
        <Outlet />
      </main>
    </VoiceProvider>
  )
}
