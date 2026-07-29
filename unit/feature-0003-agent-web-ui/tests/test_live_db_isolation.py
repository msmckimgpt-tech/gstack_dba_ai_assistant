"""테스트 스위트 전역 안전 계약 — 단위 테스트는 라이브 컨트롤플레인에 쓰지 않는다.

사고 배경 (2026-07-13 ~ 2026-07-29, test-live-db-isolation)
-------------------------------------------------------------
관리 콘솔 `시스템 > 설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃` 을 사용자가 900초로
설정해도 반복적으로 90초로 되돌아가는 현상이 관측됐다. 원인은 외부 요인이 아니라 **자기 자신의
`make test`** 였다:

1. `make test` 는 `docker compose run --rm --no-deps ... agent` 로 pytest 를 돌린다.
   `--no-deps` 는 의존 서비스를 *기동*하지 않을 뿐, **이미 떠 있는 운영 컨테이너와의 연결을
   차단하지 않는다.** agent 서비스는 `networks: [dbnet, ...]` + `env_file: .env/.env.mysql` +
   `volumes: ../artifacts/shared:/shared` 를 상속하므로 라이브 MySQL·라이브 스냅샷에 직결됐다.
2. `conftest.py` 는 "TestClient 를 context manager 없이 만들면 lifespan 미발화 → DB 미접속" 을
   전제했지만, `get_conn` 은 lifespan 이 아니라 **요청 스코프 Depends** 라 매 요청 실행된다.
3. `test_runtime_settings_api.py` 의 PUT 테스트가 `assert status in (200, 500)` 로 성공 저장까지
   허용해, 오염이 테스트 통과로 위장됐다.

결과: `agent_memory.WebRuntimeSettings` 가 매 테스트 실행마다 테스트 리터럴로 덮어써졌고
(audit `RemoteAddr=testclient` 150건), 스냅샷 reconcile 을 타고 `/shared/runtime_settings.json`
까지 전파돼 라이브 워커·web 에 즉시 반영됐다. 사용자가 설정한 sonnet 총 출력 128000 도 42초 뒤
100000 으로 롤백된 것이 audit 에 남아 있다.

본 파일은 그 재발을 유닛 레벨에서 잡는 계약 테스트다. 방어는 2겹이며 각각 여기서 검증한다:
- 애플리케이션 레벨: conftest `_no_live_memory_conn` autouse fixture (get_conn → None 고정)
- 컨테이너 레벨: Makefile `TEST_ISOLATION_ENV` (컨트롤플레인 호스트 도달 불가 + 스냅샷 경로 격리)
"""
from __future__ import annotations

import app as appmod


def test_memory_conn_entrypoint_is_blocked():
    """conftest autouse fixture 가 memory DB 커넥션 진입점을 막고, get_conn 이 None 을 준다.

    이 차단이 사라지면 테스트가 실 커넥션을 잡고, 저장 경로를 타는 테스트가 라이브 컨트롤플레인을
    오염시킨다(위 사고). 진입점 차단과 그 결과(conn=None)를 함께 고정한다.
    """
    import pytest

    with pytest.raises(RuntimeError):
        appmod._connect_memory()

    # get_conn 은 연결 실패를 흡수해 None 을 yield 한다(app.py get_conn 계약).
    assert list(appmod.get_conn()) == [None], (
        "get_conn 이 None 을 yield 하지 않는다 — 저장 경로가 실 DB 에 도달할 수 있다."
    )


def test_runtime_setting_put_cannot_reach_live_db(client, as_account):
    """런타임 설정 저장 endpoint 가 유닛 환경에서 DB 에 도달하지 못한다(500).

    200 이면 라이브 `WebRuntimeSettings` 에 override 가 실제로 저장된 것 — 운영 관리 콘솔의
    설정값이 테스트 리터럴로 롤백된다. 사고의 직접 표면이라 endpoint 레벨로도 고정한다.
    """
    as_account(perms={"console.access": True, "system.runtime.read": True, "system.runtime.write": True})
    resp = client.put("/api/admin/settings/runtime", json={"key": "AGENT_TIMEOUT_SEC", "value": 90})
    assert resp.status_code == 500, (
        f"PUT 이 {resp.status_code} 를 반환했다 — 500 이 아니면 실 DB 저장 경로가 열려 있다는 뜻이다. "
        "라이브 운영 설정이 테스트 값으로 덮어써지므로 즉시 격리를 복원할 것."
    )


def test_runtime_settings_snapshot_path_is_not_shared_volume():
    """스냅샷 경로가 라이브 공유 볼륨(`/shared`)을 가리키지 않는다.

    `write_snapshot` 은 DB 저장 후 reconcile 로 호출돼 `/shared/runtime_settings.json` 을 원자적
    재작성한다. 이 파일은 web·워커가 TTL 로 읽는 live 전파 채널이라, 테스트가 여기에 쓰면 DB 를
    막아도 라이브 런타임 값이 오염된다. Makefile `TEST_ISOLATION_ENV` 가 경로를 컨테이너 임시
    파일로 돌린다 — 그 env 가 빠지면 여기서 잡는다.

    강제 조건은 "`/shared` 디렉토리 존재" 가 아니라 **운영 스냅샷 파일의 실재** 다. CI 러너는
    `app.py` 의 `SESSION_DIR.mkdir()` 를 위해 빈 `/shared` 를 만들지만(ci.yml) 그 안에 운영
    스냅샷은 없어 오염 표면이 없다 — 디렉토리 존재로 판정하면 CI 가 거짓 FAIL 한다(실측).
    반대로 운영 스택이 마운트된 컨테이너에는 이 파일이 실재하므로, Makefile 의 격리 env 가
    빠지면 여기서 잡힌다.
    """
    import os

    from shared import runtime_settings

    if not os.path.exists("/shared/runtime_settings.json"):
        return  # 운영 스냅샷 부재 — 덮어쓸 대상이 없다.
    path = runtime_settings.snapshot_path()
    assert not path.startswith("/shared/"), (
        f"스냅샷 경로가 라이브 공유 볼륨({path}) 이다 — 테스트 저장이 운영 프로세스로 전파된다. "
        "Makefile `TEST_ISOLATION_ENV` 의 RUNTIME_SETTINGS_SNAPSHOT_PATH override 를 복원할 것."
    )
