"""feature-0012 P5b Final — 도메인 APIRouter 패키지.

app.py(29K 모놀리스)를 도메인별 APIRouter 로 점진 분할한다. 각 router 는 공유 의존
(get_current_account / get_conn / require_permission / _json_error 등)을 app 정본에서 import 하며,
app.py 는 맨 끝(모든 정의 후)에서 `from routers.<domain> import router; app.include_router(router)`
하므로 순환 import 가 안전하다(app 모듈이 sys.modules 에 부분 적재된 상태에서 필요한 심볼은 이미 정의됨).
"""
