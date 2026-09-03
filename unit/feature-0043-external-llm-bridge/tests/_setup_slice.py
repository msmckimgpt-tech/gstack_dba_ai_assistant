"""`bridge_setup.sh` 의 **조각을 떼어 실제 `sh` 로 돌리는** 하네스의 공용 부품.

## 왜 필요한가

이 저장소의 설치 스크립트 테스트는 전체를 돌리지 않는다(네트워크·설치·프로세스 기동이
일어난다). 대신 함수나 heredoc 블록만 떼어 진짜 `sh` 에 먹여 **파싱·전개·인용까지** 본다.

그런데 2026-09-03 명칭 개명이 `DQA_SCHEME` 같은 **스크립트 상단 변수**를 도입하면서, 떼어낸
조각이 그 변수를 참조하는데 정의는 따라오지 않는 상태가 됐다 — `set -eu` 아래에서
`parameter not set` 으로 조각이 통째로 죽고, 그 죽음이 **테스트 실패로 위장**한다
(실측: `test_wsl_scheme_handler` 5건 · `test_launcher_ca_pin` 10건).

## 왜 하네스가 값을 «지어내지» 않는가

`DQA_SCHEME=dqa-connect` 를 테스트에 하드코딩하면 조각은 돌지만, 그때부터 그 테스트는
**하네스가 준 값**을 검증하게 된다 — 정본이 바뀌어도 통과한다. 그래서 여기서는 정본
파일에서 **대입문을 그대로 떼어 온다**. 정본이 바뀌면 조각도 함께 바뀐다.

(값 자체가 다섯 자리에서 같은지는 `test_name_ssot.py` 가 본다. 이 모듈은 «조각이 정본의
값으로 돈다» 만 보장한다 — 두 축이 겹치지 않는다.)
"""
from __future__ import annotations

import pathlib
import re

_HERE = pathlib.Path(__file__).resolve()
SETUP_SH = _HERE.parents[1] / "src" / "bridge_setup.sh"

#: 상단 명칭 블록의 대입문. `DQA_` 접두 하나로 잡으면 새 축이 추가돼도 자동으로 따라온다
#: — 목록을 손으로 나열하면 다음 추가 때 조용히 다시 벌어진다(AGENTS.md §16.7 G12-b).
_ASSIGN = re.compile(r"^(DQA_[A-Z_]+=(?:'[^']*'|\"[^\"]*\"))\s*$", re.M)


def naming_block(src: str | None = None) -> str:
    """정본에서 `DQA_*` 대입문만 뽑아 조각 앞에 붙일 수 있는 셸 텍스트로 돌려준다."""
    text = src if src is not None else SETUP_SH.read_text(encoding="utf-8")
    found = _ASSIGN.findall(text)
    assert found, "bridge_setup.sh 에서 DQA_* 명칭 대입을 찾지 못했다 — 슬라이스 경계가 깨졌다"
    return "\n".join(found) + "\n"
