import type { Meta, StoryObj } from '@storybook/react-vite'
import { roundError, roundLoading } from '../src/mocks/handlers'
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
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(roundLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(roundError) }
export const Phone: Story = { tags: ['visual-phone'] }
