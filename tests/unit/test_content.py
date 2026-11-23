"""The content packs: the shipped ones pass every rule, and each rule refuses the mistake it is there for.

Rule tests copy the real packs into `tmp_path` and add one small pack with the mistake, so they run the real reader and
checker over real files, and a rule that stopped firing would show here.
"""

import shutil
from pathlib import Path

import pytest

from flashtap import content, lexicon, rounds
from flashtap.content import registry
from flashtap.content.model import Relation


@pytest.fixture
def packs(tmp_path: Path) -> Path:
    folder = tmp_path / "packs"
    shutil.copytree(content.PACKS, folder)
    return folder


def problems_with(folder: Path, toml: str) -> list[str]:
    (folder / "zz-test.toml").write_text(toml, encoding="utf-8")
    _, found = content.build(folder)
    return [str(p) for p in found]


HEAD = 'pack = "test"\nversion = 1\ntitle = "Test"\nstatus = "draft"\n'


def test_the_shipped_packs_pass_every_rule():
    r, found = content.build()
    assert found == []
    assert r is not None
    assert content.load().skills.keys() == r.skills.keys()


def test_every_eyfs_maths_and_literacy_goal_is_mapped_or_set_aside():
    r = content.load()
    eyfs = [o for o in r.objectives.values() if r.objective_curriculum[o.id] == "uk_eyfs"]
    goals = {(o.area, o.goal) for o in eyfs}
    assert goals == {
        ("Mathematics", "Number"),
        ("Mathematics", "Numerical Patterns"),
        ("Literacy", "Comprehension"),
        ("Literacy", "Word Reading"),
        ("Literacy", "Writing"),
    }
    assert len(eyfs) == 15  # three statements under each goal
    assert all(bool(o.skills) != bool(o.out_of_scope) for o in eyfs)
    assert {o.id for o in eyfs if o.out_of_scope} == {
        "uk_eyfs.elg.comprehension.1",
        "uk_eyfs.elg.writing.1",
        "uk_eyfs.elg.writing.3",
    }


def test_the_first_slice_of_skills_is_there():
    ids = content.load().skills.keys()
    for skill in (
        "maths.counting.objects",
        "maths.cardinality.last_number",
        "maths.subitising.perceptual",
        "maths.numerals.recognise",
        "maths.comparison.more_fewer",
        "literacy.letters.identify",
        "literacy.phonemic.initial_sound",
        "literacy.gpc.grapheme_from_sound",
    ):
        assert skill in ids


def test_every_round_names_skills_that_exist():
    skills = content.load().skills
    assert set(rounds.MODE_SKILLS) == set(rounds.PLAYABLE)
    for ids in rounds.MODE_SKILLS.values():
        assert ids
        assert all(i in skills for i in ids)


def test_phase_2_starts_s_a_t_p_and_every_letter_has_a_sound_by_phase_3():
    ph = content.load().phonics["phonics.ls"]
    assert [g.grapheme for g in ph.sets[0].gpcs] == ["s", "a", "t", "p"]
    assert [g.grapheme for g in ph.sets[1].gpcs] == ["i", "n", "m", "d"]
    single = {g.grapheme for gs in ph.sets for g in gs.gpcs if len(g.grapheme) == 1}
    assert single == set("abcdefghijklmnoprstuvwxyz")  # q is taught as "qu"
    digraphs = {g.grapheme for gs in ph.sets for g in gs.gpcs if len(g.grapheme) == 2}
    assert len(digraphs) >= 10  # the Word Reading goal: "at least 10 digraphs"


def test_words_resolve_to_their_sounds():
    r = content.load()
    w = r.words
    assert [g.key for g in r.word_gpcs(w["chicken"])] == ["ch:tʃ", "i:ɪ", "ck:k", "e:e", "n:n"]  # noqa: RUF001 (IPA)
    assert [g.key for g in r.word_gpcs(w["moon"])] == ["m:m", "oo:uː", "n:n"]  # noqa: RUF001 (IPA)
    onset = r.onset(w["horse"])
    assert onset is not None
    assert onset.key == "h:h"
    assert r.onset(w["aeroplane"]) is None
    assert r.resolve("oo") is None  # two sounds: a word must say which
    assert r.resolve("q") is None


