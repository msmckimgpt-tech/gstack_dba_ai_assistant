---
doc_type: DQA_ROADMAP
initiative: ssot-consolidation
created_at: 2026-06-23
source_research: ./RESEARCH.md
status: active
schema_version: 1
source_of_truth: false
---

# 개발 로드맵 — SSOT 통합 (Single Source of Truth)

> 적대 리뷰(42 에이전트, 확정 16/기각 19, blocker 1) 반영 v2. **다른 세션이 0 맥락으로 읽고 착수 가능**해야 한다.
> 진단 증거: [RESEARCH.md](./RESEARCH.md). SSOT 계약 정본: [../../DECISIONS.md](../../DECISIONS.md) ADR-0031 + [../../DOC_REGISTRY.md](../../DOC_REGISTRY.md).

> **⚠ 2026-08-03 실측 재검증 — P5a/P5b 의 근거 수치가 낡았다.**
> `app.py` 25,823줄→**3,883줄**, `from modules.*` 148→**2**, `@app` 라우트 **0**
> (`feature-0012-web-router-modularization` 이 21개 APIRouter 로 전량 추출 완결).
> **백엔드 모놀리스 분할은 완료 — 재착수 대상이 아니다.** 남은 실체는 프론트 3파일이고 오히려 커졌다
> (admin.js +59% / app.js +51% / styles.css +23%). 각 항목의 '실측 갱신' 표와, 신선한 세션용
> 진입 프롬프트는 **§3b** 참조.

## 0. 맥락 (context-free 진입)
프로젝트가 거버넌스(메타)·제품 두 레이어로 14개월 누적되며 정본이 다중화·비대화·stale 화되어,
AI 세션이 "무엇이 진실인지" 판정에 실패 → 작업 미정립. 목표 = 모든 사실이 정확히 한 곳의 정본을 갖는 구조.
- 대상 제품: `mysql_ai` (AI assistant). 정본 진입: repo/AGENTS.md · docs/PROJECT.md · docs/ARCHITECTURE.md
- 측정 기반: `bin/ssot-lint.sh` (Phase 0 신설), `bin/verify-completion.sh` check #9

## SSOT 계약 4조 (ADR-0031 정본)
1. 한 도메인 = 한 정본. `source_of_truth: true` 는 도메인당 정확히 1개.
2. 참조는 복제 금지 — `mirrors:`/`sources:` 로 정본 경로 선언.
3. archived 는 `docs/archive/` 로 격리(루트 오염 금지).
4. drift 는 lint 가 강제(도메인당 SOT 1개 / 참조의 source 선언 / archived 위치 / tracked secret 0).

## 1. 종속성 그래프
```
P0(계약·lint·registry) ──requires──▶ P1(문서정본) ──▶ P2(worktree 흡수) ──▶ P4(wiki 참조-only)
P0 ──▶ P3(secret/clutter, CRITICAL) [rotation 선행=사용자]
P1 ──▶ P5a(코드 파편화: 중복·경계) ──▶ P5b(코드 비대화 분할, Critical) [import 실측 선행]
```
- P3 는 P0(글롭 가드·registry) 후 가능하나 rotation(사용자/외부) 완료 전 secret 단계 진행 금지.
- P4 는 P1(docs 정본 확정) 의존(mirror 출처 고정 후 동기화 의미 성립).
- P5 는 P1(정본 지도) 의존 + import 의존성 그래프 실측 선행.

