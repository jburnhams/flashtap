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

## Still to review

The packs are drafts written from the sources in `core.toml`. Before treating them as right: a phonics teacher checks the IPA and word segmentations (spec §9: generated text never supplies unchecked transcriptions); someone who teaches early maths and reading checks the `src.flashtap_judgement` edges and the confidence words; the EYFS goal wording is compared once more with the framework PDF.
