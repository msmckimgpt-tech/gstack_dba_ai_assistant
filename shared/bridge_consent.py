"""feature-0043 (TASK-20260901T190000) — **배경 배치 동의**의 단일 정본.

## 무엇에 대한 동의인가

배경 배치(인사이트 요약 · 클러스터 라벨링)는 그 사람이 **요청한 적 없는 일**이고, 처리하면
**그 사람 개인 계정의 AI 사용량**을 태운다. 관리 콘솔 작업(사람이 눌러서 생김)이나 대화
답변(자기 질문)과 성질이 다르므로, 능력 신고(`console_jobs`)와 **별도 동의**로 둔다.

## 왜 이 모듈이 생겼나 — 동의의 **표현 수단**을 옮긴다

종전 동의는 러너 CLI 플래그 `--batch` 하나였다. 그 값은:

- 러너를 띄우는 명령줄에만 있어서, **웹 어디에서도 켜고 끌 수 없다**
- 바꾸려면 러너를 종료하고 다시 띄워야 한다(진행 중 작업이 끊긴다)
- 온보딩 명령을 복사해 붙인 사람은 그런 플래그가 있는 줄도 모른다

사용자 결정(2026-09-01): *"`--batch` 와 같이 명령어를 구성하는 부분과 같이, 접근성이 떨어지는
부분은 별도로 구성합니다. 웹페이지에서 토글할 수 있도록 구성해주세요."*

그래서 **동의의 주체는 그대로 계정 소유자**로 두되, 표현 수단을 웹으로 옮긴다. 서버가 계정별
동의 값을 보관하고 하트비트 응답에 실어 보내면, 러너가 그것을 읽어 자기 `features` 신고를
갱신한다.

## 두 겹이지 이중 정의가 아니다

| 축 | 누가 정하나 | 무엇을 말하나 |
|---|---|---|
| 서버 동의(웹 토글) | 계정 소유자 | "내 AI 가 배경 작업을 받아도 된다" |
| 러너 override(`--batch` / `--no-batch`) | **그 머신에서** 러너를 띄운 사람 | "이 머신은 예외" |

계정과 머신은 같지 않다 — 노트북에서는 받고 싶지 않은데 데스크톱에서는 받고 싶을 수 있고,
반대로 계정 토글을 켜 둔 채 잠깐 이 머신만 빼고 싶을 수도 있다. 그래서 override 는 남긴다.

다만 **판정은 한 곳에서만** 한다: 서버가 배급 자격을 볼 때 읽는 것은 언제나 러너가 신고한
`features` 하나다(`ai_tools._grants_for`). 서버가 "동의했으니 준다" 를 따로 판단하면 같은
질문에 두 개의 답이 생기고, 갈리는 순간 느슨한 쪽이 사실이 된다. 여기 있는
`apply_consent()` 는 **러너가 자기 신고를 만들 때** 쓰는 함수이고, 서버는 그것을 예측·설명하는
용도로만 쓴다.

⚠ 러너(`bridge_agent.py`)는 사용자 머신에 홀로 놓이는 단일 파일이라 이 모듈을 import 하지
못한다. 그래서 같은 진리표를 **거울 함수**로 갖고, 이음매 테스트가 두 구현을 같은 입력으로
돌려 대조한다(교훈: 프로세스 경계의 값 모양은 양쪽을 각각 검사해도 안 잡힌다).
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "BATCH_FEATURE",
    "DEFAULT_BATCH_CONSENT",
    "CONSENT_NOTICE",
    "apply_consent",
    "normalize_consent",
]

#: 러너가 하트비트에 실어 신고하는 기능 이름. `bridge_tasks.RUNNER_FEATURE_BATCH_JOBS` 와
#: 같은 값이어야 한다 — 계약 테스트가 두 상수를 대조한다(이름을 두 곳에 적는 것이 아니라,
#: 한쪽은 배급 자격의 이름이고 한쪽은 동의의 이름이라 **뜻이 다르되 값이 같아야** 한다).
BATCH_FEATURE = "batch_jobs"

#: 모르면 **받지 않는다.** 남의 계정 토큰을 태우는 축이라 fail-closed 가 유일하게 정직한
#: 기본값이다 — 컬럼이 아직 없는 배포 창, 값이 NULL 인 기존 계정, 파싱 실패 전부 여기로 떨어진다.
DEFAULT_BATCH_CONSENT = False

#: 웹 토글 옆에 **반드시 함께** 보이는 1줄 고지. 화면과 러너 로그가 각자 문구를 지으면
#: 같은 사실을 두 가지로 말하게 되므로 여기 하나만 둔다.
CONSENT_NOTICE = (
    "켜면 내 AI 가 서비스의 배경 작업(인사이트 요약·클러스터 라벨링)도 처리합니다 — "
    "내가 요청하지 않은 일이며 내 AI 계정의 사용량을 씁니다."
)


def normalize_consent(value: Any) -> bool:
    """DB·JSON·폼에서 온 동의 값을 bool 로 굳힌다. **모르면 False.**

    받는 모양이 제각각이다: MySQL `TINYINT` 는 `1`/`0`/`None`, JSON 은 `true`/`false`,
    폼은 `"on"`/`"1"`/`""`. 각 소비처가 각자 해석하면 한 곳만 `"0"` 을 참으로 읽는 날
    (비어 있지 않은 문자열이므로) 동의하지 않은 사람의 계정이 배경 작업을 태운다.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return DEFAULT_BATCH_CONSENT
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return DEFAULT_BATCH_CONSENT
    return text in {"1", "true", "yes", "on", "t", "y"}


def apply_consent(base_features: Any, *, server_consent: Any,
                  local_override: bool | None = None) -> tuple[str, ...]:
    """러너가 신고할 `features` 를 만든다 — 이 결정의 **정본 진리표**.

    Args:
        base_features: 이 러너가 원래 신고하는 것들(`console_jobs` 등). 배치 항목은 여기서
            제거된 뒤 아래 판정 결과로 다시 붙는다 — 호출측이 이미 넣어 둔 값이 판정을
            앞지르지 않게 하려는 것이다.
        server_consent: 서버(계정 소유자)가 웹에서 켠 값. 하트비트 응답의 `batch_consent`.
        local_override: 그 머신의 명시 지시. `True`=`--batch`, `False`=`--no-batch`,
            `None`=지시 없음(서버 값을 따른다).

    | override | 서버 동의 | 결과 |
    |---|---|---|
    | `None`   | False | 받지 않는다 |
    | `None`   | True  | **받는다** |
    | `True`   | 무관  | 받는다 (이 머신에서 명시 허용) |
    | `False`  | 무관  | 받지 않는다 (이 머신만 예외) |

    override 가 서버 값을 **양방향으로** 이긴다. 한쪽만 이기게 하면(예: 서버가 끄면 무조건
    끔) "이 머신만 켜 두기" 가 불가능해지고, 그 순간 사용자는 계정 토글을 켰다 껐다 하며
    다른 머신까지 흔들게 된다.
    """
    feats = [str(f) for f in (base_features or []) if str(f) and str(f) != BATCH_FEATURE]
    if local_override is None:
        want = normalize_consent(server_consent)
    else:
        want = bool(local_override)
    if want:
        feats.append(BATCH_FEATURE)
    return tuple(feats)
