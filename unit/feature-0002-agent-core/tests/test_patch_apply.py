"""unified diff 적용기 — fail-closed 계약 (FR-attach-delivery-truncated-by-output-cap ②).

패치 적용은 **조용히 틀릴 수 있는** 종류의 코드다. 잘못 적용된 패치는 그럴듯한 파일을 만들고,
사용자는 그것을 배포한다 — 전달 실패보다 나쁘다(CODE_REVIEW §1). 그래서 이 모듈의 계약은
"최대한 적용" 이 아니라 **"애매하면 거부"** 다. 아래 테스트는 그 거부들을 고정한다.
"""
from __future__ import annotations

import pytest

from modules.patch_apply import PatchError, apply_unified_diff

SRC = "\n".join([
    "USE Log_v2;",              # 1
    "",                         # 2
    "SELECT 1;",                # 3
    "SELECT 2;",                # 4
    "SELECT 3;",                # 5
])


# ── 정상 적용 ───────────────────────────────────────────────────────────────


def test_applies_simple_replacement():
    patch = "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;"
    out = apply_unified_diff(SRC, patch)
    assert out.splitlines()[0] == "USE log_v2;"
    assert out.splitlines()[2:] == ["SELECT 1;", "SELECT 2;", "SELECT 3;"], "다른 줄은 불변"


def test_at_at_inside_file_content_is_not_a_hunk_header():
    """파일 본문에 `@@` 가 있어도 hunk 경계로 오해하면 안 된다(선언 길이가 경계를 정한다)."""
    src = "\n".join(["a;", "@@ note @@", "b;"])
    out = apply_unified_diff(src, "@@ -1,1 +1,1 @@\n-a;\n+A;")
    assert out.splitlines() == ["A;", "@@ note @@", "b;"]


def test_applies_multiple_hunks_in_order():
    patch = (
        "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;\n"
        "@@ -5,1 +5,1 @@\n-SELECT 3;\n+SELECT 33;"
    )
    out = apply_unified_diff(SRC, patch).splitlines()
    assert out[0] == "USE log_v2;" and out[4] == "SELECT 33;"


def test_ignores_diff_headers_and_no_newline_marker():
    patch = (
        "diff --git a/x.sql b/x.sql\nindex 111..222 100644\n--- a/x.sql\n+++ b/x.sql\n"
        "@@ -3,1 +3,1 @@\n-SELECT 1;\n+SELECT 11;\n\\ No newline at end of file"
    )
    assert "SELECT 11;" in apply_unified_diff(SRC, patch)


def test_pure_insertion_hunk_is_rejected():
    """§18.8 [P1] — 초판은 `-N,0` 을 한 줄 **앞**에 삽입했다(EOF append 가 마지막 줄 앞으로).

    문맥이 없으면 위치를 검증할 방법이 원리적으로 없다 → 거부하고 앵커를 요구한다.
    """
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, "@@ -3,0 +4,1 @@\n+SELECT 99;")
    assert "문맥 줄이 없습니다" in str(e.value)
    assert "최소 1줄" in str(e.value), "회복 방법을 줘야 모델이 재시도할 수 있다"


def test_insertion_with_context_lands_exactly_where_diff_would_put_it():
    """문맥을 포함한 삽입은 결과 줄 목록이 정확히 일치해야 한다(위치까지 고정)."""
    patch = "@@ -3,1 +3,2 @@\n SELECT 1;\n+SELECT 99;"
    assert apply_unified_diff(SRC, patch).splitlines() == [
        "USE Log_v2;", "", "SELECT 1;", "SELECT 99;", "SELECT 2;", "SELECT 3;"]


def test_append_at_eof_with_context():
    patch = "@@ -5,1 +5,2 @@\n SELECT 3;\n+SELECT 4;"
    assert apply_unified_diff(SRC, patch).splitlines()[-2:] == ["SELECT 3;", "SELECT 4;"]


def test_rejects_hunk_body_shorter_than_declared():
    """§18.8 [P1] — 잘린 패치가 부분 적용되고 '성공' 을 반환하던 경로.

    이 cycle 이 없애려는 실패(출력 절단 → 부분 전달 → 성공 보고)의 재현이었다.
    """
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, "@@ -3,3 +3,3 @@\n-SELECT 1;\n+SELECT 11;")
    assert "선언한 크기와 다릅니다" in str(e.value)
    assert "적용하지 않았습니다" in str(e.value)


def test_rejects_hunk_body_longer_than_declared():
    with pytest.raises(PatchError):
        apply_unified_diff(SRC, "@@ -3,1 +3,1 @@\n-SELECT 1;\n-SELECT 2;\n+SELECT 11;")


def test_trailing_prose_after_last_hunk_is_not_written_into_file():
    """§18.8 [P1] — 모델이 hunk 뒤에 덧붙인 설명이 파일에 기록되던 경로."""
    patch = "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;\n이상입니다. 확인 부탁드립니다."
    out = apply_unified_diff(SRC, patch)
    assert "이상입니다" not in out
    assert out.splitlines() == ["USE log_v2;", "", "SELECT 1;", "SELECT 2;", "SELECT 3;"]


