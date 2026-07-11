---
doc_type: DQA_ROADMAP
initiative: parallel-work-structure
created_at: 2026-07-10
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — parallel-work-structure (병렬 AI 작업 충돌 구조 개선)

> 경로는 모두 **repo-상대**(`policy_root` = repo 체크아웃 / worktree root 기준).
> `repo/` prefix 는 wrapper checkout 전용이라 본 문서에선 쓰지 않는다.

## 0. 맥락 (context-free 진입)

초고병렬 AI 작업(30일 PR 428건 · worktree 21개 · 작업자 3계열)에서 머지 충돌·재번호·stale
정정이 반복된다(최근 300커밋의 3.7%가 충돌 봉합 커밋). 원인은 worktree 격리 부족이 아니라
**격리된 브랜치들이 같은 착지점에 수렴**하는 구조다: (a) 거대 단일 파일(admin.js 17.7k줄
·app.py 19.7k줄), (b) 수동 선점하는 전역 순번(TASK.md `## N.`·alembic·ADR), (c) 파일 끝
append 공유 문서. 본 로드맵은 그 착지점을 분해하고, feature-0012 모놀리스 모듈화의 잔여
workstream(web_context 추출·프론트 분할·DEFER DI-rework — 2026-07-10 중단 세션에서 승계)을
같은 종속성 체계 안에 통합한다.

- **대상 제품**: 온프레미스 DBA AI Assistant (FastAPI web + ask-worker + Postgres KB).
  본 로드맵의 대부분은 제품 기능이 아니라 **개발 파이프라인·코드 구조 개선**이다.
- **정본 진입**: `AGENTS.md`(특히 §5·§6·§13·§16.3) · `docs/PROJECT.md` · `docs/ARCHITECTURE.md`.
  근거 수치·커밋 증거: `./RESEARCH.md` (F-001~F-010).
