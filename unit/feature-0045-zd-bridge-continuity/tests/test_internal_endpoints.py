"""feature-0045 — 배포 제어 창구(`/internal/*`)의 경계와 의미.

이 엔드포인트들은 배포 스파인이 부른다. 두 가지가 틀리면 안 된다:
 1. **누가 부를 수 있는가** — 드레인은 replica 를 LB 후보에서 빼는 조작이다. 외부에서
    부를 수 있으면 그것이 곧 서비스 거부다.
 2. **무엇을 하는가** — 점유 회수가 `ClaimedBy` 까지 지우면, 끊기지도 않은 작업을 배포가
    버리는 셈이 된다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SYSTEM_PY = (Path(__file__).resolve().parents[2] / "feature-0003-agent-web-ui"
             / "src" / "routers" / "system.py")


@pytest.fixture(scope="module")
def src() -> str:
    return SYSTEM_PY.read_text(encoding="utf-8")


def _func(src: str, name: str) -> str:
    start = src.index(f"def {name}(")
    nxt = src.find("\n@router.", start)
    return src[start:nxt if nxt != -1 else len(src)]


@pytest.mark.parametrize("name", [
    "internal_bridge_drain", "internal_bridge_reclaim", "internal_bridge_activity",
])
def test_internal_endpoints_are_loopback_only(src, name):
    """엣지에서도 `/internal/*` 을 404 로 막지만, **앱이 스스로 판정하는 쪽이 정본**이다 —
    엣지 설정이 바뀌어도 이 경계는 남아야 한다.

    판정은 `_loopback_only` 하나로 모은다. 세 곳에 흩어 놓으면 새 엔드포인트가 그 중 하나를
    빠뜨린 채 추가되고, 그 누락은 조용하다.
    """
    body = _func(src, name)
    assert "_loopback_only(request)" in body, f"{name} 이 호출자를 확인하지 않는다"
    assert "return denied" in body, f"{name} 이 판정 결과를 무시한다"


def test_loopback_predicate_covers_ipv4_mapped_form(src):
    """`::ffff:127.0.0.1` 은 bind 가 `::` 로 바뀌면 나타난다.

    빠뜨리면 그날 배포가 **원인 불명의 403** 으로 멈춘다(드레인을 걸 수 없다).
    """
    body = _func(src, "_loopback_only")
    for form in ('"127.0.0.1"', '"::1"', '"::ffff:127.0.0.1"'):
        assert form in body, f"{form} 이 loopback 판정에서 빠졌다"
    assert "403" in body


@pytest.mark.parametrize("name", ["internal_bridge_reclaim", "internal_bridge_activity"])
def test_db_endpoints_guard_a_none_connection(src, name):
    """`app.get_conn` 은 연결 실패를 흡수해 **None 을 yield 한다**(raise 하지 않는다).

    확인하지 않으면 `conn.cursor()` 가 AttributeError 로 터져 generic 500 이 나가고, "조회
    실패는 503 으로 말한다" 는 계약이 그 경로에서 실행되지 않는다. 이 저장소가 반복해 온
    결함 유형(자원 획득을 try 밖에 두는 것)의 같은 얼굴이다.
    """
    body = _func(src, name)
    assert "if conn is None" in body, f"{name} 이 None 커넥션을 확인하지 않는다"
    # ⚠ 주석·docstring 을 걸러낸 **코드 라인**만 본다. 이 파일의 주석은 결함을 설명하느라
    #   `conn.cursor()` 를 인용하고 있어서, 문자열 위치로 비교하면 그 인용이 판정을 뒤집는다.
    code = "\n".join(l for l in body.split("\n")
                     if l.strip() and not l.strip().startswith("#"))
    try_at = code.index("try:")
    assert code.index("conn.cursor()") > try_at, "cursor 획득이 try 밖이다"
    # 실패 경로가 문서화된 503 을 낸다(generic 500 이 아니라).
    assert "status_code=503" in code


def test_livez_reports_draining_as_unavailable(src):
    """드레인 신호가 Caddy 에 닿는 유일한 경로다.

    `/livez` 가 계속 200 이면 엣지는 이 replica 를 계속 후보로 두고, 신규 요청이 곧 교체될
    프로세스로 계속 들어온다.
    """
    body = _func(src, "livez")
    assert "_drain.snapshot()" in body, "livez 와 드레인 상태가 다른 출처를 쓴다"
    assert "status_code=503" in body
    # 본문 모양은 200 일 때와 같아야 한다 — 상태 코드만 보고 카운터를 못 읽으면 진단이 막힌다.
    assert "active_streams" in body


def test_readyz_stays_200_while_draining(src):
    """여기서 503 을 내면 recreate 후 대기(`wait_ready`)가 **자기가 건 드레인 때문에**
    영원히 못 끝나는 자기참조가 생긴다."""
    body = _func(src, "readyz")
    assert "_drain.snapshot()" in body
    assert "200 if ready else 503" in body, (
        "readyz 의 상태 코드가 드레인에 좌우된다 — 배포가 스스로를 막는다")


def test_drain_endpoint_has_a_release_path(src):
    """되돌릴 수 없으면, 게이트에서 중단된 배포가 replica 를 문 닫힌 채로 남긴다."""
    body = _func(src, "internal_bridge_drain")
    assert "release" in body and "_drain.end_drain()" in body


def test_reclaim_expires_the_lease_but_keeps_the_owner(src):
    """`ClaimedBy` 를 지우면 살아남은 원 소유자의 제출이 "점유하지 않았다" 로 409 거절된다.

    끊기지도 않은 작업을 배포가 버리는 셈이다. 점유 시각만 밀어 **먼저 끝내는 쪽이 이기게**
    두는 것이 손실이 없다.
    """
    body = _func(src, "internal_bridge_reclaim")
    start = body.index('sql = ("UPDATE WebAiTasks')
    stmt = body[start:body.index("cur.execute(sql, params)")]
    assert "SET ClaimedAt" in stmt, "점유 시각을 밀지 않는다"
    assert "ClaimedBy = NULL" not in stmt and "ClaimedBy=NULL" not in stmt, (
        "소유자를 지운다 — 살아남은 러너의 제출이 거절된다")
    assert "SubmittedAt IS NULL" in stmt, "이미 제출된 답변까지 건드린다"
    assert "Origin='web'" in stmt, "외부 AI 가 스스로 연 task 까지 회수 대상이 된다"


def test_reclaim_has_a_grace_window(src):
    """배포 직후 새 replica 에서 막 시작된 정상 작업까지 재노출하면, 하나뿐인 연결이
    자기가 처리 중인 질문을 다시 가져가는 중복이 생긴다."""
    body = _func(src, "internal_bridge_reclaim")
    assert "grace_sec" in body
    assert "INTERVAL %s SECOND" in body, "grace 가 쿼리에 반영되지 않는다"


def test_activity_reports_unreadable_as_an_error_not_zero(src):
    """조회 실패를 0 으로 돌려주면 quiesce 게이트가 항상 '조용함' 으로 통과한다
    (= 이 축을 추가한 이유가 사라진다)."""
    body = _func(src, "internal_bridge_activity")
    assert "status_code=503" in body
    assert '"claimed": 0' not in body, "실패 시 0 을 돌려주는 경로가 있다"


def test_reclaim_is_bounded_below_by_the_deploy_window(src):
    """상한만 두면 배포와 무관하게 오래 조사 중이던 작업까지 되돌린다 (적대 리뷰 P1).

    그 작업이 다른 세션에 재점유되면 원 소유자의 제출이 `ClaimedClient` 불일치로 409 가
    된다 — 15분짜리 조사가 통째로 버려지고, 원장에는 "점유하지 않았다" 는 **틀린** 사유가
    남는다. 배포 창(또는 보수적 window) 안에서 점유된 것만 대상으로 한다.
    """
    body = _func(src, "internal_bridge_reclaim")
    assert "since_epoch" in body, "배포 창 시작을 받지 않는다"
    assert "ClaimedAt >= FROM_UNIXTIME(%s)" in body, "하한 술어가 없다"
    assert "window_sec" in body and "ClaimedAt >= DATE_SUB(NOW(), INTERVAL %s SECOND)" in body, (
        "since_epoch 미지정 시의 보수적 상한이 없다 — 무제한 전역 sweep 이 된다")
