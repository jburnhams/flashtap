// What `GET /api/content` answers, cut down from the real packs (`flashtap content list --json`) to a few skills,
// curriculum goals and phonics sets, so the Content screen's stories and screenshots stay short. Regenerate by hand
// when the server's shape changes: the jsdom tests and the server's own tests read the same fields.
import type { ContentSummary } from '../api'

export const content: ContentSummary = {
  "packs": [
    {
      "id": "core",
      "version": 1,
      "title": "Sources, domains and dimensions",
      "status": "draft"
    },
    {
      "id": "curriculum.uk_eyfs",
      "version": 1,
      "title": "Curriculum: EYFS Early Learning Goals (mathematics, literacy)",
      "status": "draft"
    },
    {
      "id": "maths.number",
      "version": 1,
      "title": "Number: counting, cardinality, subitising, numerals, comparison, composition",
      "status": "draft"
    },
    {
      "id": "phonics.letters_and_sounds",
      "version": 1,
      "title": "Phonics sequence: Letters and Sounds, Phases 2 and 3",
      "status": "draft"
    }
  ],
  "skills": [
    {
      "id": "literacy.phonemic.initial_sound",
      "title": "Hear the first sound in a word",
      "description": "Find the picture whose word starts with a given sound.",
      "domain": "Literacy",
      "strand": "Phonemic awareness",
      "stages": [],
      "modes": [],
      "needs": [
        {
          "skill": "Hear words that start the same",
          "relation": "facilitates",
          "confidence": "high",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        }
      ],
      "leads_to": [
        {
          "skill": "Find the picture for a spoken word",
          "relation": "confounded_by",
          "confidence": "high",
          "source": "Flashtap's own judgement, to be reviewed",
          "note": "A learner who does not know the picture's word cannot hear its first sound."
        },
        {
          "skill": "Blend spoken sounds into a word",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        },
        {
          "skill": "Split a spoken word into its sounds",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        },
        {
          "skill": "Find the letters for a sound",
          "relation": "facilitates",
          "confidence": "high",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        },
        {
          "skill": "Find a word that starts with a letter's sound",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        }
      ],
      "misconceptions": []
    },
    {
      "id": "literacy.gpc.initial_letter",
      "title": "Find a word that starts with a letter's sound",
      "description": "See a letter and find the picture whose word starts with that letter's sound (the Letters round).",
      "domain": "Literacy",
      "strand": "Grapheme-phoneme correspondences",
      "stages": [],
      "modes": [
        "letters"
      ],
      "needs": [
        {
          "skill": "Say the sound for the letters",
          "relation": "prerequisite_strong",
          "confidence": "medium",
          "source": "Flashtap's own judgement, to be reviewed",
          "note": ""
        },
        {
          "skill": "Hear the first sound in a word",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Letters and Sounds: principles and practice of high quality phonics",
          "note": ""
        }
      ],
      "leads_to": [],
      "misconceptions": [
        "Gives the letter's name, not its sound"
      ]
    },
    {
      "id": "maths.counting.one_to_one",
      "title": "Touch or tag each thing once",
      "description": "One number word per object, none skipped or counted twice.",
      "domain": "Mathematics",
      "strand": "Counting objects",
      "stages": [],
      "modes": [],
      "needs": [],
      "leads_to": [
        {
          "skill": "Count a set of things",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        }
      ],
      "misconceptions": [
        "Skips or double-counts objects"
      ]
    },
    {
      "id": "maths.counting.objects",
      "title": "Count a set of things",
      "description": "Count a set by saying the sequence in step with each object.",
      "domain": "Mathematics",
      "strand": "Counting objects",
      "stages": [
        "eyfs"
      ],
      "modes": [
        "counting"
      ],
      "needs": [
        {
          "skill": "Say the number names in order",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        },
        {
          "skill": "Touch or tag each thing once",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        }
      ],
      "leads_to": [
        {
          "skill": "Find the numeral for a spoken number",
          "relation": "confounded_by",
          "confidence": "high",
          "source": "Flashtap's own judgement, to be reviewed",
          "note": "When the answer is a tapped numeral, not knowing the numeral explains a wrong tap as well as a wrong count."
        },
        {
          "skill": "Know the last number counted is how many",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        }
      ],
      "misconceptions": [
        "Skips or double-counts objects"
      ]
    },
    {
      "id": "maths.cardinality.last_number",
      "title": "Know the last number counted is how many",
      "description": "Answer 'how many?' with the last number said, without counting again.",
      "domain": "Mathematics",
      "strand": "Cardinality",
      "stages": [
        "eyfs"
      ],
      "modes": [
        "counting"
      ],
      "needs": [
        {
          "skill": "Count a set of things",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        },
        {
          "skill": "See how many without counting, up to 5",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Early years: cardinality and counting",
          "note": ""
        }
      ],
      "leads_to": [
        {
          "skill": "Give a number of things",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Early years: cardinality and counting",
          "note": ""
        },
        {
          "skill": "Know rearranging does not change how many",
          "relation": "prerequisite_strong",
          "confidence": "medium",
          "source": "Early years: cardinality and counting",
          "note": ""
        },
        {
          "skill": "Match a numeral to a quantity",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Improving Mathematics in the Early Years and Key Stage 1",
          "note": ""
        },
        {
          "skill": "Know zero as none",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Mastering Number: building strong foundations in early maths",
          "note": ""
        },
        {
          "skill": "Tell which has more, fewer or the same",
          "relation": "facilitates",
          "confidence": "high",
          "source": "Mastering Number: building strong foundations in early maths",
          "note": ""
        },
        {
          "skill": "See a number as made of two parts",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Mastering Number: building strong foundations in early maths",
          "note": ""
        }
      ],
      "misconceptions": [
        "Counts again when asked how many"
      ]
    },
    {
      "id": "maths.subitising.perceptual",
      "title": "See how many without counting, up to 5",
      "description": "Name a small number of things shown too briefly to count.",
      "domain": "Mathematics",
      "strand": "Subitising",
      "stages": [
        "eyfs"
      ],
      "modes": [],
      "needs": [],
      "leads_to": [
        {
          "skill": "Know the last number counted is how many",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Early years: cardinality and counting",
          "note": ""
        },
        {
          "skill": "See a number as smaller groups",
          "relation": "prerequisite_strong",
          "confidence": "high",
          "source": "Mastering Number: building strong foundations in early maths",
          "note": ""
        },
        {
          "skill": "Tell which has more, fewer or the same",
          "relation": "facilitates",
          "confidence": "medium",
          "source": "Mastering Number: building strong foundations in early maths",
          "note": ""
        }
      ],
      "misconceptions": []
    }
  ],
  "objectives": [
    {
      "id": "uk_eyfs.elg.number.1",
      "curriculum": "EYFS statutory framework (England)",
      "stage": "eyfs",
      "area": "Mathematics",
      "goal": "Number",
      "text": "Have a deep understanding of number to 10, including the composition of each number.",
      "skills": [
        "Count a set of things",
        "Know the last number counted is how many",
        "Give a number of things",
        "Know rearranging does not change how many",
        "Match a numeral to a quantity",
        "Know zero as none",
        "See a number as made of two parts"
      ],
      "out_of_scope": "",
      "note": ""
    },
    {
      "id": "uk_eyfs.elg.number.2",
      "curriculum": "EYFS statutory framework (England)",
      "stage": "eyfs",
      "area": "Mathematics",
      "goal": "Number",
      "text": "Subitise (recognise quantities without counting) up to 5.",
      "skills": [
        "See how many without counting, up to 5"
      ],
      "out_of_scope": "",
      "note": ""
    },
    {
      "id": "uk_eyfs.elg.word_reading.1",
      "curriculum": "EYFS statutory framework (England)",
      "stage": "eyfs",
      "area": "Literacy",
      "goal": "Word Reading",
      "text": "Say a sound for each letter in the alphabet and at least 10 digraphs.",
      "skills": [
        "Say the sound for the letters",
        "Find the letters for a sound"
      ],
      "out_of_scope": "",
      "note": "Phases 2 and 3 of the phonics sequence hold every letter and 15 or more digraphs. Saying needs speech input; choosing (grapheme_from_sound) is the evidence until then."
    },
    {
      "id": "uk_eyfs.elg.writing.1",
      "curriculum": "EYFS statutory framework (England)",
      "stage": "eyfs",
      "area": "Literacy",
      "goal": "Writing",
      "text": "Write recognisable letters, most of which are correctly formed.",
      "skills": [],
      "out_of_scope": "Letter formation is handwriting with a pencil; tap rounds cannot observe it. The skill is named (literacy.handwriting.letter_formation) so a tracing mechanic can map to it later.",
      "note": ""
    }
  ],
  "phonics": [
    {
      "id": "phonics.ls",
      "title": "Letters and Sounds",
      "dialect": "en-GB",
      "sets": [
        {
          "id": "phonics.ls.p2_set1",
          "title": "Phase 2, set 1",
          "gpcs": [
            {
              "grapheme": "s",
              "phoneme": "s",
              "example": "sun"
            },
            {
              "grapheme": "a",
              "phoneme": "æ",
              "example": "ant"
            },
            {
              "grapheme": "t",
              "phoneme": "t",
              "example": "tap"
            },
            {
              "grapheme": "p",
              "phoneme": "p",
              "example": "pan"
            }
          ],
          "words": []
        },
        {
          "id": "phonics.ls.p2_set2",
          "title": "Phase 2, set 2",
          "gpcs": [
            {
              "grapheme": "i",
              "phoneme": "ɪ",
              "example": "pin"
            },
            {
              "grapheme": "n",
              "phoneme": "n",
              "example": "net"
            },
            {
              "grapheme": "m",
              "phoneme": "m",
              "example": "map"
            },
            {
              "grapheme": "d",
              "phoneme": "d",
              "example": "dog"
            }
          ],
          "words": [
            "map"
          ]
        },
        {
          "id": "phonics.ls.p2_set3",
          "title": "Phase 2, set 3",
          "gpcs": [
            {
              "grapheme": "g",
              "phoneme": "ɡ",
              "example": "got"
            },
            {
              "grapheme": "o",
              "phoneme": "ɒ",
              "example": "on"
            },
            {
              "grapheme": "c",
              "phoneme": "k",
              "example": "cat"
            },
            {
              "grapheme": "k",
              "phoneme": "k",
              "example": "kit"
            }
          ],
          "words": [
            "pig",
            "dog",
            "cat",
            "cap"
          ]
        }
      ]
    }
  ]
}
