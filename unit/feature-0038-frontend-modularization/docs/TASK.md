---
doc_type: TASK
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
feature_status_date: 2026-08-03
feature_status_note: ITEM-P5b 잔여 — Cycle 1~3 배포 완료, Cycle 4(accounts/roles) 진행 — admin.js 10,466줄
---

# Task

## 1. Current Status
- State: in-progress (PLAN-APPROVED 2026-08-03 — Cycle 1~3 완료·배포, Cycle 4 진행 중)
- Owner: AI (claude-corp) / Human 승인 게이트
- Priority: high
- Last Updated: 2026-08-03
- 근거 로드맵: `docs/improvements/ssot-consolidation/ROADMAP.md` ITEM-P5b 잔여분
  (⚠ 2026-08-03 실측 갱신 — 백엔드 app.py 분할은 feature-0012 완결, **재착수 금지**.
  잔여 실체 = 프론트 3파일: admin.js 14,007줄 · app.js 13,165줄 · styles.css 9,328줄)

## 2. Implementation Plan

### 2.1 Plan

**목표**: `unit/feature-0003-agent-web-ui/src/static/` 의 모놀리스 3파일을
behavior-neutral 점진 추출로 모듈화한다. big-bang 금지 — 추출 단위(cycle)마다
`make test` PASS + 헤드리스 스위트 + PB-0008 브라우저 QA + 롤백 리허설 + 별도 PR/배포.
근거는 "충돌 회피"가 아니라 **파일 크기로 인한 AI 로드·편집 정확도 저하**(로드맵 §3b —
app.js 충돌 최근 60일 0건 실측).

**패턴 선례** (전부 본 repo 에서 검증된 것만 사용):
- ES module 분할: admin.js ↔ `graph/*.js` 8모듈 (ITEM-09, `type="module"` + 순환 import + `?v=dev` specifier)
- CSS 물리 분할: 구 styles.css L8246~8682 → `graph/graph.css` (ITEM-09 batch2)
- byte-동치 이동: feature-0012 (app.py 148 route → 21 APIRouter, 본문 무수정·배선만)
- 캐시 무결성: `inject_asset_stamp.py` 가 html/first-party js 의 `?v=` 전 토큰을
  빌드 시 content-hash 로 재작성 (신규 파일 자동 커버) + `.asset-stamp` 사이드카(feature-0014)

**영향받는 파일 (구체 경로)**:
- `unit/feature-0003-agent-web-ui/src/static/styles.css` → `css/` 7분할 (Cycle 1)
- `unit/feature-0003-agent-web-ui/src/static/admin.js` → `admin/` 도메인 모듈 (Cycle 2~6)
- `unit/feature-0003-agent-web-ui/src/static/app.js` → module 전환 + `app/` 도메인 모듈 (Cycle 7~10)
- `unit/feature-0003-agent-web-ui/src/static/{index,admin}.html` (link/script 태그)
- 소스-추출형 테스트: admin.js 참조 21파일 · app.js 참조 13파일 · styles.css 참조 6파일
  (`unit/feature-0003-agent-web-ui/tests/**` — 이동 함수의 추출 경로 갱신)
- `docs/CONVENTIONS.md` (code-modularity 컨벤션, Final cycle)
- `docs/improvements/ssot-consolidation/ROADMAP.md` ITEM-P5b status (Final cycle)

**Cycle 시퀀스** (각 cycle = 독립 worktree + 단일 PR + 배포; 위험 낮은 것부터):

