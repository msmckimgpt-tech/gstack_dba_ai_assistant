"""저장소 루트 conftest — **단위 테스트는 라이브 데이터플레인에 붙지 않는다** (불변식).

## 왜 필요한가 (근본 원인)

`make test` 는 `agent` 서비스 이미지로 컨테이너를 띄우는데, 그 서비스는 `docker-compose.yml`
의 `x-agent-common` 을 통해 **운영 `.env` 를 통째로 상속**한다(`.env`, `.env.postgres`, …).
그래서 테스트 프로세스가 운영과 동일한 런타임 라우팅 스위치를 켠 채 실행됐다:

    AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND=postgres
    AGENT_RUNTIME_READ_BACKEND=postgres
    AGENT_KB_READ_BACKEND=postgres

`--no-deps` 는 의존 서비스를 *같이 띄우지 않을* 뿐 네트워크를 끊지 않는다 — 컨테이너는
compose 네트워크에 붙으므로 이미 떠 있는 `pgbouncer`/`postgres-replica` 에 그대로 도달한다.
결과:

1. 테스트가 주입한 fake connection 이 **무시되고** 코드가 라이브 PG 를 실제로 조회했다
   (`_build_attachment_context_section` 의 PG 우선 경로). 라이브 PG 에는 테스트가 꾸민 행이
   없으니 0행 → 빈 섹션 → attachment 계열 **13건 실패**.
2. 반대로 *라이브 PG 가 살아 있을 때만* 통과하던 테스트도 생겼다(2건). 그래서 실패 집합이
   인프라 기동 상태·cutover 설정에 따라 요동쳐, 여러 세션이 "main 기준선과 동일한 N건 실패"
   를 서로 다른 N(4·8·13·15)으로 반복 관측했다.
3. `PATCH /api/conversations/{cid}/product` 테스트는 라이브 Postgres 에 **UPDATE 를 실행**
   하고 있었다 — 단위 테스트가 운영 데이터에 쓰기를 시도하는 상태.

MySQL 쪽은 이미 `Makefile` 의 `TEST_ISOLATION_ENV`(`DB_PORT=1`)로 막혀 있었으나 PG 는 열려
있었다. 본 파일은 그 격리를 **PG 까지 확장하고, 하네스 밖(로컬 `pytest`)에서도** 성립시키는
2중 방어다(1차 = `Makefile` 의 컨테이너 env, 2차 = 본 파일).

## 무엇을 하는가

- KB Postgres 접속 포트를 도달 불가 값으로 고정 → 라이브 PG 로의 연결이 성립하지 않는다.
  코드의 PG 경로는 이미 "실패 시 MySQL 폴백 또는 빈 결과 저하" 계약이므로 테스트는
  결정적으로 폴백 경로(=테스트가 주입한 fake conn)를 탄다.
- 런타임 라우팅 스위치를 `mysql` 로 중립화 → 런타임에 `os.environ` 을 직접 읽는 경로
  (예: `routers/conversations.update_conversation_product`)도 결정적이 된다.

## 예외 (라이브 백엔드 통합 테스트)

`AGENT_TEST_ALLOW_LIVE_BACKENDS=1` 이면 본 격리를 적용하지 않는다. 라이브 PG 를 실제로 겨냥한
통합 점검에서만 사용하고, `make test`(회귀 게이트)에서는 쓰지 않는다.

module-level 에서 수행하는 이유: `config.py` 같은 모듈이 import 시점에 `os.environ` 을 읽어
상수를 굳히므로, fixture(테스트 실행 시점)로는 늦다.
"""

import os

# 라이브 백엔드를 명시적으로 허용한 경우가 아니면 데이터플레인 도달을 차단한다.
if os.environ.get("AGENT_TEST_ALLOW_LIVE_BACKENDS", "").strip() not in ("1", "true", "TRUE"):
    # KB Postgres — primary(pgbouncer) / replica 양쪽. 호스트가 아니라 포트를 무효화한다:
    # 호스트명을 바꾸면 DNS 해석 대기(수초)가 테스트마다 붙지만, 포트는 즉시 refuse 된다.
    # (`DB_HOST` 를 건드리지 않는 Makefile 의 이유와 동형 — 호스트는 SSRF allowlist 등
    #  다른 판정에도 쓰이므로 값 자체를 보존한다.)
    os.environ["AGENT_KB_PG_PORT"] = "1"
    os.environ["AGENT_KB_PG_PORT_RO"] = "1"

    # 런타임 read 라우팅 — 단위 테스트의 기본 전제는 MySQL 경로다. PG 경로를 검증하는
    # 테스트는 자기 안에서 monkeypatch 로 명시 전환한다(현재 그렇게 작성되어 있다).
    os.environ["AGENT_RUNTIME_READ_BACKEND"] = "mysql"
    os.environ["AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND"] = "mysql"
    os.environ["AGENT_KB_READ_BACKEND"] = "mysql"
