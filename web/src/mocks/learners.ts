// What the learner endpoints answer, made by the real server: an invented learner ("Fox") played 24
// seeded rounds into a scratch database, one was struck out, and `store.profile` and `evidence_rows`
// were printed (cut to the skills seen plus three not seen). Regenerate by hand when the shapes
// change. A grown-up's word on rhyming and the engagement block (kinds, faces, picks, patterns) were
// written by hand in the server's shapes (0.8.0). Learners are invented (AGENTS.md rule 8).
import type { EvidenceRow, LearnerRow, Profile } from '../api'

export const FOX = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
export const OWL = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
export const HARE = 'dddddddddddddddddddddddddddddddd'

export const learners: LearnerRow[] = [
  { id: FOX, nickname: 'Fox', created_at: '2026-11-02T08:00:00Z', attempts: 24, last_played: '2026-11-11T09:23:00Z' },
  { id: OWL, nickname: 'Owl', created_at: '2026-11-03T08:00:00Z', attempts: 0, last_played: null },
  { id: HARE, nickname: 'Hare', created_at: '2026-11-03T08:00:00Z', attempts: 3, last_played: '2026-11-04T16:10:00Z' },
]

export const foxProfile: Profile = {
  "learner": {
    "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "nickname": "Fox",
    "created_at": "2026-11-02T08:00:00Z",
    "attempts": 24,
    "last_played": "2026-11-11T09:23:00Z"
  },
  "sessions": 4,
  "struck": 1,
  "models": [
    {
      "model": "bkt@1",
      "description": "Bayesian knowledge tracing: prior 0.2, learn 0.1, slip 0.1, guess 1 in the number of tiles"
    },
    {
      "model": "rule@1",
      "description": "Share right among the last 5 counted first answers"
    }
  ],
  "skills": [
    {
      "skill": "language.vocabulary.receptive",
      "title": "Find the picture for a spoken word",
      "domain": "Communication and language",
      "strand": "Vocabulary",
      "state": "introduced",
      "estimates": [],
      "counted": 0,
      "right": 0,
      "held": 4,
      "mechanics": [],
      "last_seen": "2026-11-11T09:21:00Z",
      "told": null
    },
    {
      "skill": "literacy.phonemic.initial_sound",
      "title": "Hear the first sound in a word",
      "domain": "Literacy",
      "strand": "Phonemic awareness",
      "state": "introduced",
      "estimates": [],
      "counted": 0,
      "right": 0,
      "held": 4,
      "mechanics": [],
      "last_seen": "2026-11-11T09:21:00Z",
      "told": null
    },
    {
      "skill": "literacy.gpc.initial_letter",
      "title": "Find a word that starts with a letter's sound",
      "domain": "Literacy",
      "strand": "Grapheme-phoneme correspondences",
      "state": "introduced",
      "estimates": [],
      "counted": 0,
      "right": 0,
      "held": 4,
      "mechanics": [],
      "last_seen": "2026-11-11T09:21:00Z",
      "told": null
    },
    {
      "skill": "maths.counting.one_to_one",
      "title": "Touch or tag each thing once",
      "domain": "Mathematics",
      "strand": "Counting objects",
      "state": "introduced",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.9903225806451613,
          "used": 2,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 1.0,
          "used": 2,
          "told": 0
        }
      ],
      "counted": 2,
      "right": 2,
      "held": 1,
      "mechanics": [
        "give_n"
      ],
      "last_seen": "2026-11-08T09:12:00Z",
      "told": { "id": "f0000000000000000000000000000002", "skill": "maths.counting.one_to_one", "says": "not_yet", "observer": "teacher", "note": "", "at": "2026-11-09T15:30:00Z", "withdrawn_at": null }
    },
    {
      "skill": "maths.counting.objects",
      "title": "Count a set of things",
      "domain": "Mathematics",
      "strand": "Counting objects",
      "state": "independent",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.9999468430689268,
          "used": 8,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 1.0,
          "used": 5,
          "told": 0
        }
      ],
      "counted": 8,
      "right": 8,
      "held": 1,
      "mechanics": [
        "select_one"
      ],
      "last_seen": "2026-11-05T09:09:00Z",
      "told": null
    },
    {
      "skill": "maths.cardinality.last_number",
      "title": "Know the last number counted is how many",
      "domain": "Mathematics",
      "strand": "Cardinality",
      "state": "emerging",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.9999468430689268,
          "used": 8,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 1.0,
          "used": 5,
          "told": 0
        }
      ],
      "counted": 8,
      "right": 8,
      "held": 1,
      "mechanics": [
        "select_one"
      ],
      "last_seen": "2026-11-05T09:09:00Z",
      "told": null
    },
    {
      "skill": "maths.cardinality.give_n",
      "title": "Give a number of things",
      "domain": "Mathematics",
      "strand": "Cardinality",
      "state": "emerging",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.9345941351466214,
          "used": 3,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 0.6666666666666666,
          "used": 3,
          "told": 0
        }
      ],
      "counted": 3,
      "right": 2,
      "held": 0,
      "mechanics": [
        "give_n"
      ],
      "last_seen": "2026-11-08T09:12:00Z",
      "told": null
    },
    {
      "skill": "maths.subitising.perceptual",
      "title": "See how many without counting, up to 5",
      "domain": "Mathematics",
      "strand": "Subitising",
      "state": "emerging",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.2033109366145876,
          "used": 5,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 0.4,
          "used": 5,
          "told": 0
        }
      ],
      "counted": 5,
      "right": 2,
      "held": 0,
      "mechanics": [
        "brief_exposure"
      ],
      "last_seen": "2026-11-08T09:17:00Z",
      "told": null
    },
    {
      "skill": "maths.numerals.recognise",
      "title": "Find the numeral for a spoken number",
      "domain": "Mathematics",
      "strand": "Numeral symbols",
      "state": "emerging",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.9999998338760969,
          "used": 11,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 1.0,
          "used": 5,
          "told": 0
        }
      ],
      "counted": 11,
      "right": 11,
      "held": 5,
      "mechanics": [
        "brief_exposure",
        "select_one",
        "sequence"
      ],
      "last_seen": "2026-11-11T09:23:00Z",
      "told": null
    },
    {
      "skill": "maths.comparison.order",
      "title": "Put numbers in order",
      "domain": "Mathematics",
      "strand": "Magnitude and comparison",
      "state": "introduced",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.414828897338403,
          "used": 2,
          "told": 0
        },
        {
          "model": "rule@1",
          "p": 0.5,
          "used": 2,
          "told": 0
        }
      ],
      "counted": 2,
      "right": 1,
      "held": 0,
      "mechanics": [
        "sequence"
      ],
      "last_seen": "2026-11-11T09:23:00Z",
      "told": null
    },
    {
      "skill": "language.vocabulary.colours",
      "title": "Know the colour words",
      "domain": "Communication and language",
      "strand": "Vocabulary",
      "state": "unobserved",
      "estimates": [],
      "counted": 0,
      "right": 0,
      "held": 0,
      "mechanics": [],
      "last_seen": null,
      "told": null
    },
    {
      "skill": "language.listening.story",
      "title": "Listen to a short story or text",
      "domain": "Communication and language",
      "strand": "Listening and understanding",
      "state": "unobserved",
      "estimates": [],
      "counted": 0,
      "right": 0,
      "held": 0,
      "mechanics": [],
      "last_seen": null,
      "told": null
    },
    {
      "skill": "literacy.phonological.rhyme",
      "title": "Hear which words rhyme",
      "domain": "Literacy",
      "strand": "Phonological awareness",
      "state": "unobserved",
      "estimates": [
        {
          "model": "bkt@1",
          "p": 0.95,
          "used": 0,
          "told": 1
        }
      ],
      "counted": 0,
      "right": 0,
      "held": 0,
      "mechanics": [],
      "last_seen": null,
      "told": { "id": "f0000000000000000000000000000001", "skill": "literacy.phonological.rhyme", "says": "can", "observer": "parent", "note": "Rhymes in songs at bath time", "at": "2026-11-10T18:00:00Z", "withdrawn_at": null }
    }
  ],
  "engagement": {
    "kinds": [
      { "mode": "counting", "title": "Counting", "rounds": 9, "right_first": 8, "median_seconds": 2.4, "mean_tries": 1.11, "left": 0, "liked": 2, "okay": 1, "disliked": 0, "offered": 2, "picked": 2, "preference": 0.4 },
      { "mode": "give", "title": "Give a number", "rounds": 4, "right_first": 2, "median_seconds": 9.5, "mean_tries": 1.5, "left": 1, "liked": 0, "okay": 0, "disliked": 0, "offered": 0, "picked": 0, "preference": 0 },
      { "mode": "letters", "title": "Letters", "rounds": 6, "right_first": 1, "median_seconds": 16.2, "mean_tries": 2.5, "left": 0, "liked": 0, "okay": 1, "disliked": 2, "offered": 2, "picked": 0, "preference": -0.357 },
      { "mode": "listen", "title": "Listen", "rounds": 0, "right_first": 0, "median_seconds": null, "mean_tries": null, "left": 0, "liked": 0, "okay": 0, "disliked": 0, "offered": 2, "picked": 0, "preference": -0.2 },
      { "mode": "matching", "title": "Matching", "rounds": 5, "right_first": 5, "median_seconds": 3.1, "mean_tries": 1, "left": 0, "liked": 0, "okay": 0, "disliked": 0, "offered": 0, "picked": 0, "preference": 0 }
    ],
    "hypotheses": [
      { "code": "stuck", "mode": "letters", "seen": "Letters: right first time in 17% of the last 6, with long pauses or many tries.", "could_be": "Stuck on the skill, unsure what the round asks, or finding the taps hard.", "try_": "Play one together and say what it asks, or fewer choices." },
      { "code": "disliked", "mode": "letters", "seen": "Letters: rated with the sad face 2 of 3 times.", "could_be": "It is not fun, it feels hard, or the faces were tapped at random.", "try_": "Fewer of these for a while (the engine already offers it less), then try it again." }
    ]
  }
}

