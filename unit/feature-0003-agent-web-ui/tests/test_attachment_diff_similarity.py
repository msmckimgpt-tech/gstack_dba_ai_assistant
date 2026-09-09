"""SQL alignment acceptance and lossless patch regression tests."""
import random
import subprocess

import pytest

import app
from routers import _attachment_diff as alignment


def view(left, right, **kwargs):
    return app._build_version_diff_view(
        left, right, left_version=1, right_version=4, filename="query.sql",
        context_lines=kwargs.pop("context_lines", None), **kwargs)


def assert_source(result, left, right):
    for side, source in (("left", left), ("right", right)):
        rows = [r for r in result["rows"] if r.get(side + "_no") is not None]
        assert [r[side] for r in rows] == source.splitlines()
        assert [r[side + "_no"] for r in rows] == list(range(1, len(rows) + 1))
    for row in result["rows"]:
        if row["type"] == "equal":
            assert row["left"] == row["right"]
        for side in ("left", "right"):
            if side + "_segs" in row:
                assert "".join(s["v"] for s in row[side + "_segs"]) == row[side]


def test_try_wrapper_aligns_reindented_coupon_sql_and_modified_date():
    left = "\n".join([
        "-- 현재 시각 문자열", "SET @CURRENT_DATE = CONVERT(varchar(10), GETDATE(), 20) + ' ' + CONVERT(varchar(5), GETDATE(), 108)",
        "", "-- 카드형 쿠폰 판별", "IF (@G_COUPON LIKE '[A-Za-z0-9]%')", "BEGIN",
        "    SET @NUMBER = @G_COUPON", "END", "ELSE", "BEGIN",
        "    SELECT TOP 1 @NUMBER = C.number_coupon", "    FROM [dbo].[T_COUPON] C",
        "    INNER JOIN [dbo].[T_EVENT] E ON E.event_index = C.event_index",
        "    WHERE C.string_coupon = @G_COUPON AND E.contants = @G_CONTANTS",
        "    ORDER BY C.coupon_index", "END", "SET @O_COUPON_NUMBER = @NUMBER",
    ])
    right = "IF @G_MEMBER_SRL IS NULL\nBEGIN\n    RETURN\nEND\n\nBEGIN TRY\n    BEGIN TRAN\n\n" + "\n".join(
        "    " + line if line else "" for line in left.splitlines()) + "\nEND TRY"
    right = right.replace("CONVERT(varchar(10), GETDATE(), 20) + ' ' + CONVERT(varchar(5), GETDATE(), 108)",
                          "CONVERT(char(16), GETDATE(), 120)")
    result = view(left, right)
    assert_source(result, left, right)
    for text in ("SET @CURRENT_DATE", "SELECT TOP 1", "FROM [dbo]", "INNER JOIN", "WHERE C.", "ORDER BY"):
        row = next(r for r in result["rows"] if text in (r["left"] or ""))
        assert text in row["right"]
        assert row["type"] == "replace"
    assert next(r for r in result["rows"] if r["right"] == "BEGIN TRY")["left"] is None


def test_insertions_do_not_shift_similar_changed_statements():
    left = "SELECT id, name FROM users WHERE enabled = 1;\nUPDATE users SET seen = 1 WHERE id = @id;"
    right = "PRINT 'starting';\nselect id, name FROM users WHERE enabled = 0;\nPRINT 'updating';\nUPDATE users SET seen = 2 WHERE id = @id;"
    result = view(left, right)
    assert_source(result, left, right)
    pairs = [(r["left_no"], r["right_no"]) for r in result["rows"] if r["type"] == "replace"]
    assert pairs == [(1, 2), (2, 4)]


@pytest.mark.parametrize("old,new", [
    ("SELECT 'a b';", "SELECT 'ab';"), ("SELECT 'a';", "SELECT 'A';"),
    ("SELECT [a b];", "SELECT [ab];"), ("WHERE x >= 1", "WHERE x <= 1"),
    ("SELECT 1 -- keep", "SELECT 1 -- drop"), ("SELECT\tx", "select x"),
])
def test_normalization_never_hides_real_changes(old, new):
    result = view(old, new, context_lines=0)
    assert_source(result, old, new)
    assert not result["stats"]["identical"]
    assert result["stats"]["added"] == result["stats"]["removed"] == 1
    assert result["rows"][0]["type"] == "replace"
    assert "-" + old in result["unified"] and "+" + new in result["unified"]


def test_repeated_control_lines_do_not_steal_body_anchors():
    left = "\n".join(f"IF @id = {i}\nBEGIN\n    SELECT value_{i} FROM table_{i};\nEND\n" for i in range(20))
    right = "BEGIN TRY\n" + "\n".join("    " + s for s in left.splitlines()) + "\nEND TRY"
    result = view(left, right)
    assert_source(result, left, right)
    for row in result["rows"]:
        if "SELECT" in (row["left"] or ""):
            assert row["left"].strip() == row["right"].strip()


