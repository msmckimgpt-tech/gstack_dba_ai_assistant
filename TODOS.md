# TODOS

이 파일은 gstack 워크플로우와의 인터페이스다. 특정 feature 에 귀속되는 작업 항목은 `unit/feature-NNNN/docs/TASK.md` 의 Task Queue 에서 관리하며, 본 파일은 **repo-level · cross-cutting · 운영 후속** 항목만 추적한다.

기록 규칙:
- 본문: 한 줄 요약 + **Why** / **Where** / **Next step** 세 보조 라인
- 상태: `[ ]` (미착수) / `[~]` (착수 중) / `[x]` (완료 — 최근 N개만 보존)
- 우선순위: `P1` (다음 세션에 반드시) / `P2` (가까운 일정) / `P3` (여력 될 때)
- feature 단위 작업은 여기에 쓰지 말고 해당 feature 의 `TASK.md` 에 기록한다

---

## Active

- [ ] **P3** 리미디에이션(TASK-0134 #15) alembic 마이그레이션 프레임워크 도입
  - **Why**: 스키마가 startup/handler 의 raw `CREATE TABLE IF NOT EXISTS`/`ALTER` 부작용으로 적용 — 버전드·가역 이력 없음, 라이브 ivfflat index 가 DDL 파일과 drift(lists=100 vs 32). GC 는 TASK-0134 로 처리됨(kv 고아 sweep + 세션 purge, `make gc`).
  - **Where**: app.py/agent_core 부트스트랩 DDL + `scripts/agent_kb_schema.sql`
  - **Next step**: alembic 도입(라이브 36GB 주의 — Task 5 백업 선행), 모든 DDL 을 versioned 마이그레이션으로, agent_kb_schema.sql 을 라이브에서 재생성 + drift 체크. 죽은 Agent* DDL 삭제.

- [ ] **P3** 리미디에이션(TASK-0133 #7) planner.py(2276줄) + phantom AGENT_* 플래그 정리
  - **Why**: planner.plan_next_step 은 죽은 agent_cli 만 호출했으나 `modules/__init__.py` 가 `from .planner import *` 로 import → 삭제 전 dead-export 분석 필요. phantom 플래그(소비처 0, 예: AGENT_ENABLE_QUERY_CONTRACT_GRADER) 도 정리 대상.
  - **Where**: `modules/planner.py`, `modules/__init__.py`(20,61), `modules/config.py` AGENT_* + `docs/CODEBASE_MAP.md`(agent_cli 'primary source' 표기 정정)
  - **Next step**: planner export 사용처 grep → 미사용 확인 후 import 제거 + 파일 삭제. config AGENT_* 를 live/dead/phantom 분류 후 phantom 삭제.

- [ ] **P2** 리미디에이션(TASK-0132 #8) os.environ 첨부 채널 → kwargs 전면 제거
  - **Why**: ATTACHMENT_IDS/NEW_ATTACHMENT_IDS/ATTACHMENT_IMAGE_INLINE_PATH/ATTACHMENT_TEXT_INLINE_PATH 가 프로세스 전역 os.environ 으로 web→agent 전달돼 동시요청 race. **교차테넌트 데이터 유출은 TASK-0132 의 AccountId 스코프로 이미 차단**됨 — 남은 위험은 본인 계정 내 attachment 혼선/유실(정확성 glitch).
  - **Where**: `app.py`(os.environ set ~7452/7569/7588) + `agent_core.py`(read ~195/209/632)
  - **Next step**: run_agent/_run_agent_core/compose_system_prompt 에 attachment_ids/new_attachment_ids/image_path/text_path 를 명시 kwarg 로 전달, os.environ set/read/pop 제거.

- [ ] **P2** 리미디에이션(#9) async 핸들러 동기 DB I/O + ask 커넥션 lifecycle 리팩터
  - **Why**: 48개 async 라우트가 이벤트 루프에서 동기 mysql.connector 호출 → 느린 쿼리 1건이 전체 in-flight 요청 stall. ask() 가 to_thread 에이전트 실행 내내 커넥션 점유. 커넥션 풀 없음(connect-per-request), pgbouncer 미사용.
  - **Where**: `app.py` 49개 async 핸들러 + ask() 6963~7432 + db.py
  - **Next step**: 핸들러를 def(Starlette threadpool) 또는 to_thread 래핑, mysql.connector.pooling 또는 pgbouncer 경유, ask() 커넥션을 에이전트 실행 전 반환. 단계적(핸들러별).

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