def test_decodability_follows_the_sequence():
    r = content.load()
    after = {k: r.decodable_after(r.words[k], "phonics.ls") for k in ("cat", "map", "fox", "ship", "moon", "horse")}
    assert after == {
        "cat": "phonics.ls.p2_set3",
        "map": "phonics.ls.p2_set2",
        "fox": "phonics.ls.p3_set6",
        "ship": "phonics.ls.p3_consonant_digraphs",
        "moon": "phonics.ls.p3_vowel_digraphs",
        "horse": None,  # not segmented: "se" is outside Phases 2 and 3
    }


def test_edges_turn_to_one_direction():
    edges = content.load().edges
    e = next(e for e in edges if e.target == "maths.cardinality.give_n")
    assert (e.source, e.relation) == ("maths.cardinality.last_number", Relation.PREREQUISITE_STRONG)
    to = next(e for e in edges if e.source == "maths.counting.objects" and e.relation is Relation.CONFOUNDED_BY)
    assert to.target == "maths.numerals.recognise"


def test_stages_are_labels_from_the_curriculum():
    r = content.load()
    assert r.stages_of("maths.subitising.perceptual") == ["eyfs"]
    assert r.stages_of("maths.counting.one_to_one") == []  # named by no objective directly


def test_a_later_stage_skill_needs_no_schema_change(packs):
    # A Key Stage 1 skill and objective: new entries in a new pack, edges back to the early skills, nothing else.
    found = problems_with(
        packs,
        HEAD
        + """
[[skills]]
id = "maths.place_value.tens_ones"
title = "Know tens and ones in a two-digit number"
strand = "maths.composition"
dimensions = { number_range = [10, 99] }
edges = [{ relation = "prerequisite_strong", from = "maths.composition.bonds_to_10", confidence = "medium", source = "src.flashtap_judgement" }]

[curriculum]
id = "uk_ks1_test"
title = "Key stage 1"
source = "src.flashtap_judgement"
stages = [{ id = "ks1", title = "Key stage 1" }]

[[objectives]]
id = "uk_ks1_test.y2.place_value"
stage = "ks1"
area = "Mathematics"
goal = "Number and place value"
text = "Recognise the place value of each digit in a two-digit number."
skills = ["maths.place_value.tens_ones"]
""",
    )
    assert found == []