## 2. Phase 시퀀스
| Phase | 포함 | risk | 진입 조건 | worktree |
|---|---|---|---|---|
| P0 | 계약 ADR·DOC_REGISTRY·ssot-lint 골격·ROADMAP 정식화 | low | (없음) | ai/claude/META-0003-ssot-consolidation |
| P1 | 아카이빙·포인터화·STATUS 인덱스화·frontmatter | medium | P0 | 〃 |
| P2 | 활성 worktree 정본 흡수·in-flight TASK | medium | P1 | 〃 |
| P3 | secret 노출 종료·clutter | **critical** | P0 + **rotation(사용자)** | ai/claude/META-0004-secret-cleanup (별도 PR) |
| P4 | wiki 참조-only·자동 동기화 | medium | P1 | 〃 ssot-consolidation |
| P5a | 코드 파편화(SSOT 중복·경계: shared·0009·reconciliation·Dockerfile) | major | P1 + import 실측 | 단위별 독립 PR |
| P5b | 코드 비대화(모놀리스 분할: app.py 25.8K·프론트) | **critical** | P5a | 별도 cycle/initiative |

> P0·P1·P2·P4 는 본 worktree 공유(순차 commit). P3·P5 단위는 격리 PR(롤백 단위 분리, §13.2.7).

## 3. 항목 (각 1 cycle)

### ITEM-P0 · SSOT 계약 고정 + META cycle 등록 + lint 골격
- **status**: in-progress
- **feature_id**: META-0003-ssot-consolidation
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **why**: 정본이 기계적으로 결정되려면 계약(ADR)·기계가독 지도(DOC_REGISTRY)·강제(lint)가 선행돼야 함.
- **작업**:
  - ADR-0031(SSOT 계약 4조 + 도메인 정본 지도) → docs/DECISIONS.md
  - docs/DOC_REGISTRY.md 신설(domain→canonical→mirrors→lifecycle)
  - bin/ssot-lint.sh 골격(WARN-only) + `--selftest`
  - 본 RESEARCH/ROADMAP 정식화
  - META 층위(§18.4) 명시 — Meta-Cycle trailer/path-fallback 으로 cycle 경계 등록
- **gate**: `bash bin/ssot-lint.sh --selftest` 통과(오탐 0) + verify-completion check #9(REVIEW.md entry) + 신규 문서만(비파괴)

### ITEM-P1 · 문서 정본 정리
- **status**: done (1a 아카이빙 cc5ce41 · 1b STATUS 인덱스화 3f35e46 · 1c 거버넌스 포인터 검증=이미 clean[CONVENTIONS§7·GEMINI·CLAUDE 포인터, AGENTS ADR=참조]+CLAUDE/GEMINI reference frontmatter. 전 문서 frontmatter 백필은 점진)
- **feature_id**: META-0003-ssot-consolidation
- **risk_grade**: Major   <!-- STATUS 정본 재정의 → plan-review -->
- **depends_on**: [ITEM-P0]
- **작업**: GOAL/OBSERVATIONS → docs/archive/; STATUS 인덱스화(상태+최근 TASK 3링크); CONVENTIONS §3.1·§7→포인터, AGENTS §18 ADR본문→DECISIONS 링크, CLAUDE/GEMINI/CONTRIBUTING/README 포인터화; WIKI.md vs wiki/README.md 정본 1개; cross-cut(0009) 정본 보정 + TASK/REPORT §1 stale 라인 정합; frontmatter(mirrors/sources/lifecycle) 백필.
- **gate**: ssot-lint(도메인당 SOT 1) + 링크 무결성 + STATUS<30KB + check #9 + in-flight TASK 'active' 링크 정확

### ITEM-P2 · 활성 worktree 정본 흡수 + in-flight TASK 마이그레이션
- **status**: done (정책 명문화 — DOC_REGISTRY "In-flight worktree 현황 흡수". 현 충돌 위험 0: 현행 worktree ahead=0, stale leftover 는 정리 대상)
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **작업**: 활성 worktree(attach-cutover/conn-health/feature-0002/feature-0010/task0234) 미머지 TASK 를 STATUS 인덱스가 'active' 링크로 표기; STATUS 재작성 vs doc-sync rollup 동시편집 충돌 방지(동결창/머지순서); 흡수 마이그레이션 가이드.
- **gate**: 머지 시 ssot-lint 통과 + in-flight TASK 미단절 + 동시편집 충돌 0

