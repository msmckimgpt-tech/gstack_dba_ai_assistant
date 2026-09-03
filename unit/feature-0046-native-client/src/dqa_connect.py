"""PyInstaller 진입점 — **패키지 밖**에 둔다.

## 왜 `client/__main__.py` 를 진입점으로 주면 안 되는가 (실측, 2026-09-03)

PyInstaller 는 넘겨받은 파일을 **최상위 스크립트로**, 즉 `__name__ == "__main__"` 이고
`__package__` 가 비어 있는 상태로 실행한다. 그 상태에서 `from .gui import main` 같은
상대 임포트는 부모 패키지가 없어 `ImportError` 로 죽는다.

종전 빌드는 정확히 그 상태였다. `DQAConnect.exe` 는 더블클릭하면 파이썬 창이 아니라
**「Unhandled exception in script — attempted relative import with no known parent
package」** 오류 대화상자를 띄웠다. 즉 **한 번도 실행된 적이 없다**.

⚠ 이것이 늦게 잡힌 이유를 남긴다. 종전 검증은 「실행하면 창이 뜬다 · 멈추지 않는다」였다.
그런데 정상 경로(`gui.tell()`)도 대화상자이고 이 실패도 대화상자다 — **창이 떴다는 사실은
두 경우를 구분하지 못한다.** 창이 떴는지가 아니라 **무엇이 적혀 있는지**를 봐야 했다.

## 계약

- 이 파일은 `client` 패키지 **바깥**에 있고 **절대 임포트만** 쓴다. 그래서 최상위 스크립트로
  실행돼도 성립한다.
- `client/__main__.py` 는 그대로 둔다 — `python -m client` 경로는 부모 패키지가 있으므로
  상대 임포트가 옳다. 두 진입은 서로 다른 규약을 따르며, 하나로 합치면 한쪽이 깨진다.
- `tests/test_client_entrypoint.py` 가 **이 파일을 실제로 최상위 실행**해 회귀를 막는다.
"""

import sys

from client.gui import main

if __name__ == "__main__":
    sys.exit(main())
