import type { Meta, StoryObj } from '@storybook/react-vite'
import { nextBreak, nextChoice, nextEnd, nextError, quickLookGoes, quickLookStays, roundError, roundFor, roundLoading, roundUnreachable } from '../src/mocks/handlers'
import { FOX } from '../src/mocks/learners'
import { AppAt } from './app-at'

/** Earlier stories in the same browser keep rounds (src/reserve.ts): a story of the server away starts with none. */
const forgetKept = () => window.localStorage.clear()

const meta = {
  title: 'Screens/Play',
  render: () => <AppAt route="/" />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const Matching: Story = {}
export const Colours: Story = { render: () => <AppAt route="/?mode=colours" /> }
export const Shapes: Story = { render: () => <AppAt route="/?mode=shapes" /> }
export const Letters: Story = { render: () => <AppAt route="/?mode=letters" /> }
/** Play inside another app's frame (a video player's break): no nav, rounds chosen for the learner in the link. */
export const Break: Story = { render: () => <AppAt route={`/break?learner=${FOX}`} /> }
export const Counting: Story = { render: () => <AppAt route="/?mode=counting" /> }
export const Missing: Story = { render: () => <AppAt route="/?mode=missing" /> }
/** A quick look while its pictures show (held on screen for the shot), and after they have gone. */
export const QuickLook: Story = { render: () => <AppAt route="/?mode=quick_look" />, beforeEach: ({ msw }) => msw.use(quickLookStays) }
export const QuickLookGone: Story = { render: () => <AppAt route="/?mode=quick_look" />, beforeEach: ({ msw }) => msw.use(quickLookGoes) }
export const Listen: Story = { render: () => <AppAt route="/?mode=listen" /> }
export const GiveANumber: Story = { render: () => <AppAt route="/?mode=give" /> }
export const Order: Story = { render: () => <AppAt route="/?mode=order" /> }
export const Capitals: Story = { render: () => <AppAt route="/?mode=capitals" /> }
export const SortBySound: Story = { render: () => <AppAt route="/?mode=sort_sounds" /> }
/** A sound on its own is said (from its clip, or described by the browser), never printed: the speaker stands for it. */
export const Sounds: Story = { render: () => <AppAt route="/?mode=sounds" /> }
/** A learner chosen in Who is playing: each round is recorded for them. */
export const PlayingAsFox: Story = { render: () => <AppAt route={`/?learner=${FOX}`} /> }
/** Chosen for them: the adaptive engine picks each round for the learner and says why, for the grown-up. */
export const ChosenForFox: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} /> }
/** Chosen for them needs to know who is playing. */
export const ChosenForNobody: Story = { render: () => <AppAt route="/?mode=next" /> }
/** Every few rounds the learner picks the next activity: two picture tiles, their names said aloud. */
export const ChoiceOfTwo: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} />, beforeEach: ({ msw }) => msw.use(nextChoice) }
export const ChoiceOfTwoPhone: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} />, beforeEach: ({ msw }) => msw.use(nextChoice), tags: ['visual-phone'] }
export const BreakOffered: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} />, beforeEach: ({ msw }) => msw.use(nextBreak) }
export const SessionOver: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} />, beforeEach: ({ msw }) => msw.use(nextEnd) }
/** The engine cannot be reached and no round of the kinds it chose is kept on this device. */
export const ChosenServerAway: Story = { render: () => <AppAt route={`/?mode=next&learner=${FOX}`} />, beforeEach: ({ msw }) => { forgetKept(); msw.use(nextError) } }
/** The server cannot be reached: a round the device kept earlier is played, and the line under it says so. */
export const KeptRound: Story = {
  render: () => <AppAt route={`/?mode=counting&learner=${FOX}`} />,
  beforeEach: ({ msw }) => {
    msw.use(roundUnreachable)
    // Two of the same: when the learners arrive after the first round was asked for, the change of who is playing
    // asks again (PlayScreen's Game), and a second take must not find the reserve empty and fail the shot.
    const kept = { ...roundFor('counting'), seed: 9000 }
    window.localStorage.setItem('flashtap:reserve:counting', JSON.stringify([kept, kept]))
    return () => window.localStorage.removeItem('flashtap:reserve:counting')
  },
}
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(roundLoading) }
/** The server answered 503 and no round is kept on this device. */
export const ServerError: Story = { beforeEach: ({ msw }) => { forgetKept(); msw.use(roundError) } }
export const Phone: Story = { tags: ['visual-phone'] }
