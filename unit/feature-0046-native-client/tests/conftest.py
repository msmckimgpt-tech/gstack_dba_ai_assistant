"""이 unit 의 테스트가 **실제 사용자 홈을 건드리지 않게** 한다.

## 왜 생겼나 (실측 2026-09-04)

인자 없는 실행을 살리면서 진입점이 `~/.dqa-connect` 를 **읽고 쓰게** 됐다(어느 서버를 열지
기억한다). 그 직후 테스트 한 번에 개발 머신의 `~/.dqa-connect/server.json` 이 생겼고, 그
파일 때문에 **다른 테스트가 갈래를 바꿔** 실패했다. 즉 이 파일이 없으면:

- 테스트가 사용자 상태를 오염시킨다(러너가 쓰는 홈과 같은 폴더다).
- 테스트 결과가 **그 머신에 무엇이 적혀 있는가**에 달린다 — 내 PC 에서는 통과하고 CI 에서만
  깨지거나 그 반대가 된다. 이 저장소가 반복해 겪은 「환경이 판정을 가르는」 형태다.

⚠ `Path.home()` 은 POSIX 에서 `HOME`, Windows 에서 `USERPROFILE` 을 본다. 한쪽만 세우면
  다른 OS 에서 이 격리가 조용히 사라진다.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home
