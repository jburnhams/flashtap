// Sample data for the mock server (handlers.ts): the same records answer the unit and integration
// tests, every Storybook story and the visual suite's screenshots, so a screen looks the same in
// each. Rounds are fixed (one per mode), so screenshots do not change from run to run.
import type { Mechanic, ModeInfo, Round, Settings } from '../api'

export const defaultSettings: Settings = { mode: 'mixed', choices: 4, tries: 0, session_rounds: 20, session_minutes: 15, break_every: 10, choice_every: 5, rate_every: 4 }

export const modes: ModeInfo[] = [
  { mode: 'matching', name: 'Matching', description: 'Find the animal, food or vehicle that was named', mechanic: 'select_one' },
  { mode: 'colours', name: 'Colours', description: 'Find the shape of the named colour', mechanic: 'select_one' },
  { mode: 'shapes', name: 'Shapes', description: 'Find the named coloured shape', mechanic: 'select_one' },
  { mode: 'letters', name: 'Letters', description: 'Find the picture whose word starts with the letter', mechanic: 'select_one' },
  { mode: 'counting', name: 'Counting', description: 'Count the pictures and tap the number', mechanic: 'select_one' },
  { mode: 'missing', name: 'Missing number', description: 'Find the number missing from a run', mechanic: 'fill_missing' },
  { mode: 'quick_look', name: 'Quick look', description: 'See a few pictures for a moment and say how many', mechanic: 'brief_exposure' },
  { mode: 'listen', name: 'Listen', description: 'Hear a word and tap the letter it starts with', mechanic: 'audio_respond' },
  { mode: 'give', name: 'Give a number', description: 'Put the asked-for number of pictures in the basket', mechanic: 'give_n' },
  { mode: 'order', name: 'Order', description: 'Put numbers in order, smallest first', mechanic: 'sequence' },
  { mode: 'capitals', name: 'Capitals', description: 'Put each small letter on its capital', mechanic: 'match_pairs' },
  { mode: 'sort_sounds', name: 'Sort by sound', description: 'Put pictures with the letter of their first sound', mechanic: 'sort' },
  { mode: 'sounds', name: 'Sounds', description: 'Hear a sound on its own and tap the letters that make it', mechanic: 'audio_respond' },
  { mode: 'mixed', name: 'Mixed', description: 'A different kind of round each time', mechanic: null },
]