| Cycle | 대상 | 산출물 | 핵심 symbol/경계 |
|---|---|---|---|
| 1 | styles.css 순차 분할 | `css/base.css`(L1–357: tokens·AUTH·FORM·BUTTONS) · `css/shell.css`(L358–942: APP SHELL·SIDEBAR) · `css/chat.css`(L943–3415: CHAT PANE·provider notice·첨부/실행 패널) · `css/drawers.css`(L3416–3700: SETTINGS DRAWER·TOAST) · `css/admin.css`(L3701–6060: ADMIN PAGE) · `css/profile.css`(L6061–7235: PROFILE·RESPONSIVE) · `css/search-audit.css`(L7236–9328: Spotlight·Audit·메타데이터 콘솔) | 원본 순서 보존 — **7파일 순차 concat == 원본 byte-identical** 기계 검증. index/admin.html 에 동일 순서 `<link ?v=dev>` 7개, styles.css 소멸. url()/@import 0건 실측이라 경로 안전 |
| 2 | admin.js leaf 도메인 ① | `admin/usage.js`(LLM 사용량·사용 기록 드릴다운) · `admin/aiops.js`(AI 운영 현황) | 독립 pane 렌더러 — adminState/apiFetch/showToast/can 은 admin.js 기존 export 재사용 |
| 3 | admin.js leaf 도메인 ② | `admin/audit.js`(감사 pane) · `admin/settings.js`(런타임 설정·성능 knob) | 〃 |
| 4 | admin.js 계정/역할 | `admin/accounts.js` · `admin/roles.js` (권한 grid: `renderPermissionGrid`·`PERMISSION_DEPENDENCIES`·`_orderItemsAsTree`·`ADMIN_PERMISSION_SECTIONS`) | CONVENTIONS §10.6/§10.7 계약 불변 — pending/apply 엔진은 본체 잔류 |
| 5 | admin.js 제품/DS | `admin/products.js` · `admin/datasources.js` | 〃 |
| 6 | admin.js 최대 덩어리 | `admin/metadata.js`(지식베이스 콘솔: 용어/ENUM/테이블/컬럼/검토큐/채택인박스/샘플검수) | `_meta*` 계열 — graph/ 와의 기존 import 계약 유지 |
| 7 | app.js module 전환 (B0) | index.html `<script type="module" src="app.js">` — **전환만, 분할 없음** (회귀 원인 격리) | inline handler 0·동반 classic 은 window.* 결합만·body 말미 로드 실측 완료. 실패 시 fallback: classic 순차 분할(전역 lexical 공유) |
| 8 | app.js 도메인 ① | `app/auth.js`(로그인·세션) · `app/profile.js`(프로필 drawer·설정) | module 패턴 (Cycle 7 이후) |
| 9 | app.js 도메인 ② | `app/sidebar.js`(대화목록·폴더·검색) · `app/composer.js`(입력·첨부·전송) | |
| 10 | app.js 도메인 ③ | `app/messages.js`(말풍선·markdown·SQL 결과·diff) · `app/progress.js`(run 추적·폴러·재연결·타임아웃 연장 배너) | progress 계열은 최근 회귀 다발 영역·테스트 결합 최다 — 마지막 |
| Final | 재발 방지·정합 | CONVENTIONS code-modularity(임계: 단일 프론트 파일 3,000줄 초과 신규 기여는 모듈로, 5,000줄 초과 파일 증설 PR 은 추출 계획 동반) · ROADMAP ITEM-P5b status·STATUS.md·CODEBASE_MAP | |

목표 잔존: admin.js ≤ ~3,000줄(오케스트레이터: tab 라우팅·adminState·pending/apply·공용 유틸),
app.js ≤ ~3,000줄(부트스트랩·공용 상태). 도메인 경계는 각 cycle 착수 시 심볼 단위로
재실측해 §3 Task Queue 에 고정한다(이 표의 라인/심볼은 2026-08-03 실측 기준).

**접근 방법 (원칙)**:
1. byte-동치 이동 — 함수 본문 무수정, import/export 배선만 추가 (feature-0012 방식).
2. 모든 ES import specifier 는 `?v=dev` 명시 (이중 인스턴스화 차단 — inject_asset_stamp 계약).
3. 추출로 깨지는 소스-추출형 테스트는 같은 cycle 에서 경로 갱신 (FAIL = 감지 신호, 무음 통과 금지).
4. `graph/` 서브트리는 본 작업 범위 밖 (활성 병렬 세션 feature-0016 계열과의 충돌 회피).
5. 각 cycle 은 단일 PR·비혼합 커밋 — `git revert <merge-commit>` 1회로 롤백 가능해야 함.

