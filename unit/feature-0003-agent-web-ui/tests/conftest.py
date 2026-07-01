"""feature-0012 P5b — DI seam 테스트 인프라 (Phase 1, DI_SEAM_BLUEPRINT §3.2).

app.py 의 FastAPI auth DI seam(get_current_account / get_optional_account / require_permission)
을 TestClient + dependency_overrides 로 검증하기 위한 공용 픽스처.

배경: 기존 테스트는 핸들러를 `asyncio.run(app.handler(_FakeRequest(...)))` 로 직접 함수호출했는데,
이는 DI(Depends)가 적용된 핸들러엔 통하지 않는다(Depends 마커가 인자 기본값으로 새어 들어가 실행됨).
Phase 1 부터 마이그된 핸들러는 본 TestClient 경로(dependency_overrides)로 검증한다(블루프린트 §0).

픽스처(클러스터 마이그 표준):
- `client`           : TestClient. base_url=localhost(TrustedHost 통과) + lifespan 미발화(--no-deps).
- `make_account`     : permissions 명시 계정 dict 빌더(callable). {"Id":1} 축약 금지(§3.2 보정 MEDIUM-2).
- `as_account`       : get_current_account/get_optional_account 를 그 계정으로 override(callable).
- `as_anonymous`     : 미인증 override(get_optional_account=None, get_current_account=401)(callable).
- (autouse) override 정리 — 각 테스트 후 dependency_overrides 를 비워 격리.

환경 제약 처리(make test, agent 이미지, --no-deps):
- TrustedHost: WEB_ALLOWED_HOSTS 기본값(localhost,127.0.0.1,web) → base_url="http://localhost" 로 통과.
- startup 훅(@app.on_event): TestClient 를 context manager 없이 생성하면 lifespan 미발화 → DB 미접속.
- httpx: TestClient(starlette) 의존. agent 이미지에 openai>=1.0.0 의 transitive dep 로 존재.
  방어적으로 fixture 안에서 import 한다(부재 시 client 미사용 테스트는 영향 없음).
"""
from __future__ import annotations

from typing import Any, Callable

import pytest

import app as appmod


@pytest.fixture(autouse=True)
def _isolate_dependency_overrides():
    """각 테스트 전후로 app.dependency_overrides 를 스냅샷·복원(전 테스트 격리).

    clear() 가 아니라 사전 상태를 복원한다 — 다른 conftest/플러그인이 미리 설정한 override 를
    보존하기 위함(단일 소비자 전제에 묶이지 않는 robust 격리, 적대 패널 REV LOW).
    """
    saved = dict(appmod.app.dependency_overrides)
    yield
    appmod.app.dependency_overrides.clear()
    appmod.app.dependency_overrides.update(saved)


@pytest.fixture
def client():
    """auth DI seam 검증용 TestClient.

    base_url=localhost(TrustedHost 통과) + context manager 미사용(startup 훅·DB 미발화).
    raise_server_exceptions=True — 미처리 예외는 테스트로 재전파(명확한 실패). 처리된 예외
    (_AuthError 등 등록 핸들러 경유)는 응답으로 반환된다. 미처리-예외→500 응답 자체를 검증할
    때는 client_capture_errors 를 쓴다.
    """
    from fastapi.testclient import TestClient

    return TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=True)


@pytest.fixture
def client_capture_errors():
    """미처리 예외를 재전파하지 않고 500 응답으로 받는 TestClient.

    legacy 의 'conn-open + 인증쿼리 raise → 500 전파' byte-동치를 응답 셰이프 단위로 검증할 때 사용.
    """
    from fastapi.testclient import TestClient

    return TestClient(appmod.app, base_url="http://localhost", raise_server_exceptions=False)


@pytest.fixture
def make_account() -> Callable[..., dict[str, Any]]:
    """permissions 를 명시한 테스트 계정 dict 빌더.

    permissions 는 항상 명시한다(403 테스트=해당 perm False, happy=True) — {"Id":1} 축약 금지
    (블루프린트 §3.2 보정 MEDIUM-2). _account_has_permission(account, p) = permissions.get(p).
    """

    def _make(*, perms: dict[str, bool] | None = None, **extra: Any) -> dict[str, Any]:
        acct: dict[str, Any] = {
            "id": 1,
            "Id": 1,
            "username": "tester",
            "permissions": dict(perms or {}),
        }
        acct.update(extra)
        return acct

    return _make


@pytest.fixture
def as_account(make_account) -> Callable[..., dict[str, Any]]:
    """get_current_account / get_optional_account 를 주어진 계정으로 override 하고 그 계정을 반환.

    require_permission(...) 의 내부 dep 는 get_current_account 에 의존하므로 함께 override 된다
    (require_permission 자체는 override 불요 — 실제 _account_has_permission 검사를 그대로 탄다).
    """

    def _as(*, perms: dict[str, bool] | None = None, **extra: Any) -> dict[str, Any]:
        acct = make_account(perms=perms, **extra)
        appmod.app.dependency_overrides[appmod.get_current_account] = lambda: acct
        appmod.app.dependency_overrides[appmod.get_optional_account] = lambda: acct
        return acct

    return _as


@pytest.fixture
def as_anonymous() -> Callable[[], None]:
    """미인증 상태로 override — get_optional_account=None, get_current_account=401(_AuthError)."""

    def _as() -> None:
        appmod.app.dependency_overrides[appmod.get_optional_account] = lambda: None

        def _unauth() -> dict[str, Any]:
            raise appmod._AuthError("로그인이 필요합니다.", 401)

        appmod.app.dependency_overrides[appmod.get_current_account] = _unauth

    return _as