@pytest.mark.parametrize(
    ("toml", "expected"),
    [
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [{ relation = "facilitates", to = "x.nowhere", confidence = "low", source = "src.flashtap_judgement" }]\n',
            "x.a: edge end 'x.nowhere' does not exist",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [{ relation = "facilitates", to = "maths.counting.objects", confidence = "low", source = "src.nowhere" }]\n',
            "x.a: source 'src.nowhere' does not exist",
        ),
        ('[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "x.nowhere"\n', "x.a: strand 'x.nowhere' does not exist"),
        (
            '[[skills]]\nid = "maths.counting.objects"\ntitle = "Again"\nstrand = "maths.counting"\n',
            "maths.counting.objects: id used twice",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [{ relation = "facilitates", to = "x.a", confidence = "low", source = "src.flashtap_judgement" }]\n',
            "x.a: facilitates edge to itself",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [\n'
            ' { relation = "related_to", to = "maths.counting.objects", confidence = "low", source = "src.flashtap_judgement" },\n'
            ' { relation = "related_to", to = "maths.counting.objects", confidence = "low", source = "src.flashtap_judgement" },\n]\n',
            "maths.counting.objects: related_to from x.a written twice",
        ),
        ('[[strands]]\nid = "x.s"\ndomain = "x.nowhere"\ntitle = "S"\n', "x.s: domain 'x.nowhere' does not exist"),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\ndimensions = { number_range = [5, 2000] }\n',
            "x.a: number_range [5, 2000] is outside 0 to 1000 or reversed",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\ndimensions = { number_range = ["a", "b"] }\n',
            "x.a: number_range is a range: give [low, high]",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\ndimensions = { arrangement = ["spiral"] }\n',
            "x.a: arrangement: spiral (allowed: line, scattered, dice, ten_frame, fingers)",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\ndimensions = { colourfulness = ["high"] }\n',
            "x.a: dimension 'colourfulness' does not exist",
        ),
        (
            '[[misconceptions]]\nid = "x.m"\ntitle = "M"\nskills = ["x.nowhere"]\nsigns = "s"\nprobe = "p"\nsource = "src.nowhere"\n',
            "x.m: source 'src.nowhere' does not exist",
        ),
        (
            'words = [{ id = "x_dot", word = "dot", category = "things", picture = "🟣", segments = ["d", "o", "q"] }]\n',
            "x_dot: segment 'q' is not one GPC in the inventory",
        ),
        (
            'words = [{ id = "x_dot", word = "dot", category = "things", segments = ["d", "o", "g"] }]\n',
            "x_dot: segments spell 'dog', not 'dot'",
        ),
        (
            'words = [{ id = "x_dot", word = "dot", category = "things", onset = "t" }]\n',
            "x_dot: onset 't' is not how 'dot' starts",
        ),
        (
            'words = [{ id = "x_dog", word = "dog", category = "animals", picture = "🐕" }]\n',
            "x_dog: picture 🐕 is also dog",
        ),
        (
            '[[phonics]]\nid = "x.ph"\ntitle = "P"\nsource = "src.nowhere"\n[[phonics.sets]]\nid = "x.ph.one"\ntitle = "One"\n'
            'gpcs = [{ grapheme = "s", phoneme = "s" }, { grapheme = "s", phoneme = "s" }]\n',
            "x.ph: s:s taught twice",
        ),
        (
            '[curriculum]\nid = "x_cur"\ntitle = "C"\nsource = "src.nowhere"\nstages = [{ id = "one", title = "One" }]\n'
            '[[objectives]]\nid = "x_cur.a"\nstage = "two"\narea = "A"\ngoal = "G"\ntext = "T"\nskills = ["x.nowhere"]\n',
            "x_cur.a: stage 'two' is not one of its curriculum's (one)",
        ),
    ],
)
def test_check_refuses(packs, toml, expected):
    found = problems_with(packs, HEAD + toml)
    assert any(f.startswith(expected) for f in found), found


def test_check_finds_a_prerequisite_cycle(packs):
    found = problems_with(
        packs,
        HEAD + '[[skills]]\nid = "maths.cycle"\ntitle = "C"\nstrand = "maths.counting"\nedges = [\n'
        ' { relation = "prerequisite_strong", from = "maths.cardinality.give_n", confidence = "low", source = "src.flashtap_judgement" },\n'
        ' { relation = "prerequisite_strong", to = "maths.counting.objects", confidence = "low", source = "src.flashtap_judgement" },\n]\n',
    )
    cycles = [f for f in found if "prerequisite_strong cycle" in f]
    assert len(cycles) == 1
    assert "maths.cycle" in cycles[0]
    assert "maths.counting.objects" in cycles[0]


def test_a_facilitates_loop_is_allowed(packs):
    # Only prerequisite_strong and part_of must be acyclic: two skills can help each other.
    found = problems_with(
        packs,
        HEAD + '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [\n'
        ' { relation = "facilitates", to = "maths.counting.objects", confidence = "low", source = "src.flashtap_judgement" },\n'
        ' { relation = "facilitates", from = "maths.counting.objects", confidence = "low", source = "src.flashtap_judgement" },\n]\n',
    )
    assert found == []