**게이트 (각 cycle, 로드맵 ITEM-P5b 명시 그대로)**:
1. `make test` PASS (격리 compose 프로젝트 `repo-unittest`)
2. 헤드리스 스위트 PASS (node vm 소스-추출 + chromium 실렌더) + **acorn-globals 자유 식별자 스캔 0** (JS 분할 cycle — §18.8 패널 권고 2026-08-03 채택)
3. `bin/verify-completion.sh --pre-commit` PASS (check #9 REVIEW entry · check #13 Windows-browser Run staged — `visual_verification_scope: always`)
4. PR 머지 → 배포 (deploy_scope: included — deploy-web.sh 스파인: asset-stamp verify·soak·자동 롤백)
5. POST-DEPLOY PB-0008 실 Windows 브라우저 검증 (JS 는 docker cp 사전검증 불가 — 모듈 캐시 이중 인스턴스 함정)
6. 롤백 리허설 — Cycle 1 에서 실제 revert→재빌드→스모크 실증, 이후 cycle 은 단일-PR revert 가능성 확인

**완료 판정 기준 (acceptance criteria)**:
- AC-1 (Cycle 1): 분할 7파일 순차 concat 이 원본 styles.css 와 byte-identical + 헤드리스 getComputedStyle 대비 무변화 + PB-0008 라이브(작업화면·관리콘솔 렌더 정상)
- AC-2 (Cycle 2~6): 각 추출 후 admin.js 라인 감소 실측 + 이동 도메인 pane 의 라이브 동작(렌더+인터랙션) PB-0008 확인 + 회귀 0
- AC-3 (Cycle 7): module 전환 후 로그인→대화→요청→진행표시→관리 진입 풀 스모크 PASS
- AC-4 (Cycle 8~10): 각 추출 후 app.js 라인 감소 실측 + 해당 도메인 라이브 동작 확인 + 회귀 0
- AC-5 (Final): CONVENTIONS code-modularity 등재 + ROADMAP ITEM-P5b 갱신
- AC-공통: 전 cycle 에서 make test FAILED 0 · 헤드리스 PASS · verify-completion PASS

**위험도**: **Critical** (로드맵 ITEM-P5b 명시 — 라이브 web app 런타임 회귀 위험.
§12.3 표의 인증/인가·데이터 파괴 축은 아니나 로드맵·사용자 지정 등급을 따름)
→ §7.1: 본 계획 사람 승인(PLAN-APPROVED) 후 Execute. REPORT.md 교차 기록 완료.

**위험 요소와 완화**:
- 소스-추출형 테스트 결합(21+13+6 파일) → cycle 내 동반 갱신, 게이트 2가 강제 감지
- ES module 이중 인스턴스화 → `?v=dev` specifier 규약 + asset-stamp 전파(전 참조 동일 스탬프)
- 병렬 세션 충돌 → REGISTRY hot_paths 선언 완료(3파일+html), cycle 착수마다 활성 worktree 의 3파일 접촉 재실측(2026-08-03 실측: committed/dirty 전부 0)
- app.js module 전환 타이밍 변화 → Cycle 7 단독 격리 + classic 순차 분할 fallback
- 롤링 배포 창 구버전 캐시 → feature-0014 asset-stamp cache-integrity 로 기해소(07-28)

<!-- PLAN-APPROVED by mckim on 2026-08-03 (AskUserQuestion "전체 승인" — 세션 기록) -->

## 3. Task Queue
- [ ] TASK-0012 Cycle 4 — verify → PR → 배포 → POST-DEPLOY PB-0008 (accounts/roles pane·권한 grid 보안 표면)
- [ ] TASK-0013 Cycle 5 착수 (admin/products.js·admin/datasources.js) — 이하 §2.1 표 순서
- [ ] TASK-0100 Final — CONVENTIONS code-modularity + ROADMAP/STATUS 정합

## 4. In Progress
- TASK-0012 (Cycle 4 마감 절차 — make test·적대 패널 진행 중)

## 5. Blocked
- 없음
<!-- 승인 대기 항목은 아래 형식으로 기록한다:
- TASK-XXXX: BLOCKED: awaiting-human-approval — 사유 설명
-->

## 6. Done
- [x] TASK-0001 plan-review 승인 — PLAN-APPROVED by mckim 2026-08-03
- [x] TASK-0002 기준선 실측 — styles.css 9,328줄 sha256 349ce797…·url()/@import 0건 (TEST Run-001)
- [x] TASK-0003 styles.css 7분할 + html 링크 교체 + 참조 테스트 5건 갱신 (CHG-20260803T1745)
- [x] TASK-0004 byte-parity cmp identical + per-file 주석/중괄호 균형 + 헤드리스 27+11 PASS + make test EXIT 0 + PB-0008 사전 시각검증 PASS (TEST Run-002~005)
- [x] TASK-0005 Cycle 1 롤백 리허설 실증 — revert 왕복 base diff 0 (TEST Run-006)
- [x] TASK-0006 Cycle 1 마감 — PR #1124 머지(1da17988)·deploy-web RC=0(soak 통과)·POST-DEPLOY PB-0008 PASS(TEST Run-007)·worktree/REGISTRY 정리
- [x] TASK-0007 Cycle 2 추출 — admin/usage.js(699)·admin/aiops.js(287), 역재구성 byte-parity IDENTICAL (TEST Run-008, CHG-20260803T190000·T193000 패널 흡수)
- [x] TASK-0008 Cycle 2 마감 — PR #1125 머지(3748c4fd)·배포 RC=0·POST-DEPLOY PB-0008 PASS(운영현황 85KB 렌더·에러 0, TEST Run-011)
- [x] TASK-0009 Cycle 3 추출 — admin/settings.js(881)·admin/audit.js(388), admin.js 11,827줄, parity IDENTICAL·free-vars 0/0 (TEST Run-012, CHG-20260803T203000)
- [x] TASK-0010 Cycle 3 마감 — 패널 SHIP(REV-20260804T090000)·PR #1128 머지(86c0d7c3)·배포 RC=0·POST-DEPLOY PB-0008 PASS(설정 5패널 실렌더·감사 100행·re-export 축, TEST Run-014)
- [x] TASK-0011 Cycle 4 추출 — admin/accounts.js(785)·admin/roles.js(609), admin.js 10,466줄, parity IDENTICAL·free-vars 6모듈 0 (TEST Run-015, CHG-20260804T100000)

## 7. Next Action
- Cycle 4 verify → PR → 배포 → POST-DEPLOY PB-0008 → Cycle 5

## 8. Completion Checklist
- [ ] 모든 REQ의 AC가 구현되었다
- [ ] 단위 테스트(unit test)가 통과한다 (AGENTS.md §8.2 단계 1)
- [ ] 전체/통합 테스트(integration test)가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다 (AGENTS.md §8.2 단계 2)
- [ ] 웹/UI 변경 시 실제 Windows 브라우저 검증을 수행하고 TEST.md §3 또는 test-runs.d/ fragment 에 `Environment: Windows-browser` Run 을 기록했다 (§15.4.1 · PB-0008)
- [ ] FUNCTION.md가 현재 동작과 일치한다
- [ ] MODIFY.md에 변경 이력이 기록되었다
- [ ] REVIEW.md에 판단 근거가 기록되었다
- [ ] REPORT.md에 최종 상태가 반영되었다
- [ ] TEST.md에 테스트 결과가 기록되었다
- [ ] BLOCKED 항목이 없거나 사람에게 전달되었다
- [ ] STATUS.md에 기능 상태가 갱신되었다
- [ ] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 시)
- [ ] Git 커밋이 완료되었다
- [ ] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다
- [ ] 요청 범위 자기-열거 완결성 게이트를 통과했다 (§9 + AGENTS.md §16.7)