- **측정 기반**: `./RESEARCH.md §4` 재측정 명령 세트. 기준선(2026-07-10) = 충돌 봉합
  11/300 커밋 · 원격 ai/* 223(미머지 73) · TASK.md § 중복 2건. P0~P1 완료 30일 후 재측정.
  외부 비교 기준: 에이전트 PR 충돌률 27.67%(AgenticFlict 대규모 실측), 동시 변경 16건
  ≈ 충돌 확률 40%(Uber SubmitQueue) — `./RESEARCH.md §3` W-findings.
- **웹 리서치 반영(2026-07-10)**: 본 로드맵의 채택 방향은 외부 사례로 교차 검증됨 —
  격리는 표준이나 충돌은 머지로 지연될 뿐(W-001), 머지 불변식은 "최신 base 합산 green
  만 main"(W-002), fragment 는 towncrier/reno 표준(W-004), 마이그레이션은 heads 게이트
  + 의도적 충돌 파일 이중 방어(W-005), 근본 변수는 WIP×수명(W-006). 상세 근거·URL 은
  `./RESEARCH.md §3`.
- **feature_id 규약**: 코드 항목은 소유 unit 의 기존 feature id. 거버넌스·bin 도구 항목은
  **`META-NNNN-<slug>`** 를 쓴다 — `bin/verify-completion.sh` 의 feature-id 정규식
  (`^(feature|META)-[0-9]+...`)이 이 형식만 인정하고, META 순번 경합은 §13.1 의
  감지-후-재번호가 정본 규정된 backstop 이다. **본 문서의 META 번호는 잠정 할당**
  (0023~0029, 작성 시점 최대 META-0022 기준) — 각 cycle 착수 시 최대번호를 재확인하고
  선점돼 있으면 §13.1 대로 +1 재번호한다. META 항목은 verify META mode(check #9·#10·
  #11·#13 실행, #9 REVIEW 태그가 핵심 게이트 — §18.4)를 탄다. **혼합 changeset 금지**:
  META 항목이 unit/ 하위 파일을 함께 바꾸면 META mode 가 깨지므로, unit 측 적용분은
  해당 feature 의 별도 사이클로 분리한다(각 항목 guards 에 명시).
- **AGENTS.md 개정 공통 규약** (ITEM-01·03·06·07·12 해당): AGENTS.md 는 프로젝트 수준
  rewrite 문서이자 template 계보(v3.x) 문서다. 개정 항목은 (i) 개정안을
  `docs/DECISIONS.md` 에 제안으로 기록하고 승인 후 반영 — **본 로드맵에 명세된 개정
  범위는 §6 드레인 모드 사전 승인(2026-07-10)으로 승인 충족**, 명세 밖으로 확장되는
  개정만 blocked(§6.3), (ii) template base 전파(inbox) 계획 1줄을 REPORT 에 남기며
  (§13.2.3-A 가 선례), (iii) AGENTS.md·`bin/verify-completion.sh` 를 편집하는 항목들
  끼리는 DAG 로 **완전 직렬화**되어 있다(01→03→06→07→12) — 본 로드맵이 스스로 착지점
  경합을 만들지 않기 위함.
- **실행 모드**: 본 로드맵은 **§6 연속 드레인 운영 모드**(단일 세션 직렬 — 2026-07-10
  사용자 지시)로 실행한다. Major 사전 승인·blocked 축소·재개 프로토콜은 §6 이 정본이며,
  §2 의 "병렬 가능" 표기는 DAG 상 허용일 뿐 실제 실행은 §6.2 선형 순서를 따른다.

## 1. 종속성 그래프 (requires = 실선)

```
P0 (독립·병렬 — 편집 파일 상호 무겹침)
ITEM-01 (§/ADR/archive id 위생)        ──requires▶ (없음)
ITEM-02 (alembic multi-head gate)      ──requires▶ (없음)
ITEM-04 (worktree stale sweep)         ──requires▶ (없음)
ITEM-08 (STATUS 기능현황표 autogen)    ──requires▶ (없음)

P1 (meta 직렬 체인 + 독립 코드 항목)
ITEM-05 (라우터 자동 등록)             ──requires▶ (없음)
ITEM-03 (rerere + merge driver 브리지) ──requires▶ ITEM-01   # AGENTS.md §13.1 + verify 편집 직렬화
ITEM-06 (TEST Run fragment 전환)       ──requires▶ ITEM-03   # (전이적으로 01) 같은 AGENTS.md·verify 편집
ITEM-07 (merge mutex + 신선도 gate)    ──requires▶ ITEM-06   # 같은 AGENTS.md·verify 편집
ITEM-12 (핫스팟 WIP 상한+순차 머지 규약)──requires▶ ITEM-07   # 같은 AGENTS.md 편집 (체인 말단)

P2
ITEM-09 (admin.js 그래프 모듈 분리)    ──requires▶ ITEM-04, ITEM-07   # in-flight 가시화 + 머지 직렬화 선행
ITEM-10 (web_context 헬퍼 추출)        ──requires▶ ITEM-05            # app.py 꼬리 배선 경합 제거 선행

P3
ITEM-11 (DEFER 핸들러 DI-rework)       ──requires▶ ITEM-10            # DI seam 선행 (원본 세션 명시 블로커)
```

DAG 비순환 확인: 간선 8개, 전부 단방향(01→03→06→07→12 직렬 체인 4개 + 04→09, 07→09,
05→10, 10→11). ✅ AGENTS.md/verify-completion.sh 를 편집하는 항목(01·03·06·07·12)은
완전 직렬 — 병렬 Phase 안에 같은 파일을 만지는 조합이 없다.

## 2. Phase 시퀀스

| Phase | 포함 ITEM | 병렬? | 진입 조건 | 순서 근거 |
|---|---|---|---|---|
| P0 | ITEM-01·02·04·08 | 4개 전부 병렬(편집 파일 무겹침) | (없음) | 즉효·저위험 — 현재 진행 중인 병렬 작업의 충돌률을 먼저 낮춰 이후 Phase 자체를 안전하게 만든다 |
| P1 | ITEM-05 ‖ (03→06→07→12 직렬) | 05 는 병렬, meta 4종은 직렬 체인 | 03 은 01 완료 후, 이후 06→07→12 순차 | AGENTS.md·verify-completion.sh 공유 편집을 직렬화(로드맵 스스로 착지점을 만들지 않음) + 파이프라인 장치 완성 |
| P2 | ITEM-09·10 | DAG 상 병렬 가능 — §6 드레인 모드에선 직렬 | ITEM-09: 04·07 완료 + 그래프 활성 PR 0 **기계 확인**(§6.3 — 사전 승인 대체). ITEM-10: 05 완료 | 대형 리팩터는 보호 장치(P0·P1) 가동 후에만 — F-007 의 BLOCKED 사유 해제 |
| P3 | ITEM-11 | — | ITEM-10 완료 (§6.1 사전 승인 + 기계 게이트: 스냅샷·§18.8 패널) | 인증 인접 재편은 DI seam 확보 후 (원본 세션 명시 순서) |

## 3. 항목 (각 1 cycle)

### ITEM-01 · TASK.md § 섹션·ADR·archive 순번의 timestamp 전환 (id 위생 완결)
- **status**: done
- **note**: 2026-07-10 완료 (PR #677) — AGENTS.md §13.1/§5.5/§6 개정 + ADR-20260710T231146-parallel-id-hygiene
  + REV-20260710T231146(meta/REVIEW.md). acceptance (a)(b)(c) 전부 충족 — 기준선 grep 39줄/md5
  0a223f9a 불변(소급 재번호 0). META-0023 최대번호(0022) 재확인 후 확정(재번호 불요).
- **feature_id**: META-0023-parallel-id-hygiene   <!-- 확정 — 착수 시 최대 META-0022 확인, 잠정 번호 그대로 -->

- **dimension**: operational
- **risk_grade**: Major   <!-- 거버넌스 정본(rewrite) 개정 — §6.1 사전 승인으로 드레인 중 비차단 -->
- **depends_on**: []
- **enables**: [ITEM-03]
- **why**: F-002 — `TASK-`/`REV-` 등은 timestamp 전환(§13.1 v3.32.0/v3.34.x)으로 경합이
  제거됐으나 **§ 섹션 헤더·레거시 ADR 순번·archive 파일 순번만 규약 밖에 잔존**, TASK.md
  `## 33.`/`## 56.` 중복과 재번호 커밋(e79688f6, 0f692942)이 실측됨. fit: 기존 timestamp
  규약의 자연 확장(아키텍처·제약·보안 무영향), 신규 비용 ≈ 0.
- **fit_verdict**: adopt
- **what**:
  1. `AGENTS.md §13.1` 식별자 충돌 회피 절에 "**TASK.md 등 사이클-append 문서의 신규
     최상위 섹션 헤더는 `## <YYYYMMDDTHHMM>-<slug>` 형식**(순번 `## N.` 신규 사용 금지,
     기존 번호는 불변)" 규정 추가. `§5.5` 아카이브 파일명을
     `_archive/<DOC>-archive-<YYYYMMDDTHHMMSS>.md` 로 개정(날짜 단위로는 같은 날 병렬
     아카이빙이 다시 충돌 — timestamp 초 단위). `§6` 의 ADR 순번 fallback 을
     "신규 ADR 은 timestamp-slug 만 유효" 로 강화.
  2. `docs/DECISIONS.md` 에 본 개정 ADR(timestamp-slug 형식) 1건 append.
  3. 기존 문서의 소급 재번호는 **하지 않는다**(참조 파손 방지) — 신규 항목부터 적용.
- **entry_points**: `AGENTS.md` §13.1·§5.5·§6 (rewrite 문서 — §13.1 "동시 1 AI" 규칙 준수,
  본 cycle 이 단독 mutator), `docs/DECISIONS.md`(append).
- **acceptance**: (a) AGENTS.md 3개 절 개정 diff 존재 (b) ADR(제안→승인 근거 §6.1 기록
  포함) 1건 추가 (c) 기존 § 참조 무파손(`grep -rn '## 5[0-9]' unit/*/docs/TASK.md` 결과
  불변).
- **guards**: 소급 재번호 금지. §0 "AGENTS.md 개정 공통 규약" 적용 — DECISIONS.md 제안
  기록(승인은 §6.1 사전 승인으로 충족) + template base 전파(inbox) 계획 1줄. 이 cycle 이
  AGENTS.md 단독 mutator.
- **effort**: 小
- **notes**: verify-completion META mode 진입(#9·#10·#11·#13 실행, #9 이 핵심) —
  `meta/REVIEW.md` 에 REV 인식 태그 필수. 배포 무관(doc-only). **후행 관측**(done 판정식
  아님): 개정 후 신규 사이클들이 timestamp 헤더로 기록되는지 — 본 로드맵 이후 항목들의
  TASK.md 기록이 검증 표본.

### ITEM-02 · alembic multi-head CI gate + re-parent 자동화
- **status**: done
- **note**: 2026-07-10 완료 — migrate-lint `--heads`(head 단일성·번호중복·MAX 정합, self-test 10/10)
  + MAX_MIGRATION.txt(의도적 충돌 파일) + alembic-reparent.sh + ci.yml Migration gate 스텝.
  acceptance (a)(b)(c)(e) 실증(TEST.md §3), (d)=본 cycle PR checks. CHG/REV-20260710T232503.
- **feature_id**: feature-0002-agent-core
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: F-003 — 병렬 브랜치의 동번호 마이그레이션(0036 실충돌, `6263e641` 수동
  re-parent)이 머지 후에야 발견됨. 분산 브랜치에서 순번 자동 발급은 원천 불가하므로,
  **머지 전 감지(CI) + 해소 자동화(스크립트)** 가 정합 해법. fit: 기존 ci.yml `test` job
  ·`bin/migrate-lint.sh` 재사용, DB 스키마 무변경.
- **fit_verdict**: adopt
- **what**:
  1. `bin/migrate-lint.sh` 에 head 단일성 검사 추가: versions/ 를 정적 파싱해
     `down_revision` 그래프의 head 가 2개 이상이거나 **revision id**(파일명
     `YYYYMMDD_NNNN_slug.py` 의 두 번째 토큰 4자리 번호) 중복이면 exit 1
     (라이브 DB 불필요 — 파일 파싱만으로 판정, CI 에서 실행 가능).
  2. ci.yml `test` job 에 위 lint 를 스텝으로 추가(머지 게이트).
  3. `bin/alembic-reparent.sh <file> <new-number>` 신설: 파일명 번호·`revision`·
     `down_revision`(현 head 를 가리키도록) 3곳을 원자적으로 치환 + lint 재실행.
  4. **의도적 충돌 파일** `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt`
     도입(django-linear-migrations 의 `max_migration.txt` 검증 패턴 — RESEARCH W-005):
     최신 revision id 1줄 기록, 신규 마이그레이션·reparent 시 함께 갱신. 병렬 브랜치가
     각자 head 를 만들면 이 파일에서 **git 머지 시점에 반드시 충돌 → fail-fast**(CI 도달
     전 조기 발각). lint 는 이 파일과 실제 head 의 일치도 검사.
- **entry_points**: `bin/migrate-lint.sh`, `bin/alembic-migrate.sh:71`(head 계산 로직 참조),
  `.github/workflows/ci.yml`(test job — 실제 워크플로 파일 경로는 착수 시
  `ls .github/workflows/` 로 확정), `unit/feature-0002-agent-core/alembic/versions/`.
- **acceptance**: (a) 의도적으로 중복 `0040` 2개를 만든 시나리오에서 lint FAIL (b) reparent
  스크립트 1회 실행으로 lint PASS 복원 (c) 현행 0001~0039 체인에서 lint PASS (d) CI 에서
  스텝 실행 확인(PR 1건의 checks 로그) (e) 병렬 두 브랜치가 각자 마이그레이션을 추가한
  재현에서 MAX_MIGRATION.txt git 충돌 발생(fail-fast 실증).
- **guards**: reparent 는 **아직 main 에 머지되지 않은 자기 브랜치 파일만** 대상(머지된
  마이그레이션 재번호 금지 — 라이브 stamp 파손 방지, MIGRATIONS.md 규약 준수).
- **effort**: 小
- **notes**: 라이브 DB `alembic heads` 는 쓰지 않는다(CI 는 폐쇄망 DB 미접근) — 정적 파싱
  필수. 배포 무관.

### ITEM-03 · rerere 활성 + append-only 문서 path-scoped merge driver (과도기 브리지)
- **status**: done
- **note**: 2026-07-11 완료 — §13.1 개정(ADR-20260711T042631) + setup-git-parallel.sh(rerere
  2계정+driver 등록, 'claude' 계정은 호스트 부재 skip) + merge-append-doc.sh(말미 append 병존
  ·그 외 merge-file 위임=default 동등) + .gitattributes 3종(LEARNINGS 는 구조상 제외) + verify
  check #14(conflict-marker, merge-commit 1st-parent 대응). §18.8 패널 2-round: NOT-SHIP
  (BLOCKING 2·MAJOR 3) → 전건 반영 → SHIP-WITH-FIXES → 잔존 텍스트 반영. acceptance (a)(b)(c)
  재현 + 매트릭스 5종. REV-20260711T042631.
- **feature_id**: META-0024-merge-hygiene   <!-- 잠정 — 착수 시 최대 META 번호 재확인 -->
- **dimension**: operational
- **risk_grade**: Major   <!-- 3계정 git 전역 config + 머지 자동화 driver + AGENTS.md 개정 — §6.1 사전 승인으로 드레인 중 비차단 -->
- **depends_on**: [ITEM-01]
- **enables**: [ITEM-06]
- **why**: F-004·F-009 — append 문서 텍스트 충돌이 반복 수동 해소되고 있고(7c653ea8),
  conflict marker 잔존 커밋(a77180ca)까지 발생. fragment 전환(ITEM-06)이 근본 해법이지만
  전 문서 전환 전 과도기에 **비용 ≈ 0 인 git 장치**로 해소 자동화. **주의**: §13.1
  (v3.35.1) 원문의 path-scoped driver 허용은 **단일-라인 monotonic stamp 한정 2순위**
  해법이다 — append-only 문서 블록 병합 driver 는 그 허용 범위 **밖**이므로, 본 항목은
  §13.1 의 driver 허용 범위를 확대하는 **정식 개정을 선행 스텝으로 포함**해야 성립한다
  (개정 없이는 정책 위반 — 적대 리뷰 B-2 지적 반영).
- **fit_verdict**: adopt-with-guard (guard: ① §13.1 개정이 1급 선행 스텝 — §0 공통 규약
  적용(승인은 §6.1 사전 승인으로 충족), ② 전체파일 union 금지 유지 — 항목 경계 인식
  driver 만, ③ driver 실패 시 표준 충돌로 폴백해 사람/AI 해소)
- **what**:
  1. **선행: AGENTS.md §13.1(v3.35.1) 개정** — path-scoped custom merge driver 허용
     범위를 "단일-라인 stamp" 에서 "append-only 문서의 말미 블록 병합(항목 경계 인식,
     실패 시 표준 충돌 폴백)" 까지 확대. §0 공통 규약(DECISIONS 제안 기록 + §6.1 사전
     승인 + template 전파 계획) 적용.
  2. 작업자 3계열 계정(root·claude·claude-corp) git 전역에 `rerere.enabled=true` +
     `rerere.autoUpdate=true` 설정(설정 스크립트 `bin/setup-git-parallel.sh` 신설, 계정
     추가 시 재실행 가능하게 idempotent).
  3. `bin/merge-append-doc.sh` merge driver 신설: 3-way 병합에서 양측이 **파일 끝에
     추가한 `## ` 단위 블록**을 timestamp 순으로 병존시키고, 본문 중간 충돌은 driver
     실패(exit 1 → git 표준 충돌)로 폴백.
  4. `.gitattributes` 신설 + path-scoped 지정: `unit/*/docs/MODIFY.md`,
     `unit/*/docs/REVIEW.md`, `docs/LEARNINGS.md`, `docs/RELEASE_NOTES.md` (TEST.md 는
     ITEM-06 이 fragment 로 전환하므로 제외). `.git/config` 에 driver 등록도 setup
     스크립트에 포함(gitattributes 의 driver 는 로컬 등록 필요 — clone 마다 setup 실행을
     AGENTS.md 세션 시작 절차에 1줄). **`.gitattributes` 는 repo 루트 신규 파일**이라
     verify-completion META-경로 목록 밖 — 같은 커밋에서 `bin/verify-completion.sh` 의
     META-경로 인식에 `.gitattributes` 를 추가(이 항목이 verify 를 이미 편집하므로 동반).
  5. verify-completion pre-commit 경로에 conflict-marker 잔존 검사(`^<<<<<<<` staged-diff
     grep) 경량 추가(a77180ca 재발 방지).
