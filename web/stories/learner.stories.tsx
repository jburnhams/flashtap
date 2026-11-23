import type { Meta, StoryObj } from '@storybook/react-vite'
import { evidenceLoading, profileError, profileLoading } from '../src/mocks/handlers'
import { FOX, OWL } from '../src/mocks/learners'
import { AppAt } from './app-at'

const meta = {
  title: 'Screens/Learner',
  render: () => <AppAt route={`/learners/${FOX}`} />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

/** The skills with evidence, each with BKT's estimate beside the rule baseline's. */
export const Seen: Story = {}
/** Every skill, the unobserved ones kept apart as "Not seen yet". */
export const AllSkills: Story = { render: () => <AppAt route={`/learners/${FOX}?show=all`} /> }
/** A skill opened to the rounds behind it: counted or not, and why. */
export const EvidenceOpen: Story = { render: () => <AppAt route={`/learners/${FOX}?open=maths.counting.objects`} /> }
export const EvidenceLoading: Story = { render: () => <AppAt route={`/learners/${FOX}?open=maths.counting.objects`} />, beforeEach: ({ msw }) => msw.use(evidenceLoading) }
/** How they play: each kind with its numbers, the faces and the picks, and the patterns worth a look as hypotheses. */
export const Engagement: Story = { render: () => <AppAt route={`/learners/${FOX}?show=engagement`} /> }
/** Nothing played yet, so nothing to say about how. */
export const EngagementNothingYet: Story = { render: () => <AppAt route={`/learners/${OWL}?show=engagement`} /> }
/** Added, never played. */
export const NothingYet: Story = { render: () => <AppAt route={`/learners/${OWL}`} /> }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(profileLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(profileError) }
export const Phone: Story = { tags: ['visual-phone'] }
