import type { Meta, StoryObj } from '@storybook/react-vite'
import { voiceAllRecorded, voiceError, voiceLoading } from '../src/mocks/handlers'
import { AppAt } from './app-at'

const meta = {
  title: 'Screens/Sounds',
  render: () => <AppAt route="/sounds" />,
  tags: ['visual-wide'],
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

/** Four consonants recorded, most vowels made: the rest are to record. */
export const Sounds: Story = {}
export const AllRecorded: Story = { beforeEach: ({ msw }) => msw.use(voiceAllRecorded) }
export const Loading: Story = { beforeEach: ({ msw }) => msw.use(voiceLoading) }
export const ServerError: Story = { beforeEach: ({ msw }) => msw.use(voiceError) }
export const Phone: Story = { tags: ['visual-phone'] }
