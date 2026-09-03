"""연결 단계 체크리스트 — 화면이 「어디서 막혔는지」를 말한다 (ROADMAP ITEM-03·ITEM-06).

## 왜 이 모듈이 있는가

GUI 편향 사용자에게 가장 직접적인 처방이다 — *"터미널을 안 봐도 된다"* 를 참으로 만든다.

실측된 최악 사례: 능력 협상 실패로 **240초 침묵**. 그동안 하트비트·로그·질문 수신이 0인데
설치 스크립트는 2초 뒤 「완료」를 선언했고, 실패 사유는 **러너 로그(터미널)에만** 있었다
(`REPORT.md` TASK-20260902T140000 ②). 네이티브 클라이언트(feature-0046)가 자기 창에 로그를
그리지만, **사용자가 질문하는 곳은 웹**이다 — 웹이 모르면 「연결됨」만 보고 아무도 없는 곳에
질문하게 된다(제보 2026-08-27).

## 판정은 서버 한 곳

프런트가 `connected && listening` 같은 곱을 스스로 조립하면 **판정이 두 벌**이 되고, 축이 하나
늘 때 화면과 서버가 갈린다 — 갈리는 순간 **느슨한 쪽이 사용자가 보는 진실**이 된다(P0-R 실측).
단독 페이지와 모달이 같은 배열을 그리므로 문안도 갈리지 않는다(P0-L 계약).

## 각 행은 「다음 행동」을 함께 낸다

상태만 그리면 사용자는 무엇을 할지 모른다. `action` 이 없는 행은 **할 일이 없는 행**이다.
"""

from __future__ import annotations

#: 단계 상태. 화면은 이 세 값만 안다.
OK, PENDING, FAIL = "ok", "pending", "fail"


def build_steps(*, connected: bool, listening: bool, has_caps: bool,
                answered: bool, client_download: str | None) -> list[dict]:
    """연결 단계 5행. **순서가 의미를 갖는다** — 앞이 막히면 뒤는 판정하지 않는다.

    Args:
        connected: 유효 토큰이 있다 (`account_has_live_token`)
        listening: 최근 하트비트가 있다 (`HEARTBEAT_WINDOW_SEC` 안)
        has_caps: 러너가 쓸 수 있는 모델을 신고했다 = **답할 AI 가 실재한다**
        answered: 이 계정이 답변을 받아 본 적이 있다 (퍼널 `first_answer`)
        client_download: 네이티브 클라이언트를 받을 수 있으면 그 URL, 아니면 `None`

    ⚠ `client_download` 가 `None` 이면 **클라이언트를 권하지 않는다.** 없는 다운로드를 안내하면
    사용자는 안내받은 대로 갔다가 막힌다 — P0-I 가 닫은 결함 클래스다(가이드와 실제의 불일치).
    """
    install_action = None
    if not connected and client_download:
        install_action = {"label": "연결 프로그램 받기", "href": client_download}

    steps: list[dict] = [
        {
            "key": "connected",
            "label": "연결 정보 발급",
            "state": OK if connected else PENDING,
            "detail": ("이 계정에 유효한 연결 정보가 있습니다."
                       if connected else "아래 [연결 준비] 를 눌러 시작하세요."),
            "action": install_action,
        },
        {
            "key": "listening",
            "label": "내 컴퓨터가 듣는 중",
            # 토큰이 있는 것과 **지금 듣고 있는 것**은 다르다. 재부팅하면 러너만 사라지고
            # 토큰은 남아, 「연결됨」만 보면 아무도 없는 곳에 질문하게 된다(제보 2026-08-27).
            "state": (OK if listening else (FAIL if connected else PENDING)),
            "detail": ("연결 프로그램이 실행 중입니다."
                       if listening else
                       "연결 정보는 살아 있는데 프로그램이 실행 중이 아닙니다 — "
                       "컴퓨터를 껐다 켰다면 다시 실행해 주세요."
                       if connected else "아직 시작하지 않았습니다."),
            "action": ({"label": "내 AI 실행", "scheme": True}
                       if connected and not listening else None),
        },
        {
            "key": "ai",
            "label": "답할 AI 있음",
            # ⚠ **연결 축과 AI 축을 갈라 말한다.** 서버 연결이 멀쩡한데 「연결 확인 실패」로
            #   보이면 사용자는 서버를 의심한다(REQ-20260901-win-ai-detect 의 실제 제보).
            "state": (OK if (listening and has_caps)
                      else (FAIL if listening else PENDING)),
            "detail": ("이 컴퓨터의 AI 로 답할 수 있습니다." if (listening and has_caps)
                       else "프로그램은 실행 중인데 쓸 수 있는 AI 를 찾지 못했습니다. "
                            "**서버 연결과는 별개입니다** — AI 를 설치하고 로그인해 주세요."
                       if listening else "앞 단계가 끝나면 확인합니다."),
            "action": None,
        },
        {
            "key": "answered",
            "label": "첫 답변 받음",
            "state": OK if answered else PENDING,
            "detail": ("답변을 받아 본 적이 있습니다." if answered
                       else "대화 화면에서 질문하면 이 컴퓨터의 AI 가 답합니다."),
            "action": None,
        },
    ]
    return steps


def overall(steps: list[dict]) -> str:
    """전체 한 줄. 화면 맨 위에 그린다.

    **가장 앞선 미완료 단계**를 말한다 — 뒤쪽 실패를 먼저 말하면 사용자는 이미 지난 단계를
    다시 손댄다.
    """
    for s in steps:
        if s["state"] == FAIL:
            return s["label"] + " — 확인이 필요합니다"
    for s in steps:
        if s["state"] == PENDING:
            return s["label"] + " 차례입니다"
    return "모두 준비되었습니다"
