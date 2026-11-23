import type { Meta, StoryObj } from '@storybook/react-vite'
import { learnersError, learnersLoading, learnersNone, learnersUnplayed } from '../src/mocks/handlers'
import { AppAt } from './app-at'

const meta = {
  title: 'Screens/Learners',
  render: () => <AppAt route="/learners" />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const Ready: Story = {}
export const NobodyYet: Story = { beforeEach: ({ msw }) => msw.use(learnersNone) }
export const NobodyPlayed: Story = { beforeEach: ({ msw }) => msw.use(learnersUnplayed) }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(learnersLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(learnersError) }
export const Phone: Story = { tags: ['visual-phone'] }
