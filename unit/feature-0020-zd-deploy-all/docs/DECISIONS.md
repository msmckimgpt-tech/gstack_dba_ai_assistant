---
doc_type: FEATURE_DECISIONS
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-20260714T104500-gateway-surge-deploy
- Status: accepted
- Context: bedrock-gateway(litellm)는 LLM 단일 관문(SPOF)인데 단일 replica 라 재배포(이미지/
  설정 변경) 창에 대화 요청이 실패한다. 상시 2-replica 는 호스트 메모리 압박(라이브 mem_limit
  하향 튜닝 중 + gateway OOM 이력 2g)으로 별도 예산 결정이 필요.
- Decision: **배포 창 한정 surge replica** — profile `deploy-surge` 뒤의 동일 구성 서비스가
  DNS alias `bedrock-gateway` 로 합류(양 네트워크) → 본체 recreate 동안 신규 요청 흡수(클라이언트
  OpenAI SDK 기본 connect-retry 가 전환 blip 흡수), in-flight 는 stop_grace 120s uvicorn drain.
  드리프트 판정 3종(state 기록 config sha ≠ 현행 / bind inode-stale / 이미지 ID)일 때만 발동 —
  평시 및 무드리프트 배포는 gateway 무접촉(blip 0), steady-state 리소스 증가 0.
- Alternatives: 상시 2-replica(메모리 예산 — 보류, surge 구조가 밑돌)·compose scale(개별
  one-at-a-time 제어 불가)·앱단 재시도 강화만(기동 30~60s 창 미커버).
- Consequences: surge 실패 시 본체 무접촉 ABORT(무중단 보존). 본체 recreate 실패 시 surge 가
  임시 서빙 유지(restart:no — 호스트 재부팅 시 소멸하므로 방치 금지, 스크립트가 경고).

## ADR-20260714T104501-worker-pin-single-image
- Status: accepted
- Context: insight/ask/agent/memory-init 은 동일 Dockerfile 인데 compose 가 서비스별 태그
  (`repo-*`)로 각각 빌드 — 워커 배포가 무핀·무롤백이었다.
- Decision: 워커 2종(insight/ask)을 공용 `mysql-ai-agent:<sha>` 로 build-once 핀(pin overlay
  확장, web 과 동형 last-good/current 태그 회전·keep-N prune). `agent`(ephemeral compose run)·
  `memory-init`(one-shot)은 핀 제외 — 배포 개념 없음. alembic 직접 호출은 별도 가드(선행 재빌드).
- Consequences: 워커 롤백 즉시성 확보. `make insight-up` 등 수동 경로는 여전히 `repo-*` 무핀
  빌드(기능 유지 — 다음 스파인 배포가 핀으로 재수렴).
