import type { Meta, StoryObj } from '@storybook/react-vite'
import { voiceAllMade, voiceError, voiceLoading } from '../src/mocks/handlers'
import { AppAt } from './app-at'

const meta = {
  title: 'Screens/Sounds',
  render: () => <AppAt route="/sounds" />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

/** Four consonants recorded, some sounds made, the rest not made yet. */
export const Sounds: Story = {}
export const AllMade: Story = { beforeEach: ({ msw }) => msw.use(voiceAllMade) }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(voiceLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(voiceError) }
export const Phone: Story = { tags: ['visual-phone'] }
