// Sample data for the mock server (handlers.ts): the same records answer the unit and integration
// tests, every Storybook story and the visual suite's screenshots, so a screen looks the same in
// each. Rounds are fixed (one per mode), so screenshots do not change from run to run.
import type { ModeInfo, Round, Settings } from '../api'

export const defaultSettings: Settings = { mode: 'mixed', choices: '4', tries: '0' }

export const modes: ModeInfo[] = [
  { mode: 'matching', name: 'Matching', description: 'Find the animal, food or vehicle that was named' },
  { mode: 'colours', name: 'Colours', description: 'Find the shape of the named colour' },
  { mode: 'shapes', name: 'Shapes', description: 'Find the named coloured shape' },
  { mode: 'letters', name: 'Letters', description: 'Find the picture whose word starts with the letter' },
  { mode: 'counting', name: 'Counting', description: 'Count the pictures and tap the number' },
  { mode: 'mixed', name: 'Mixed', description: 'A different kind of round each time' },
]

const opt = (id: string, picture: string, word: string, correct: boolean, feedback: string) => ({ id, picture, word, correct, feedback })

/** One round per mode, in the server's shape (taken from `flashtap round --json`). */
export const rounds: Record<Round['mode'], Round> = {
  matching: {
    mode: 'matching', seed: 7, prompt: 'Find the cow.', show: '🐄', answer: 'cow', tries: null,
    options: [
      opt('pig', '🐖', 'pig', false, 'No, that’s a pig.'),
      opt('cow', '🐄', 'cow', true, 'Yes! You found the cow.'),
      opt('duck', '🦆', 'duck', false, 'No, that’s a duck.'),
      opt('lion', '🦁', 'lion', false, 'No, that’s a lion.'),
    ],
  },
  colours: {
    mode: 'colours', seed: 3, prompt: 'Which one is yellow?', show: 'YELLOW', answer: 'yellow_circle', tries: null,
    options: [
      opt('yellow_circle', '🟡', 'yellow circle', true, 'Yes! That one is yellow.'),
      opt('orange_diamond', '🔶', 'orange diamond', false, 'No, that’s an orange diamond.'),
      opt('blue_square', '🟦', 'blue square', false, 'No, that’s a blue square.'),
      opt('red_circle', '🔴', 'red circle', false, 'No, that’s a red circle.'),
    ],
  },
  shapes: {
    mode: 'shapes', seed: 4, prompt: 'Find the green square.', show: '🟩', answer: 'green_square', tries: null,
    options: [
      opt('green_circle', '🟢', 'green circle', false, 'No, that’s a green circle.'),
      opt('green_square', '🟩', 'green square', true, 'Yes! You found the green square.'),
      opt('white_square', '⬜', 'white square', false, 'No, that’s a white square.'),
      opt('red_square', '🟥', 'red square', false, 'No, that’s a red square.'),
    ],
  },
  letters: {
    mode: 'letters', seed: 11, prompt: 'What starts with the letter D?', show: 'D', answer: 'dog', tries: null,
    options: [
      opt('apple', '🍎', 'apple', false, 'No, that’s an apple.'),
      opt('monkey', '🐒', 'monkey', false, 'No, that’s a monkey.'),
      opt('dog', '🐕', 'dog', true, 'Yes! Dog starts with D.'),
      opt('pig', '🐖', 'pig', false, 'No, that’s a pig.'),
    ],
  },
  counting: {
    mode: 'counting', seed: 5, prompt: 'How many apples are there?', show: '🍎 🍎 🍎', answer: 'n3', tries: null,
    options: [
      opt('n5', '5', '5', false, 'No, that’s 5.'),
      opt('n3', '3', '3', true, 'Yes! There are 3 apples.'),
      opt('n9', '9', '9', false, 'No, that’s 9.'),
      opt('n2', '2', '2', false, 'No, that’s 2.'),
    ],
  },
}
