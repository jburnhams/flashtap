// The frame every screen shares: product name, side nav (a scrolling row on phones) and the main
// region, from Strata's AppShell, inside the app's voice (../voice.ts: the clips list, read once). Play is the
// learner's screen; Learners, Content, Sounds and Settings are for the grown-up. `Bare` is the frame of the Break
// screen, shown inside another app: the voice and the answers' queue, nothing else.
// Answers waiting on this device (the server out of reach, or refusing one) are said above every screen, in words for
// the grown-up, so they can check before closing the tab; the queue starts here, so what an earlier visit left is sent
// whichever screen opens first. Every answer the server takes, whenever it goes (at once, on a retry, or left by an
// earlier visit), refreshes the learners' records, so a report never lags behind what was sent.
// The grown-up's screens keep to a reading width; Play takes the whole main region and centres itself in it (the
// owner, 2026-11-27: "grow with viewport to fill ... centre content"), since a round is pictures, not lines to read.
import { useQueryClient } from '@tanstack/react-query'
import { AudioLines, Gamepad2, Library, Settings, Users } from 'lucide-react'
import { useEffect } from 'react'
import { Outlet, useMatch } from 'react-router'
import { AppShell, cn, OutboxStatus, useOutboxStarted, type NavItem } from 'strata-react'
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
  const play = useMatch({ path: '/', end: true }) !== null
  return (
    <VoiceProvider>
      <AppShell product={product} nav={nav}>
        <div className={cn('grid gap-8 pb-16', !play && 'max-w-5xl')}>
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