- **entry_points**: `.gitattributes`(신설), `bin/setup-git-parallel.sh`(신설),
  `bin/merge-append-doc.sh`(신설), `bin/verify-completion.sh`(META-경로 목록·marker 검사),
  `AGENTS.md §13.1`(개정 — depends_on 으로 ITEM-01 과 직렬화됨).
- **acceptance**: (a) 재현 테스트 — 같은 base 에서 두 브랜치가 MODIFY.md 끝에 각자 CHG
  블록 append → `git merge` 무충돌 병존, 양 블록 모두 보존 (b) 본문 중간을 고친 케이스는
  표준 충돌 발생(폴백 확인) (c) rerere 가 동일 충돌 재발 시 자동 해소하는 것 1회 실증.
- **guards**: driver 는 append-only 문서 4종에만 path-scoped. 실패 시 무조건 표준 충돌
  폴백(자동 오병합 금지). §13.1 개정(what-1)이 본 항목 명세를 벗어나는 확대로 판정되면
  (§6.3) driver 스텝(3·4)은 폐기하고 rerere(2)+marker 검사(5)만 축소 출하.
  verify-completion 변경분(what-4·5)은 §18.8 패널 검증 대상.
- **effort**: 中
- **notes**: 배포 무관. ITEM-06 완료 영역부터는 driver 대상에서 제거(브리지 수명 명시).

