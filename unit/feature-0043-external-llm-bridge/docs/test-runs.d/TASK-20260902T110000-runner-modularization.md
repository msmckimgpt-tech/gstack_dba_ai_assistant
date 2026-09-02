---
run_at: 2026-09-02T11:30:00+09:00
session: ai/claude/feature-0043-runner-modularization
scope: 러너 모듈 분할(18) + 배포본 이중화 제거 + 빌드/배포 게이트
verdict: PASS
---

# Run — TASK-20260902T110000 러너 모듈 분할

## Environment

- 컨테이너 `repo-unittest-agent:latest`, worktree 마운트(`/work`), Makefile `test` 와 같은 배선
  (`PYTHONPATH=/work/unit/feature-0002-agent-core/src:/work/unit/feature-0003-agent-web-ui/src:/work`,
  `DB_PORT=1`, `PYTHONDONTWRITEBYTECODE=1`)
- **Environment: Windows-browser — 미수행(사유)**: 본 cycle 의 `static/**` 변경은
  **배포 산출물 3개를 git 추적에서 뺀 것**뿐이다(내용 동일, 빌드가 같은 바이트를 만든다).
  HTML·CSS·JS **변경 0** — 브라우저가 렌더하는 표면이 하나도 바뀌지 않았다. 러너는 브라우저가
  실행하지 않는 다운로드 파일이다. 다만 배포 후 다운로드 경로 도달성은 §5 POST-DEPLOY 로 남긴다.

## 1. 회귀 — 전량 통과

| 범위 | 수집 | 결과 |
|---|---:|---|
| Makefile `test` 전 대상 9 디렉터리 | **6,956** | **rc=0 (전량 통과)** |
| 그중 feature-0043 (러너 계약) | 1,191 (40파일) | 전량 통과 |

러너 계약 테스트는 **배포 산출물**(`bridge_agent.py`)을 대상으로 그대로 유지된다 — 검증 대상이
바뀌지 않았으므로 분할로 인한 계약 회귀 0.

## 2. 산출물 동치 — diff 실측

번들 산출물 vs 종전 커밋본: **4,267행 중 57행 변경**. 전부 의도한 셋뿐이다.

| 부류 | 건수 |
|---|---:|
| `_RUNNER_INSTANCE`/`_PREV_RUNNER_INSTANCE` → `state` 접근자 호출 | 12 |
| `state` 블록 위치 이동 (모듈 수준 문장 아님 — 의미 무관) | 1 블록 |
| PEP8 빈 줄 | 2 |

## 3. 구조 — 분할 실측

| 항목 | 종전 | 현재 |
|---|---:|---:|
| 러너 소스 파일 수 | 1 | **18** (`__init__` 포함) |
| 최대 단일 파일 행수 | 4,238 | **784** (`caps.py`) |
| 커밋 대상 사본 (러너) | 2 (바이트 동일) | **0** (빌드 생성물) |
| 커밋 대상 사본 (설치 스크립트) | 2 × 2 | **0** |
| 모듈 순환 | — | **0** (비순환 DAG) |

## 4. 적대 검증 — 뮤테이션 8/8 KILL

상세·근거는 `REVIEW.md` `REV-20260902T113000-…`. 하네스 함정 2건(pytest 미설치로 전건 미실행 ·
최종 집계 줄 유실로 출력 매칭 무력)을 먼저 제거하고, 무결 rc=0 · 의도적 실패 rc=1 로 판별력을
실증한 뒤 실행했다.

| # | 주입 | 결과 |
|---|---|---|
| M1 | `_EMIT_ORDER` 에서 `caps` 누락 | **KILL** (conftest fail-loud) |
| M2 | 패키지 내부 import 이름 파손 | **KILL** |
| M3 | Dockerfile 빌드 RUN 제거 | **KILL** |
| M4 | 배포 게이트 호출 제거(정의만 잔존) | **KILL** |
| M5 | 모듈 순환 주입 | **KILL** |
| M6 | 번들 비결정성 주입 | **KILL** |
| M7 | `.gitignore` 에서 배포본 제거 | **KILL** |
| M8 | claim 페이로드에서 러너 인스턴스 제거 | **KILL** |

## 5. POST-DEPLOY (배포 후 확인 항목)

- [ ] `bridge_runner_verify` 게이트가 실제 배포에서 통과 (baked 이미지에 러너 + 설치 스크립트
      2종 존재 · `py_compile` OK)
- [ ] `GET /static/agent/bridge_agent.py` 200 + 내용이 소스 빌드와 일치
- [ ] 러너 다운로드 → 실행 → 하트비트 왕복 1회 (지문 `_self_build` 갱신 확인)
