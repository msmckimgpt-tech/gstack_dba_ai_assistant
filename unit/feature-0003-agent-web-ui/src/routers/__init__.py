"""feature-0012 P5b Final — 도메인 APIRouter 패키지.

app.py(29K 모놀리스)를 도메인별 APIRouter 로 점진 분할한다. 각 router 는 공유 의존
(get_current_account / get_conn / require_permission / _json_error 등)을 app 정본에서 import 하며,
app.py 는 맨 끝(모든 정의 후)에서 `register_all(app)` 을 호출하므로 순환 import 가 안전하다
(app 모듈이 sys.modules 에 부분 적재된 상태에서 필요한 심볼은 이미 정의됨).

라우터 자동 등록 (parallel-work-structure ITEM-05): 신규 라우터는 본 패키지에 `router` 심볼을
가진 모듈 파일을 추가하기만 하면 등록된다 — app.py 꼬리 배선 편집 불필요(병렬 배선 경합 제거).
등록 순서는 각 모듈의 `INCLUDE_ORDER: int` 상수가 고정한다(2026-07-10 현행 23개 include 순서
스냅샷 — 순서 변경 금지 guard). INCLUDE_ORDER 미지정 모듈은 맨 뒤에 파일명 순으로 붙는다.
"""

import importlib
import pkgutil

_DEFAULT_INCLUDE_ORDER = 10_000  # INCLUDE_ORDER 미지정 신규 모듈 → 맨 뒤(파일명 순)


def register_all(app):
    """routers/ 하위 전 모듈의 `router` 심볼을 (INCLUDE_ORDER, 모듈명) 순으로 일괄 include."""
    entries = []
    for m in pkgutil.iter_modules(__path__):
        if m.ispkg or m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{m.name}")
        router = getattr(mod, "router", None)
        if router is None:
            continue
        entries.append((getattr(mod, "INCLUDE_ORDER", _DEFAULT_INCLUDE_ORDER), m.name, router))
    for _, _, router in sorted(entries, key=lambda t: (t[0], t[1])):
        app.include_router(router)