### ITEM-04 · worktree/branch stale sweep 자동화 (`bin/worktree-audit.sh`)
- **status**: done
- **note**: 2026-07-10 완료 — worktree-audit.sh(4분류·merged 이중확인+tip 일치·통지 후 유예 상태파일
  ·DIRTY/IN-USE 불가침) + install-worktree-audit-cron.sh(평일 08:40 리포트 + 08:50 --apply).
  라이브 sweep: 원격 ai/* 200→소수(미머지·ACTIVE 만 잔존)·stale worktree 정리. IN-USE 가드는
  구현 중 실측(doc-sync 라이브 세션 SAFE_REMOVE 오분류)으로 추가. REV-20260710T234500.
- **feature_id**: META-0025-worktree-audit   <!-- 확정 — 최대 META-0023 확인(0024 미점유), 잠정 번호 그대로 -->
- **dimension**: operational
- **risk_grade**: Major   <!-- 원격 브랜치 삭제 cron — §6.1 사전 승인 + 기계 가드로 드레인 중 비차단 -->
- **depends_on**: []
- **enables**: [ITEM-09]
- **why**: F-006 — 원격 ai/* 223개(미머지 73), 41~129 behind 브랜치 방치 = 예약된 충돌.
  §13.2.3-A 가 판정 기준과 스크립트 구조를 **이미 규정**했으나 미구현(사용자 수동 sweep).
  fit: 거버넌스가 요구하는 도구의 구현일 뿐 — 신규 정책 없음.
- **fit_verdict**: adopt-with-guard (guard: 자동 삭제는 §13.2.3-A **1단계 SAFE_REMOVE 만**
  — merged 판정 이중확인(`git branch --merged` + `gh pr list --state merged --head`
  **+ main 동일 내용 확인** — squash-merge 후 추가 커밋이 있는 브랜치 오삭제 방지,
  §13.2.3-A 원문 요건); 2단계 LIKELY_ABANDON/NEEDS_REVIEW 는 보고만, 삭제는 사람 확인)
- **what**:
  1. `bin/worktree-audit.sh` 신설 — §13.2.3-A 로직 구현: 전 원격/로컬 ai/* 브랜치·worktree
     를 SAFE_REMOVE / LIKELY_ABANDON / NEEDS_REVIEW / ACTIVE 로 분류. `--apply` 시
     SAFE_REMOVE 만 제거(worktree remove + branch -d + 원격 push --delete), 나머지는
     리포트 출력(+ `TODOS.md` 후보 블록 stdout).
  2. root 소유 잔여물 대응: worktree remove 가 Permission denied 면 해당 경로의
     `__pycache__`/root-소유 파일을 `sudo rm` 후 재시도(F-006 quirk), `git worktree prune`
     마무리.
  3. cron 등록(평일 1회, 기존 doc-sync cron 패턴 재사용): 기본 리포트 모드. **cron 의
     `--apply`(SAFE_REMOVE 자동 삭제) 활성화는 §6.1 사전 승인으로 충족** — 단 기계 조건
     선행: 첫 리포트 1회 생성 → 리포트의 SAFE_REMOVE 판정을 acceptance (b)(c) 재현으로
     검증 → 이상 없으면 같은 드레인 내 활성화(오판정 발견 시 blocked, §6.3).
- **entry_points**: `bin/worktree-audit.sh`(신설), crontab(운영 — repo 밖, `bin/` 에 설치
  스크립트 동봉). AGENTS.md 는 편집하지 않는다(직렬 체인 밖 유지 — §13.2.3-A 구현 존재
  표기는 ITEM-12 의 AGENTS.md 편집에 1줄 편승).
- **acceptance**: (a) 드라이런 리포트가 현행 브랜치를 4분류로 출력 (b) merged 확인된
  테스트 브랜치 1개가 `--apply` 로 제거 (c) squash-merge 브랜치가 `gh pr list` 병행
  판정으로 SAFE_REMOVE 분류(§13.2.3-A 감지 Gap 대응) (d) open PR 브랜치는 무조건 ACTIVE
  (e) cron 1회 실행 로그.
- **guards**: 삭제는 SAFE_REMOVE 만 + `--apply` 명시 시만. **dry-run 이 기본값** + 원격
  브랜치 삭제는 직전 리포트에 1회 노출된 항목만(통지 후 유예 — 업계 정리봇 공통 안전장치
  4종, RESEARCH W-009). dirty worktree 는 어떤 모드에서도 건드리지 않음
  (FOREIGN_CHANGE_ALERT 대상). "자동 orphan sweep 은 사이클 외"라는 기존 결정
  (**AGENTS.md §13.2.3 Reviewer Concerns** — 주의: 소비자 `docs/DECISIONS.md` 의
  ADR-0020(slow_query_log)과 무관, template 측 절 번호로만 인용)과의 관계를 REVIEW.md 에
  명시: cron 은 사이클이 아닌 스케줄 maintenance(doc_sync 와 동급 지위)라 비충돌.
- **effort**: 中
- **notes**: 외부 영향(원격 브랜치 삭제) 있으나 merged-only 라 비파괴. 배포 무관.

### ITEM-05 · 라우터 자동 등록 — app.py 꼬리 배선 경합 제거
- **status**: done
- **note**: 2026-07-10 완료 — routers/__init__.py register_all(pkgutil+INCLUDE_ORDER 23개 스냅샷 고정)
  + app.py 꼬리 46줄→1줄(19,717→19,650). acceptance (a) 205 route byte-동치 (b) F821 clean
  (c) A/B pytest rc=0 (d) 더미 라우터 무편집 등록. CHG/REV-20260710T235820. 배포=머지 후 §6.1 자동.
- **feature_id**: feature-0012-web-router-modularization
- **dimension**: structural
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: [ITEM-10]
- **why**: F-008 — include_router 23개가 `app.py` 꼬리(약 19,639–19,716행)에 밀집, 라우터
  신설마다 같은 꼬리 블록 편집(신규 파일 추가는 무충돌인데 배선 1줄이 경합 유발). fit:
  feature-0012 추출 아키텍처의 마무리 — 재사용 100%.
- **fit_verdict**: adopt
- **what**: `unit/feature-0003-agent-web-ui/src/routers/__init__.py` 에
  `pkgutil.iter_modules` 순회로 각 모듈의 `router` 심볼을 수집·정렬(모듈별 선택적
  `INCLUDE_ORDER: int` 상수, 기본 파일명 순)해 일괄 `app.include_router` 하는
  `register_all(app)` 함수 구현. app.py 꼬리 배선 블록을 `register_all(app)` 1줄로 대체.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/__init__.py`(현재 docstring
  만 있는 7줄 — 자동 등록 미존재 확인됨), `unit/feature-0003-agent-web-ui/src/app.py`
  꼬리 include 블록 19,639–19,716(착수 시 라인 재확인 — main 전진 가능).
- **acceptance**: (a) 등록 전/후 라우트 테이블 스냅샷 동일 —
  `[(r.path, sorted(r.methods)) for r in app.routes]` 정렬 비교로 byte-동치 검증
  (b) `ruff check --select F821` 전 라우터 clean (c) `make test` 기존 baseline 동일
  (d) 신규 더미 라우터 파일 1개 추가 시 app.py diff 0 으로 라우트 노출 확인 후 제거.
- **guards**: 등록 순서가 의미를 갖는 라우터(경로 겹침·미들웨어 의존)가 있으면
  INCLUDE_ORDER 로 현행 순서 고정 — 순서 변경 금지(현행 include 순서 23개를 스냅샷으로
  못박음).
- **effort**: 小
- **notes**: 배포 scope: web 이미지 재빌드 필요(코드 baked). PB-0008 은 라우트 무변경이라
  스모크 수준.

### ITEM-06 · append 문서 fragment 전환 1차 — TEST.md Run 기록
- **status**: done
- **note**: 2026-07-11 완료 — §5.3 fragment 규약(test-runs.d/<id>.md, run_at ISO8601) + check #13
  OR 하위호환 개정 + doc_sync 90일 컴팩션 절 + §15.4.1/라우팅표/DoD 등 stale 참조 6곳 정합.
  acceptance (a) fragment-only PASS (b) 기존 방식 PASS + 음성 FAIL 보존 (c) 병렬 fragment
  머지 무충돌 (d) 규약 diff. §18.8 패널: SHIP-WITH-FIXES(우회면 없음·게이트 등가) → 잔존
  텍스트 반영. REV-20260711T051500.
- **feature_id**: META-0026-doc-fragments   <!-- 잠정 — 착수 시 최대 META 번호 재확인 -->
- **dimension**: operational
- **risk_grade**: Major
- **depends_on**: [ITEM-03]
- **enables**: [ITEM-07]
- **why**: F-004 — TEST.md Run 기록이 충돌 최다 지점 중 하나(229회/30일, 7c653ea8 등).
  파일 끝 append 를 **항목당 1파일**(fragment)로 바꾸면 병렬 추가가 git 에서 원천 무충돌
  (towncrier/reno 계열 표준 패턴). fit: F3(timestamp+session-ID 필수)이 이미 항목 단위
  식별을 강제하므로 "그 항목을 별도 파일로"는 자연 확장. **단 verify-completion check #13
  이 'TEST.md 추가 라인'을 hard gate 로 보므로 게이트 개정이 동반**되어 Major.
- **fit_verdict**: adopt-with-guard (guard: check #13 개정과 문서 규약 개정을 **같은
  cycle 에서 원자적으로** — 게이트만 먼저 바꾸면 기존 관행이 FAIL, 문서만 먼저 바꾸면
  게이트가 FAIL)
- **what**:
  1. 신규 규약: 테스트 Run 기록을 `unit/<feature>/docs/test-runs.d/<TASK-또는-REV-id>.md`
     항목당 1파일로 작성(frontmatter: run_at·session·scope·verdict). `TEST.md` 는
     §1/§2(케이스 정의, rewrite)만 유지.
  2. `bin/verify-completion.sh` check #13 을 "TEST.md 추가 라인 **또는** test-runs.d/ 신규
     파일" 인식으로 개정(하위호환 — 기존 방식도 당분간 PASS).
  3. `AGENTS.md §5.3` 개정(TEST.md §3 → fragment 규약). 기존 TEST.md §3 기록은 소급 이동
     하지 않음(이력 보존).
  4. `/_dqa:doc_sync` 컴팩션 훅: 90일 경과 fragment 를 feature 별 아카이브로 병합(선택
     단계 — acceptance 에는 규약 문서화까지만).
- **entry_points**: `bin/verify-completion.sh`(check #13 블록 = 1138–1205행, 착수 시
  재확인), `AGENTS.md §5.3`, `.claude/commands/_dqa/doc_sync.md`(컴팩션 규약 1절).
- **acceptance**: (a) **재현 브랜치**에서 fragment 1건(`unit/<임의 feature>/docs/
  test-runs.d/`)으로 verify-completion check #13 PASS 확인 후 브랜치 폐기 — 실제 feature
  문서는 이 cycle 에서 건드리지 않음 (b) 기존 TEST.md-추가 방식도 여전히 PASS(하위호환)
  (c) 병렬 재현 — 두 브랜치가 각자 fragment 추가 → 머지 무충돌 (d) AGENTS.md·doc_sync
  규약 diff.
- **guards**: check #13 개정은 하위호환 유지(OR 조건) — 일괄 강제 전환 금지. 게이트
  스크립트 변경분은 §18.8 패널 검증 대상. **changeset 분리**(§0 규약): 이 cycle 은
  bin+AGENTS+doc_sync(META 경로)만 — 실제 feature 의 fragment 파일럿 적용은 그 feature
  의 다음 정규 사이클에서 자연 발생(최다 충돌 지점인 feature-0016 부터 권장, 단 활성
  병렬 세션 없는 시점 선택 — REGISTRY·`gh pr list` 확인).
- **effort**: 中
- **notes**: 성과 확인 후 MODIFY/REVIEW/RELEASE_NOTES 확장은 별도 사이클(§4 F-015 defer).
  META+bin changeset — verify META mode. 배포 무관. 외부 검증: towncrier(pip·pytest)·
  reno(OpenStack)가 동일 목적("append 단일 파일의 merge conflict 제거")을 설계 목표로
  명시한 표준 패턴(RESEARCH W-004).

### ITEM-07 · host-local merge mutex + 신선도 hard gate
- **status**: done
- **note**: 2026-07-11 완료 — cycle-finalize Step 0b flock mutex(.git/.merge.lock, 900s timeout)
  + 신선도 게이트(behind≥20 → gh_update_branch: gh 2.57+ 명령/gh api PUT 폴백 — 라이브 실증이
  구버전 gh unknown-command 실결함 적발해 폴백 추가) + CLEAN 재폴링(600s, BLOCKED/DIRTY 자동중단)
  + verify behind≥10 WARN + §13.2.5 개정(수동 직렬화 문구 대체) + ADR-20260711T053001.
  acceptance (a) 락 대기 순차 (b) probe PR#684 behind=48 게이트 발동·머지 + probe2 PR#685
  api 폴백 tip 갱신 실증(close·정리) (c) timeout 명시 실패 (d) dry-run 기존 흐름 보존.
  REV-20260711T053001.
- **feature_id**: META-0027-merge-serialization   <!-- 잠정 — 착수 시 최대 META 번호 재확인 -->
- **dimension**: operational
- **risk_grade**: Major
- **depends_on**: [ITEM-06]   <!-- 논리 의존 아님 — AGENTS.md·verify-completion.sh 편집 직렬화(§0 공통 규약) -->
- **enables**: [ITEM-09, ITEM-12]
- **why**: F-005 — 일 18.6 PR 에서 머지 직렬화 장치가 없어 semantic drift(낡은 base 로
  통과한 테스트로 머지) 상존, 동시 push race 는 "사용자 수동 직렬화"에 위임돼 있음.
  GitHub merge queue 는 Free private 에서 불가 확정(Team 조차 불가 — RESEARCH W-003)이나
  **전 작업자가 동일 호스트**라 flock 으로 등가 구현 가능. 구현하려는 불변식은 업계
  공통핵 "최신 base 와 합친 상태가 green 인 커밋만 mainline 에"(Not Rocket Science Rule
  — bors·Zuul·Uber SubmitQueue·GitHub MQ 전부 동일, 스크립트 직렬화 실사례 sketch.dev
  — RESEARCH W-002). fit: cycle-finalize 가 이미 머지의 단일 경로(reference 구현) —
  그 안에 락만 추가, 신규 인프라 0.
- **fit_verdict**: adopt-with-guard (guard: 락 획득 실패 시 무한 대기 금지 — timeout +
  대기 사실 1줄 표면화; 락 파일은 host-local 이므로 원격/CI 에서의 머지는 보호 못함을
  문서에 명시)
- **what**:
  1. `bin/cycle-finalize.sh` 머지 단계(gh pr merge 전후)를
     `flock "$(git rev-parse --git-common-dir)/.merge.lock"` critical section 으로
     감싼다(timeout 기본 15분, 초과 시 명시 실패). 락 파일을 **git 공용 디렉터리 안**에
     두면 전 worktree 가 같은 락을 공유하면서도 working tree 밖이라 clean 검증
     (`git status --porcelain`)·gitignore 어느 쪽도 오염하지 않는다. 락 안에서:
     `git fetch` → PR base 대비 behind > 0 이면 `gh pr update-branch`(또는 rebase+push)
     → mergeStateStatus CLEAN 재폴링 → merge → main pull.
  2. 신선도 hard gate: cycle-finalize 머지 직전 branch 가 origin/main 대비 **behind ≥ 20**
     이면 자동 update-branch 후 CI 재확인을 강제(기존 "권유"를 게이트로 격상 —
     §13.2.5 개정 1줄).
  3. `bin/verify-completion.sh` 에 behind 수치 WARN(비차단) 표기 추가 — 조기 신호.
- **entry_points**: `bin/cycle-finalize.sh`(머지 Step 구간 164–195행, 착수 시 재확인),
  `AGENTS.md §13.2.5`(동시 push race 절 — 수동 직렬화 문구를 mutex 로 대체),
  `bin/verify-completion.sh`(behind WARN).
- **acceptance**: (a) 두 세션이 동시에 finalize 실행하는 재현 시나리오에서 순차 머지
  (두 번째가 락 대기 후 최신 main 기준 재검증) (b) behind 25 브랜치가 자동 update-branch
  경유 후 머지 (c) timeout 시 명시 실패 + 안내 메시지 (d) 단독 실행 경로는 기존과 동일
  (회귀 0 — dry-run 비교).
- **guards**: abnormal 자동중단 규약(§16.3 Step 6: non-MERGEABLE/dirty/non-ff) 전부 유지.
  update-branch 로 인한 CI 재실행은 UNSTABLE→CLEAN 폴링(기존 관행) 재사용. 락은 머지
  구간만(worktree 작업은 비직렬 — 병렬성 보존). **textual clean ≠ semantic safe**
  (RESEARCH W-008): CI green 만으로 머지하지 않고 기존 diff 열람·테스트 게이트를 락
  구간 안에서도 유지(생략 금지).
- **effort**: 中
- **notes**: 게이트 스크립트 변경 — §18.8 패널 검증 대상. 배포 무관. 락 파일은
  `$(git rev-parse --git-common-dir)/.merge.lock` — working tree 밖(공용 .git 디렉터리)
  이라 clean 검증·gitignore 와 무간섭, 전 worktree 공유(위치·근거를 스크립트 주석에
  명시).

### ITEM-08 · STATUS.md 기능현황표 자동 생성
- **status**: done
- **note**: 2026-07-11 완료 — bin/gen-status.sh(frontmatter feature_status* → 마커 구간 재생성,
  passthrough·--check) + STATUS.md AI-EDITABLE:STATUS-TABLE 마커 도입 + doc_sync Phase 3 통합.
  acceptance (a) 재현 브랜치 frontmatter 1행 재생성 (b) 마커 밖 diff 0 (c) passthrough 18행
  (d) 연속 실행 idempotent. 규약 키 = feature_status*(기존 doc-lifecycle status: 와 충돌 회피
  — 명세 status:/phase: 의 보수적 구체화). REV-20260711T042000.
- **feature_id**: META-0028-status-autogen   <!-- 잠정 — 착수 시 최대 META 번호 재확인 -->
- **dimension**: operational
- **risk_grade**: Minor
- **depends_on**: []
- **enables**: []
- **why**: F-004 — `docs/STATUS.md` 가 30일 109회 변경: 모든 feature 가 같은 표의 행을
  편집하는 공유 착지점. 사람이 고치는 파일을 기계가 만드는 파일로 바꾸면 충돌 대상에서
  제외됨. fit: doc_sync 인프라 재사용.
- **fit_verdict**: adopt
- **what**:
  1. 각 feature 상태의 source of truth 를 `unit/<feature>/docs/TASK.md` frontmatter
     (`status:`·`phase:` 키 — 없으면 추가 규약)로 정의.
  2. `bin/gen-status.sh` 신설: unit/*/docs/TASK.md frontmatter 를 수집해 STATUS.md 의
     기능현황표를 `<!-- AI-EDITABLE:STATUS-TABLE -->` 마커 구간으로 재생성(구간 밖 본문
     불변).
  3. 수기 편집 금지 표기는 **STATUS.md 마커 구간 안의 주석**("이 표는 bin/gen-status.sh
     생성물 — 수기 편집 금지")과 doc_sync 스킬 문서로만 — AGENTS.md 는 편집하지 않음
     (직렬 체인 밖 유지). doc_sync 실행 경로에 gen-status 통합.
- **entry_points**: `bin/gen-status.sh`(신설), `docs/STATUS.md`(마커 구간 도입),
  `.claude/commands/_dqa/doc_sync.md`. feature TASK.md frontmatter 는 이 cycle 에서
  편집하지 않음(§0 changeset 분리 — passthrough 설계로 frontmatter 없이도 동작).
- **acceptance**: (a) **재현 브랜치**에서 임의 feature 1곳에 frontmatter 를 넣고
  gen-status 가 그 행을 재생성함을 확인 후 브랜치 폐기 (b) 마커 구간 밖 STATUS.md 본문
  diff 0 (c) frontmatter 없는 feature 는 기존 행 유지(탈락 아닌 passthrough) (d) 연속
  2회 실행 idempotent(diff 0).
- **guards**: 표 재생성은 마커 구간 한정 — STATUS.md history(append-only 부분, F3) 불가침.
  frontmatter 실적용은 각 feature 의 다음 정규 사이클에 위임(활성 병렬 세션과의 F2 마찰
  회피).
- **effort**: 中
- **notes**: 배포 무관.

### ITEM-09 · admin.js 그래프 모듈 분리 (TASK-0012-10 해제)
- **status**: blocked
- **note**: 2026-07-11 착수 윈도우 게이트 FAIL(§6.3-3 — 진짜 이슈): 기계 판정 결과 그래프 구간
  활성 브랜치 발견 — ① `ai/root/feature-0016-edge-opacity` 미머지·admin.js 그래프 diff(+14),
  마지막 커밋 2026-07-10 15:00(ADR-033 관계선 opacity) ② worktree `feature-0016-graph-simcombo`
  에 미커밋 admin.js diff(+116/-43). 외부 세션 개입 신호 → 분리 착수 보류. 해제 조건: 두 흐름이
  머지/폐기되어 그래프 활성 0 재확인(worktree-audit 리포트로 기계 판정) 후 재개.
- **feature_id**: feature-0003-agent-web-ui
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-04, ITEM-07]
- **enables**: []
- **why**: F-001 + F-007-1 — 병렬 충돌의 **최대 단일 원천**(admin.js 17,671줄, 그래프
  구간을 feature-0016 브랜치 20+개가 동시 수정, 30일 약 236커밋). 원본 세션(fdd3a4b6)이
  "feature-0016 활성 ~10 브랜치와 충돌 → BLOCKED" 로 보류한 것을, 보호 장치(ITEM-04
  sweep + ITEM-07 직렬화) 가동 후 **좁은 윈도우에서 단행**한다. fit: 기능 무변경 이동 —
  아키텍처·보안 무영향, 파일 소유권도 정상화(그래프 코드가 feature-0003 유닛에 무단
  거주 중인 착종 해소는 후속 판단).
