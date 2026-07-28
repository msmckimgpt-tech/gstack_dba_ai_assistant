---
doc_type: TEST
feature_id: feature-0001-platform-runtime
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 설정 파일 경로가 새 feature 구조를 가리키는지 확인
- 런타임 산출물이 `../../../../artifacts`에 생성되는지 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`이 `src/mysql/conf.d`를 참조한다
- TEST-0002: `Makefile`이 `../../../../artifacts/mysql-data`와 `../../../../artifacts/mysql-backup`를 사용한다
- TEST-0003 (엄격한 운영 시나리오, 2026-07-28 확정): 라이브 스택이 **운영 불변식 3축**을
  동시에 만족한다 — ① 모든 장기 실행 서비스가 `restart` 정책을 보유하고 healthcheck 가 있는
  서비스는 전부 `healthy` ② 상태 산출물이 `artifacts/` 하위 정본 경로에 실재 ③ compose 가
  feature 구조(`unit/feature-*/src/...`)를 참조. 판정은 문서가 아니라 **가동 중인 스택 실측**
  (`docker inspect` 의 RestartPolicy/Health, 디스크 실재, compose 참조 grep)으로 한다.
- TEST-0004: `make browser-up` 이 compose/buildx metadata file race 환경에서도 browser 서비스를 기동한다
- TEST-0005: `make insight-up` 이 compose/buildx metadata file race 환경에서도 insight-worker 서비스를 기동한다
- TEST-0006: `make up` 후 장기 실행 서비스가 restart policy 를 가진 상태로 기동한다

## 3. Test Run History
- 2026-07-28 (TEST-0003 엄격한 운영 시나리오 — Environment: 라이브 스택 실측):
  - ① **서비스 14개 전수 PASS** — `repo-{ask-worker,insight-worker,caddy,web-a,web-b,
    bedrock-gateway,postgres,postgres-replica,pgbouncer,mysql,minio,embed-ollama,browser,mcp}-1`
    이 모두 restart 정책 보유(`unless-stopped` 13 / `on-failure` 1=insight-worker).
    healthcheck 정의 서비스는 **전부 `healthy`** (caddy·browser·mcp 는 healthcheck 미정의).
  - ② **artifacts 정본 경로 PASS** — `artifacts/mysql-data`(48G) · `artifacts/mysql-backup` 실재.
  - ③ **compose ↔ feature 구조 PASS** — `docker-compose.yml` 의 `unit/feature-*` 참조 9건,
    그중 mysql 설정은 `./unit/feature-0001-platform-runtime/src/mysql/conf.d/99-mysql-ai-server.cnf`
    로 본 feature 경로를 직접 가리킨다.
  - 판정: **PASS**. TEST-0003 을 placeholder 에서 실 시나리오로 확정하고 본 Run 으로 닫는다.

- 2026-05-15:
  - `make up`
    - 결과: 통과. `mysql`, `web`, `browser`, `insight-worker`, `mcp` 기동 확인.
  - `make status`
    - 결과: 통과. `mysql` healthy, `web`, `browser`, `insight-worker`, `mcp` 실행 상태.
  - `make browser-health`
    - 결과: 통과. `{"ok": true}` 반환.
- 2026-05-15:
  - `make browser-up`
    - 결과: 통과
  - `make insight-up`
    - 결과: 통과
  - `make status`
    - 결과: mysql/web/browser/insight-worker/mcp 실행 확인
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 운영 시나리오는 후속 작성 예정
