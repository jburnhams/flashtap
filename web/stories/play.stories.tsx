import type { Meta, StoryObj } from '@storybook/react-vite'
import { quickLookGoes, quickLookStays, roundError, roundLoading } from '../src/mocks/handlers'
import { FOX } from '../src/mocks/learners'
import { AppAt } from './app-at'

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
/** A learner chosen in Who is playing: each round is recorded for them. */
export const PlayingAsFox: Story = { render: () => <AppAt route={`/?learner=${FOX}`} /> }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(roundLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(roundError) }
export const Phone: Story = { tags: ['visual-phone'] }