- **fit_verdict**: adopt-with-guard (guard: 착수 윈도우 게이트 — 아래 guards 참조)
- **what**:
  1. admin.js 의 그래프 로직(약 3,800~7,200행 구간 — `_metaGraph*`·`_metaInitGraph`·
     `_metaShowGraph` 등)을 `unit/feature-0003-agent-web-ui/src/static/graph/` 아래
     ES 모듈 5~8개로 **byte-준동치 이동**(기능·동작 무변경): 예 `graph-core.js`(init·
     데이터로드), `graph-interactions.js`(클릭·컨텍스트메뉴·드래그), `graph-lod.js`
     (semantic zoom·컬링), `graph-panels.js`(패널·검색), `graph-anim.js`.
  2. `styles.css` 의 그래프 CSS 를 `static/graph/graph.css` 로 분리.
  3. `admin.html` 에 `<script type="module">` 로드 + cache-buster 는 build/deploy 시
     content-hash 자동 부여(§13.1 v3.35.1 — 수기 stamp 금지).
  4. 전역 의존(admin.js 잔여부와의 공유 심볼)은 명시 export/import 로 경계화 — 암묵
     전역 참조 제거.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/static/admin.js`(3,800~7,200 구간
  — 착수 시 재측정), `src/static/styles.css`(그래프 셀렉터), `src/static/admin.html`,
  신설 `src/static/graph/`.
- **acceptance**: (a) 그래프 전 기능 회귀 0 — PB-0008 실 Windows 브라우저에서 로드·노드
  클릭·우클릭 메뉴·드래그·줌 LOD·검색·패널 각 1회 이상 실증(§15.4.1 완료 게이트)
  (b) `admin.js` 라인 수 ≥ 3,000 감소 (c) console 에러 0 · 성능 회귀 없음(그래프 로드
  시간 동급).
- **guards**: **착수 윈도우 게이트(기계 판정, §6.3)** — 시작 전 `gh pr list --state open`
  + REGISTRY + `git branch -r --no-merged` 로 admin.js 그래프 구간을 만지는 활성 브랜치가
  **0** 임을 확인. §6 드레인 모드(단일 세션 직렬)에서는 이 조건이 자연 충족되며 프리즈
  confirm 은 §6.1 사전 승인으로 대체 — **활성 브랜치/PR 이 발견되면 그때만 blocked**
  (진짜 이슈). 기능 변경 절대 금지(이동만) — diff 는 이동+import/export 만. 완료 즉시
  머지(장수 브랜치 금지 — 본 항목이야말로 신선도 민감).
- **effort**: 大
- **notes**: TASK-0012-10 승계(원본 feature-0012 태스크지만 파일 소유 feature-0003 에
  귀속 — cross-feature docs 홈 규칙). 배포 scope: web(자산 baked — 이미지 재빌드).
  실패 시 롤백 = 브랜치 폐기(모듈 분리는 원자적 1 PR). **후행 관측**(done 판정식 아님):
  이후 feature-0016 사이클이 graph/ 모듈만 건드리는 것 1건 확인 — 효과 실증은 30일
  재측정에 포함.

### ITEM-10 · web_context 헬퍼 추출 — app.py 완전 thin-app (feature-0012 Final)
- **status**: in-progress
- **note**: 2026-07-11 batch 진행 — batch1: inc3(권한 카탈로그, -562)+inc4(권한빌더 폐포,
  -167) PR #688 머지. batch2: 검증 정규식·인증 파라미터·SEED_ROLE(-77, PR #689). batch3: 세션쿠키·패스워드
  ·TOTP(-285, PR #690 — §18.8 패널 SHIP)+배포 14b7d876·스모크 green. batch4: 세션 경로·출력
  정규화·미디어 URL(-94, PR #691). batch5: 계정 로더·id 맵·RBAC seed(-466, PR #692).
  batch6(A+B+C): retarget 판정표 기반 13함수(-285, KEEP 3종 확정). routers-p1 파일럿(-26)
  → p2: _metadata_* 20종(-410) → p3: 프롬프트 컨텍스트 조립 8종(-845, routers/_prompt_context
  신설 — register_all 제외 공용 모듈): app.py 19,650→16,449(-3,201).
  → p4: _conv_* 11종(-444, routers/_conv_store): app.py 16,005(-3,645 누적)
  → p5: 대화 조회 4종(-1,002, _conv_store append): app.py 15,003(-4,647 누적)
  → p6: fork·steps·첨부편집 6종(-812): app.py 14,191(-5,459 누적)
  → p7: 감사 인프라 17종(-660, _audit_infra 신설·record_audit_event 잔류): app.py 13,531(-6,119 누적)
  → p8: 부트스트랩 스키마 3종(-813, _bootstrap_schema 신설·global-쓰기 등가 변환): app.py 12,718(-6,932 누적)
  → p9: 제품 인사이트·첨부 4종(-595): app.py 12,123(-7,527 누적)
  → p10: 스키마/마이그/시드 32종(-1,407): app.py 10,716(-8,934 누적 / -45%)
  → p11: ask/prompt/usage 5종(-584): app.py 10,132(-9,518 누적 / -48%)
  → p12: share/gdrive 16종(-308): app.py 9,824(-9,826 누적 / **-50%**)
  → p13: _load_/_resolve_/_parse_/_db_rule_ 32종(-1,101, 패치 2종 KEEP·@app.on_event 가드 신설): app.py 8,723(-10,927 누적 / -56%)
  → p14: oauth/login/dash/conversation 등 65종(-1,749, 패치 12종 KEEP·module-load 게이트 가드·perm-self-scope 테스트 다중파일 retarget): app.py 6,974(-12,676 누적 / -65%)
  → p15: 전수 census 128종(-2,188, 직수입·byte-offset 가드 신설·standalone 검증기 2건 수리·DI-seam KEEP): app.py 4,786(-14,864 누적 / **-76%**)
  → p16: PATCH 32종(-919, setattr=모듈 전역 rebind 판정으로 패치-fn 이동 해금): app.py 3,867(-15,783 누적 / **-80%**). fn sweep 종료 — 잔여 KEEP 12+DEC 10, 다음 p17=상수/모듈-레벨.
  배포: batch1~3=14b7d876 라이브 ✓ · batch4~6 배포는 deploy-web preflight flake(간헐)로 보류
  (이미지 정상 실증·라이브 healthy — 스파인 하드닝은 명세 밖, 사용자 승인 대기). 게이트(배치마다): route snapshot byte-동치·F821·py_compile·전 스위트 pytest.
  목표 ≤1,000줄까지 배치 계속(다음: 도메인 클러스터 위상순·23-테스트 retarget 영역은 적대검증 후).
- **feature_id**: feature-0012-web-router-modularization
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-05]
- **enables**: [ITEM-11]
- **why**: F-007-2 — 라우트는 0 이지만 app.py 에 ~19.7k 줄 헬퍼·전역이 잔존, 여전히 전
  웹 작업의 공유 착지점(30일 198회 변경, 2026-07-10 실측). 원본 세션이 "별건 대형 workstream, DI seam
  선행이 원래 monkeypatch 블로커" 로 명시한 Final 단계. fit: feature-0012 기존 아키텍처
  (routers/ + DI seam)의 완결 — 세션이 검증한 보수적 변환 접근(cata_b_transform 계보)
  재사용.
- **fit_verdict**: adopt-with-guard (guard: byte-동치·F821·baseline 3중 게이트 — 아래)
- **what**:
  1. app.py 의 헬퍼·전역을 도메인 클러스터 단위로 `unit/feature-0003-agent-web-ui/src/`
     하위 모듈(예 `web_context.py` + 도메인별 보조 모듈)로 **batch 이동**(1 batch = 1
     커밋, 각 batch 독립 검증). 라우터는 `from .. import app` 참조 대신 web_context
     명시 import 로 전환.
  2. 이동 순서는 의존 위상순(하위 유틸 → 상위 조립) — 착수 시 call-graph 스캔으로 확정.
  3. 최종 app.py = FastAPI 앱 생성 + 미들웨어 + `register_all(app)` (ITEM-05) 조립부만
     (목표 ≤ 1,000줄).
- **entry_points**: `unit/feature-0003-agent-web-ui/src/app.py`(전역·헬퍼 구간),
  `src/routers/*.py`(import 전환), 신설 `src/web_context.py` 등.
- **acceptance**: (a) batch 마다 `ruff check --select F821` 전 모듈 clean(세션 교훈 —
  라이브 500 예방) (b) `make test` progress-chars baseline 대조 동일(기존 관행)
  (c) 라우트 테이블 스냅샷 불변 (d) 라이브 스모크: 로그인·ask 1회·관리콘솔 로드 200
  (e) app.py 최종 ≤ 1,000줄.
- **guards**: 403/401 등 응답 메시지 **verbatim 보존**(기존 테스트 계약). batch 간
  머지-가능 상태 유지(중간 상태로도 배포 가능). 이동 중 신규 기능·리네이밍 금지.
- **effort**: 大
- **notes**: 배포 scope: web + ask-worker 재빌드(공유 모듈 경로 변경 시). ITEM-09 와
  병렬 가능(다른 파일축: app.py vs admin.js) — 단 같은 feature-0003 unit docs 를 쓰므로
  docs append 는 fragment(ITEM-06 완료 시) 또는 merge driver(ITEM-03)에 의존.

### ITEM-11 · DEFER 핸들러 byte-동치 DI-rework (pre-auth gate·long-poll·txn ~46)
- **status**: pending
- **feature_id**: feature-0012-web-router-modularization
- **dimension**: structural
- **risk_grade**: Major
- **depends_on**: [ITEM-10]
- **enables**: []
- **why**: F-007-3 — P5b 에서 아키텍처 사유로 이연된 핸들러(~43 pre-auth/long-poll/txn
  + fail-soft 3)의 DI 재편. 원본 세션이 "web_context seam 선행" 을 명시. fit: feature-0012
  완결의 마지막 조각 — 완료 시 app.py/모놀리스 잔재가 충돌 표면에서 완전히 사라진다.
- **fit_verdict**: adopt-with-guard (guard: 인증·인가 인접 — 아래 guards 강제)
- **what**: DEFER 목록(feature-0012 TASK.md 의 P5b 이연 분류 정본)을 재확인하고, pre-auth
  gate 를 FastAPI dependency 로, long-poll/txn 핸들러를 web_context 기반 DI 로 byte-동치
  재편. 1 batch = 동류 핸들러 묶음, batch 별 독립 검증.
- **entry_points**: `unit/feature-0003-agent-web-ui/src/routers/*.py`(해당 핸들러),
  `unit/feature-0012-web-router-modularization/docs/TASK.md`(DEFER 정본 목록).
- **acceptance**: (a) 401/403 응답이 전 대상 핸들러에서 상태코드+본문 byte-동치(스냅샷
  테스트) (b) long-poll 타임아웃·재연결 시나리오 라이브 1회 (c) `ruff F821` + `make test`
  baseline (d) §18.8 적대 검증 패널 PASS(인증 인접 필수) (e) DEFER 분류 잔여 0.
- **guards**: **인증·인가 인접** — 착수 승인은 §6.1 사전 승인으로 충족하되, 사람 게이트를
  대체하는 **기계 게이트를 강제**: 401/403 byte-동치 스냅샷 테스트 선작성(acceptance a)
  + §18.8 적대 패널 PASS(acceptance d) 없이는 어떤 batch 도 머지 금지 — 어느 하나 FAIL
  지속이면 blocked(§6.3). 403 메시지 verbatim. 실패 batch 는 즉시 revert(batch 원자성).
- **effort**: 大
- **notes**: 배포 scope: web. 완료 시 feature-0012 종결 선언(REPORT.md Final 기록).

### ITEM-12 · 핫스팟 WIP 상한 + 순차 머지 규약 (REGISTRY hot-path 선언)
- **status**: done
- **note**: 2026-07-11 완료 — §13.2.5-A 신설((a)WIP≤2 권고 (b)hot_paths (c)순차 머지
  (d)당일 랜딩) + REGISTRY 부트스트랩(worktrees/REGISTRY.md — repo 밖, cycle-init 자동
  entry·자기 블록만) + cycle-init --hot-paths soft 게이트(겹침≥2 경고·비차단) + §13.2.3-A
  META-0025 표기 편승 + ADR-20260711T051835. acceptance (a)diff (b)겹침 경고+정상 진행(2회 실증)
  (c)REGISTRY 신설·entry 기록 (d)§13.2.8 정합(스키마 additive). §18.8 패널 SHIP-WITH-FIXES
  (MAJOR 4·MINOR 5) **전건 반영**: flock+단일패스 원자화·실패 정직성(rc 캡처)·finalize Step 6
  자동 이동(Active→Closed) 구현·distinct 겹침 지표·session_id PID fallback. REV-20260711T051835.
- **feature_id**: META-0029-wip-hotspot-policy   <!-- 잠정 — 착수 시 최대 META 번호 재확인 -->
- **dimension**: operational
- **risk_grade**: Major   <!-- cycle-init 게이트 스크립트 + AGENTS.md 개정 — §6.1 사전 승인, §18.8 패널 대상 -->
- **depends_on**: [ITEM-07]   <!-- 논리 의존 아님 — AGENTS.md 편집 직렬 체인 말단(§0 공통 규약) -->
- **enables**: []
- **why**: 당초 defer(C-13) 였으나 웹 리서치로 **채택 승격** — 충돌 확률의 근본 변수는
  동시 진행량×브랜치 수명(Uber 실측: 동시 변경 16건 ≈ 충돌 확률 40%; DORA 고성과 팀 =
  활성 브랜치 ≤3 + 당일 병합; Claude Code 커뮤니티 실효 상한 2~4 세션 — RESEARCH W-006).
  feature-0016 graphux 2~10+ 병렬은 이 임계 초과 상태였고, 인프라(큐·fragment)는
  완화책일 뿐 진행량 자체의 규율이 1차 대책. 순차 머지(한 번에 1브랜치 → 잔여 rebase)는
  Augment 가이드의 검증 규율(W-008).
- **fit_verdict**: adopt-with-guard (guard: soft 경고 — hard 차단은 처리량 죽임, 아래)
- **what**:
  0. **REGISTRY 부트스트랩**: `worktrees/REGISTRY.md` 는 §13.2.8 이 규정하나 **현재
     디스크에 실재하지 않음**(적대 리뷰 실측) — §13.2.8 스키마(활성/종료 세션,
     `session_id:`)대로 신설하고 cycle-init 이 entry 를 자동 기록하게 배선.
  1. `AGENTS.md §13.2` 에 신설 조항: (a) **동일 핫스팟**(같은 파일 또는 같은 모듈 구간)을
     건드리는 in-flight ai/* 브랜치는 **동시 2개 이하** 권고, (b) REGISTRY 활성 세션
     entry 에 `hot_paths:` 필드(주요 편집 예정 경로 1~5개) 추가, (c) **순차 머지 원칙**
     — 같은 핫스팟의 복수 브랜치는 머지 순서를 REGISTRY 에 사전 선언, 1개 머지 후
     잔여는 rebase 하고 진행, (d) **당일 랜딩 원칙** — 사이클은 24h 내 머지를 목표로
     분할(초과 시 분할 재검토). (+ §13.2.3-A 에 ITEM-04 구현 존재 1줄 편승.)
  2. `bin/cycle-init.sh` 에 soft 게이트: 신규 worktree 의 `--hot-paths` 인자(선택)를
     REGISTRY 활성 entry 들과 대조, 겹침이 2개 이상이면 **경고 출력**(차단 아님) +
     REGISTRY 에 entry 기록.
- **entry_points**: `AGENTS.md §13.2`(직렬 체인 말단 — 01·03·06·07 완료 후),
  `bin/cycle-init.sh`, `worktrees/REGISTRY.md`(신설 — what-0).
- **acceptance**: (a) AGENTS.md 조항 diff (b) cycle-init 이 hot-paths 겹침 3개 시나리오
  에서 경고 출력 + 정상 진행(soft 확인) (c) REGISTRY 가 신설되고 cycle-init 1회 실행으로
  entry 에 hot_paths 필드가 기록됨 (d) 규약이 기존 **§13.2.8** REGISTRY 규약과 모순 없음
  (스키마 additive).
- **guards**: **hard 차단 금지** — 경고·가시화까지만(처리량 보존, 판단은 세션/사용자).
  REGISTRY 자체가 공유 문서이므로 entry 는 세션당 자기 블록만 수정(기존 규약 유지 —
  조정 파일이 새 충돌원이 되지 않게, W-008 부수 관측 반영). §0 공통 규약(§6.1 사전 승인
  + template 전파) 적용, cycle-init 변경분은 §18.8 패널 검증 대상.
- **effort**: 小
- **notes**: AGENTS.md 직렬 체인(01→03→06→07→12)의 말단. REGISTRY 경로는 §13.2.8 정본
  (`<project_root>/worktrees/REGISTRY.md`)을 따르되, **본 배치처럼 project_root 가 git
  working tree 와 겹치면 부트스트랩이 `.gitignore` 에 `worktrees/` 를 등록**해 clean
  검증·커밋 오염을 방지한다(적대 리뷰 N-12 지적 반영). 배포 무관.

## 4. 보류·기각 (재논의 방지 기록)

| finding/후보 | verdict | 사유 |
|---|---|---|
| C-12 app.js/styles.css 전면 분할 | **defer** | ITEM-09(admin.js)로 패턴·게이트를 먼저 확립. 재검토 트리거: ITEM-09 완료 + 회귀 0 + app.js 충돌 실측 발생 시 |
| C-13 REGISTRY hot-path 선언 + WIP 상한 | **adopt 로 승격 → ITEM-12** | 웹 리서치 정량 근거(Uber 16건→40%, DORA 활성 ≤3, 커뮤니티 세션 상한 2~4 — RESEARCH W-006/W-008)로 초안의 defer 판정을 번복. soft 경고 방식으로 처리량 보존 |
| C-14 GitHub merge queue | **reject** | 공식 문서로 불가 확정(RESEARCH W-003): merge queue 는 public 또는 Enterprise Cloud private 전용 — Free private 는 Team 플랜조차 불가, branch protection 도 불가(403 관측과 일치). ITEM-07 host-local mutex 가 등가 대체. 재론 트리거: 외부 GitHub App(Mergify, 5인 이하 무료) 권한 허용을 사용자가 결정하거나, 플랜 업그레이드 시 |
| C-15 § 번호 중앙 할당기(reservation registry) | **reject** | AGENTS.md §13.1 말미(648–650행, template 측 "ADR-0022" 인용 — 소비자 `docs/DECISIONS.md` 의 ADR-0022(MinIO)와 무관)에서 기검토·보류된 안. timestamp 전환(ITEM-01)이 전역 카운터 자체를 제거해 근본 해소 — 할당기는 단일 장애점 + 락 복잡도만 추가 |
| F-015 fragment 전면 일괄 전환(MODIFY/REVIEW/RELEASE_NOTES/DECISIONS) | **defer** | 게이트 스크립트 대개정 리스크 분산 — ITEM-06(TEST Run 파일럿) 성과 확인 후 확장. 트리거: ITEM-06 완료 + 30일 재측정에서 해당 문서 충돌 잔존 |

## 5. 진행 현황 (improve_cycle 가 갱신)

- 총 12 항목 · done 9 (ITEM-01·02·04·05·08·03·06·07·12) · in-progress 1 (ITEM-10) · pending 1 (ITEM-11) · blocked 1 (ITEM-09)
- **실행 순서(§6.2 선형)**: ~~01~~ → ~~02~~ → ~~04~~ → ~~05~~ → ~~08~~ → ~~03~~ → ~~06~~ → ~~07~~ → ~~12~~ → **09=blocked**(그래프 활성 브랜치 — note 참조) → **10=in-progress**(batch) → 11
- ITEM-09 blocked 는 §6.3-3(그래프 구간 활성 브랜치/PR 발견 — edge-opacity 미머지 + simcombo
  미커밋 diff). 해제되면 드레인 재편입.
- ITEM-05 배포 검증(2026-07-11 04:20): web-a/b 모두 GIT_COMMIT=ff522cda·healthy 4h 유지 —
  §6.1 deploy-backed 완료. (첫 deploy-web preflight 1회 일시 실패 후 재시도 성공 — 원인
  미재현 transient, config 재현 검사는 정상.)
- Major 등급(01·03·04·06·07·09·10·11·12)은 **§6.1 사전 승인(2026-07-10 사용자 지시)으로
  드레인 중 비차단** — blocked 는 §6.3 의 "진짜 이슈" 발생 시에만. (§6 이 없는 일반
  무인 드레인이라면 Major 는 자동 blocked 가 원칙 — §6 은 본 initiative 한정 특례.)
- ITEM-09 착수 윈도우·ITEM-11 인증 인접 게이트는 §6.3 의 기계 판정으로 대체됨.

## 6. 연속 드레인 운영 모드 (2026-07-10 사용자 지시 — 본 initiative 한정)

> 사용자 지시(2026-07-10, verbatim 요지): 본 로드맵은 규모가 크므로 **단일 세션에서
> 병렬 없이** 진행하고, [모든 토큰을 소비할 때까지 작업 → 사용량 재할당 시 `continue`]
> 를 반복하며 근본 수정을 완수한다. **특별한 이슈가 없는 한 blocked 되지 않아야 한다.**

### 6.1 사전 승인 (standing approval)

- 본 로드맵 **12개 ITEM 의 명세된 범위**(what/entry_points/acceptance/guards)에 대해
  Major 위험등급의 착수 승인·AGENTS.md 개정 승인·ITEM-04 `--apply` 활성화·ITEM-09
  프리즈·ITEM-11 인증 인접 착수를 **2026-07-10 사용자 지시로 일괄 사전 승인**한다
  (PLAN-APPROVED 상당). 각 cycle 의 REVIEW.md 에 "승인 근거: ROADMAP §6.1" 1줄을 남긴다.
- **배포**: 코드 항목(05·09·10·11) 완료 시 web(필요 시 ask-worker) 재빌드·재배포 +
  healthz/스모크 검증까지 자동 진행(§16.3 deploy-backed 완료 기준). 배포 실패·스모크
  FAIL 시 즉시 롤백 후 blocked(§6.3).
- 사전 승인의 **한계**: 명세 밖 scope 확장, 새로운 파괴적 작업(데이터 삭제·스키마
  파괴 변경), 로드맵에 없는 신규 항목 추가는 포함하지 않는다 — 이 경우 사용자 확인.
- 철회: 사용자가 언제든 지시로 철회 가능. 철회 시 §5 의 일반 원칙(Major 자동 blocked)
  으로 복귀.

### 6.2 실행 방식 (단일 세션 직렬)

- **선형 순서**: 01 → 02 → 04 → 05 → 08 → 03 → 06 → 07 → 12 → 09 → 10 → 11
  (deps 위상순 + 저비용 quick-win 선행 + AGENTS.md/verify 직렬 체인 준수 + 대형 리팩터
  후반. 09 를 12 직후에 두는 이유: 드레인 중에는 그래프 활성 PR 0 이 보장되는 조용한
  윈도우라 최대 충돌원 해체의 적기).
- 항목당 기존 worktree cycle 절차(cycle-init → 구현 → verify → cycle-finalize) 유지 —
  단 **한 번에 1개 cycle 만** 활성(직렬). 병렬 worktree 금지(사용자 지시).
- **작은 착지 단위**: 토큰 소진이 언제든 올 수 있으므로 batch/스텝 단위로 커밋·push 를
  자주 남긴다. 각 ITEM 의 중간 상태도 "머지 가능(테스트 GREEN)" 을 유지해, 소진 시점의
  미완 잔여가 최소화되게 한다.

### 6.3 blocked 조건 (진짜 이슈만 — 이 목록 외에는 멈추지 않는다)

1. acceptance/기계 게이트 FAIL 이 2회 연속 해소 실패(스냅샷 불일치·§18.8 패널 BLOCKING
   미해소·make test baseline 회귀 지속).
2. 배포 후 healthz/스모크 FAIL → 롤백까지 수행한 경우.
3. ITEM-09 착수 시 그래프 구간 활성 브랜치/PR 발견(외부 세션 개입 신호).
4. FOREIGN_CHANGE_ALERT / 타 세션 동시 변경 감지(단일 세션 전제 파손).
5. ANCHOR §1~§3 명백 상충(§18.3), 또는 명세 밖 scope 확장이 필요하다는 판단.
6. 파괴적 작업의 가드가 판정 불능(예: ITEM-04 SAFE_REMOVE 오판정 발견).

blocked 발생 시: 해당 ITEM 의 status 를 `blocked`+사유로 갱신하고 **다음 ready 항목으로
진행**(전체 드레인은 멈추지 않음). 전 항목 blocked 일 때만 세션 종료 보고.

### 6.4 재개 프로토콜 (`continue` + 재귀 자가 재호출)

토큰 소진 후 재개 경로는 두 갈래이며 **어느 쪽이든 동일한 재귀 체인을 이어간다**
(2026-07-10 사용자 지시 2차: "사용자가 미처 continue 를 못 칠 수 있으니 continue 호출
+5시간 10분에 자가 재호출, 구조는 재귀적으로"):

1. **사용자 `continue`** (우선 경로 — 도착 시 자동 체인은 뒤로 밀림).
2. **자동 재호출** — `bin/drain-continue-cron.sh` (정본 구현):
   - **arm (재귀 앵커 + 세션 pin + 모델 pin)**: 드레인 시작 시 **첫 행동으로
     `bash bin/drain-continue-cron.sh arm [--session-id <워커세션 UUID>] [--model <alias>]`** →
     `next_fire = 시작 +5h10m`·TTL 재충전, 재개할 **워커 세션을 `DRAIN_SESSION_ID` 로 pin**, 사용할
     모델을 `DRAIN_MODEL` 로 pin(미지정=계정 기본 모델). **arm 은 절대 자동탐지하지 않는다**(명시
     지정, 또는 기존 pin 보존만) — "최신 세션 자동탐지"가 무관 세션 하이재킹의 원인이었기
     때문(§18.8 B2).
   - **모델별 한도 자동 전환(2026-07-12)**: 계정 5h 윈도우 한도(usage-limit)와 별개로 **특정 모델의
     한도**("You've reached your Fable 5 limit. /model to switch models.")를 별도 감지(비-서술
     3조건 동일 적용)한다. 현재 `DRAIN_MODEL` 이 opus 가 아니면 **자동으로 opus 로 전환**(사용자
     지시 2026-07-12) 후 `+2m` 신속 재시도(무진전/백오프 미카운트 — 대기가 아닌 즉시 조치로 해결).
     이미 opus 인데도 모델 한도면(대안 없음) pin 유지 + 고정 `+5h10m` 폴백(이 문구는 리셋 시각을
     포함하지 않아 §6.4 리셋-파싱 미적용).
   - **모델 접근불가 자동 복귀(§18.8 MAJOR 해소)**: 전환한(또는 `arm --model` 로 명시한) 모델이 이
     계정에 없거나 오타/폐기됐으면("… may not exist or you may not have access to it.") 그 값을
     pin 해 두면 매 fire 가 즉시 재실패하며 **일반 무진전으로 위장돼 TTL 소진까지(~8.6일) 무증상
     정지**한다(라이브 재현). 이를 별도 감지해 **즉시 `DRAIN_MODEL` 을 계정 기본값(빈값)으로 되돌리고**
     `+2m` 재시도(무진전/백오프 미카운트). 최악의 사이클(모델한도→opus전환→opus접근불가→복귀)도
     TTL 소모 없이 2 fire(~4분) 내 자기수렴 실증.
   - **fire (v3, 2026-07-11 — 세션 재개 연속성)**: 호스트 크론 체커(*/5분, root·claude-corp 양
     계정)가 `next_fire` 도달 시(flock 로 단일 버스트): ① **실패-내성 앵커**(`next_fire=now+5h10m`
     를 버스트 전 기록) ② **pin 된 워커 세션을 `claude --resume <id> -p "continue…"`** 로 헤드리스
     재개 — **컨텍스트를 보존한 채 직전 작업을 이어감**(사용자 의도: 사용량 만료마다 세션 컨텍스트·
     미완 작업 누락 방지). pin 이 없으면(부트스트랩/컨텍스트死 복구) **미리 생성한 UUID 로
     `claude --session-id <uuid> -p "<재앵커>"` 새 세션**을 시작하고 **그 uuid 를 그대로 재-pin**.
     (재-pin 을 "slug 최신 jsonl" mtime 추측으로 하면 공유 slug 의 무관 세션(사용자 VSCode·
     orchestrator·타 cron)을 잡아 하이재킹된다 — §18.8 B2 라이브 재현; `--session-id` 결정론으로
     회피.) (`--dangerously-skip-permissions` + `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` + 외곽
     timeout 300m.) ③ **종료사유별 다음 발사**:
       - `usage-limit` — 비-서술 3조건 AND(진전0 ∧ dur<90s ∧ 종단3줄이 “hit your (session|usage)
         limit”)로만 인정(서술 오탐 차단, §18.8 N3). → **pin 유지** + **CLI 가 알려준 실제 리셋
         시각 + 버퍼(5분)** 로 재개 예약(TTL−1). 고정 +5h10m 은 한도를 5h 롤링 윈도우 **초반**에
         맞으면(공유 quota 를 다른 세션들이 함께 소비) 실제 리셋을 크게 지나쳐 재개가 늦었다(관측
         2026-07-11: 16:25 한도 → +310m=21:35 vs 메시지 “resets 7:20pm”=실제 19:20). 이제 메시지의
         리셋 시각을 파싱(`parse_reset_epoch`)해 리셋 직후 정확히 재개; **파싱 실패 시 +5h10m 폴백**.
         리셋 후 **같은 세션을 이어서** 재개 = 연속성 핵심.
       - `context 소진` — 같은 3조건에서 종단이 “Prompt is too long”. → **pin 해제** → 다음 fire
         **새 세션** 재앵커(+재-pin). 세션 수명의 자연 종점에서만 갈아탄다(무한 orphan 방지, B3).
       - **진전 있음** — 버스트 시작 이후 committer-date 서명 커밋 > 0
         (`rev-list --branches --count --since=@start --grep=parallel-work-structure`; pull 유입·
         동시 sibling 커밋 배제, §18.8 N1) → **`+2m` 신속 재개**(TTL 미소모). ← “무조건 +5h10m”
         유휴(“한 cycle 후 중단”) 해소.
       - **진전 없음** N회 연속(`MAX_NOPROG`=6) → 백오프(TTL−1), 단 **2단계**(§18.8 MINOR-1 —
         핵심의도 '컨텍스트 보존' 보호): resume 세션의 **1차 백오프는 pin 유지 + `+5h10m` 리셋
         대기**(놓친 usage-limit 이면 리셋 후 같은 세션이 진전 → 컨텍스트 보존, 건강한 세션을
         성급히 버리지 않음). **리셋 뒤에도 무진전(streak≥2)이거나 fresh 부트스트랩이 실패**하면
         그때 **pin 해제 재부트스트랩**(context-death 미탐 영구 스톨 방지 — §18.8 MAJOR). `*/5`+flock
         이 재발사 폭주의 자연 상한.
     > **왜 세션 재개(v2 always-fresh 폐기)인가**: always-fresh 는 매 fire 신규 세션이라 사용량
     > 만료마다 직전 세션 컨텍스트/미완 작업이 누락됐다(사용자 지적, 2026-07-11). v3 은 pin 된
     > 세션을 `--resume` 해 연속성을 보존한다. 하이재킹(B2)은 pin 을 **명시 지정만**(자동탐지 금지)
     > 으로, 컨텍스트死(B3)는 **실제 “Prompt is too long” 감지 시에만** 새 세션으로 넘어가 막는다.
     > ⚠ **동시접근**: pin 된 세션이 VSCode 에 열린 채 cron 이 headless `--resume` 하면 한 대화에
     > 두 클라이언트가 붙는다. flock 은 cron 측만 보장하므로 **자동 버스트 중 수동 continue 자제**
     > (`status` 로 lock 확인). 사용자 승인 하 채택한 trade-off.
   - **재귀 종결 조건**: 전 ITEM done/blocked(드레인 완주) 시 세션이
     `drain-continue-cron.sh disarm` 실행. 백스톱 = TTL 40 fire(재-arm 없이 약 8.6일)
     소진 시 자동 disarm. 사용자 지시로 언제든 disarm 가능.