def test_trailing_newline_on_patch_is_tolerated():
    """```diff 펜스에서 복사하면 끝에 개행이 남는다 — 그것 때문에 실패하면 안 된다."""
    assert "USE log_v2;" in apply_unified_diff(SRC, "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;\n")
    assert "USE log_v2;" in apply_unified_diff(SRC, "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;\n\n")


def test_line_number_drift_is_tolerated_when_unique():
    """줄 번호가 밀려도 문맥이 **유일하게** 일치하면 적용한다(모델이 번호를 흘리는 흔한 경우)."""
    patch = "@@ -99,1 +99,1 @@\n-SELECT 2;\n+SELECT 22;"
    assert "SELECT 22;" in apply_unified_diff(SRC, patch)


def test_search_window_boundary_is_exact():
    """정확히 _SEARCH_WINDOW 만큼 떨어지면 적용, 한 줄 더 멀면 거부(경계 고정)."""
    from modules.patch_apply import _SEARCH_WINDOW
    src = "\n".join(["target;"] + ["filler;"] * 2000)
    ok = f"@@ -{1 + _SEARCH_WINDOW},1 +{1 + _SEARCH_WINDOW},1 @@\n-target;\n+changed;"
    assert "changed;" in apply_unified_diff(src, ok)
    with pytest.raises(PatchError):
        apply_unified_diff(src, f"@@ -{2 + _SEARCH_WINDOW},1 +{2 + _SEARCH_WINDOW},1 @@\n-target;\n+changed;")


def test_crlf_line_endings_are_preserved():
    """§18.8 [P2] — 초판은 CRLF 를 LF 로 통째 정규화해 한 줄 수정이 전체 변경으로 보였다."""
    out = apply_unified_diff(SRC.replace("\n", "\r\n"),
                             "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;")
    assert out.startswith("USE log_v2;\r\n")
    assert out.count("\r\n") == SRC.count("\n"), "줄바꿈 종류·개수가 원본과 같아야 한다"


def test_lf_source_stays_lf():
    out = apply_unified_diff(SRC, "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;")
    assert "\r" not in out


# ── fail-closed 거부 ────────────────────────────────────────────────────────


def test_rejects_when_context_does_not_match():
    """문맥 불일치는 **적용하지 않는다** — 대소문자 한 글자 차이도 다른 파일이라는 뜻이다."""
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, "@@ -1,1 +1,1 @@\n-USE LOG_V2;\n+USE log_v2;")
    assert "일치하지 않습니다" in str(e.value)
    assert "read_attachment" in str(e.value), "모델이 회복할 경로를 사유에 담아야 한다"


def test_rejects_ambiguous_context():
    """같은 문맥이 여러 곳이면 어디에 적용할지 확정할 수 없다 — 추측 금지."""
    src = "\n".join(["X;", "dup;", "Y;", "dup;", "Z;"])
    with pytest.raises(PatchError) as e:
        apply_unified_diff(src, "@@ -50,1 +50,1 @@\n-dup;\n+changed;")
    assert "여러 곳" in str(e.value)


def test_rejects_unknown_body_prefix():
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, "@@ -1,1 +1,1 @@\n*USE Log_v2;\n+USE log_v2;")
    assert "알 수 없는 접두" in str(e.value)


def test_rejects_patch_without_hunk_header():
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, "-USE Log_v2;\n+USE log_v2;")
    assert "hunk 를 찾지 못했습니다" in str(e.value)


def test_rejects_empty_patch():
    with pytest.raises(PatchError):
        apply_unified_diff(SRC, "   ")


def test_rejects_overlapping_hunks():
    """겹치는 hunk 는 부분 적용된 파일을 만든다 — 순서·비겹침을 강제한다."""
    patch = (
        "@@ -3,1 +3,1 @@\n-SELECT 1;\n+SELECT 11;\n"
        "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;"
    )
    with pytest.raises(PatchError) as e:
        apply_unified_diff(SRC, patch)
    assert "겹치거나 순서가" in str(e.value)


def test_failure_is_all_or_nothing():
    """첫 hunk 는 맞고 둘째가 틀리면 **아무것도** 적용되지 않아야 한다(반쯤 고쳐진 파일 금지)."""
    patch = (
        "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;\n"
        "@@ -5,1 +5,1 @@\n-SELECT NOPE;\n+SELECT 33;"
    )
    with pytest.raises(PatchError):
        apply_unified_diff(SRC, patch)
    # 예외가 났으므로 호출자는 원본을 그대로 쓴다 — 부분 적용 결과가 새어나갈 경로가 없다.


def test_search_window_is_bounded():
    """멀리 떨어진 우연한 일치를 끌어오지 않는다 — 탐색 범위를 넘으면 거부."""
    src = "\n".join(["target;"] + ["filler;"] * 900 + ["tail;"])
    with pytest.raises(PatchError):
        apply_unified_diff(src, "@@ -900,1 +900,1 @@\n-target;\n+changed;")