/** A learner with nothing recorded yet: every skill unobserved. */
export const owlProfile: Profile = {
  ...foxProfile,
  learner: learners[1],
  sessions: 0,
  struck: 0,
  skills: foxProfile.skills.map(s => ({ ...s, state: 'unobserved', estimates: [], counted: 0, right: 0, held: 0, mechanics: [], last_seen: null, told: null })),
  engagement: { kinds: [], hypotheses: [] },
}

/** Fox's evidence for counting objects, newest first. */
export const countingEvidence: EvidenceRow[] = [
  {
    "event_id": "0000000000000000000000000000000a",
    "at": "2026-11-05T09:09:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 109,
    "role": "primary",
    "answer": "2",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000009",
    "at": "2026-11-05T09:08:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 108,
    "role": "primary",
    "answer": "1",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000008",
    "at": "2026-11-05T09:07:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 107,
    "role": "primary",
    "answer": "5",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000007",
    "at": "2026-11-05T09:06:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 106,
    "role": "primary",
    "answer": "4",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000006",
    "at": "2026-11-02T09:05:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 105,
    "role": "primary",
    "answer": "3",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000005",
    "at": "2026-11-02T09:04:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 104,
    "role": "primary",
    "answer": "2",
    "correct": true,
    "counted": false,
    "why": "struck out: someone else was playing",
    "struck": true,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000004",
    "at": "2026-11-02T09:03:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 103,
    "role": "primary",
    "answer": "4",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000003",
    "at": "2026-11-02T09:02:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 102,
    "role": "primary",
    "answer": "5",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000002",
    "at": "2026-11-02T09:01:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 101,
    "role": "primary",
    "answer": "2",
    "correct": true,
    "counted": true,
    "why": "",
    "struck": false,
    "tries": 1,
    "outcome": "right"
  },
  {
    "event_id": "00000000000000000000000000000001",
    "at": "2026-11-02T09:00:00Z",
    "mode": "counting",
    "version": 1,
    "choices": 4,
    "seed": 100,
    "role": "primary",
    "answer": "3",
    "correct": false,
    "counted": false,
    "why": "could be Find the numeral for a spoken number, not yet shown",
    "struck": false,
    "tries": 2,
    "outcome": "right"
  }
]
