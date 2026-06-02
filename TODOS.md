# TODOS

이 파일은 gstack 워크플로우와의 인터페이스다. 특정 feature 에 귀속되는 작업 항목은 `unit/feature-NNNN/docs/TASK.md` 의 Task Queue 에서 관리하며, 본 파일은 **repo-level · cross-cutting · 운영 후속** 항목만 추적한다.

기록 규칙:
- 본문: 한 줄 요약 + **Why** / **Where** / **Next step** 세 보조 라인
- 상태: `[ ]` (미착수) / `[~]` (착수 중) / `[x]` (완료 — 최근 N개만 보존)
- 우선순위: `P1` (다음 세션에 반드시) / `P2` (가까운 일정) / `P3` (여력 될 때)
- feature 단위 작업은 여기에 쓰지 말고 해당 feature 의 `TASK.md` 에 기록한다

---

## Active

- [ ] **P2** 리미디에이션(TASK-0131 #10) app.py silent except 113건 점진 감사
  - **Why**: `except Exception: pass` 113건이 실패를 삼켜 가시성 저하(감사 #10). 핫패스(KB/KV/ask/healthz)는 Task 2~5 에서 로깅 추가됨. 나머지는 제어흐름 오인 위험이 있어 일괄 변경 대신 핸들러별 판단 필요.
  - **Where**: `unit/feature-0003-agent-web-ui/src/app.py` (`grep -A1 'except Exception:' | grep pass`)
  - **Next step**: 핸들러별로 (a) 진짜 fail-open(정당화 주석+로깅) vs (b) 제어흐름(유지) 분류 후 (a) 를 `logger.warning(exc_info=True)` + conversation_id/run_id 동반으로 전환. 모듈 레벨 `logger` 도입.

- [ ] **P2** 리미디에이션(TASK-0127 #11) CI 격리 8건 테스트 정비
  - **Why**: 리미디에이션 이전부터 깨진 8건을 CI 게이트 녹색화를 위해 `pyproject.toml` addopts `--deselect` 로 격리. 회귀 검출은 유지되나 격리 항목은 미검증 상태.
  - **Where**: `pyproject.toml` [tool.pytest.ini_options] addopts + `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py`(2: 라이브 PG fixture 의존) + `test_m5_cleanup.py`(6: `bin/kb-cleanup-mysql.sh` 셸 환경 의존, 격리 PATH 에서 returncode 2)
  - **Next step**: anchor 2건은 PG fixture(testcontainers 또는 세션 스코프 ephemeral PG) 도입, m5_cleanup 6건은 스크립트 실행 환경(PATH/필요 바이너리) 재현 또는 테스트를 환경 비의존으로 재작성. 복구 시 deselect 목록에서 제거.

- [ ] **P2** gstack 스킬 도입 후속: `/setup-deploy` 로 배포 파이프라인 구성 여부 결정
  - **Why**: 현재 배포는 `make web` + docker compose 로컬 재빌드 중심. 공식 deploy target 이 없어 `/ship` 이후 자동화가 비어있음.
  - **Where**: repo 루트 `Makefile` + `docker-compose.yml`
  - **Next step**: 운영 환경이 단일 docker host 라면 `/setup-deploy` 를 건너뛰고 `/ship` 이후 수동 `make web` 으로 충분. CI 성장 시 재평가.

- [ ] **P3** 원본 GitHub repo `msmckimgpt-tech/ai_desk_mysql.git` 처리 결정
  - **Why**: 2026-04-23 origin 을 `gstack_dba_ai_assistant.git` 으로 전환하면서 기존 repo 가 고아 상태. 혼란 방지를 위해 README 에 이전 안내를 추가하거나 archive 처리 필요.
  - **Where**: GitHub `msmckimgpt-tech/ai_desk_mysql`
  - **Next step**: 사용자가 GitHub UI 에서 직접 README 교체 또는 archive 전환. 본 repo 내 조치는 없음.

- [ ] **P3** CHANGELOG.md 생성 필요성 재검토
  - **Why**: gstack 의 `/ship` 스킬은 CHANGELOG 를 가정하지만 본 repo 는 `REPORT.md` + 커밋 메시지로 변경 이력을 추적. 이중 기록을 피하기 위해 도입 유보.
  - **Where**: repo 루트
  - **Next step**: 외부 배포 이벤트(tagged release 등) 가 필요해지는 시점에 도입 검토.

- [ ] **P3** docs/LEARNINGS.md 와 gstack `/learn` 의 분리 정책 확정
  - **Why**: 현재 `docs/LEARNINGS.md` 가 프로젝트 고유 학습 기록(LRN-YYYYMMDD-NNNN) 을 담당. gstack 글로벌 `~/.gstack/projects/<slug>/learnings.jsonl` 과 중복 가능성.
  - **Where**: `docs/LEARNINGS.md` + `~/.gstack/projects/*/learnings.jsonl`
  - **Next step**: 원칙은 "프로젝트 의사결정·설계 판단 = LEARNINGS.md, 스킬 운영 노하우 = gstack jsonl". 실제 충돌 사례가 생기면 갱신.

## Parking Lot (feature scope 항목 포인터)

feature 단위로 관리되는 미완료 작업은 다음 위치를 참조:
- `unit/feature-0001-platform-runtime/docs/TASK.md` — TASK-0004 (엄격한 운영 검증 시나리오)
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0034 (복잡 QA 성능 테스트, 진행 중)
- `unit/feature-0004-browser-automation/docs/TASK.md` — TASK-0004 (엄격한 브라우저 시나리오)
- `unit/feature-0005-qa-mcp/docs/TASK.md` — TASK-0004 (엄격한 QA 시나리오), TASK-0005 (MCP 기동 검증)
- `unit/feature-0006-lan-proxy-access/docs/TASK.md` — TASK-0004 (엄격한 네트워크 시나리오)

전체 진행률 / 의존성 / 블로킹은 `docs/STATUS.md` 참조.

## Recently Done (최근 N개)

- [x] 2026-04-23 origin 을 `gstack_dba_ai_assistant.git` 으로 전환 + `CLAUDE.md` 에 gstack skill routing 섹션 주입 + `TODOS.md` 신설
