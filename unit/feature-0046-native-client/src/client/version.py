"""클라이언트 배포 **버전의 단일 정본** 과 버전 비교.

## 왜 이 파일이 생겼나 (2026-09-07)

그 전까지 버전은 `installer/DQAConnect.iss` 의 `#define MyAppVersion "1.0.0"` **한 줄에만**
있었고, 실행 중인 프로그램은 자기 버전을 몰랐다. 그래서 다른 머신에 깔린 설치본이
「내가 지금 몇인가」를 말할 수 없었고, 「서버의 것이 더 새것인가」를 판정할 근거가 없었다 —
업데이트 구조의 첫 번째 결손이 그것이다.

이제 정본은 여기 하나이고 흐름은 한 방향이다:

    version.py (정본)
      → build_client.py 가 ISCC 에 `/DAppVersion=` 으로 주입 → 설치기 파일명·제거 항목
      → publish_release.py 가 `manifest.json` 의 `version` 으로 적재
      → 서버가 그 매니페스트를 그대로 서빙
      → 다른 머신의 클라이언트가 자기 `CLIENT_VERSION` 과 비교

`.iss` 는 `#ifndef AppVersion` 폴백을 갖되 그 폴백 값이 여기와 같아야 하며,
`tests/test_updater.py::test_iss_version_matches_the_canon` 이 두 값을 대조한다 —
갈리면 **설치기 파일명과 프로그램이 말하는 버전이 서로 다른** 상태가 되고, 그 상태에서
업데이트 판정은 «항상 새것» 또는 «영원히 최신» 중 하나로 고장난다.

## 왜 `shared/dqa_identity.py` 에 두지 않는가

이 모듈은 **동결되는 배포본** 안에서 돈다. `client/core.py` 가 `shared/` 를 import 하지
않는 것과 같은 이유이며(그 파일의 `DISPLAY_NAME` 주석 참조), 게다가 버전은 «이름» 과
수명이 다르다 — 이름은 개명 때 한 번 바뀌고 버전은 릴리스마다 바뀐다.
"""
from __future__ import annotations

import re

#: 이 소스 트리가 만들어 내는 배포본의 버전. **릴리스마다 여기를 올린다.**
#:
#: ⚠ `installer/DQAConnect.iss` 의 `#ifndef AppVersion` 폴백과 **같은 값**이어야 한다.
CLIENT_VERSION = "1.5.0"

#: 버전 문자열이 가져야 할 모양. 설치기 파일명에 그대로 들어가므로 경로·인자로 새어 나갈 수
#: 있는 문자를 애초에 배제한다(`publish_release.py` 와 `updater.py` 가 같은 정규식을 쓴다).
VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,3}$")


def parse(value: str) -> tuple[int, ...] | None:
    """`"1.2.3"` → `(1, 2, 3)`. 모양이 아니면 `None`.

    ⚠ **문자열 비교로 버전을 판정하지 않는다.** `"1.10.0" < "1.9.0"` 이 참이 되어,
    열 번째 릴리스가 아홉 번째보다 낡은 것으로 읽힌다 — 그 순간 업데이트는 조용히 멈추고
    아무도 원인을 알지 못한다.
    """
    text = str(value or "").strip()
    if not VERSION_RE.match(text):
        return None
    return tuple(int(p) for p in text.split("."))


def is_newer(candidate: str, current: str = CLIENT_VERSION) -> bool:
    """`candidate` 가 `current` 보다 **엄격히** 새것인가.

    ⚠ **같으면 거짓이다.** 같은 버전을 새것으로 읽으면 클라이언트가 매번 같은 설치기를 받아
    자기를 다시 설치한다 — 러너 자기 갱신이 규율 4(「바뀌는 것이 없으면 재기동하지 않는다」)로
    끊은 그 고리와 같은 형태다.

    ⚠ **판정 불가는 거짓이다.** 모양이 아닌 값을 「새것」으로 읽으면, 매니페스트를 오염시킬 수
    있는 상대가 아무 문자열로 설치를 유발할 수 있다. 모르면 갱신하지 않는다.
    """
    a, b = parse(candidate), parse(current)
    if a is None or b is None:
        return False
    # 자릿수가 다른 경우(`1.2` vs `1.2.0`)를 0 으로 채워 같은 길이로 본다.
    width = max(len(a), len(b))
    a = a + (0,) * (width - len(a))
    b = b + (0,) * (width - len(b))
    return a > b