## 9. Requested Scope (요청 범위 자기-열거)

완료 선언 **직전**에 채운다. 원 요청에서 요구된 항목·범위를 **항목당 1행**으로 열거하고,
각 행에 산출물·배선 확인 결과를 적는다 (AGENTS.md §16.7 G1~G3).

- [x] `ITEM-P5b 잔여 — styles.css 분할 (Cycle 1)` — 산출물: `static/css/{base,shell,chat,drawers,admin,profile,search-audit}.css` + index/admin.html 7-link 배선 · 배선 확인: concat cmp byte-identical + PB-0008 실브라우저 7 sheets 로드·렌더 정상 (TEST Run-002/005)
- [ ] `ITEM-P5b 잔여 — admin.js 모듈 분할` — Cycle 2~6 (이월, §2.1 표)
- [ ] `ITEM-P5b 잔여 — app.js 모듈 분할` — Cycle 7~10 (이월, §2.1 표)
- [x] `게이트 준수 (plan-review·make test·브라우저 QA·롤백 리허설)` — 산출물: PLAN-APPROVED 마커(TASK §2.1) + TEST Run-004(make test EXIT 0) + Run-005(PB-0008) + 롤백 리허설(Run-006 예정) · 배선 확인: verify-completion --pre-commit
- [ ] `CONVENTIONS code-modularity 재발 방지` — Final cycle (이월)

**주장 affordance 실측 (G3)**: 해당 없음 (behavior-neutral 분할 — 신규 사용자 기능 주장 없음)

**경계변수 양측 검증 (G4)**: CSS 분할 절단선 7곳 — 절단선 양측이 각각 유효한 파일이 되는지
파일별 주석/중괄호 균형 스캔으로 전건 검증 (TEST Run-002; 원본 기존재 결함 1건은 동일 파일 내 보존)
