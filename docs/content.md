# Content packs

What Flashtap can teach is data, not code: TOML files in [`src/flashtap/packs/`](../src/flashtap/packs/), read and checked by [`src/flashtap/content/`](../src/flashtap/content/) (the spec's Ontology Registry, §3 and §14). The server refuses to start on a pack that fails the check, and the unit suite runs the same check, so a bad pack never reaches a learner.

```bash
uv run flashtap content check                    # every rule below; exit 1 naming each problem
uv run flashtap content check --packs some/dir   # check another folder of packs (a draft you are writing)
uv run flashtap content list                     # skills by domain and strand, with stage labels and the rounds that play them
uv run flashtap content list --json              # the shape GET /api/content returns (the Content screen)
```

## Principles

- **Skills, not ages.** A skill is a capability plus the parameter ranges it is defined over (`number_range = [1, 10]`, `gpc_phase = ["phase2", "phase3"]`), never one skill per combination (spec §3). Nothing in a pack holds an age or a year group. A Key Stage 1 or later skill is one more `[[skills]]` entry with edges back to these; `tests/unit/test_content.py` adds one to prove no schema change is needed.
- **Stages are labels.** A curriculum pack names its stages (`eyfs`, later `ks1`...) and maps each objective to skills. The Content screen shows which stages name a skill; nothing gates on them. What a learner meets next will come from the prerequisite graph and their evidence (plan PRs 4 and 5).
- **Every edge has provenance.** Relation, confidence (`low`, `medium`, `high`: a judgement in words, not a fake probability) and a source id. `src.flashtap_judgement` marks an edge drafted here rather than read from a source: those are the first to review.
- **Every objective is mapped or set aside.** An objective lists `skills`, or gives `out_of_scope` with the reason (usually: tap rounds cannot observe it, such as handwriting or retelling a story).
- **Phonics order is the programme's.** A sequence is a list of sets of GPCs in IPA (UK English). Another programme is another `[[phonics]]` entry; a learner follows one; its order is never shuffled (spec §5).
- **Drafts say so.** Every pack has `status = "draft"` until someone who teaches it has checked it. The Content screen leads with the count of drafts.

## The files

| File | Holds |
| --- | --- |
| `starter.toml` | The first steps: the same picture, colour, letter and number, where a new learner begins ([First steps](#first-steps)) |
| `core.toml` | Sources (with edition and the date someone checked them), domains, parameter dimensions |
| `maths-number.toml` | Number to 10 and the counting system: verbal count, counting, cardinality, subitising, numerals, comparison, part-whole, patterns; the Shapes round's skill; misconceptions |
| `literacy-early.toml` | Phonological and phonemic awareness, letter forms, GPCs, decoding, exception words, spelling, comprehension, handwriting; misconceptions |
| `language.toml` | The vocabulary skills the Matching and Colours rounds lean on |
| `phonics-letters-and-sounds.toml` | The default sequence: Letters and Sounds Phases 2 and 3 (51 GPCs) |
| `words.toml` | Every word a round uses (was `lexicon.py`'s tables), with its picture, plural, article and its sounds |
| `curriculum-uk-eyfs.toml` | The EYFS Early Learning Goals for mathematics and literacy (framework effective 1 September 2026), each mapped or set aside |

## Writing a pack

One TOML file; every table is optional; ids are global across packs (lower case words joined by dots). Keys a model does not know are refused, so a typo is an error, not a silent default. Raise `version` with every change to a pack's content: every round carries the versions of the packs it drew from (`rounds.content_of`: the words and phonics packs, and the packs of the skills it names), each attempt and engine decision stores them, and only the current packs are kept, so a round made from an earlier version is never rebuilt from today's words. An attempt on such a round is refused (400) rather than judged against another round, the Learner screen shows its answer by id, and an engine replay reports the decision rather than remaking it.

```toml
pack = "maths.place_value"
version = 1
title = "Place value to 100"
status = "draft"

[[strands]]
id = "maths.place_value"
domain = "maths"
title = "Place value"

[[skills]]
id = "maths.place_value.tens_ones"
title = "Know tens and ones in a two-digit number"
strand = "maths.place_value"
dimensions = { number_range = [10, 99] }
edges = [
  # written on either end: `from` (other -> this) or `to` (this -> other)
  { relation = "prerequisite_strong", from = "maths.composition.bonds_to_10", confidence = "medium", source = "src.flashtap_judgement" },
]
```

Relations (spec §3): `prerequisite_strong` (normally necessary first; no cycles), `facilitates`, `part_of` (taxonomy; no cycles), `related_to`, `confounded_by` (the other skill can explain errors on this one, such as numeral recognition in a count-and-tap round). Curriculum mapping is an objective's `skills`; a misconception names its `skills` (a misconception's id is also named in `src/flashtap/mistakes.py` when a round's wrong option can show it: renaming one there means keeping the old id for the attempts that stored it); mechanic relations (`teaches`, `assesses_*`) arrive with the mechanics (plan PR 3).

Words: `segments` splits the spelling into graphemes from the GPC inventory (`"oo:uː"` where a grapheme has two sounds); `onset` gives only the first grapheme when a later one is outside the inventory (horse); neither when the first sound is outside it too (aeroplane), which keeps the word out of sound rounds. Decodability after each set is computed from the segments. Split digraphs (`a_e`) need a field of their own when Phase 5 arrives.

## What the check refuses

An id used twice (across every kind); an edge, strand, domain, source, skill or stage that does not exist; an edge to itself or written twice; a `prerequisite_strong` or `part_of` cycle; a skill parameter outside its dimension (a range outside its bounds or reversed, a value not in the set); a GPC taught twice in one sequence; a word segment that is not exactly one GPC, segments that do not spell the word, an onset that is not how the word starts, two words with one picture; an objective with both or neither of `skills` and `out_of_scope`; and anything malformed (bad id, unknown key, unknown relation, a source that is not `https`).

## First steps

`starter.toml` (0.14.0) holds the easiest skills there are: find the same picture, the same colour, the same letter, the same number. Each round shows the thing big, says "Find the same one", and lays out two tiles at its first step, never more than four; the wrong tiles are always unlike the right one (another kind of thing, another colour, no look-alike letters, numbers one to three first), because these rounds teach what a round is, not a mix-up. Nothing has to be named, counted or heard on its own.

Each first-steps skill is a strong prerequisite of a skill a practice kind assesses (picture → the words for pictures, colour → the colour words, letter → knowing letters by name, number → reading numerals), and from policy `utility@7` the engine opens a kind only once the learner has **shown** every skill it waits on: the strong prerequisites of each skill the kind names, and each of its secondary or confound skills that another practice kind teaches. Shown means rated known on answers of the learner's own (or a grown-up's "can do it"), never inferred from the graph. So a new learner begins on the four first steps, then opens Matching, Colours, Counting, Quick look, Capitals and Sounds; then Shapes (the colour words), Sort by sound (the words for pictures), Missing number, Order and Give (counting); then Letters and Listen. A learner who gets everything right opens every practice kind in about a hundred rounds (`tests/unit/test_engine.py`); each kind starts at its own easiest step and climbs by its stair.

`maths.number` version 2 adds two `src.flashtap_judgement` edges for that order: counting a set is a strong prerequisite of saying one more (Missing number) and of putting numerals in order (Order). Rounds and decisions made from version 1 are not rebuilt (see "Writing a pack", above, on `version`).

## Transfer kinds

A skill a learner gets right in the one kind of round that practises it may be that game learnt, not the skill (spec §11, "strong skill in one mechanic only"). So every skill a practice kind assesses has one **transfer kind** (`rounds.TRANSFER`, 0.13.0): the same skill asked another way, held out of practice (Mixed and Play's list never offer it; the engine plays it only to check a skill it rates known; `src/flashtap/learners/transfer.py`). A skill is Generalised only once its latest two answers there are right.

| Skill | Practised in | Checked in | What changes |
| --- | --- | --- | --- |
| Find the picture for a spoken word | Matching | Hear and find | the word is only heard; Matching shows the picture to match |
| Know the colour words | Colours | Colour box | every shape of the colour, of any shape, into a box; not the one shape of it |
| Name flat shapes | Shapes | Shape box | every circle (say), of any colour, into a box; Shapes shows the coloured shape it names |
| Count a set of things | Counting | Which group | a number is said and the group with that many is found; Counting gives a group and asks its numeral |
| See how many without counting | Quick look | Quick dots | dots instead of pictures |
| Say one more and one less | Missing number | One more, one less | asked straight out, not inside a run whose rhythm can carry a learner to the gap |
| Put numbers in order | Order | Biggest number | one end of a set picked, not a row arranged |
| Give a number of things | Give a number | Number card | the number is a numeral on a card, never said |
| Match capital and small letters | Capitals | Small letters | one capital, its small letter picked among look-alikes; pairs can be matched by elimination |
| Find a word that starts with a letter's sound | Letters | Letter box | every picture that starts with the letter into its box; not the one picture |
| Hear the first sound in a word | Sort by sound | Same first sound | no letters at all: a picture that starts like the named one |
| Find the same picture | Same picture | Picture twins | pairs to put together, not one picture to find |
| Find the same colour | Same colour | Colour twins | each circle or diamond onto the square of its colour: only the colour matches |
| Find the same letter | Same letter | Letter twins | pairs to put together |
| Find the same number | Same number | Number twins | pairs to put together |
| Find the letters for a sound | Listen, Sounds | First sounds | the sound inside a word, with two-letter sounds (ship on sh), and the first letter of one (s) as the tempting wrong place |

These are judgements about what counts as "the same skill in another form", like the `src.flashtap_judgement` edges, and are for the same review.

## Still to review

The packs are drafts written from the sources in `core.toml`. Before treating them as right (and the transfer kinds above, which lean on them): a phonics teacher checks the IPA and word segmentations (spec §9: generated text never supplies unchecked transcriptions); someone who teaches early maths and reading checks the `src.flashtap_judgement` edges and the confidence words; the EYFS goal wording is compared once more with the framework PDF.