### ITEM-P3 · secret 노출 종료 + 운영 잔재 (CRITICAL)
- **status**: blocked (rotation=사용자/외부 작업 + §12 사람 승인 대기)
- **feature_id**: META-0004-secret-cleanup
- **risk_grade**: Critical
- **depends_on**: [ITEM-P0]
- **작업**:
  1. **rotation 1순위 무조건**: 노출 자격증명(KEK/DB/admin/LLM/oauth/minio) 전수 식별 → rotation → 옛 키 폐기 → 로그 모니터링. (사용자/외부)
  2. ai/claude/META-0004-secret-cleanup worktree + PR(§13.2.7) + §12 사람 최종 승인 + Critical 이중 승인.
  3. .gitignore 글롭(.env*.bak*, *.bak-task*) + pre-commit/ssot-lint 'tracked .env*.bak* 0건' 가드.
  4. history rewrite(filter-repo)는 원격 브랜치+worktree+머지PR 영향 runbook 동반 별도 작업(게이트 아님). rotation 이 1차 방어선.
  5. 비파괴 clutter: legacy worktrees/ 삭제, pb0008 1곳 통합, .template-backups prune.
- **gate**: rotation 폐기증빙 + `git ls-files | grep -iE '\.env\..*(bak|secret)|\.bak-task'` → 0건 + `git log --all` 스캔 + GitHub Push Protection + check #9 + §12 승인 기록
- **rm-only 금지** — 이미 push 된 노출은 rm 으로 제거 불가.

### ITEM-P4 · wiki 참조-only 체계화
- **status**: done (핵심 — wiki/README §5.1 에 SSOT 계약 연결 + 동기화 메커니즘 명시. sot:false 이미 양호[lint 확인, Log.md 만 예외]. 85파일 mirrors frontmatter 백필·stale 카드 라벨은 /_dqa:doc_sync 점진 위임)
- **feature_id**: META-0003-ssot-consolidation
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **작업**: wiki 전역 sot:false 일관성 검증(`ssot-lint --check wiki-sot` — 현재 Log.md 1건만 sot:true, 정당; 리뷰의 ADR-0005/Module-Map '거짓 SOT' 는 실제 sot:false 로 오판이었음); 신규 카드 mirrors/sources 백필; mirror 자동 재생성 hook/CI; stale 카드(0001/0004~0007) 백필/동결 라벨; concepts→docs/improvements 승격 검토; hot/Index/overview frontmatter 정규화 + wiki-lint 의무화.
- **gate**: wiki-lint + drift 0(정본 mtime ≤ mirror mtime) + check #9

### ITEM-P5a · 코드 파편화 정리 (SSOT/중복·경계)
- **status**: pending (**범위 축소 — 아래 실측 갱신 참조**)
- **feature_id**: (코드 단위 별도 feature-NNNN cycle)
- **risk_grade**: Major
- **depends_on**: [ITEM-P1]
- **dimension**: structural (SSOT — *중복/경계*)
- **⚠ 실측 갱신 (2026-08-03)**: 이 항목의 "선행" 이던 **import 의존성 그래프 실측은 대상이 소멸**했다.
  `feature-0012-web-router-modularization` 이 app.py 모놀리스를 21개 도메인 APIRouter 로 전량
  추출·완결(STATUS.md — "모듈 분리 -81%")했기 때문이다. 재측정치:

  | 로드맵 원 전제 | 2026-08-03 실측 |
  |---|---|
  | `app.py` 148 `from modules.*` | **2** |
  | `app.py` 25,823 줄 | **3,883 줄** |
  | 모듈 5개뿐 | `src/routers/` **33 파일** |

  → "선행 실측" 과 "148 import 재정의" 작업 항목은 **무효**. 남은 것은 아래 attachment_reconciliation·
  skeleton 라벨·Dockerfile 결정뿐이며, 그 셋은 모두 **미결정 #4/#5 또는 문서 작업**이다.
