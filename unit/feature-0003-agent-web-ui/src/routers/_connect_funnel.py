"""연결 퍼널 계측 — 「어느 단계에서 사람들이 떨어지는가」 (ROADMAP ITEM-00).

## 왜 이 모듈이 있는가

`docs/improvements/onboarding-accessibility/` 의 로드맵은 온보딩을 크게 바꾸는 항목들
(네이티브 클라이언트 등)을 담고 있는데, **그것들이 나아지게 했는지 반증할 수단이 저장소에
없었다.** 전환 **전** 기준선을 잡아 두지 않으면 「쉬워졌다」는 주장은 영원히 검증되지 않는다.
그래서 이 항목이 그 전환들의 **선행**이다.

## 왜 한 모듈인가

기록 지점이 5곳(연결 화면·토큰 발급·하트비트·점유·제출)이고 서로 다른 라우터에 산다. 각자
`_audit_user_action` 을 직접 부르면 단계 이름·경로 이름·멱등 규칙이 **다섯 벌**이 되고, 그것이
정확히 이 저장소가 방금 겪은 결함이다(허용목록이 6자리로 갈렸던 건 — `FUNCTION.md` P0-Z6.1-a).
여기 한 곳에서만 조립한다.

## 무엇을 남기지 않는가 (`docs/SECURITY.md` D12 정합)

토큰 원문 · 질문/답변 본문 · 명령문 · 프롬프트를 **적재하지 않는다.** 남는 것은
`{step, path_kind}` 와 감사 원장이 자체적으로 붙이는 행위자·시각뿐이다.

## 보장 등급 — **best-effort (0..N)** (codex 적대 리뷰 2라운드, 2026-09-03)

⚠ 초판 docstring 은 이것을 `at-least-once` 라고 적었다. **거짓이다** — 아래 두 경로가 기록을
그냥 건너뛴다: 조회 실패(`_already_recorded` → True) · 모든 예외 삼킴(fail-open). 즉 실제
보장은 **0..N** 이고, `DISTINCT` 는 중복만 지울 뿐 **누락은 복구하지 못한다.**

그래도 이 등급으로 충분한 이유: 퍼널은 **상대 비교**(단계 간 이탈률)에 쓰는 분석 지표이고,
누락은 장애 창에서만 발생해 단계 전체에 고르게 걸린다. 절대 수치를 SLA 로 쓰면 안 된다 —
그 용도가 생기면 전용 테이블 + UNIQUE 키가 정답이고 그때는 별 cycle 이다.

퍼널의 질문은 「이 계정이 그 단계까지 갔는가」이므로 **계정당 단계당 1행**을 목표로 한다.
로드맵은 `first_*` 3단계만 계정당 1회로 요구했으나 여기서는 **다섯 단계 전부**에 적용한다:
- **원장 폭주 방지**: 하트비트는 30초마다 온다. `page_view` 도 화면을 열 때마다 온다.
- **정의의 일관성**: 일부만 누적이면 단계별 행 수가 어떤 단계는 사람 수, 어떤 단계는 방문 수가
  되어 **같은 표에서 단위가 갈린다.**

⚠ **그러나 그 1행은 보장이 아니다.** 가드는 `SELECT` 후 `INSERT` 라 원자적이지 않고,
`IX_WAE_Resource` 는 **비고유** 인덱스다(감사 원장은 범용 테이블이라 여기에 UNIQUE 를 걸면 다른
감사 용도가 깨진다). 동시 하트비트 두 건이 모두 「없음」을 보면 2행이 남을 수 있다.

**그래서 소비 계약이 dedupe 를 진다**: 퍼널을 읽을 때는 행을 세지 말고
`COUNT(DISTINCT ResourceId)` 로 센다. `ResourceId` 가 `"{account}:{step}"` 이라 **구성상
dedupe 키가 이미 존재**한다(`dedupe_key_of` 가 그 계약의 코드면이고 테스트가 잠근다).
이 가드가 실제로 막는 것은 경합 1~2행이 아니라 **정상 운영의 120행/시간**이다.

## 계측은 **자기 커넥션**으로 쓴다 (codex 적대 리뷰 P1-2 — 이게 더 심각했다)

`app._audit_user_action` 은 성공 시 `conn.commit()`, 실패 시 `conn.rollback()` 을 부른다.
업무용 `conn` 을 그대로 넘기면 **계측이 사용자의 트랜잭션을 커밋하거나 되돌린다** — 실제로
초판 배선에서 `claim_request`(점유 확정 직후)와 `submit_answer`(답변 저장 직후)에 걸려 있었고,
계측 예외 하나가 **사용자의 답변을 롤백**할 수 있는 형태였다. 예외를 삼키는 것은 fail-open 이
아니다 — 부수효과는 이미 일어난 뒤다.

그래서 `app._connect_memory()` 로 **전용 커넥션**을 열고 쓰고 닫는다. 커넥션을 못 얻으면
그냥 기록하지 않는다(계측 때문에 요청이 느려지거나 실패하지 않는다).

## 실패해도 연결을 막지 않는다

계측은 부가 기능이다. 어떤 예외도 삼키고 호출자에게 돌려주지 않는다 — 이 파일 때문에 사용자가
연결하지 못하는 일은 없어야 한다.
"""