const opt = (id: string, picture: string, word: string, correct: boolean, feedback: string) => ({ id, picture, word, correct, feedback, distractor: correct ? '' : 'random' })
/** The content packs each kind of round draws from and their versions, as `rounds.content_of` gives them. */
const CONTENT: Record<Round['mode'], Record<string, number>> = {
  matching: {"language": 1, "phonics.letters_and_sounds": 1, "words": 1},
  colours: {"language": 1, "phonics.letters_and_sounds": 1, "words": 1},
  shapes: {"language": 1, "maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  letters: {"language": 1, "literacy.early": 1, "phonics.letters_and_sounds": 1, "words": 1},
  counting: {"maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  missing: {"maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  quick_look: {"maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  listen: {"literacy.early": 1, "phonics.letters_and_sounds": 1, "words": 1},
  give: {"maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  order: {"maths.number": 1, "phonics.letters_and_sounds": 1, "words": 1},
  capitals: {"literacy.early": 1, "phonics.letters_and_sounds": 1, "words": 1},
  sort_sounds: {"language": 1, "literacy.early": 1, "phonics.letters_and_sounds": 1, "words": 1},
  sounds: {"literacy.early": 1, "phonics.letters_and_sounds": 1, "words": 1},
}
/** The fields a one-tap round carries besides its question and options. */
const tap = (mode: Round['mode'], seed: number, skill: string, mechanic: Mechanic = 'select_one') => ({
  mode, seed, version: 1, content: CONTENT[mode], choices: 4, mechanic, skills: [{ skill, role: 'primary' as const }], exposure_ms: null, pieces: [], places: [], done_feedback: '',
})

/** One round per mode, in the server's shape. The first five are kept from 0.2 (tests and baselines name their
 * pictures); the rest are `flashtap round --mode <kind> --choices 4 --seed <n> --json` as printed. */
export const rounds: Record<Round['mode'], Round> = {
  matching: {
    ...tap('matching', 7, 'language.vocabulary.receptive'), prompt: 'Find the cow.', say: 'Find the cow.', show: '🐄', answer: 'cow', tries: null,
    options: [
      opt('pig', '🐖', 'pig', false, 'No, that’s a pig.'),
      opt('cow', '🐄', 'cow', true, 'Yes! You found the cow.'),
      opt('duck', '🦆', 'duck', false, 'No, that’s a duck.'),
      opt('lion', '🦁', 'lion', false, 'No, that’s a lion.'),
    ],
  },
  colours: {
    ...tap('colours', 3, 'language.vocabulary.colours'), prompt: 'Which one is yellow?', say: 'Which one is yellow?', show: 'YELLOW', answer: 'yellow_circle', tries: null,
    options: [
      opt('yellow_circle', '🟡', 'yellow circle', true, 'Yes! That one is yellow.'),
      opt('orange_diamond', '🔶', 'orange diamond', false, 'No, that’s an orange diamond.'),
      opt('blue_square', '🟦', 'blue square', false, 'No, that’s a blue square.'),
      opt('red_circle', '🔴', 'red circle', false, 'No, that’s a red circle.'),
    ],
  },
  shapes: {
    ...tap('shapes', 4, 'maths.geometry.name_2d'), prompt: 'Find the green square.', say: 'Find the green square.', show: '🟩', answer: 'green_square', tries: null,
    options: [
      opt('green_circle', '🟢', 'green circle', false, 'No, that’s a green circle.'),
      opt('green_square', '🟩', 'green square', true, 'Yes! You found the green square.'),
      opt('white_square', '⬜', 'white square', false, 'No, that’s a white square.'),
      opt('red_square', '🟥', 'red square', false, 'No, that’s a red square.'),
    ],
  },
  letters: {
    ...tap('letters', 11, 'literacy.gpc.initial_letter'), prompt: 'What starts with the letter D?', say: 'What starts with the letter D?', show: 'D', answer: 'dog', tries: null,
    options: [
      opt('apple', '🍎', 'apple', false, 'No, that’s an apple.'),
      opt('monkey', '🐒', 'monkey', false, 'No, that’s a monkey.'),
      opt('dog', '🐕', 'dog', true, 'Yes! Dog starts with D.'),
      opt('pig', '🐖', 'pig', false, 'No, that’s a pig.'),
    ],
  },
  counting: {
    ...tap('counting', 5, 'maths.counting.objects'), prompt: 'How many apples are there?', say: 'How many apples are there?', show: '🍎 🍎 🍎', answer: 'n3', tries: null,
    options: [
      opt('n5', '5', '5', false, 'No, that’s 5.'),
      opt('n3', '3', '3', true, 'Yes! There are 3 apples.'),
      opt('n9', '9', '9', false, 'No, that’s 9.'),
      opt('n2', '2', '2', false, 'No, that’s 2.'),
    ],
  },
  missing: {"mode": "missing", "version": 1, "content": CONTENT.missing, "choices": 4, "seed": 5, "mechanic": "fill_missing", "skills": [{"skill": "maths.verbal_count.one_more", "role": "primary"}, {"skill": "maths.verbal_count.forwards", "role": "secondary"}, {"skill": "maths.numerals.recognise", "role": "confound"}], "prompt": "Which number is missing?", "say": "Which number is missing?", "show": "4 5 ? 7 8", "exposure_ms": null, "options": [{"id": "n7", "picture": "7", "word": "7", "correct": false, "feedback": "No, that's 7.", "distractor": "near_number"}, {"id": "n9", "picture": "9", "word": "9", "correct": false, "feedback": "No, that's 9.", "distractor": "reversal"}, {"id": "n6", "picture": "6", "word": "6", "correct": true, "feedback": "Yes! 6 is missing.", "distractor": ""}, {"id": "n5", "picture": "5", "word": "5", "correct": false, "feedback": "No, that's 5.", "distractor": "random"}], "answer": "n6", "pieces": [], "places": [], "done_feedback": "", "tries": null},
  quick_look: {"mode": "quick_look", "version": 1, "content": CONTENT.quick_look, "choices": 4, "seed": 4, "mechanic": "brief_exposure", "skills": [{"skill": "maths.subitising.perceptual", "role": "primary"}, {"skill": "maths.numerals.recognise", "role": "confound"}], "prompt": "How many did you see?", "say": "Look quickly! How many ducks?", "show": "🦆 🦆 🦆", "exposure_ms": 1500, "options": [{"id": "n4", "picture": "4", "word": "4", "correct": false, "feedback": "No, that's 4.", "distractor": "near_number"}, {"id": "n8", "picture": "8", "word": "8", "correct": false, "feedback": "No, that's 8.", "distractor": "random"}, {"id": "n3", "picture": "3", "word": "3", "correct": true, "feedback": "Yes! There were 3 ducks.", "distractor": ""}, {"id": "n2", "picture": "2", "word": "2", "correct": false, "feedback": "No, that's 2.", "distractor": "near_number"}], "answer": "n3", "pieces": [], "places": [], "done_feedback": "", "tries": null},
  listen: {"mode": "listen", "version": 1, "content": CONTENT.listen, "choices": 4, "seed": 2, "mechanic": "audio_respond", "skills": [{"skill": "literacy.gpc.grapheme_from_sound", "role": "primary"}, {"skill": "literacy.phonemic.initial_sound", "role": "secondary"}], "prompt": "Listen, then tap the letter it starts with.", "say": "dog. Which letter does dog start with?", "show": "🐕", "exposure_ms": null, "options": [{"id": "l_p", "picture": "p", "word": "p", "correct": false, "feedback": "No, that's p.", "distractor": "confusable_grapheme"}, {"id": "l_t", "picture": "t", "word": "t", "correct": false, "feedback": "No, that's t.", "distractor": "random"}, {"id": "l_b", "picture": "b", "word": "b", "correct": false, "feedback": "No, that's b.", "distractor": "confusable_grapheme"}, {"id": "l_d", "picture": "d", "word": "d", "correct": true, "feedback": "Yes! Dog starts with d.", "distractor": ""}], "answer": "l_d", "pieces": [], "places": [], "done_feedback": "", "tries": null},
  give: {"mode": "give", "version": 1, "content": CONTENT.give, "choices": 4, "seed": 4, "mechanic": "give_n", "skills": [{"skill": "maths.cardinality.give_n", "role": "primary"}, {"skill": "maths.counting.one_to_one", "role": "confound"}], "prompt": "Put 3 ducks in the basket.", "say": "Put 3 ducks in the basket.", "show": "", "exposure_ms": null, "options": [], "answer": "", "pieces": [{"id": "duck1", "picture": "🦆", "word": "duck"}, {"id": "duck2", "picture": "🦆", "word": "duck"}, {"id": "duck3", "picture": "🦆", "word": "duck"}, {"id": "duck4", "picture": "🦆", "word": "duck"}, {"id": "duck5", "picture": "🦆", "word": "duck"}], "places": [{"id": "basket", "picture": "🧺", "word": "the basket", "takes": ["duck1", "duck2", "duck3", "duck4", "duck5"], "holds": 3}], "done_feedback": "Yes! There are 3 ducks in the basket.", "tries": null},
  order: {"mode": "order", "version": 1, "content": CONTENT.order, "choices": 4, "seed": 6, "mechanic": "sequence", "skills": [{"skill": "maths.comparison.order", "role": "primary"}, {"skill": "maths.numerals.recognise", "role": "confound"}], "prompt": "Put the numbers in order, smallest first.", "say": "Put the numbers in order, smallest first.", "show": "", "exposure_ms": null, "options": [], "answer": "", "pieces": [{"id": "n4", "picture": "4", "word": "4"}, {"id": "n7", "picture": "7", "word": "7"}, {"id": "n9", "picture": "9", "word": "9"}, {"id": "n1", "picture": "1", "word": "1"}], "places": [{"id": "first", "picture": "", "word": "first", "takes": ["n1"], "holds": 1}, {"id": "second", "picture": "", "word": "second", "takes": ["n4"], "holds": 1}, {"id": "third", "picture": "", "word": "third", "takes": ["n7"], "holds": 1}, {"id": "fourth", "picture": "", "word": "fourth", "takes": ["n9"], "holds": 1}], "done_feedback": "Yes! 1, 4, 7 and 9.", "tries": null},
  capitals: {"mode": "capitals", "version": 1, "content": CONTENT.capitals, "choices": 4, "seed": 2, "mechanic": "match_pairs", "skills": [{"skill": "literacy.letters.case_match", "role": "primary"}, {"skill": "literacy.letters.identify", "role": "secondary"}], "prompt": "Put each small letter on its capital.", "say": "Put each small letter on its capital.", "show": "", "exposure_ms": null, "options": [], "answer": "", "pieces": [{"id": "small_b", "picture": "b", "word": "small b"}, {"id": "small_p", "picture": "p", "word": "small p"}, {"id": "small_e", "picture": "e", "word": "small e"}, {"id": "small_d", "picture": "d", "word": "small d"}], "places": [{"id": "capital_p", "picture": "P", "word": "capital P", "takes": ["small_p"], "holds": 1}, {"id": "capital_e", "picture": "E", "word": "capital E", "takes": ["small_e"], "holds": 1}, {"id": "capital_d", "picture": "D", "word": "capital D", "takes": ["small_d"], "holds": 1}, {"id": "capital_b", "picture": "B", "word": "capital B", "takes": ["small_b"], "holds": 1}], "done_feedback": "Yes! Every letter is with its capital.", "tries": null},
  sort_sounds: {"mode": "sort_sounds", "version": 1, "content": CONTENT.sort_sounds, "choices": 4, "seed": 2, "mechanic": "sort", "skills": [{"skill": "literacy.phonemic.initial_sound", "role": "primary"}, {"skill": "literacy.gpc.sound_from_grapheme", "role": "secondary"}, {"skill": "language.vocabulary.receptive", "role": "confound"}], "prompt": "Put each picture with the letter it starts with.", "say": "Put each picture with the letter it starts with. Say the word, and listen for its first sound.", "show": "", "exposure_ms": null, "options": [], "answer": "", "pieces": [{"id": "bell", "picture": "🔔", "word": "bell"}, {"id": "bus", "picture": "🚌", "word": "bus"}, {"id": "duck", "picture": "🦆", "word": "duck"}, {"id": "dog", "picture": "🐕", "word": "dog"}], "places": [{"id": "sound_b", "picture": "b", "word": "b", "takes": ["bus", "bell"], "holds": 2}, {"id": "sound_d", "picture": "d", "word": "d", "takes": ["dog", "duck"], "holds": 2}], "done_feedback": "Yes! Every picture is with its first sound.", "tries": null},
  sounds: {"mode": "sounds", "version": 1, "content": CONTENT.sounds, "choices": 4, "seed": 81, "mechanic": "audio_respond", "skills": [{"skill": "literacy.gpc.grapheme_from_sound", "role": "primary"}], "prompt": "Listen, then tap the letters that make the sound.", "say": "Listen. /ʃ/ Which letters make that sound?", "show": "🔊", "exposure_ms": null, "options": [{"id": "g_l", "picture": "l", "word": "l", "correct": false, "feedback": "No, that's l.", "distractor": "random"}, {"id": "g_sh", "picture": "sh", "word": "sh", "correct": true, "feedback": "Yes! sh makes that sound.", "distractor": ""}, {"id": "g_oo", "picture": "oo", "word": "oo", "correct": false, "feedback": "No, that's oo.", "distractor": "random"}, {"id": "g_s", "picture": "s", "word": "s", "correct": false, "feedback": "No, that's s.", "distractor": "random"}], "answer": "g_sh", "pieces": [], "places": [], "done_feedback": "", "tries": null},
}
