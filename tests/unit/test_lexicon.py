from flashtap import lexicon


def test_words_have_their_forms():
    by_id = {t.id: t for t in lexicon.words().everything}
    assert by_id["sheep"].many == "sheep"
    assert by_id["cow"].many == "cows"
    assert by_id["bus"].many == "buses"
    assert by_id["apple"].a == "an apple"
    assert by_id["grapes"].a == "some grapes"
    assert by_id["police"].label == "Police car"
    assert by_id["chicken"].letter is None
    assert by_id["cat"].letter == "C"


def test_ids_and_pictures_are_unique():
    ids = [t.id for t in lexicon.words().everything]
    assert len(ids) == len(set(ids))
    assert len({t.picture for t in lexicon.words().everything}) == len(ids)


def test_shapes_name_their_colour_and_shape():
    assert all(t.word == f"{t.colour} {t.shape}" for t in lexicon.words().shapes)