- 재개(어느 경로든) 시 첫 행동: **arm** → 본 문서 **§5 진행 현황**과 활성 worktree
  (`git worktree list`)·미커밋 diff·마지막 커밋을 교차확인해 중단 지점을 복원하고,
  in-progress 항목부터 이어간다(§5 를 항목 전환 시마다 갱신해 두는 것이 재개 정확도의
  전제).
- **ScheduleWakeup(하네스 내부 예약)은 여전히 금지** — 사용량 한도 리셋 후 stale 발화
  사고 이력(2026-07). 재귀는 상태파일 기반 호스트 크론으로만(발화 시각을 상태파일이
  단일 결정 — pending 큐가 쌓이지 않음).
- 주의: 자동 버스트 실행 중(상태 `status` 가 lock 점유 표시) 사용자 `continue` 는 같은
  대화에 대한 동시 접근이 되므로 자제 — `bash bin/drain-continue-cron.sh status` 로 확인.
- 세션 rollover(context 요약) 후에도 §5 + worktree 상태가 복원 기준점이다.

### 6.5 연속성 규약 — 버스트는 **하드-스톱에서만** 끝난다 (2026-07-11 개선)

> 관측된 실패(2026-07-11): 드레인 세션이 토큰·컨텍스트가 **남아 있는데도** "이번 버스트를
> 정리하고 다음 체인(예: +5h10m 크론 버스트)이 이어간다"며 **한 cycle(또는 한 조각) 후
> 스스로 종료**했다. 그 결과 재개까지 수 시간 유휴가 생겨 "토큰 소진까지 지속 작업"(사용자
> 원지시)이 "한 조각 하고 장시간 잠"으로 퇴화했다. 이 자발적 중단이 정확한 실패 모드다.

