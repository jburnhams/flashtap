import type { Meta, StoryObj } from '@storybook/react-vite'
import { contentEmpty, contentError, contentLoading, contentReviewed } from '../src/mocks/handlers'
import { AppAt } from './app-at'

const meta = {
  title: 'Screens/Content',
  render: () => <AppAt route="/content" />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const Skills: Story = {}
/** A skill opened in place: what it builds on, what it leads to, its misconceptions. */
export const SkillOpen: Story = { render: () => <AppAt route="/content?open=maths.counting.objects" /> }
export const Curriculum: Story = { render: () => <AppAt route="/content?tab=curriculum" /> }
export const Phonics: Story = { render: () => <AppAt route="/content?tab=phonics" /> }
export const Reviewed: Story = { beforeEach: ({ msw }) => msw.use(contentReviewed) }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(contentLoading) }
export const NoPacks: Story = { beforeEach: ({ msw }) => msw.use(contentEmpty) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(contentError) }
export const Phone: Story = { tags: ['visual-phone'] }