- **작업**:
  - ~~선행: import 의존성 그래프 실측(app.py 148 `from modules.*`)~~ — **완료/무효**(feature-0012 가 해소, 위 표).
  - ~~shared/ 추출(modules.→shared. 재정의 + 148 import)~~ — 전제 소멸. Dockerfile 분리(미결정 #5)를 여전히 추진한다면 **현행 `routers/` 구조 기준으로 재설계**가 필요하다(구 전제로 착수 금지).
  - attachment_reconciliation 'dedup' 폐기: live 0003판 무변경, 0002판 GDPR(admin_purge/legal, 미배선) 사양 여부 결정(**미결정 #4**), env키(POLL_SEC vs INTERVAL_SEC) 정본 ADR 후 alias. 단순 합치기 금지.
  - feature-0009 '코드 이동' 옵션 삭제 → cross-cut 을 ANCHOR/CODEBASE_MAP 에 명시만. skeleton(0005/0008/0009) '코드 없음/계획' 라벨.
  - 단일 Dockerfile 분리 여부 = **미결정 #5**.
- **gate**: make test PASS + 전체 build + browser + 롤백 리허설 + plan-review 승인 + check #9 + 단독 cycle

### ITEM-P5b · 코드 비대화 해소 (모놀리스 분할/모듈화) — 신규
- **status**: pending
- **feature_id**: (코드 단위 별도 feature-NNNN cycle, 라이브 web app)
- **risk_grade**: **Critical** (라이브 web app, 146 endpoint, 런타임 회귀)
- **depends_on**: [ITEM-P5a]   <!-- import 실측·shared 추출 선행과 정합 -->
- **dimension**: structural (모듈화 — *파일 크기/유지보수*, SSOT-중복 아님)
- **why**: 사용자 원 요청 "비대화된 코드들". AI 전체 로드·정확 편집 어려움 → "요청 미수행" 증상 기여.
- **⚠ 실측 갱신 (2026-08-03) — 백엔드는 해소, 프론트만 남았고 오히려 커졌다**:

  | 대상 | 로드맵 원 전제 | 2026-08-03 실측 | 판정 |
  |---|---|---|---|
  | `app.py` | 25,823 줄 / 146 endpoint / 554 함수 | **3,883 줄 / `@app` 라우트 0** | **해소** — feature-0012 가 21개 APIRouter 로 전량 추출 |
  | 백엔드 모듈 | 모듈 5개뿐 | `src/routers/` **33 파일 / 223 endpoint** | **해소** |
  | `admin.js` | 8.8K 줄 | **14,007 줄** | **미해소 · +59%** |
  | `app.js` | 8.7K 줄 | **13,165 줄** | **미해소 · +51%** |
  | `styles.css` | 7.6K 줄 | **9,328 줄** | **미해소 · +23%** |

  → **이 항목의 남은 실체는 프론트 3파일뿐**이다. 백엔드 분할을 다시 착수하지 말 것(완료됨).
  프론트는 3주 만에 증가했으므로 방치 시 계속 악화된다.
- **참고 — 자매 initiative 의 트리거는 아직 미충족**: `parallel-work-structure` C-12(프론트 전면 분할)
  재검토 트리거가 "ITEM-09 완료 + 회귀 0 + **app.js 충돌 실측 발생**" 인데, 최근 60일 머지 커밋에서
  app.js 충돌 해소 흔적 **0건**(커밋은 166건으로 활발하나 실제 충돌 미발생, 2026-08-03 측정).
  즉 "충돌 때문에" 라는 근거로는 착수할 수 없고, 착수한다면 근거는 **파일 크기·편집 정확도**여야 한다.
- **모델**: feature-0002(38 모듈, agent_core 는 오케스트레이터)를 패턴으로. **안전망**: feature-0003 테스트 54파일/11K줄.
- **작업**:
  - ~~app.py → APIRouter/모듈 점진 추출~~ — **완료**(feature-0012, 위 표). 재착수 금지.
  - 프론트(admin.js/app.js/styles.css) 모듈 분할(번들 또는 ES module).
  - CONVENTIONS 에 *code-modularity* 컨벤션(파일 크기 임계 → 추출 trigger) 추가 — SSOT 계약과 sibling 인 code-health 규약(재발 방지).
- **gate**: 각 추출 단위 make test PASS + 브라우저 QA + 롤백 리허설 + plan-review(Critical) + check #9. **별도 cycle, doc-SSOT cycle 에 번들 금지.**
- **note**: SSOT(중복/정본)와 구분되는 *모듈화* 문제. 본 SSOT initiative 의 산출(정본 명확화)과 독립 추진 가능 — 별도 initiative(`docs/improvements/code-modularity`)로 분리해도 무방.

## 3b. 신선한 세션 진입점 (2026-08-03 갱신)

다른 AI 작업자가 **0 맥락**으로 이어받을 때 쓸 프롬프트. 그대로 복사해 실행하면 된다.

### 지금 유일하게 실체가 남은 작업 — 프론트 3파일 모듈 분할 (ITEM-P5b 잔여)

```
/_template:entry docs/improvements/ssot-consolidation/ROADMAP.md 의 ITEM-P5b 잔여분을 진행해주세요.
백엔드(app.py) 분할은 feature-0012 가 이미 완료했으니 손대지 마시고, 프론트 3파일만 대상입니다:
admin.js(14,007줄) · app.js(13,165줄) · styles.css(9,328줄) — 2026-08-03 실측, 3주 만에 +23~59% 증가.
로드맵의 게이트를 그대로 지켜주세요: 추출 단위마다 make test PASS + 브라우저 QA(PB-0008) +
롤백 리허설 + risk_grade Critical 이므로 plan-review 승인 선행. big-bang 금지, 단위별 점진 추출.
착수 전에 로드맵 ITEM-P5b 의 '실측 갱신' 표를 먼저 읽어 전제가 바뀐 것을 확인해주세요.
```

**착수 전 반드시 확인할 것**
- 이 항목은 **risk_grade Critical**(라이브 web app)이라 §7.1 plan-review 승인이 게이트다. 무단 착수 금지.
- 근거는 "충돌 회피" 가 **아니다** — app.js 충돌은 최근 60일 0건이다(위 참고). 근거는 파일 크기로 인한
  AI 로드·편집 정확도 저하이며, 그것이 사용자 원 요청("비대화된 코드들")이다.
- 안전망: feature-0003 테스트 54파일/11K줄. 패턴 참고: feature-0002(38 모듈) · feature-0012(라우터 추출).

### 착수 불가 항목 (같은 로드맵)
- **ITEM-P5a**: 남은 작업이 전부 **미결정 #4(attachment_reconciliation GDPR)·#5(Dockerfile 분리)** 에 걸려 있다. 사용자 결정 없이는 진행 금지.
- **ITEM-P3**: secret rotation — 사용자/외부 작업 + §12 사람 승인 대기.
- **ITEM-P0**: in-progress(다른 세션 가능성) — REGISTRY 확인 후 접근.

## 4. Open Decisions (사용자 입력)
1. secret rotation 범위 + history rewrite 추가 수행 여부(+저장소 public/private 확인)
2. STATUS 과거 누적 셀: unit TASK 링크만 vs STATUS_ARCHIVE 보존
3. wiki 자동 동기화: pre-commit hook vs CI vs 수동 lint
4. 0002 attachment_reconciliation GDPR legal-erasure: 배선/제거/보존
5. 단일 Dockerfile 분리: Phase 5 에서 분리까지 vs cross-cut 명시 + 단일 이미지 유지
6. §18.4 인간 개입 강도: 전 Phase vs Critical(P3)·Major(P5)만
