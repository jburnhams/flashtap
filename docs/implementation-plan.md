# Implementation plan

From a one-mechanic game to the early years adaptive learning spec (v0.1, 2026-11-17, "Technical design specification": ontology, seeded items, mechanics, evidence, learner model, scheduler, P0 to P5 roadmap). The full plan, with the gap analysis and the decisions it needs, was written 2026-11-22 with Jonathan; this is its working copy. Section numbers (§) are the spec's.

## Where Flashtap stood (0.1.9)

One mechanic (tap one of N pictures), five unseeded round types, no learner state, a points-and-streak score, in the browser only. Bugs against §9: Colours could offer two right answers, Counting hung above ten choices, every tile printed its own name (so Letters and Colours were reading tasks), Letters mixed /k/ and /tʃ/ under C, and sentences were built from string templates ("How many Sheeps").

## PRs

1. **Migrate (0.2.0, done).** python-app-template shape; seeded, checked rounds in Python with the five bugs fixed; `GET /api/round`; Play and Settings on strata-react; no score or streak.
    - Exit: property tests over thousands of seeds per mode find exactly one right option, and the same seed gives the same round.
2. **P0 ontology seed.** `packs/` as versioned YAML with pydantic models: skills, parameter dimensions, typed edges with provenance (§3), misconceptions, curriculum objectives. First slice: maths counting, cardinality, subitising 1-5, numerals 0-10, more/fewer; literacy letter forms, initial sounds, Phase 2 GPCs (s a t p i n m d). `flashtap content check` refuses dangling edges and `prerequisite_strong` cycles. An adult Content screen.
    - Exit: every EYFS maths and literacy Early Learning Goal is mapped or marked out of scope.
3. **P1 mechanics.** Templates declare Q-matrix roles (§7, §8). Mechanics: select one, match pairs, sort, sequence, give-N, fill missing, brief exposure, audio respond. Distractor generators: near-number, reversal (6/9, 12/21), confusable graphemes (b/d/p/q), phonological neighbour.
    - Exit: every item rebuilds from (template, version, seed); the validator suite over 1,000 seeds per template finds no ambiguous key.
4. **P2 learner baseline.** `strata_python.db`: learners (pseudonymous id plus nickname), sessions, append-only attempt events keyed by `event_id`, tombstones. Rule and BKT estimators behind one interface (§10); derived reporting states (§13), unobserved kept apart from not mastered. Adult Learner screen with evidence provenance; export and delete (§17).
    - Exit: rebuilding from the event log reproduces identical estimates.
5. **P3 adaptive engine.** `POST /api/v1/sessions` and `/next` with rationale codes (§15). Eligibility filters, utility ranking, seeded exploration, logged candidates and probabilities (§12). Placement, spaced review, diagnostic contrasts, a session length cap and offered breaks. Replay endpoint.
    - Exit: on simulated learners, held-out log loss beats the rule baseline.
6. **P4 engagement, light.** Choice of two activities, a 3-point face rating, hesitation and retry patterns shown as hypotheses (§11), parent session limits.
    - Exit: a short pilot checklist; it needs real sessions.

P5 (field validation) is a study, not code.

## Decisions (recommended answers; PR 1 went ahead on them)

| Question | Recommendation |
| --- | --- |
| Keep the npm library and its Pages demo? | Replace them with the app (done in 0.2.0) |
| Who plays, and where does it run? | A family first, served from one home server behind a reverse proxy |
| Device and offline use? | Tablet browser on home wifi; attempts queued in the browser later |
| Voice? | Pre-generated UK English clips (strata-models `speak`), browser speech as fallback |
| Look of the Play screen? | Strata tokens; the large tap tiles are being added to strata-react (Jonathan, 2026-11-22: "add components to strata react as needed"), and `styles/play.css` is the stand-in until that release, then deleted |
| First content pack? | Numbers to 10 and Phase 2-3 phonics, grown per pack version |
| Where does data live? | `strata_python.db`: SQLite in tests, the app's schema on the shared Postgres when deployed |
