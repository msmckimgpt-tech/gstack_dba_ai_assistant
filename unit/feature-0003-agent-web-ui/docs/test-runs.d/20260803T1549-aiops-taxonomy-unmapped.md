---
run_at: 2026-08-03T15:49:22+09:00
session: ai/claude/aiops-taxonomy-unmapped
scope: shared/model_catalog.py TASK_TAXONOMY — `AI 운영 현황 > 운영 현황` 미분류 활동 3종 재배치 (Minor §12.3)
verdict: PASS
---

# Run 2026-08-03 — PRE-LANDING (단위 + 라이브 데이터 대조)

## 1. 라이브 데이터 대조 (변경 전 — 재배치 대상 확정)

`agent_runtime.llm_usage` 전량 `GROUP BY task` (2026-08-03 15:4x KST):

| task | 호출 | first_seen | last_seen | 변경 전 카테고리 |
|---|---|---|---|---|
| `analysis_verify` | 1,258 | 2026-07-31 | 2026-08-03 | **ai.other.unmapped (미분류 활동)** |
| `cluster_summary` | 332 | 2026-07-30 | 2026-07-31 | **ai.other.unmapped (미분류 활동)** |
| `domain_summary` | 4 | 2026-07-31 | 2026-07-31 | **ai.other.unmapped (미분류 활동)** |
| (나머지 13종) | — | — | — | 등록됨 |

세 task 전부 `conversation_id='__insight_worker__'` 단일이고 `target` 은 각각 객체(`log_v2.tf_log_00_common`)·
데이터소스(`mssql-dk-dev`)·스키마(`atum2_db_1`) 축 → insight 분석 파이프라인 산출물로 확정.

## 2. 단위 테스트 — **PASS**

**Environment: pytest (agent 이미지, `make test` 격리 compose 프로젝트 `repo-unittest`)**

- `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py` — **22 passed** (기존 20 + 신규 2), 0.94s.
  - `test_taxonomy_insight_pipeline_tasks_mapped` (신규) — 3종이 `ai.insight.analyze` + 지정 라벨.
  - `test_every_recorded_task_literal_is_registered` (신규) — AST 전수 게이트.
  - `test_taxonomy_unmapped_self_surface` (기존) — 미등록 self-surface 계약 무회귀.
- 전체 스위트 `make test` — **EXIT=0** (feature-0002 + 0003 + 0023, 실패·에러 0), `ruff check` All checks passed.

## 3. AST 게이트 실측 + 역검증 (codex 적대 리뷰 8라운드 반영본)

- 수집: `shared/**` · `unit/*/src/**` 119 파일에서 task 리터럴 **19종**(직접 호출 + 래퍼 경유),
  `TASK_TAXONOMY` 미등록 **0**. 동적 호출부는 `f'metadata_{task}'` 1건이며 선언된 파생 규칙
  (`_metadata_llm_complete` → `metadata_summary`/`metadata_prompt_gen`)과 집합 동치.
- **taxonomy 변이 검증** — 등록 task 를 하나씩 제거하고 게이트 재실행:
  `metadata_summary` / `metadata_prompt_gen` / `cluster_summary` / `domain_summary` /
  `analysis_verify` / `redteam` / `agent` **전건 적발**, 선언 튜플 축소(`metadata_prompt_gen` 미선언)도 적발.
- **미확정 경로 변이 검증** — 합성 소스 트리로 fail-closed 실증:
  지역변수 task · `*args` 앞선 unpacking · `**kwargs` 전달 · 미등록 리터럴 · 파라미터 재대입 ·
  `def`/`class`/`import-as`/`except-as`/`match-as`/중첩 파라미터 shadowing · 기본값·데코레이터 호출 ·
  sink 별칭 할당/인자 전달 — **전 케이스 적발**, 순수 passthrough 대조군만 통과(오탐 0).