- **한 버스트(= arm 부터 하드-스톱까지의 구간)는 아래 하드-스톱 4개 중 하나에 도달하기
  전까지 절대 자발적으로 종료하지 않는다.** ready 작업이 남아 있고 토큰·컨텍스트가 남아
  있는 한, 한 ITEM 을 마치면 **곧바로 다음 ready ITEM 으로 이어가고**, 한 ITEM 안에서도
  batch 를 마치면 **곧바로 다음 batch 로** 진행한다. "이번 버스트 정리 후 다음 체인이
  이어감" 식의 **선제적 종료·인계 서술은 금지**(그 유휴가 실패 모드다).
- **하드-스톱(버스트를 끝내도 되는 유일한 4조건)**:
  1. **usage-limit 도달** — 사용량 한도(session/usage limit)에 실제로 막혀 남은 토큰으로 더
     진행 불가. → 크론이 비-서술 3조건(진전0 ∧ 짧은 dur ∧ 종단 줄이 한도문구)으로 감지해
     `+5h10m` 리셋 대기(§6.4). (한도 CLI 문구 원문은 이 문서에 남기지 않는다 — 판정 오탐 방지.)
  2. **context 소진** — 현 세션 컨텍스트 초과(context-overflow abort)로 더 못 이어감. → 이때만
     크론이 pin 을 해제하고 **다음 fire 를 새 세션**으로 시작(§6.4 v3), §5+worktree 에서 복원해
     이어간 뒤 그 세션을 재-pin. (그 외 재개는 pin 된 같은 세션을 `--resume` 해 컨텍스트 보존.
     감지 CLI 원문은 이 문서에 남기지 않는다 — 판정 오탐 방지.)
  3. **전 ready 항목 blocked** — §6.3 조건으로 남은 모든 항목이 blocked(진행 가능한 ready
     0). → blocked 사유 요약 후 종료(다음 fire 가 언블록/외부변화를 재확인).
  4. **드레인 완주** — 전 ITEM done/blocked. → `disarm` 실행, 체인 종결.
- 위 4조건 **외의 자발적 종료는 결함**이다. 특히 "확립된 패턴이니 다음 버스트가 이어감",
  "안전하게 여기서 끊고 신선한 컨텍스트에서" 류의 판단으로 멈추지 않는다 — 그 "신선한
  컨텍스트로의 인계"는 **하드-스톱 2(context 소진)** 가 실제로 왔을 때 크론이 자동 수행한다.
- **안전판(크론 측, §6.4 fire)**: 그럼에도 세션이 하드-스톱 전에 종료하면, 크론이 종료
  사유를 판정해 usage-limit 이 아닌 한 **다음 */5 틱(~2분)에 재개**한다 — 자발적 중단이
  발생해도 수 시간이 아니라 수 분 안에 이어지도록 하는 이중 방어. 단 이는 **보정 장치**일
  뿐, 세션이 스스로 안 멈추는 것이 1차 규약이다.
- **잦은 커밋과의 관계(§6.2)**: batch 단위 잦은 커밋·push 는 유지한다(소진 시 잔여 최소화).
  "자주 커밋" 은 "자주 멈춤" 이 아니다 — 커밋 후 곧바로 다음 batch 로 이어간다.