from __future__ import annotations

import sys

#: 감사 원장의 행위 코드. 조회는 `ActionCode='ai.connect.funnel'` 로 한다.
FUNNEL_ACTION = "ai.connect.funnel"

#: `ResourceType` — 멱등 조회의 인덱스 선행 컬럼(`IX_WAE_Resource`).
FUNNEL_RESOURCE_TYPE = "ai_connect_funnel"

#: 퍼널 단계 — **순서가 의미를 갖는다**(앞 단계 없이 뒤 단계만 있는 계정은 관측 구멍이다).
FUNNEL_STEPS: tuple[str, ...] = (
    "page_view",        # 연결 화면(단독 페이지 또는 모달)이 인증 상태로 열렸다
    "handoff_issued",   # 연결 정보(토큰)를 발급받았다
    "first_heartbeat",  # 그 계정의 무언가가 처음으로 살아 있다고 신고했다
    "first_claim",      # 처음으로 질문을 점유했다
    "first_answer",     # 처음으로 답변을 제출했다
)

#: 경로 종류 — **경로별 이탈률을 가르는 것이 이 계측의 목적**이라 단계만 세면 가치의 절반을 잃는다.
#:
#: ⚠ `unknown` 은 로드맵 열거에 없던 값인데 **필요하다**: `page_view` 시점에는 사용자가 아직
#:   어느 경로도 고르지 않았다. 없는 값을 지어내 넣는 것보다 「아직 모른다」를 값으로 말하는 편이
#:   낫다(P0-T 가 빈 목록 대신 `hidden` 을 실은 것과 같은 이유 — 상태를 값으로 말한다).
PATH_KINDS: tuple[str, ...] = (
    "runner_posix", "runner_windows", "native_client",
    "connector", "probe", "handoff", "unknown",
)

#: 러너가 신고하는 OS 계열(`oauth_store.BRIDGE_OS_FAMILIES`) → 경로 종류.
#: 두 곳이 갈리면 같은 러너가 화면과 원장에서 다른 이름을 갖는다.
_OS_TO_PATH = {"posix": "runner_posix", "windows": "runner_windows"}


def path_kind_from_agent_os(agent_os: str | None) -> str:
    """하트비트의 `agent_os` 를 경로 종류로. 모르면 `unknown` (지어내지 않는다)."""
    return _OS_TO_PATH.get(str(agent_os or "").strip().lower(), "unknown")


def dedupe_key_of(account_id: int, step: str) -> str:
    """소비측 dedupe 키 = `ResourceId`. **계약의 코드면**이다.

    퍼널을 세는 쪽은 행이 아니라 이 키를 `DISTINCT` 로 센다 — 경합으로 2행이 남아도 수치가
    틀어지지 않는다. 문서로만 두면 소비자가 `COUNT(*)` 를 쓰고 조용히 틀린다.
    """
    return f"{int(account_id)}:{step}"


#: 이미 기록됐음을 아는 (account, step) — **양성 전용** 프로세스 로컬 캐시.
#:
#: codex 적대 리뷰 P2-1: 조회가 실패하는 장애에서 하트비트가 30초마다 **전용 커넥션 획득 +
#: SELECT** 를 반복한다. INSERT 폭주는 막았지만 연결·조회 부하는 남는다. 한 번 「있음」을
#: 확인했으면 그 사실은 뒤집히지 않으므로(원장은 append-only) 캐시해도 안전하다.
#: 음성(「없음」)은 캐시하지 않는다 — 그러면 다른 프로세스가 기록한 것을 영원히 모른다.
_SEEN: set[str] = set()

#: 캐시 상한. 프로세스 수명 내 계정 수 × 5단계라 작지만, 무한 증가는 두지 않는다.
_SEEN_MAX = 20_000


def _resource_id(account_id: int, step: str) -> str:
    return dedupe_key_of(account_id, step)


def _remember_seen(key: str) -> None:
    if len(_SEEN) >= _SEEN_MAX:
        _SEEN.clear()       # 단순 상한 — 캐시는 성능 보조일 뿐 정확성의 근거가 아니다
    _SEEN.add(key)


def _already_recorded(cur, account_id: int, step: str) -> bool:
    """이 계정이 이 단계를 이미 남겼는가.

    ⚠ **조회 실패는 「이미 있음」으로 떨어진다(= 기록하지 않는다)** — codex 적대 리뷰 P2-1 이
    초판을 뒤집었다. 초판은 「없는 행은 복원할 수 없다」를 근거로 실패 시 기록을 **시도**했는데,
    그러면 조회만 실패하는 장애(읽기 경로 문제·락 타임아웃)에서 **하트비트마다 INSERT 가 재시도**돼
    폭주 방지와 계정당 1행이 **동시에** 깨진다. 잃는 것은 장애 창의 퍼널 표본 일부(분석 데이터)이고,
    막는 것은 감사 원장 오염이다 — 두 오류의 값이 다르다.
    """
    try:
        cur.execute(
            "SELECT 1 FROM WebAuditEvents "
            "WHERE ResourceType = %s AND ResourceId = %s LIMIT 1",
            (FUNNEL_RESOURCE_TYPE, _resource_id(account_id, step)),
        )
        return cur.fetchone() is not None
    except Exception:
        return True


