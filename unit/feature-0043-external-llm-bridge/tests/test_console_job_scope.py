"""feature-0043 TASK-20260831T100000 — 콘솔 작업 **배급 자격 경계** 회귀 가드.

codex 적대 리뷰(REV-20260831T140000)가 잡은 세 지점을 잠근다. 지적을 고치기만 하면 다음
사람이 같은 자리를 다시 연다 — 특히 여기 셋은 **전부 조용히 열린다**(에러가 나지 않고
권한만 넓어진다).

| 지점 | 잠그는 것 |
|---|---|
| P1-1 | 자격은 **그 토큰**의 신고에서 온다 — 계정의 다른 러너가 대신 동의해 주지 않는다 |
| P1-2 | 배치 점유분 조회는 **제출 경로만** — 조사 도구는 소유 스코프 그대로 |
| P2   | 기능 CSV 가 컬럼 폭에서 **항목 중간에 잘리지 않는다** — 잘린 꼬리가 다른 이름이 된다 |
"""
from __future__ import annotations

import pathlib

import oauth_store as store

_AI_TOOLS = pathlib.Path(__file__).resolve().parents[2] / \
    "feature-0003-agent-web-ui" / "src" / "routers" / "ai_tools.py"


def _fn_src(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    start = src.index(f"def {name}(")
    return src[start:src.index("\ndef ", start + 1)]


# ── P2: 직렬화가 컬럼 폭을 넘지 않고, 항목 중간에서 자르지 않는다 ────────────────────

def _distinct_names(size: int, count: int) -> list[str]:
    """길이 `size` 의 **서로 다른** 이름 `count` 개.

    ⚠ 중복을 쓰면 `parse_runner_features` 의 dedup 에 접혀 길이가 폭에 미치지 못한다 —
    그러면 절단 자체가 일어나지 않아 검사가 **통과하지만 아무것도 잠그지 않는다**
    (이 테스트를 처음 쓸 때 실제로 그렇게 됐다: 뮤턴트가 살아남았다).
    """
    return [("%03d" % i) + "z" * (size - 3) for i in range(count)]


def test_features_never_truncate_mid_token():
    """잘린 꼬리가 **다른 기능 이름**이 되는 경로를 만들지 않는다.

    개수·항목길이 상한만으로는 최대 395자가 나와 VARCHAR(255) 를 넘고, 비엄격 SQL 모드에서는
    조용히 잘린다. 저장 전에 항목 단위로 끊어 그 상황 자체를 만들지 않는다.

    ⚠ **여러 길이로 돈다.** 한 길이만 쓰면 그 길이가 우연히 절단 경계에 정렬돼(예: 31자 +
    구분자 = 32, 255 = 8×32 − 1) 문자 절단 뮤턴트가 **온전한 항목만 남기고 살아남는다**.
    정렬 여부는 길이에 따라 달라지므로 범위를 돌아 그 우연을 없앤다.
    """
    for size in range(4, store.RUNNER_FEATURE_MAX_LEN + 1):
        names = _distinct_names(size, store.RUNNER_FEATURES_MAX)
        csv = store.serialize_runner_features(names)
        assert len(csv) <= store.RUNNER_FEATURES_COLUMN_CHARS, (
            f"size={size}: 컬럼 폭을 넘겨 저장하면 조용히 잘린다")
        for name in (csv.split(",") if csv else []):
            assert name in names, f"size={size}: 항목이 중간에서 잘렸다 — {name!r}"


def test_truncation_cannot_forge_a_shorter_feature_name():
    """정확히 그 공격 형태 — 앞을 채운 뒤 `batch_jobs_evil` 이 `batch_jobs` 로 변하지 않는다.

    절단이 `batch_jobs` 직후에 떨어지도록 **앞부분 길이를 계산해서** 만든다. 대충 채우면
    경계가 어긋나 공격이 성립하지 않고, 그러면 이 검사는 통과하지만 아무것도 증명하지 않는다.
    """
    target = "batch_jobs_evil"
    forged = "batch_jobs"
    # 절단점이 forged 의 끝과 겹치려면 prefix(구분자 포함) 길이가 정확히 이 값이어야 한다.
    want_prefix = store.RUNNER_FEATURES_COLUMN_CHARS - len(forged)
    filler, used = [], 0
    i = 0
    while used < want_prefix:
        size = min(store.RUNNER_FEATURE_MAX_LEN, want_prefix - used - 1)
        if size < 4:
            break
        filler.append(("%03d" % i) + "z" * (size - 3))
        used += size + 1                       # 이름 + 구분자
        i += 1
    assert used == want_prefix, f"공격 fixture 를 만들지 못했다(prefix={used}/{want_prefix})"

    csv = store.serialize_runner_features([*filler, target])
    parsed = store.parse_runner_features(csv)
    assert forged not in parsed, "잘린 꼬리가 유효 기능 이름으로 인식된다 — 자격 오판"
    # 온전히 실렸거나 통째로 빠졌거나 — 둘 중 하나여야 한다(중간은 없다).
    assert target in parsed or all(n in filler for n in parsed)


def test_features_round_trip_is_stable():
    """읽기·쓰기가 **같은 정규화**를 쓴다 — 한쪽만 소문자화하면 신고가 조용히 무시된다."""
    csv = store.serialize_runner_features(["Console_Jobs", " batch_jobs ", "console_jobs"])
    parsed = store.parse_runner_features(csv)
    assert parsed == ["console_jobs", "batch_jobs"], parsed


# ── P1-1: 자격은 그 토큰의 신고에서 온다 ─────────────────────────────────────────────

def test_grants_read_the_token_profile_not_the_account():
    """`_runner_job_grants` 가 **토큰** 프로필을 읽는다.

    계정 프로필(`account_runner_profile`)은 그 계정에서 가장 최근 하트비트한 러너 하나를
    고른다. 자격에 쓰면 R1 의 `batch_jobs` 동의가 동의하지 않은 R2 에게 부여된다 —
    동의는 **러너 단위**라는 설계가 무너지고, 그 사람의 계정 토큰이 조직 배경 작업을 태운다.
    """
    fn = _fn_src(_AI_TOOLS, "_runner_job_grants")
    assert "token_runner_profile(" in fn, "자격을 토큰이 아니라 계정에서 읽는다"
    assert "account_runner_profile(" not in fn, (
        "계정 최신 러너 프로필로 자격을 판정한다 — 다른 러너의 동의가 새어 온다")


def test_token_profile_shares_the_live_predicate():
    """토큰 프로필도 인증과 **같은 술어**를 쓴다 — 따로 세면 로그아웃을 무시하는 뒷문이 된다."""
    fn = _fn_src(pathlib.Path(store.__file__), "token_runner_profile")
    assert "_LIVE_TOKEN_PREDICATE" in fn
    assert "LastHeartbeatAt" in fn, "신선도 없이 자격을 주면 꺼진 러너가 자격을 유지한다"


def test_token_profile_is_empty_without_a_token():
    """토큰이 없으면 자격도 없다(fail-closed)."""
    assert store.token_runner_profile(None, "") == {
        "capabilities": [], "features": [], "agent_version": "", "listening": False}


# ── P1-2: 배치 점유분 조회는 제출 경로만 ────────────────────────────────────────────

def test_batch_widening_is_opt_in_not_default():
    """`_load_task` 기본값은 **소유 스코프**다.

    배치 task 는 소유자가 없어 제출하려면 점유자 조건으로 열어야 하는데, 같은 함수를
    조사 도구(`execute_sql`·`read_task_attachment`)도 쓴다. 그 도구들은 반환된
    `ProductId`/`DatasourceKey` 로 데이터 스코프를 정하므로, 기본으로 열면 배치 task 행이
    **그 계정에 없던 스코프를 나르는 bearer** 가 된다.
    """
    fn = _fn_src(_AI_TOOLS, "_load_task")
    assert "include_claimed_batch: bool = False" in fn, "배치 확대가 기본값이다"


def test_only_submit_answer_opts_into_the_batch_widening():
    """`include_claimed_batch=True` 는 **제출 경로에서만** 켜진다.

    개수로 센다 — "어느 함수가 부르는가" 를 텍스트로 판정하면 호출부가 옮겨질 때 검사가
    조용히 무력해진다. 켜진 자리가 하나뿐이라는 사실 자체가 계약이다.
    """
    src = _AI_TOOLS.read_text(encoding="utf-8")
    opt_ins = src.count("include_claimed_batch=True")
    assert opt_ins == 1, (
        f"배치 확대 opt-in 이 {opt_ins}곳이다 — 제출 경로 하나여야 한다")
    # 그 하나가 제출 핸들러 안인지 확인(정의부가 아니라 호출부).
    submit = src[src.index("async def submit_answer("):]
    submit = submit[:submit.index("\n@router.")]
    assert "include_claimed_batch=True" in submit, "opt-in 이 제출 경로 밖에 있다"


def test_investigation_tools_still_use_owner_scope():
    """조사 도구는 `_load_task` 를 **기본 인자로** 부른다(소유 스코프 유지)."""
    src = _AI_TOOLS.read_text(encoding="utf-8")
    plain = src.count("_load_task(conn, task_id, account)")
    assert plain >= 1, "소유 스코프 호출이 하나도 없다 — 전부 확대된 것 아닌가"