- vacuous pass 방지: 스캔 파일 하한 `>= 50`(실측 119) · 수집 task 하한 `>= 10`(실측 19) ·
  선언 목록 stale 검사 · 고정점 미수렴 시 실패.
- **잔여 한계**: `getattr` 문자열·`exec`·동적 import 등 AST 밖 경로는 원리상 정적 확정 불가 —
  게이트 계약은 "미확정 경로를 조용히 통과시키지 않는다"(docstring 명시).

## 4. Environment: Windows-browser (PB-0008) — POST-DEPLOY **PASS**

본 cycle 은 `shared/model_catalog.py` dict 데이터와 테스트만 바꾸고 정적 자산(`static/**`·HTML·
CSS·JS)·렌더 경로는 무변경이라 pre-commit 시점엔 화면 delta 가 없다(표시 내용은 배포된 web
이미지의 API 응답에서 나온다). 배포 후 실측한다.

### 배포

`sudo -E bin/deploy-web.sh --web-only` → **GIT_COMMIT=c0c6800f** (web-a·web-b 실측, soak 90s 통과,
Caddyfile 무변경으로 edge blip 0). `git merge-base --is-ancestor 7c562a0a c0c6800f` 로 본 cycle
커밋 포함 확인. 워커는 미접촉(`--web-only`) — taxonomy 는 web 의 관제 표시 전용이라 워커 소비 경로가
없다(`ai_ops.py`·`admin_usage.py` 만 참조).

### BEFORE / AFTER (배포본 컨테이너 실측)

| 시점 | `analysis_verify` | `cluster_summary` | `domain_summary` | 등록 수 |
|---|---|---|---|---|
| 배포 전 (구 이미지) | `ai.other.unmapped` / `analysis_verify` | `ai.other.unmapped` / `cluster_summary` | `ai.other.unmapped` / `domain_summary` | 18 |
| 배포 후 (c0c6800f, web-a·web-b 동일) | `ai.insight.analyze` / 분석문 사실성 검증 | `ai.insight.analyze` / 콘텐츠 그룹 요약 | `ai.insight.analyze` / 도메인 종합 요약 | 21 |

미등록 self-surface 계약 무회귀도 배포본에서 확인(`taxonomy_for('brand_new_x') → ai.other.unmapped`).

### 라이브 API 대조 (`admin_ai_ops(days=7)`, 배포본 web-a 내부 호출)

- `categories[]` 에 `ai.other.unmapped` **부재** — 인사이트 분석 하위로 편입
  (`analysis_verify` 1,591 · `cluster_summary` 333 · `domain_summary` 4).
- `attention[]` 에 "미분류 AI 활동" 배지 **부재**.

### Windows-browser 육안 (실 Chrome 150.0.7871.128 via `bin/win-browser.py` relay, https://localhost/admin)

`AI 운영 현황 > 운영 현황` 진입 후:

- ✅ **AI 활동 카테고리 표에 '미분류 활동' 그룹 소멸** — pane 전체 텍스트에서 "미분류" 출현 **0회**.
- ✅ 인사이트 분석(8,689 호출 · 31,328,202 토큰 · $86.01) 하위에 신규 3행 표시:
  `분석문 사실성 검증 (analysis_verify)` 1,594 · `콘텐츠 그룹 요약 (cluster_summary)` 333 ·
  `도메인 종합 요약 (domain_summary)` 4.
- ✅ **최근 활동 피드**도 raw task 문자열 대신 사람이 읽는 작업명으로 노출
  (예: "분석문 사실성 검증 masangsoftweb.Ace_Influence_Mother_Ship").
- ✅ 기존 카테고리(에이전트 추론·보조 추론·지식베이스 보강·프롬프트 자동생성) 라벨·수치 무회귀,
  상태 축 4종·KPI 타일·워커 자원 표 정상 렌더.
- 증거: `artifacts/pb0008/20260803-aiops-taxonomy-unmapped.png`