def record_step(conn, request, account: dict | None, *, step: str,
                path_kind: str = "unknown") -> None:
    """퍼널 단계 1건을 감사 원장에 남긴다 (계정당 단계당 1행 목표, fail-open).

    ⚠ **인자 `conn` 은 쓰지 않는다** — 시그니처 호환과 호출부 가독성을 위해 받되, 실제 기록은
    이 함수가 여는 **전용 커넥션**으로 한다. 업무 커넥션에 쓰면 감사 헬퍼의 `commit`/`rollback`
    이 호출자의 트랜잭션을 건드린다(모듈 docstring 「계측은 자기 커넥션으로 쓴다」).

    `account` 가 없거나 계정 id 를 못 읽으면 조용히 아무것도 하지 않는다 — 비인증 방문은
    퍼널의 대상이 아니다(누가 떨어졌는지 셀 수 없으므로).
    """
    own = None
    try:
        if step not in FUNNEL_STEPS:
            return
        if path_kind not in PATH_KINDS:
            # 모르는 값을 원장에 넣지 않는다. 버리지 말고 `unknown` 으로 접는다 —
            # 단계 자체는 남아야 도달 수가 맞는다.
            path_kind = "unknown"
        account_id = int((account or {}).get("id") or 0)
        if account_id <= 0:
            return

        # 이미 기록된 것으로 아는 조합이면 **커넥션도 열지 않는다** (P2-1).
        key = _resource_id(account_id, step)
        if key in _SEEN:
            return

        # `app` 경유가 이 저장소의 규약이다(`routers/share.py` 와 동형) — `_audit_user_action`
        # 은 `routers/_audit_infra.py` 에 살지만 `app` 이 재노출하고, 테스트가 패치하는 지점도
        # 거기 하나다(app.py:2877 «app.X 동적 — 패치-단일점»).
        import app

        own = app._connect_memory()
        if own is None:
            return

        cur = own.cursor()
        try:
            if _already_recorded(cur, account_id, step):
                _remember_seen(key)
                return
        finally:
            try:
                cur.close()
            except Exception:
                pass

        app._audit_user_action(
            own, request, account,
            action=FUNNEL_ACTION,
            resource_type=FUNNEL_RESOURCE_TYPE,
            resource_id=key,
            request_ctx={"step": step, "path_kind": path_kind},
        )
        _remember_seen(key)
    except Exception as exc:  # noqa: BLE001
        # 계측이 연결을 막지 않는다. 삼키되 흔적은 남긴다.
        try:
            sys.stderr.write(f"[connect-funnel] {step} 기록 실패: {exc!r}\n")
        except Exception:
            pass
    finally:
        if own is not None:
            try:
                own.close()
            except Exception:
                pass


def account_path_kind(conn, account_id: int) -> str:
    """그 계정이 앞선 단계에서 보인 경로 종류. 없으면 `unknown`.

    `first_claim`·`first_answer` 시점에는 **그 요청만 봐서는 경로를 알 수 없다** — 도구 호출은
    러너든 등록형 클라이언트든 같은 토큰 표면을 지난다. 그래서 그 계정이 앞서 남긴 기록에서
    가져온다. 이것이 없으면 뒤 두 단계의 `path_kind` 가 전부 `unknown` 이 되어 **경로별 이탈률이
    앞 세 단계에서 끊긴다.**

    ⚠ **커서는 이 함수가 소유한다.** 호출자가 `conn.cursor()` 를 인자로 만들어 넘기면 그 커서를
    닫을 주체가 사라져 요청마다 누수된다(호출 지점이 둘이라 두 배로 샌다).
    """
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT JSON_UNQUOTE(JSON_EXTRACT(ChangeJson, '$.path_kind')) AS pk "
            "FROM WebAuditEvents "
            "WHERE ResourceType = %s AND ActionCode = %s AND ResourceId IN (%s, %s) "
            "  AND JSON_UNQUOTE(JSON_EXTRACT(ChangeJson, '$.path_kind')) <> 'unknown' "
            "ORDER BY Id DESC LIMIT 1",
            (FUNNEL_RESOURCE_TYPE, FUNNEL_ACTION,
             _resource_id(account_id, "first_heartbeat"),
             _resource_id(account_id, "handoff_issued")),
        )
        row = cur.fetchone()
        if not row:
            return "unknown"
        value = row[0] if isinstance(row, (tuple, list)) else row.get("pk")
        value = str(value or "").strip()
        return value if value in PATH_KINDS else "unknown"
    except Exception:
        return "unknown"
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
