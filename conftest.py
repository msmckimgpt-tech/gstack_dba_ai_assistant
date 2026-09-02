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

    # memory/data MySQL(컨트롤플레인) — 종전엔 Makefile 의 `-e DB_PORT=1` 만 담당했다.
    # 그래서 하네스를 거치지 않는 실행(로컬 `pytest`, IDE 러너, 다른 Make 타깃)에서는 라이브
    # MySQL 이 열려 있었고, 실제로 관리 콘솔 런타임 설정이 테스트 값으로 덮어써지는 사고가
    # 났다(2026-07-13~29, audit RemoteAddr=testclient). 격리를 파일 쪽으로 끌어와 하네스
    # 유무와 무관하게 성립시킨다(Makefile 은 동일 값을 유지 — 컨테이너 레벨 1차 방어).
    os.environ["DB_PORT"] = "1"

    # 런타임 read 라우팅 — 단위 테스트의 기본 전제는 MySQL 경로다. PG 경로를 검증하는
    # 테스트는 자기 안에서 monkeypatch 로 명시 전환한다(현재 그렇게 작성되어 있다).
    os.environ["AGENT_RUNTIME_READ_BACKEND"] = "mysql"
    os.environ["AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND"] = "mysql"
    os.environ["AGENT_KB_READ_BACKEND"] = "mysql"

    # ── 격리 실효 검증 (fail-loud) ────────────────────────────────────────────
    # 위 값 방어는 "라이브 자원에 닿아도 값으로 막는다" 는 층이다. 그 아래에 도달성 층이
    # 있어야 한다 — `make test` 는 전용 compose 프로젝트(`repo-unittest`)로 떠서 라이브
    # `mysql` 서비스명이 DNS 로 해석조차 되지 않는다(Makefile `DC_TEST` 참조).
    #
    # 여기서는 그 도달성 층이 실제로 서 있는지 **운영 기본 포트로 직접 확인**한다. env 를
    # 읽지 않고 3306 리터럴을 쓰는 이유: 위에서 DB_PORT 를 1 로 덮었으므로 env 기반 probe 는
    # 자기 자신을 검사하는 동어반복이 된다. 확인하려는 것은 "이 프로세스가 라이브 스택
    # 네트워크 안에 있는가" 이고, 그 답이 예이면 값 방어 하나가 뚫릴 때 곧바로 운영 오염으로
    # 이어진다(실측 사고 경로). 그래서 조용히 통과시키지 않고 collection 단계에서 중단한다.
    #
    # 정상 경로는 모두 통과한다 — `make test`(전용 프로젝트: DNS 미해석) · CI 러너(mysql 호스트
    # 부재) · 호스트 로컬 pytest(`mysql` 은 컨테이너 내부 DNS 이름). 라이브 백엔드를 겨냥한
    # 통합 점검은 위 AGENT_TEST_ALLOW_LIVE_BACKENDS=1 로 본 블록 전체를 건너뛴다.
    def _assert_live_stack_unreachable() -> None:
        import socket

        host = (os.environ.get("DB_HOST") or "mysql").strip()
        if not host:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)  # 닫힌 포트/미해석 호스트는 즉시 실패 — 테스트 지연 없음
        try:
            reachable = sock.connect_ex((host, 3306)) == 0
        except OSError:
            reachable = False  # DNS 미해석 등 = 격리 성립
        finally:
            sock.close()
        if reachable:
            raise RuntimeError(
                f"단위 테스트가 라이브 스택 네트워크 안에서 실행되고 있다 ({host}:3306 도달 가능). "
                "이 상태에서는 값 격리가 한 겹만 뚫려도 운영 DB(agent_memory)가 테스트 값으로 "
                "덮어써진다 — 실제로 관리 콘솔 런타임 설정이 그렇게 오염됐다. "
                "`make test` 로 실행하면 전용 compose 프로젝트가 도달성을 끊는다. "
                "COMPOSE_PROJECT_NAME 으로 라이브 프로젝트를 지정하지 말 것. "
                "라이브 백엔드를 의도적으로 겨냥한 통합 점검이면 AGENT_TEST_ALLOW_LIVE_BACKENDS=1."
            )

    _assert_live_stack_unreachable()


# ── 브리지 러너 배포 산출물 배치 (feature-0043 모듈 분할) ──────────────────────────
#
# 러너의 소스는 `unit/feature-0043-external-llm-bridge/src/agent/` 패키지이고, 내려받는
# 실물(단일 파일)과 배포본은 **빌드 생성물**이다(AGENTS.md §13.1 v3.35.1 «1순위» — 생성물을
# 소스에 커밋하지 않는다). 이미지에서는 Dockerfile 이 만들지만, 테스트는 이미지 밖에서 돌므로
# 여기서 같은 스크립트로 같은 산출물을 만든다.
#
# **왜 fixture 가 아니라 import 시점인가**: 러너 계약 테스트 37개가 모듈 수준에서 이 경로를
# 상수로 잡는다. fixture 는 그보다 늦다. 또 collection 단계에서 실패하면 「배포본이 없어서
# 통과한 것처럼 보이는」 상태가 원천적으로 생기지 않는다.
#
# 실패는 **조용히 넘기지 않는다** — 산출물이 없으면 러너 계약 테스트가 전부 무의미해지고,
# 그 무의미함은 「초록불」로 보인다.
def _stage_bridge_runner() -> None:
    import subprocess
    import sys

    root = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(root, "unit", "feature-0002-agent-core", "src", "scripts",
                          "build_bridge_agent.py")
    bridge_src = os.path.join(root, "unit", "feature-0043-external-llm-bridge", "src")
    served = os.path.join(root, "unit", "feature-0003-agent-web-ui", "src", "static", "agent")
    if not os.path.isfile(script):
        return  # 빌드 스크립트가 없는 트리(부분 체크아웃 등) — 러너 테스트도 없다

    for out, extra in ((os.path.join(bridge_src, "bridge_agent.py"), []),
                       (os.path.join(served, "bridge_agent.py"),
                        ["--stage-assets", bridge_src])):
        r = subprocess.run(
            [sys.executable, script, "--src", os.path.join(bridge_src, "agent"),
             "--out", out, *extra],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                "브리지 러너 배포 산출물 빌드 실패 — 러너 계약 테스트가 검증할 실물이 없다.\n"
                f"  {r.stdout.strip()}\n  {r.stderr.strip()}")


_stage_bridge_runner()
