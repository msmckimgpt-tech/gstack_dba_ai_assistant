---
doc_type: REPORT
feature_id: feature-0001-platform-runtime
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
**2026-05-15 TASK-0058 완료 — browser-up / insight-up buildx metadata race 대응** (CHG-20260515-0003, REQ-20260515-0003, Minor §12.3). `make browser-up` 실행 중 `make web`에서 이미 확인했던 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 가 재현됐다. 이미지 빌드는 성공했지만 `open /tmp/.tmp-compose-build-metadataFile-... no such file or directory` 후처리 오류로 target 이 실패했다. 기존 `dc-build SERVICE=...` 가드 패턴을 `browser-up` / `insight-up` 에도 적용해 빌드는 가드에서 수행하고 서비스 기동은 `up -d --no-build` 로 분리했다.

**2026-05-12 TASK-0057 완료 — dev 환경 가동 시 single TLS termination 원칙 회복** (CHG-20260512-0002, REQ-20260512-0003, Minor §12.3). 사용자 follow-up: TASK-0055 QA 진행 중 web 컨테이너의 self-signed HTTPS 가 gstack browse 데몬을 차단해 정적 검증 fallback 이 필요했던 issue 의 root cause 해결. 진단: 운영 구조에서 Caddy (외부 80/443) 가 TLS 종단을 담당하는데 web 컨테이너도 `ENABLE_WEB_TLS=1` (`.env` 기본) 로 self-HTTPS 가동 → 이중 TLS → host `localhost:18080` 직접 접근 (Caddy 우회) 시 browser 자동화 차단. 해결: `docker-compose.override.yml.example` template 신설 (web entrypoint 를 plain HTTP `uvicorn web.app:app --host 0.0.0.0 --port 8000` 으로 override) + `.gitignore` 에 `docker-compose.override.yml` 추가 (환경별 file) + `CONTRIBUTING.md §10` "Dev 환경 가동 — single TLS termination 원칙" 섹션 신설. 개발자는 `cp docker-compose.override.yml.example docker-compose.override.yml && make web` 1회 setup 으로 host `localhost:18080` plain HTTP 가동, gstack `/qa` / `/browse` / playwright 가 env var · opt-in 옵션 추가 없이 자연 동작. production 영향 0 (override 는 dev 한정). gstack-upgrade 마다 별도 patch 적용 불필요. 검증: `curl http://localhost:18080/admin` HTTP 200 + admin.html cache-bust `v=20260512-perm-sections` 정상 반영 + uvicorn 로그 `Uvicorn running on http://0.0.0.0:8000` + browse `goto http://localhost:18080/admin` env var 없이 200 OK 응답.

운영 자산을 기능 단위 구조로 이관했고, 런타임 산출물은 `../../../../artifacts`로 분리했다.

## 2. Progress
- Planned: 0
- In Progress: 엄격한 검증 시나리오 정의
- Done: 설정 파일/SQL 유틸리티 이관, 루트 경로 반영, 내장 Local LLM bootstrap 제거

## 3. Recent Changes
- 2026-05-15: `Makefile` 의 `browser-up` / `insight-up` 을 `dc-build SERVICE=...` + `up -d --no-build` 로 전환.
- MySQL/DAB 설정을 feature 경로로 이동
- SQL 유틸리티를 버전관리 대상 자산으로 정리
- 2026-04-15: 현재 repo가 소유하던 `src/local-llm/init_ollama_models.sh`를 제거해 MySQL runtime 경계를 복구
- 총 변경 횟수: 2

## 4. Open Issues
- 운영 검증 기준이 아직 구조/기동 수준에 머물러 있다.

## 5. Test Status
- 2026-05-15:
  - `make browser-up`: compose/buildx metadata race 가드 적용 후 기동 확인
  - `make insight-up`: compose/buildx metadata race 가드 적용 후 기동 확인
  - `make status`: mysql/web/browser/insight-worker/mcp 실행 확인
- 자동 테스트: 미구성
- 수동 테스트: 루트 기동 검증 예정
- 미검증 항목: 엄격한 운영 시나리오

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 추후 운영 검증 시나리오 기준 확정