@pytest.mark.parametrize(
    ("toml", "expected"),
    [
        ('[[skills]]\nid = "Bad Id"\ntitle = "A"\nstrand = "maths.counting"\n', "is not an id"),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\ncolour = "red"\n',
            "Extra inputs are not permitted",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [{ relation = "facilitates", confidence = "low", source = "s.x" }]\n',
            "an edge names exactly one of to or from",
        ),
        (
            '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "maths.counting"\nedges = [{ relation = "comes_before", to = "x.b", confidence = "low", source = "s.x" }]\n',
            "relation",
        ),
        ('[[dimensions]]\nid = "x.d"\ntitle = "D"\nkind = "range"\nlow = 5\nhigh = 1\n', "a range needs low <= high"),
        ('[[dimensions]]\nid = "x.d"\ntitle = "D"\nkind = "set"\n', "a set needs values"),
        ('[[dimensions]]\nid = "x.d"\ntitle = "D"\nkind = "ordered"\nvalues = ["a", "a"]\n', "repeated values"),
        (
            'words = [{ id = "x_w", word = "cat", category = "c", onset = "c", segments = ["c", "a", "t"] }]\n',
            "give segments or onset",
        ),
        (
            '[[objectives]]\nid = "x.o"\nstage = "eyfs"\narea = "A"\ngoal = "G"\ntext = "T"\nout_of_scope = "no"\n',
            "need a [curriculum]",
        ),
        (
            '[curriculum]\nid = "x_c"\ntitle = "C"\nsource = "s.x"\nstages = [{ id = "one", title = "One" }]\n'
            '[[objectives]]\nid = "x_c.o"\nstage = "one"\narea = "A"\ngoal = "G"\ntext = "T"\n',
            "give skills or out_of_scope",
        ),
        ('[[sources]]\nid = "s.x"\ntitle = "S"\nurl = "http://example.com"\n', "url"),
    ],
)
def test_read_refuses_a_malformed_entry(packs, toml, expected):
    found = problems_with(packs, HEAD + toml)
    assert any(f.startswith("zz-test.toml:") and expected in f for f in found), found


def test_read_refuses_a_file_that_is_not_toml(packs):
    found = problems_with(packs, "this is = = not toml")
    assert any(f.startswith("zz-test.toml: not TOML") for f in found), found


def test_read_refuses_an_empty_folder(tmp_path):
    _, found = content.build(tmp_path)
    assert [str(p) for p in found] == [f"{tmp_path}: no *.toml packs"]


def test_load_refuses_bad_packs(packs, monkeypatch):
    problems_with(packs, "not toml at all = =")
    monkeypatch.setattr(registry, "build", lambda: content.build(packs))
    registry.load.cache_clear()
    try:
        with pytest.raises(content.ContentError, match=r"1 content problem\(s\); first: zz-test.toml: not TOML"):
            registry.load()
    finally:
        registry.load.cache_clear()


def test_the_summary_flattens_the_registry():
    s = content.summarise(content.load(), {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})
    by_id = {k.id: k for k in s.skills}
    count = by_id["maths.counting.objects"]
    assert count.domain == "Mathematics"
    assert count.strand == "Counting objects"
    assert count.modes == ["counting"]
    assert count.stages == ["eyfs"]
    assert {n.skill for n in count.needs} == {"Say the number names in order", "Touch or tag each thing once"}
    assert any(
        e.relation == "confounded_by" and e.skill == "Find the numeral for a spoken number" for e in count.leads_to
    )
    assert by_id["maths.cardinality.last_number"].misconceptions == ["Counts again when asked how many"]
    out = next(o for o in s.objectives if o.id == "uk_eyfs.elg.writing.1")
    assert out.skills == []
    assert out.out_of_scope.startswith("Letter formation")
    first = s.phonics[0].sets[0]
    assert (first.title, [g.grapheme for g in first.gpcs]) == ("Phase 2, set 1", ["s", "a", "t", "p"])
    assert first.words == []  # s, a, t, p alone make no word in the pack
    assert "map" in s.phonics[0].sets[1].words
    assert {p.id for p in s.packs} >= {"core", "maths.number", "literacy.early", "words", "curriculum.uk_eyfs"}


def test_the_lexicon_comes_from_the_words_pack():
    words = content.load().words
    assert {t.id for t in lexicon.EVERYTHING} == {w.id for w in words.values() if w.picture}
