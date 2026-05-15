---
doc_type: REVIEW
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260515-0004
- Date: 2026-05-15
- Decision: `mysql`, `web`, `browser`, `caddy`, `mcp` 에 `restart: unless-stopped` 를 적용하고, `agent` / `memory-init` 은 restart 대상에서 제외한다.
- Reason: 현재 `make status` 에서 `mcp` 만 실행 중이고 `mysql/web/browser/insight-worker` 가 모두 내려간 상태가 확인됐다. 또한 `insight_worker.log` 에 `2005 (HY000): Unknown MySQL server host 'mysql' (-2)` 오류가 반복되어, 워커 내부 예외가 아니라 compose 네트워크에서 `mysql` 서비스가 사라진 시간이 있었다. 기존 Compose 에서는 장기 실행 서비스 중 `insight-worker` 만 restart policy 를 가지고 있어 Docker daemon/WSL 재시작이나 일시적 프로세스 종료 뒤 나머지 서비스가 자동 복구되지 않는다. `unless-stopped` 는 사람이 명시적으로 멈춘 상태는 존중하면서 비의도 종료와 daemon 재시작 복구를 제공하므로 `make up` 의 기대 동작에 맞다.
- Risk: 명시적 장애 상황에서도 컨테이너가 재시작을 반복할 수 있다. 그러나 MySQL healthcheck 와 서비스 로그로 원인 확인이 가능하고, `make down` / `make stop` 은 명시 중지 의도를 유지한다. `memory-init` 에 restart 를 적용하면 초기화 작업이 반복될 수 있어 제외했다.

## REV-20260515-0003
- Date: 2026-05-15
- Decision: `browser-up` / `insight-up` 도 `web` 타깃과 동일하게 `dc-build` 가드 + `up --no-build` 패턴으로 전환한다.
- Reason: `make browser-up` 실행 중 compose/buildx provenance metadata file race 가 재현됐다. 이미지 빌드는 성공했지만 compose 후처리에서 임시 metadata 파일을 찾지 못해 exit 2로 종료했다. 이미 `Makefile`에는 이 환경 결함을 흡수하는 `dc-build` 가드가 있으므로 같은 원인을 같은 방식으로 처리하는 것이 맞다.
- Risk: `up -d --no-build` 는 직전 `dc-build` 성공을 전제로 한다. `dc-build`가 실제 빌드 오류와 metadata race를 구분하므로, 빌드 실패를 숨기지 않는다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: 운영 자산만 버전관리 대상으로 두고 데이터/로그는 외부 산출물로 분리
- Reason: 기능 단위 추적성과 런타임 안전성 확보
- Risk: 엄격한 운영 검증 시나리오가 아직 없다