def test_context_expansion_preserves_pairing():
    left = "\n".join(f"SELECT value_{i} FROM table_{i};" for i in range(35))
    right = left.replace("value_15", "updated_15")
    full = view(left, right)
    folded = view(left, right, context_lines=1)
    assert any(r["type"] == "gap" for r in folded["rows"])
    assert all(r in full["rows"] for r in folded["rows"] if r["type"] != "gap")
    assert full["stats"] == folded["stats"]


@pytest.mark.parametrize("count", [499, 500, 1000])
def test_large_repeated_sql_survives_insertions_at_both_ends_and_middle(count):
    lines = ["SET @i = @i + 1;", "INSERT INTO audit_log (id) VALUES (@i);"] * count
    left = "\n".join(lines)
    right = "\n".join(["BEGIN TRAN;"] + lines[:count] + ["PRINT 'middle';"] + lines[count:] + ["COMMIT;"])
    result = view(left, right)
    assert_source(result, left, right)
    assert sum(r["type"] == "equal" for r in result["rows"]) == len(lines)
    assert result["stats"]["added"] == 3
    assert result["stats"]["removed"] == 0


def test_fuzzy_budget_keeps_all_lines(monkeypatch):
    monkeypatch.setattr(alignment, "_FUZZY_CELL_CAP", 0)
    left = "SELECT id FROM users;\nUPDATE users SET x=1;"
    right = "PRINT 'start';\nSELECT name FROM users;\nUPDATE users SET x=2;"
    result = view(left, right)
    assert_source(result, left, right)
    assert result["truncated"]["alignment"] is True


@pytest.mark.parametrize("old,new", [
    ("SELECT 'A';", "SELECT 'a';"), ("SELECT 'a b';", "SELECT 'a  b';"),
    ('SELECT "A";', 'SELECT "a";'), ("SELECT [A];", "SELECT [a];"),
    ("SELECT `A`;", "SELECT `a`;"), ("SELECT 'it''s A';", "SELECT 'it''s a';"),
])
def test_quoted_exact_match_beats_normalization_collision(old, new):
    result = view(old + "\n" + new, new)
    assert [(r["left_no"], r["right_no"]) for r in result["rows"]] == [(1, None), (2, 1)]
    assert result["rows"][1]["type"] == "equal"


def test_long_tokens_skip_expensive_fuzzy_matching(monkeypatch):
    calls = []
    original = alignment.difflib.SequenceMatcher

    def track(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(alignment.difflib, "SequenceMatcher", track)
    left = [" ".join("a" for _ in range(2000))]
    right = [" ".join("b" for _ in range(2000))]
    assert alignment.align_lines(left, right) == ([(0, 0)], True)
    assert len(calls) == 1


@pytest.mark.parametrize("opening", ["[", "'", '"', "`"])
def test_unterminated_quoted_input_is_consumed_once(opening):
    text = opening + "[" * 100_000
    assert alignment._line_key(text) == (text,)


def test_large_reordered_input_has_no_unbounded_fallback(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("large comparison re-entered SequenceMatcher")

    monkeypatch.setattr(alignment.difflib, "SequenceMatcher", forbidden)
    left = [f"SELECT {i % 100};" for i in range(5000)]
    right = [f"SELECT {99 - i % 100};" for i in range(5000)]
    pairs, limited = alignment.align_lines(left, right)
    assert limited
    assert [i for i, _ in pairs if i is not None] == list(range(len(left)))
    assert [j for _, j in pairs if j is not None] == list(range(len(right)))


@pytest.mark.parametrize("context", [0, 1, 3])
def test_unified_patch_reconstructs_target_for_varied_edits(tmp_path, context):
    rng = random.Random(907)
    cases = [("", "SELECT 1;\n"), ("SELECT 1;\n", ""), ("", "")]
    for _ in range(20):
        old = [f"SELECT value_{i} FROM table_{i};" for i in range(15)]
        new = list(old)
        for _ in range(6):
            index = rng.randrange(len(new))
            action = rng.randrange(3)
            if action == 0:
                new.insert(index, "PRINT 'extra';")
            elif action == 1:
                new.pop(index)
            else:
                new[index] = "    " + new[index].replace("SELECT", "select")
        cases.append(("\n".join(old) + "\n", "\n".join(new) + "\n"))
    path = tmp_path / "query.sql"
    for old, new in cases:
        result = view(old, new, context_lines=context)
        if not result["unified"]:
            assert old == new
            continue
        patch = result["unified"].splitlines()
        patch[:2] = ["--- a/query.sql", "+++ b/query.sql"]
        path.write_text(old)
        applied = subprocess.run(
            ["git", "apply", "--unsafe-paths", "--unidiff-zero", "-"],
            input="\n".join(patch) + "\n", text=True, cwd=tmp_path,
            capture_output=True, check=False)
        assert applied.returncode == 0, applied.stderr
        assert path.read_text() == new
