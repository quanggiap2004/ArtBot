from articlebots.diff import classify
from articlebots.hashing import content_hash, parse_remote_name, remote_name


def test_first_run_adds_everything():
    plan = classify({"a": "11111111", "b": "22222222"}, {})
    assert plan.added == ["a", "b"]
    assert plan.updated == [] and plan.skipped == []


def test_unchanged_content_is_skipped():
    state = {"a": "11111111"}
    plan = classify(state, state)
    assert plan.skipped == ["a"]
    assert plan.added == [] and plan.updated == []


def test_changed_hash_means_update():
    plan = classify({"a": "aaaaaaaa"}, {"a": "bbbbbbbb"})
    assert plan.updated == ["a"]


def test_summary_line_format():
    plan = classify({"a": "1" * 8, "b": "2" * 8}, {"a": "1" * 8})
    assert plan.summary() == "RESULT added=1 updated=0 skipped=1"


def test_hash_is_stable_and_short():
    d = content_hash("# Hello\n")
    assert d == content_hash("# Hello\n")
    assert len(d) == 8


def test_remote_name_round_trip():
    name = remote_name("my-article", "deadbeef")
    assert name == "my-article__deadbeef.md"
    assert parse_remote_name(name) == ("my-article", "deadbeef")


def test_foreign_filenames_are_rejected():
    assert parse_remote_name("random.pdf") is None
    assert parse_remote_name("noslug__zzzz.md") is None
