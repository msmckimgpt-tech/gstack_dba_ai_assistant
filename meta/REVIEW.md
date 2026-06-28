# META REVIEW

> META-layer 변경(`.claude/commands/`, `meta/`, `docs/improvements/` 등)의 검증 패널 기록. AGENTS.md §18.4 / §18.8 / §16.3 check #9.

## REV-20260625T023049-meta-ac-timestamp-id [SUBAGENT:policy-coherence-adversarial + reverify] — SHIP (BLOCKER 2 + MAJOR 2 + MINOR 2 + 재검증 MAJOR 1 흡수)

- **cycle**: ai/claude/meta-ac-timestamp-id — spec 앵커(`REQ`/`AC`/`ADR`/`TEST`) 식별자 형식을 순번 `*-XXXX` → **timestamp+slug** `<PREFIX>-<YYYYMMDDTHHMMSS>-<slug>[-<n>]` 로 전환 (사용자 직접 지시 2건: "AC-NNNN 도 timestamp-slug 로" → "REQ, ADR, TEST 또한 같은 형식"). `feature-NNNN`/`META-NNNN` 은 순번 유지. 신규 ADR `ADR-20260625T023049-spec-anchor-timestamp-id`(본 형식의 첫 적용 예시).
- **동기**: 고병렬 cycle 머지에서 순번 spec 앵커 충돌이 반복 관측(실측: `gc-member-kick-ban` rebase 중 `auto-product-prompt`/`admin-metadata-relocate` 와 AC-0625 연쇄 충돌 → 2회 재번호). v3.32.0 가 TASK/CHG/REV/LRN 에 이미 적용한 timestamp+branch 전환의 잔여 표면 해소.
- **changeset (pure-meta, 전 파일 META path → verify-completion META mode)**:
  - `AGENTS.md` §6(식별자 표 4행 REQ/AC/ADR/TEST + prose 의 spec 앵커 전환 단락) · §13.1(감지-후-재번호 대상을 feature/META 로 한정) · timestamp+branch 출처의 틀린 `ADR-0025` 인용 2곳(line 608·2000)을 §6/버전 참조로 정정.
  - `docs/CONVENTIONS.md`(식별자 목록 REQ/AC/ADR/TEST) · `docs/DECISIONS.md`(신규 ADR + registry 주의) · `unit/_template/docs/{FUNCTION.md §11, TEST.md §2}`(템플릿 예시 주석) · `wiki/Glossary/_Index.md`(용어집 행) · `playbooks/PB-0006-template-migration.md`(ADR 작성 절차).
  - `bin/verify-completion.sh` `is_meta_path()`: `playbooks/*` META-class 분류 누락 보강(프로세스 거버넌스 문서 — 본 changeset 의 PB-0006 포함을 pure-meta 로 정합화). bin/* 이 이미 META 라 pure-meta 불변.
- **§18.8 적대 패널(정합성) + 재검증**:
  - 1차 적발: **BLOCKER 2**(① 새 ADR/AGENTS 가 "ADR-0024 supersede·ADR-0025 확장" 으로 엉뚱한 ADR 인용 — DECISIONS.md 의 ADR-0024=Postgres 격리·ADR-0025=M5/pgvector 중복, 식별자 정책 아님 ② ADR-0025 중복 정의 pre-existing) + **MAJOR 2**(wiki/Glossary·PB-0006 순번 형식 잔존) + **MINOR 2**(부모 REQ↔자식 AC timestamp 예시 불일치 · `-<n>` 필수/선택 표기 불일치).
  - 흡수: 특정 순번 ADR 번호 비인용(§6/§13.1 위치 + v3.32.0 버전 참조) + 새 ADR 상단 registry 주의(번호 불일치·중복을 전환 동기로 명시) + Glossary/PB-0006 갱신 + 예시를 "AC 는 부모 REQ slug 공유 + cycle 초 timestamp" 로 명확화 + `-<n>` 규칙 통일("AC 2개↑ 필수, 단일 생략").
  - 재검증 1차: **MAJOR 1 NEW-ISSUE**(line 608·2000 의 동일 틀린 `ADR-0025` 인용 잔존) 적발 → 흡수(§6 참조로 정정). **재검증 2차 잔여 BLOCKER/MAJOR 0**.
- **검증**: 식별자 ID 를 숫자(`[0-9]{4}`)로 파싱하는 스크립트 0건(bin/ 전수 grep — verify-completion/review-panel/anchor-migrate 무영향). 새 ADR id 7개 문서 8 인용처 오타 0. 기존 순번 ID 소급 재번호 0(additive). §6 표↔prose↔§13.1↔ADR 삼각 정합 확인.
- **Human Approval Needed**: 아니오 (Minor governance, 비파괴 doc-only·additive, 사용자 직접 지시). 단 ADR 형식이 길어지는 가독성 trade-off 는 사용자 결정으로 수용.

## REV-20260625T013000-META-0010-doc-sync-0625 [SKIPPED:doc-sync-index-mirror-alignment]

> ID 주: 본 cycle 은 당초 `META-0009-doc-sync-0624` 로 시작했으나, 동시 진행된 `ai/root/META-0009-presentation-title-rename`(#414)이 먼저 머지돼 META-0009 를 선점 → 충돌 회피 위해 **META-0010-doc-sync-0625** 로 리넘버(본 ledger 하단 그 entry 와 구분).

- **cycle**: ai/claude/META-0010-doc-sync-0625 — `/_dqa:doc_sync`(no-arg, maintenance) 가 06-24 머지 작업과 정책문서·wiki 간 drift 를 정합. 정본(`unit/<id>/docs/*`)을 새로 쓰지 않고 **색인·미러·서사 표면만** 최신화(SSOT 인덱스 모델 — ADR-0031).
- **delta 근거**: main `unit/` = 11 feature(0001~0011)인데 STATUS 인덱스/wiki narrative 가 9~10 에 정체. feature-0010-google-drive-integration(06-23 19:04 landing, 비활성 scaffold)이 STATUS 에 "미머지 worktree note" 로 stale, feature-0011-shared-extraction(06-24 landing, P5a Step1~3)은 전 표면 부재. 0002/0003/0009 는 06-24 머지로 행 stale.
- **changeset (pure-meta, docs/* + wiki/* → verify-completion META mode)**:
  - `docs/STATUS.md`(인덱스) — feature-0010·0011 행 승격/신설 + 0002/0003/0009 06-24 최종갱신·요지 정합 + §2 의존요약 0010/0011 + §5 진행률(9→11, in-progress 8→10) + sources frontmatter 0010/0011. **rollup blockquote 미누적**(ADR-0031 §1 셀 누적 0 유지). worktree note 를 "미머지 활성 worktree 없음(ahead=0)"으로 정정.
  - `docs/ARCHITECTURE.md` §4 기능맵 + §6 의존맵 — feature-0011 행 추가(색인/기능맵 정합 한정, 구조 결정 변경 아님 §13.1).
  - `wiki/` — `Features/feature-0011-shared-extraction.md` 카드 신설 + `Features/_Index`(10→11 + 행) · `overview.md`(9→11 ×2 + 06-24 서사) · `Index.md`(9-feature→11 ×2) · `Architecture/Overview.md`(Feature 수 9→11 + 기능맵·의존맵 0010/0011 미러 backfill + 진화 06-24 bullet) · `hot.md` refresh(feature-0011·메타데이터 거버넌스 반영, feature-0010 활성화·insight-worker thread **보존**) · `Log.md` append(append-only).
- **panel skipped 사유 (§18.8 — 정책-doc 이나 패널 불요)**: 전 changeset 이 정본을 재서술하지 않는 **additive 색인/미러/서사 정합**. 정책 의미(보안 경계·구조 결정·ADR)는 무변경 — SECURITY/DECISIONS 무수정(이미 최신, 정직 무변경 보고). 새 판단 로직·production 동작 0. precedent: `REV-20260623T092428-doc-sync-skill [SKIPPED:additive-meta-tooling-docs]`.
- **타깃별 실질 검증(verify check #1/#5 deferred 대체)**: ① wiki feature 수 정합 — ground-truth `ls -d unit/feature-* | wc -l`=11, narrative 전 파일(overview·Index·Features/_Index·Architecture/Overview) stale 9/10 잔존 0 으로 기계 확인. ② 신규 wikilink/STATUS 링크 대상(unit/feature-0011/docs/*·card) 존재 확인. ③ `bin/ssot-lint.sh` PASS(잔존 4 WARN = 기존 tracked secret 백업, P3 rotation 대기 — STATUS §3 기록된 알려진 blocker, 본 변경과 무관·신규 위반 0). ④ STATUS 인덱스 rollup 셀 누적 0 유지.
- **릴리즈노트 타깃 분리**: `unit/feature-0003/src/static/release-notes-data.js` 는 operational(is_meta_path 비META, code-file → check #4 FUNCTION.md 강제) — 본 META commit 과 **별도 처리/사용자 판단**. 본 entry 범위 아님.
- **Human Approval Needed**: 아니오 (additive index/mirror 정합, 정본·정책 의미 무변경).
- **deploy**: 해당 없음 — `docs/*`·`wiki/*` 는 라이브 서빙 자산 아님. 완료 = main 병합.

## REV-20260624T154711-META-0007-presentation-tiering [AGENT-TEAM:presentation-tiering-verify]

- **cycle**: ai/claude/META-0007-presentation-tiering — `repo/docs/presentation/*` 발표자료 갱신 + **클라이언트별 기능 분류**(작업 화면 + 관리 콘솔 / 작업 화면 only 2-덱 티어링). `/_template:resume` 로 중단 세션(ac9c0072, session-limit)의 기존 의도 재개·완수.
- **changeset (pure-meta, docs-only → verify-completion META mode)**:
  - `docs/presentation/index.html` (풀 덱) — 15→20 슬라이드. 작업화면 면 +3(실패 결과 ‘AI 로 고치기’·답변 피드백·그룹 대화) + 릴리즈 노트 chip, 관리콘솔 면 +2(메타데이터 용어/ENUM 사전·샘플 검수 큐) + 정리 일꾼 슬라이드에 DB별 분석 상태 카드. EXPLAIN 팝업 +27키(46→73), work/admin kicker 재번호(1/7·1/5), 표지·목차·chrome 배지에 대상 클라이언트(작업 화면 + 관리 콘솔) 명시, outro 로드맵 갱신.
  - `docs/presentation/practitioner.html` (작업화면 only) — 9→12 슬라이드. 작업화면 면 신규 3(실패 고치기·피드백·그룹 대화) + 릴리즈 노트 tip. EXPLAIN +13키(23→36). 관리콘솔 면 기능 **미포함**(티어 분리). 표지·목차 대상 명시 보강.
  - `docs/presentation/SCENARIO.md` — §0.5 덱 라우팅 가이드(어느 덱을 누구에게) 신설 + 신규 기능 스크립트(작업화면 F/G/H, 관리콘솔 3-7/3-8) + §1 인덱스·§5 정합성 주석·§6 로드맵 갱신.
  - `docs/presentation/OBJECTION-HANDLING.md` — §6.5 신규 기능 Q&A 3건(그룹 대화 데이터 노출·피드백 학습 오염·메타데이터 오등록) + §7 빠른참조 표 3행.
- **grounding (정합성)**: 모든 신규 기능을 실제 구현과 대조 — 그룹 대화(feature-0009 라이브) · ‘AI 로 고치기’(ITEM-08 `POST /api/conversations/{cid}/fix-with-ai`, 1회 dispatch·nonce 봉인 인젝션 방어) · 답변 피드백→샘플 검수 큐(sample feedback flywheel, `kb.sample.curate`, 자동학습 없음) · 메타데이터(ITEM-11 glossary/enum, `kb.ingest.manual` 게이트) · 제품 인사이트(db-insights 3-state). Google Drive(비활성 scaffold)·하이브리드 검색(gated-OFF)은 **로드맵에만 정직 표기**(구현된 것처럼 미서술).
- **panel (AGENT-TEAM, 적대적 4축)**: ① 정합성(구현 대조) 0 BLOCKING — do_not_claim 가드 전부 준수(AR-1 열람≠발화 정확, 1회 재실행, 👎 자동강등 미구현 미주장 등). ② 티어 분리 0 BLOCKING — practitioner 에 관리콘솔 UI 누출 0, ‘admin’ 어휘 0. ③ HTML/JS 유효성 — BLOCKING 1(검수큐 ‘승인’ 버튼 `.composer .send` 스코프 밖 → primary 채움 누락) **수정**(인라인 background/color 명시). ④ 톤/카피 — BLOCKING 1(표지 본문에 발표자向 명령문 ‘…안내하세요’+파일명 노출) **수정**(청중 대상 서술형으로 교체, 발표자 라우팅은 SCENARIO §0.5 로 일원화). NIT(o-prog/o-todo 팝업 동기화·알림=브라우저 명확화·md-accuracy 확률적 표현·fb-vote best-effort·예시화면 중복·admin-link→topbtn·발신자 이름 대비) 전부 수정. 수용 NIT: info-overload(frag 단계공개로 통제, 렌더 확인) · message-actions 클래스 미정의이나 인라인 스타일 동반(정상 렌더).
- **render-verified**: Playwright(chromium) headless 로 양 덱 로드 — **콘솔 에러 0**, 슬라이드 20/12, totNum 동적, data-explain↔EXPLAIN 1:1(차집합 0), 팝업 개폐 정상, 신규 슬라이드 9종 스크린샷 육안 확인(레이아웃 무파손).
- **Human Approval Needed**: 아니오 (additive 발표 docs, 사용자 지시 resume — 기존 의도 완수, 신규 scope 없음).
- **deploy**: 해당 없음 — `docs/presentation/*` 는 라이브 서빙 자산 아님(배포 스크립트 무참조). 완료 = main 병합.

## REV-20260624T115856-resume-claude-corp-root [SKIPPED:additive-meta-tooling]

- **cycle**: META-0006-resume-claude-corp-root — `/_template:resume` 가 스캔하는 세션 루트에 `/home/claude-corp/.claude` 추가
- **changeset (pure-meta)**:
  - `.claude/commands/_template` gitlink a08bf56→ff723fe (personas PR#4) — 정본 `resume.md`: no-arg 목록·arg-given 키워드 추적·Phase 1 slug surface·Phase 3A·3B bash·권한 서술을 두 Claude home 루트(`/root/.claude`, `/home/claude-corp/.claude`) 합산으로 확장(brace-expansion `{/root,/home/claude-corp}`)
  - `.codex/commands/_template/resume.md` (Codex shim) — no-arg 설명 동기화
- **panel skipped 사유 (§18.4 additive meta-tooling carve-out)**: 스킬 문서에 2번째 세션 루트 경로를 additive 추가. 신규 판단 로직·production 동작 0, 없는 루트는 `2>/dev/null` 로 무해(project-agnostic 유지). 비파괴·additive·meta-class 라 독립 패널 불요.
- **note**: 실측상 본 소비자 프로젝트 세션이 `/home/claude-corp/.claude/projects/` 에 저장돼 있어 기존 단일 루트(`/root/.claude`) 스캔이 통째로 누락하던 것을 교정. `.codex/skills/_template-resume/SKILL.md` 는 경로 미언급(정본 위임)이라 변경 불요.

## REV-20260619T024257-dqa-skill-suite [SUBAGENT:dqa-skill-design-review]

- **cycle**: ai/claude/dqa-skill-suite — `/_dqa` 개선 파이프라인 스킬 3종 + 부속 구조 신설
- **changeset (pure-meta)**:
  - `.claude/commands/_dqa/{improve_research,improve_listup,improve_cycle,README}.md`
  - `docs/improvements/_TEMPLATE-ROADMAP.md`
  - `docs/improvements/dba-ai-nl2sql/{RESEARCH,ROADMAP}.md` (seed)
- **panel**: 독립 general-purpose 리뷰어 1, 적대적 검토(거버넌스 충돌·스크립트 인터페이스·핸드오프·스케줄 안전성·종속성 모델·0맥락 계약).
- **verdict (1차)**: **NOT-SHIP** — BLOCKER 2 + MAJOR 4 + MINOR 3.
- **findings → 조치**:
  - **B1** (improve_cycle 가 `/loop` 전용 ScheduleWakeup 에 의존 → 범용 스케줄 부적합) → allowed-tools 에서 제거. Phase 6 을 "1 호출 = 1 항목, 연속 소진은 외부 wrapper(`/loop`·`/schedule`=CronCreate)" 로 외부화.
  - **B2** (cycle-init `--feature <item-slug>` ↔ verify-completion `<feature-id>` 불일치 → 구조적 미통과) → ROADMAP 항목 스키마에 `feature_id` 필드 신설. improve_cycle 이 양쪽에 동일 사용. unit doc(TASK/MODIFY/FUNCTION/ANCHOR/REVIEW) 갱신 단계를 Phase 3~5 에 명시.
  - **M1** (worktree 내부에서 `repo/` prefix 오류 → 0맥락 착수 시 "파일 없음") → 정본/코드 경로를 repo-상대(`AGENTS.md`·`unit/...`·`docs/...`)로 통일. ROADMAP entry_points·skill 본문·RESEARCH 정합화.
  - **M2** (무인 모드가 Major 를 plan-only 로 우회 → §7.1/§12.3 승인 게이트 위반) → 무인 모드는 **Minor 만 자율**, Major/Critical 은 `blocked: needs-human-plan-approval`.
  - **M3** (ROADMAP status 단독 doc-only 커밋이 META check #9 미충족) → status 갱신을 feature cycle 커밋에 동봉(별도 doc-only 커밋 회피); 불가피 시 `[SKIPPED]` 엔트리 절차.
  - **M4** (ready 선택 로직 모호 → starvation 가능) → 단일 규칙 확정: ready=(pending ∧ deps done), 정렬 Phase asc → risk asc → id asc. Phase=권장(배리어 아님) 합의.
  - **m1** (`in-progress(awaiting-merge)` status enum 외) → `status: in-progress` + `note: awaiting-merge PR#n`.
  - **m2** (`.codex` 미러 부재) → 의도(Claude 전용) — README 명시.
  - **m3** (research/listup 산출의 worktree 책임 공백) → 산출도 worktree 에서 작성(§13.2.7 F0) 명시.
- **verdict (2차, 조치 후)**: SHIP-WITH-FIXES — BLOCKER/MAJOR 전건 반영. 잔여 MINOR 없음(전건 조치).
- **note**: 본 묶음은 메타-도구(스킬 정의)로 비파괴 추가. 실제 ROADMAP 항목 구현은 각 `improve_cycle` 호출이 독립 feature cycle 로 verify-completion 게이트를 거친다.

## REV-20260619T030718-dqa-skill-suite [SKIPPED:additive-meta-tooling-docs]

- **cycle**: ai/claude/dqa-skill-suite (2차 commit) — 파이프라인 가동 + 추가 구조
- **changeset (pure-meta)**:
  - `docs/improvements/dba-ai-nl2sql/RESEARCH.md` — `## Round 2` append(F-015~F-019: enterprise 벤치마크·safety lower-bound·동적 few-shot·분해·NL rewriter + 채널 C 내부 히스토리 정합).
  - `.claude/agents/improve-fit-reviewer.md` — improve_listup 전용 적대적 정합 리뷰어(REV-1 패널이 쓴 6축 기준을 subagent 로 codify).
  - `CLAUDE.md` — Skill routing 에 `/_dqa:*` 1블록 등록.
- **panel skipped 사유 (§18.4 doc/meta-tooling carve-out)**: ① Round 2 = RESEARCH 에 findings append 만(ROADMAP/코드 무변경, 신규 production 동작 0) ② fit-reviewer agent = REV-1 에서 이미 검증된 패널 기준의 codify(신규 판단 로직 아님) ③ CLAUDE.md = 1블록 라우팅 추가. 비파괴·additive·meta-class 라 독립 패널 불요.
- **note**: Round 2 의 F-016(safety lower-bound 거부 평가축)·F-015(execution-based 벤치마크)는 차후 `improve_listup` 가 ITEM-01 acceptance 로 fold 예정(현재 RESEARCH 에만 적재 — research↔listup 단계 분리 준수).

## REV-20260619T032212-dqa-drain-mode [SUBAGENT:dqa-drain-mode-review]

- **cycle**: ai/claude/dqa-drain-mode — `/_dqa:improve_cycle` 드레인 모드 추가(no-arg → ready 항목 종속/순차 전체 구현)
- **changeset (pure-meta)**: `.claude/commands/_dqa/improve_cycle.md`(드레인 모드 + 실행모드 섹션 + Phase 6 + 종료조건) · `README.md`(정합 갱신)
- **panel**: `improve-fit-reviewer` subagent(첫 자가 사용). 적대적 검토 — 거버넌스 우회/외부영향 confirm/무인 안전선/종속 무결성/단건 회귀.
- **verdict (1차)**: **SHIP-WITH-FIXES** — MAJOR 3 + MINOR 2.
- **findings → 조치**:
  - **MAJOR-1** (시퀀스 batch 승인이 9개 Major 의 §7.1 개별 plan-review 를 대체=우회) → 드레인 승인을 **orchestration 메타승인으로 한정**(자동전진+Minor+commit/push 만 인가). 각 Major 는 항목 차례에 file/symbol/acceptance plan→PLAN-APPROVED 개별 유지.
  - **MAJOR-2** (불변제약 §외부영향 confirm ↔ "batch 가 per-item PR/머지 인가" 자기모순 + 전역 PR-confirm 이탈) → batch consent 에서 **PR 생성·머지·deploy 제거**. 항목별 confirm 유지.
  - **MAJOR-3** (무인 모드 판별 미정의 = fail-open 위험) → **fail-closed 기본값**: `--unattended` 명시 신호 또는 게이트 미응답이면 자동 진행 안 함(Minor-only 강등·blocked).
  - **MINOR-1** (종속 재로드 위치 모호) → 의사코드에 `cd main_worktree; git pull --ff-only; reload ROADMAP`(§13.2.5) 명시.
  - **MINOR-2** (STOP 분기 `continue` 누락·진행성 가드 일반화) → `continue` + `no_progress` 카운터로 교착 종료.
- **verdict (2차, 조치 후)**: SHIP-WITH-FIXES — MAJOR/MINOR 전건 반영. 단건 모드 회귀 없음(reviewer 통과).
- **note**: 드레인은 orchestration 만 자동화, 거버넌스 게이트(Major plan-review·Critical confirm·PR/deploy)는 항목별 유지 — "전체 자동 구현"이되 §7.1/§12.3/외부영향 confirm 불변.

## REV-20260623T055339-resume-codex-mirror [SKIPPED:additive-meta-tooling-codex-mirror]
- **cycle**: ai/claude/META-0001-resume-codex-mirror — `/_template:resume` 정본(personas submodule)의 소비자측 동기화 = submodule 포인터 bump + Codex 미러 2종.
- **changeset (pure-meta)**: `.claude/commands/_template`(gitlink 7f3ae74→a08bf56, personas PR#3 머지 반영) · `.codex/commands/_template/resume.md`(Codex shim, 정본 포인터) · `.codex/skills/_template-resume/SKILL.md`(Codex skill discovery wrapper) · `meta/REVIEW.md`(본 entry).
- **panel SKIP 사유**: 정본 `resume.md` 의 설계·정확성은 personas PR#3 직전 **5개 적대적 리뷰어 패널**(요구사항·거버넌스·스니펫 실측·엣지케이스·project-agnostic)로 이미 검증·수정 완료(FAIL 1 + leak 4 + nit 다수 반영). 본 소비자측 changeset 은 (a) 검증된 정본을 가리키는 thin shim/wrapper + (b) 머지된 업스트림 커밋으로의 포인터 bump 뿐 — 신규 로직 0, 행동 차이 0. §18.8 additive-meta-tooling 경량 경로 → SKIPPED.
- **verification**: Codex shim 상대경로(`../../../.claude/commands/_template/resume.md`) resolve 확인, SKILL.md `name: _template-resume`(하이픈)·description 형식이 기존 `_template-entry` 와 정합. gitlink 대상 a08bf56 은 personas origin/main(PR#3 머지)에 존재 → submodule fetch 가능.
- **Human Approval Needed**: 아니오 (additive meta tooling, 정본 패널 검증 완료, 사용자 전체 전파 승인).


## REV-20260623T092428-doc-sync-skill [SKIPPED:additive-meta-tooling-docs]

- **cycle**: ai/claude/doc-sync-skill — `/_dqa` 묶음에 standalone maintenance persona `doc_sync` 신설(머지 작업↔정책문서·wiki·릴리즈노트 drift 정합)
- **changeset (pure-meta)**:
  - `.claude/commands/_dqa/doc_sync.md` (신규 skill 본문 — frontmatter~종료조건)
  - `.claude/commands/_dqa/README.md` (`## 부가: 유지보수 persona (doc_sync)` 섹션 추가 — 파이프라인 표/다이어그램 불변)
  - `CLAUDE.md` (Skill routing 의 `/_dqa` 블록에 doc_sync 라우팅 1줄)
- **panel skipped 사유 (§18.4 doc/meta-tooling carve-out)**: skill 정의(.md)·README·CLAUDE.md 라우팅의 비파괴 additive 추가로, 신규 production 동작 0·코드 무변경. 신규 standalone persona 의 거버넌스 정합성은 독립 fit/convention/agnostic/repro 리뷰(아래 findings)로 이미 검증됨 → 별도 패널 불요.
- **review findings → 조치 (BLOCKER/MAJOR 전건 반영)**:
  - **B1·B2(repro·fit, verify META-mode 전제 거짓)**: 릴리즈노트는 `unit/feature-NNNN/src/static/...`(operational) 라 META mode 아님(`is_meta_path` 폴스루 실측). 불변 제약에 "타깃별 commit 분류" 신설 + Phase 4 를 (a)pure-meta META mode / (b)릴리즈노트 포함 operational gate 두 갈래로 재서술. 릴리즈노트 commit 은 owning feature-id 로 verify, 충족 불가 시 owning cycle 위임 정직 보고.
  - **B3(fit·repro, verify 인자 `META`)**: bare `META`/`<feature-id-or-META>` 가 `validate_feature_id` 정규식 미충족(die). 정규식 적합 `META-NNNN-<slug>` 발급 의무 + pure-meta short-circuit 발화 순서(`:1180`<`:1210`) 명시. bare META 예시 전면 제거.
  - **B4(repro, REVIEW entry path)**: pure-meta → `meta/REVIEW.md`, operational feature-bound → `unit/<fid>/docs/REVIEW.md` 분리 명시. entry 헤더 정규식(`REV-YYYYMMDDThhmmss-<branch> [SKIPPED|CODEX|...]`) 박음.
  - **M(convention, README/CLAUDE.md 미등록)**: README 에 maintenance 전용 섹션(파이프라인 표 밖) 추가, CLAUDE.md `/_dqa` 블록에 라우팅 1줄 추가.
  - **M(agnostic, project-specific 토큰 하드코딩)**: `feature-0009`·`WEB_PORT=18080`·`pgbouncer`·`repo-web-1`·`?v=20260623-rn-0623`·`verify_release_notes.mjs`·`WIKI_FEATURE_CARD`·`releases[0]`·`work/admin/common` enum·`/healthz` 전부 제거 → 카테고리 일반 서술 + "매번 discovery" 행동지시로 치환.
  - **M(repro, Phase 6 TLS/서비스 discovery)**: TLS 종단 discovery + `curl -k https→http fallback` + 서비스키/컨테이너명 discovery(`docker compose ps`) + `--no-deps` surgical rebuild + make-init 우회 명시.
  - **M(repro, no-delta 종결)**: 전 타깃 delta 0 시 브랜치·commit·verify 없이 early-exit("모두 최신") — 빈 changeset landing 도달 금지(불변 제약 + Phase 1 + 종료조건).
  - **MINOR/NIT 반영**: §13.1 ARCHITECTURE 색인 한정·신규 ADR 본문 금지(색인만); `/_template:entry`·`/document-release` 와 idempotency 경계 단락; §13.2.7 canonical worktree add(repo-상대 path) 인용; SKIP 토큰 `[SKIPPED:non-policy-doc]` vs `[SKIPPED:<슬러그>]` 구분; `git add -A/./-u` 금지 + `.env*.bak*`·`artifacts/`·`.worktrees/` 디코이 명시 + `git status` 확인; ACL setfacl 은 EACCES+`getfacl` 검출 게이트 후에만; wiki feature 수 정합 grep recipe(`ls -d unit/feature-*|wc -l` ground-truth) 명시; 정책문서 미구성/first-sync skip 분기; `pipeline_stage: standalone (maintenance)` + persona intro 어휘를 sibling("파이프라인") 정합.
- **잔여 MINOR(미반영, 사유)**: frontmatter `target_project: mysql_ai_delegated_dev` 유지(sibling 3종 동일 house-style — 묶음 일관성 우선, 런타임 무영향). `pipeline_stage` 자유형 값(`standalone (maintenance)`)은 의도적(번호 단계 아님 — 기존 `N/3` parser 와 불일치는 수용).
- **verdict**: SHIP-WITH-FIXES — BLOCKER 4 + MAJOR 7 전건 반영, MINOR/NIT 합리적 항목 전건 반영. 잔여는 house-style 메타데이터 2건(behavioral over-fit 아님).
- **note**: 비파괴 메타-도구(skill 정의) 추가. 실제 doc 정합 실행은 각 `/_dqa:doc_sync` 호출이 changeset 분류대로 verify-completion 게이트(META mode 또는 operational gate)를 직접 거친다.

## REV-20260624T005709-META-0003-ssot-consolidation [AGENT-TEAM:ssot-plan-redteam]

- **cycle**: ai/claude/META-0003-ssot-consolidation — SSOT 통합 initiative **Phase 0** (계약·레지스트리·lint 골격)
- **changeset (pure-meta)**:
  - `docs/DECISIONS.md` — ADR-0031 (SSOT 계약 4조) append
  - `docs/DOC_REGISTRY.md` — 신규 (도메인→정본 단일 지도, 기계가독)
  - `bin/ssot-lint.sh` — 신규 (WARN-only 골격 + `--selftest`)
  - `docs/improvements/ssot-consolidation/{RESEARCH,ROADMAP}.md` — 신규 (진단 + 0~5 강화 plan)
  - `meta/REVIEW.md` — 본 entry
- **panel (AGENT-TEAM)**: SSOT plan 적대 리뷰 workflow — 6 렌즈(SSOT 정합성·거버넌스 준수·런타임 안전성·누락·secret 처리·순서/실현성) × 독립 비평가, 적대 검증(refute 시도, 불확실시 기각), 강화 합성. 42 에이전트, raw 35 finding.
- **verdict**: SHIP-WITH-FIXES (Phase 0 한정) — 확정 16 / 기각 19, **BLOCKER 1**.
- **findings → 조치 (Phase 0 반영분)**:
  - **BLOCKER (#12 secret)**: 노출 secret `rm-only` 무의미(이미 origin/main+원격 브랜치+머지 PR push) → ADR-0031 §4 + `ssot-lint` 가 'tracked `.env*.bak*` 0건' 가드로 포착. rotation 1순위는 **Phase 3(META-0004, 사용자 rotation 진행 의사 확인)** 로 명시. Phase 0 자체는 secret 무변경.
  - **#9 (check #9 게이트 누락)**: 전 Phase 게이트에 verify-completion check #9(REVIEW.md) 추가 — 본 entry 가 첫 적용.
  - **#10/#16 (secret grep false pass/fail)**: ssot-lint 패턴 `(^|/)\.env[^/]*\.bak|\.bak-task[0-9]|\.secret\.bak` 로 3건 전수 검출 + `.example` 오탐 0 (`--selftest` 검증).
  - **#15 (.gitignore 글롭 부재)**: Phase 3 작업으로 명시.
  - **리뷰 오류 정정 (lint=ground truth)**: 리뷰가 지목한 wiki '거짓 SOT 2건(ADR-0005·Module-Map)' 은 실측 결과 `sot:false` — wiki `sot:true` 는 `wiki/Log.md` 1건뿐(정당). RESEARCH/ROADMAP/DOC_REGISTRY 정정.
- **gate**: `bash bin/ssot-lint.sh --selftest` **PASS**(오탐·미탐 0) + 실제 스캔이 secret 3건 + GOAL.md(archived) 검출(baseline — P1·P3 해소 예정). 신규 문서만 추가(비파괴).
- **Human Approval Needed**: Phase 0 = 비파괴 계약/골격 (사용자 "commit 후 Phase 1 계속" 승인). Major(P1 STATUS 인덱스화)·Critical(P3 secret)은 차례에 §12 별도 승인.
- **note**: 적대 리뷰 전문: `docs/improvements/ssot-consolidation/RESEARCH.md §4`. Phase 0 는 계약·강제 도구만 — 실제 정본 정리/노출 종료/코드 재배치는 P1~P5 가 각자 게이트를 거친다.

## REV-20260624T010743-META-0003-ssot-consolidation [SKIPPED:meta-docs-archive]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 1a** (stale 문서 아카이빙 + archive 위치 교정)
- **changeset (pure-meta)**:
  - `GOAL.md`(루트) → `docs/archive/GOAL.md` (R100 rename), `docs/OBSERVATIONS.md` → `docs/archive/OBSERVATIONS.md` (R100) + frontmatter `lifecycle: archived`
  - `docs/archive/README.md` 신규 (아카이브 보관소 색인)
  - `docs/DECISIONS.md` — ADR-0031 Addendum (archive 위치 `docs/_archive/`→`docs/archive/` 교정, 사유: `.gitignore:27` `_archive/` 무시)
  - `docs/DOC_REGISTRY.md` · `docs/improvements/ssot-consolidation/ROADMAP.md` · `bin/ssot-lint.sh` — `_archive`→`archive` 정합
- **panel SKIP 사유 (§18.4 doc/meta carve-out)**: 신규 production 동작 0. (1) GOAL.md 아카이빙은 STATUS.md(TASK-0133)가 이미 결정·기록한 의도의 물리적 완성(정본 변경 아님), (2) OBSERVATIONS 는 stale 스냅샷 격리, (3) archive 위치 교정은 gitignore 충돌 해소(기계적). rename R100(내용 무변경) + frontmatter only.
- **verification**: `bash bin/ssot-lint.sh --selftest` **PASS**. 실제 스캔 archived **0건**(이전 GOAL.md 1건 해소), secret 3건은 Phase 3(META-0004) 대상으로 잔존. staged changeset pure-meta(루트 비-meta 0). GOAL/OBSERVATIONS 참조는 전부 과거 이력 prose(코드 import 0) — 링크 무결성 영향 없음.
- **Human Approval Needed**: 아니오 (비파괴 아카이빙, 정본 무변경). Major(P1b STATUS 인덱스화)·Critical(P3 secret)은 차례에 §12 별도 승인.

## REV-20260624T012043-META-0003-ssot-consolidation [SKIPPED:status-index-verbatim-preserved]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 1b** (STATUS.md 인덱스화, Major §12.3)
- **changeset (pure-meta)**:
  - `docs/STATUS.md` — 290KB → **4.6KB** lean 인덱스(feature별 상태 1줄 + 정본 링크 + 1줄 요지). 누적 rollup·heavy 셀 제거
  - `docs/archive/STATUS_ARCHIVE.md` 신규 — 인덱스화 이전 STATUS verbatim 보존(cmp IDENTICAL) + archived frontmatter
  - `meta/REVIEW.md` — 본 entry
- **risk**: Major (정본 재정의 — 현황 상세 정본을 STATUS→`unit/<f>/docs/{TASK,REPORT}` 로 명시 이동). **plan-review 수행**(사용자 미결정 #2 = "STATUS_ARCHIVE 보존 후 인덱스화" 선택).
- **panel SKIP 사유**: 비파괴 — 전문 verbatim 보존(`cmp -s` IDENTICAL, rollup 159줄 유지)으로 **정보 손실 0**. STATUS 는 정책문서(AGENTS/CONVENTIONS/SECURITY) 아님(§18.8.1 경량 대상). 신규 production 동작 0. 정본 위계는 ADR-0031 + DOC_REGISTRY 가 정의.
- **verification**: STATUS.md 4,682 bytes(<30KB 성공기준 충족). 내부 링크 6개(unit TASK ×9, STATUS_ARCHIVE, DOC_REGISTRY, DECISIONS, ARCHITECTURE) 전부 타깃 존재 확인. ssot-lint archived 0건(STATUS_ARCHIVE 가 docs/archive/ 내 → skip), secret 3건 잔존(P3). feature-0009 cross-cut·feature-0010 worktree 미병합 명시.
- **Human Approval Needed**: 아니오 (사용자 plan-review + 미결정 #2 승인 완료, verbatim 보존으로 비가역성 없음). 원복 = git revert(미머지).

## REV-20260624T013056-META-0003-ssot-consolidation [SKIPPED:additive-meta-docs]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 3 prep** (secret 노출 종료 turnkey 런북)
- **changeset (pure-meta)**: `docs/improvements/ssot-consolidation/SECRET-ROTATION-RUNBOOK.md` 신규 + `meta/REVIEW.md` 본 entry
- **panel SKIP 사유**: 비파괴 additive 문서(런북). 코드/secret/config 무변경 — 실제 rotation 은 사용자/feature-owner cycle 이 수행. 노출 표면은 값 비노출로 키 이름만 확인(`git show HEAD:<bak> | sed 'KEY 추출'`).
- **노출 분류 (값 비노출)**: `.env.bak-task0211/0279` = MySQL/PG/admin/LLM/MSSQL 자격증명, `.env.secret.bak-task0228` = `AGENT_DATASOURCE_KEK_V1`. `.env.secret` 본체·MinIO 비밀값은 추적 안 됨(무해). origin = 외부 GitHub.
- **AI 자율 비실행 근거**: ① 라이브 데이터 보호 자격증명(오조작=DB 잠김) ② KEK = re-encryption 마이그레이션(값만 교체 시 데이터소스 cred 전소실) ③ 외부 계정(MSSQL/AWS/GitHub). → 런북으로 turnkey 화, 실행은 eyes-on.
- **Human Approval Needed**: rotation 실행은 사용자(또는 feature-owner cycle, KEK re-wrap). 본 commit(런북 문서)은 비파괴 prep.

## REV-20260624T013734-META-0003-ssot-consolidation [SKIPPED:additive-meta-docs]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 2** (in-flight worktree 현황 흡수 정책 명문화)
- **changeset (pure-meta)**: `docs/DOC_REGISTRY.md`("In-flight worktree 현황 흡수" 정책 + 미해소 잔여 갱신) · `docs/improvements/ssot-consolidation/ROADMAP.md`(ITEM-P2 status→done) · `meta/REVIEW.md` 본 entry
- **조사 결과(실측)**: `git worktree list` + ahead/behind 측정 — 현행 worktree(feature-0002, gc-share-group-sync, 06-24)는 **ahead=0**(작업 main 머지 완료) → 미머지 in-flight 작업 0, STATUS 인덱스화와 **충돌 위험 0**. stale leftover 3개(attach-cutover/conn-health/task0232, 258~417 behind, 06-12~15 방치)는 흡수 대상 아닌 정리 대상.
- **정책**: 미머지 worktree 현황 정본 = 그 worktree 의 unit TASK/REPORT; STATUS 인덱스는 main 머지 기준 + 미머지는 note 표기; 머지 시 행 갱신. (적대 리뷰 #11 의 "in-flight 마이그레이션 규칙 부재" 해소)
- **panel SKIP 사유**: 비파괴 additive 정책 문서. 코드/secret 무변경. 흡수할 실제 in-flight 작업이 없음(ahead=0)을 실측 확인.
- **Human Approval Needed**: 아니오 (정책 명문화). stale worktree 정리(`worktree remove`)는 운영 잔재 정리 시 별도 수행.

## REV-20260624T015428-META-0003-ssot-consolidation [SKIPPED:meta-verify-and-scope]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 1c**(거버넌스 포인터 검증) + **ROADMAP P5a/P5b 분리**(사용자 요청)
- **changeset (pure-meta)**:
  - `docs/improvements/ssot-consolidation/ROADMAP.md` — ITEM-P5 → **P5a(코드 파편화/SSOT 중복·경계, Major)** + **P5b(코드 비대화/모놀리스 분할, Critical, 신규)**; Phase 표·종속성 그래프·ITEM-P1 status 갱신
  - `CLAUDE.md`·`GEMINI.md` — `lifecycle:reference` + `source_of_truth:false` + `sources:[AGENTS.md]` frontmatter 추가(기계가독 포인터 선언)
  - `docs/DOC_REGISTRY.md` — AI 운영 정책 행 정정
  - `meta/REVIEW.md` — 본 entry
- **Phase 1c ground-truth 결과 (3번째 phantom 교정)**: "CONVENTIONS §3.1/§7 ↔ AGENTS §3.1 중복 흡수"는 **실재하지 않음** — CONVENTIONS 에 §3.1 자체가 없고 §7 "AI 에이전트 매핑"은 이미 깨끗한 포인터("정본=../AGENTS.md"); GEMINI.md line35 "AGENTS.md 를 가리키는 참조 역할만"; AGENTS.md 의 ADR 언급 8건 전부 **참조 링크**(본문 복제 0). → **거버넌스 dedup 불요, AGENTS.md 본문 무편집**(우려한 §18.8.1 codex-review 트리거 미해당). 실제 작업 = 포인터 문서 reference frontmatter 추가뿐.
- **P5 분리 근거 (사용자 검토 승인)**: 실측 `app.py` 25,823줄/146 endpoint(모듈 5개), 프론트 admin/app.js·styles.css ~25K. "비대화된 코드"는 사용자 원 요청 포함이나 **SSOT(중복) 아닌 모듈화 문제** → P5b(Critical, 라이브 web app, test 54파일 안전망, 점진 추출, 별도 cycle/initiative). doc-SSOT cycle 번들 금지.
- **panel SKIP 사유**: 검증(ground-truth) + 비파괴 frontmatter/계획 문서. 코드·정책 semantic 무변경.
- **Human Approval Needed**: 아니오. P5b 실제 실행은 Critical → 별도 cycle plan-review + §12 승인.

## REV-20260624T015752-META-0003-ssot-consolidation [SKIPPED:additive-meta-docs]

- **cycle**: ai/claude/META-0003-ssot-consolidation — **Phase 4** (wiki 참조-only 체계화)
- **changeset (pure-meta)**: `wiki/README.md`(§5.1 신설) · `wiki/Log.md`(append, wiki 규약) · `docs/improvements/ssot-consolidation/ROADMAP.md`(ITEM-P4 done) · `meta/REVIEW.md` 본 entry
- **ground-truth 결과**: wiki 는 **이미 reference-only** — README §2/§6 이 "wiki 는 source of truth 아님, 정본 우선" 명시, 전역 `sot:false`(lint: 위반 0, 예외 Log.md ledger). 거버넌스·STATUS 와 동일하게 코어는 이미 양호.
- **실제 작업(gap 메움)**: README §5.1 신설 — SSOT 계약(ADR-0031)·정본 지도(DOC_REGISTRY) 연결 + **동기화 메커니즘 명시**(정본 변경→wiki 갱신 = `/_dqa:doc_sync` persona, 결정론 렌더러 없음 = LLM-persona 유지[적대 리뷰 권고 b], 구조 drift = `wiki-lint`) + stale 카드 maturity 라벨 정책.
- **deferred(점진)**: 85파일 mirrors/sources frontmatter 백필 + stale 카드(0001/0004~0007) 라벨 = `/_dqa:doc_sync` 가 주기 수행(mechanical, 저가치-고노력이라 일괄 미실행).
- **panel SKIP 사유**: 비파괴 additive 정책 문서 + 검증. 코드/secret 무변경.
- **Human Approval Needed**: 아니오.

## REV-20260624T024525-doc-sync-ssot-align [SKIPPED:additive-meta-tooling-docs]

- **cycle**: ai/claude/META-0005-doc-sync-ssot-align — `/_dqa:doc_sync` 스킬을 ADR-0031 SSOT 계약(STATUS=인덱스)에 정합
- **배경**: doc_sync(PR#386)는 STATUS=누적 rollup 전제로 작성됐으나, 이후 ADR-0031(PR#395, META-0003)이 STATUS 를 290KB rollup → 4.6KB **인덱스**로 강등(상세 정본=unit docs, 누적 이력=`docs/archive/STATUS_ARCHIVE.md`, 도메인→정본 지도=`docs/DOC_REGISTRY.md`, drift 강제=`bin/ssot-lint.sh`). 2026-06-24 cron 수동 검증에서 doc_sync 가 인덱스 STATUS 위에 rollup 을 또 얹어 **ADR-0031 §1 위반 산출물**(브랜치 doc-sync-0624 — 미머지 폐기)을 만든 것이 적발됨.
- **changeset (pure-meta)**: `.claude/commands/_dqa/doc_sync.md`
- **변경 요지**:
  - 불변 제약: "참조는 복제하지 않는다"(§2) + SSOT 계약 준수(STATUS 인덱스·셀 누적 금지·mirror 포인터) 추가.
  - Phase 0: SSOT 모델 판정(DOC_REGISTRY/STATUS frontmatter/archive/ssot-lint 신호 → 인덱스 vs 누적) discovery 추가.
  - Phase 3 STATUS: "rollup blockquote 추가" → **(a) 인덱스 모델**(행 갱신만·rollup 누적 금지·미머지 worktree note) / **(b) 누적 모델**(기존 rollup) 2분기. 불명 시 인덱스 보수 처리.
  - Phase 1/2: STATUS 매핑·스코프 질문 모델별 분기. Phase 4: ssot-lint PASS + 인덱스 rollup 미누적·행 ground-truth 정합 점검. 종료조건 항목 추가.
- **project-agnostic 유지**: ADR-0031 하드코딩 아님 — "SSOT 계약 채택 여부 discovery" + 누적 모델 fallback(SSOT 미채택 프로젝트 호환).
- **panel skipped 사유 (§18.4 carve-out)**: 검증된 기존 스킬을 신규 머지 ADR 에 맞추는 비파괴 alignment, 신규 production 동작 0. ADR-0031 §1~§4 · DOC_REGISTRY · STATUS.md 인덱스 포맷 정본 실측 대조.
- **verification**: grep — 무조건 "모든 작업 → STATUS rollup" 잔존 0, 인덱스/누적 2분기 공존, DOC_REGISTRY·ssot-lint 참조. verify-completion META mode.
- **Human Approval Needed**: 아니오 (additive meta-tooling alignment, 사용자 지시).

## REV-20260624T080555-ai-claude-META-0008-presentation-remove-fix-with-ai [SUBAGENT:design]

- **cycle**: ai/claude/META-0008-presentation-remove-fix-with-ai — 발표자료(`docs/presentation/*`) 개선 (사용자 직접 지시)
- **changeset (pure-meta)**: `docs/presentation/index.html` · `docs/presentation/practitioner.html` · `docs/presentation/SCENARIO.md` · `meta/REVIEW.md`(본 entry). (영업/소개용 정적 발표자료 — 제품 코드·secret 무변경.)
- **작업 1 — ‘AI 로 고치기’(fix-with-ai) 발표자료 전면 제거**: index 슬라이드 `[4b]`(작업 화면 4/7) + practitioner 슬라이드 `[5b]` 삭제, index 작업화면 kicker **7장→6장 재번호**(1/6~6/6), 마무리 타임라인·EXPLAIN(fx-* 7+4키)·SCENARIO 대본(시퀀스 F)·목차(7장→6장)·정합성 주석·덱 라우팅에서 관련 언급 제거. 사유(사용자): 내부 방어적 기능이라 클라이언트가 미완성/불안정 서비스로 받아들일 소지. 검증: 4파일 `grep "AI 로 고치기|fix-with-ai|fx-"` = 0, EXPLAIN JSON 유효성(index 66키·practitioner 32키, fx-키 0).
- **작업 2 — 그룹 대화 시각 결함 3건 수정**:
  - (a) `@assistant` 멘션이 파란 말풍선(--bubble-user #2563eb) 위 파랑 글자(--primary #2563eb)로 **불가시** → 동료 메시지를 좌측 흰 말풍선(`.msg.peer`)으로 분리 + 멘션 `.mention` pill(흰 배경=primary, 파란 배경=흰색)로 대비 확보.
  - (b) 발신자 **프로필 아바타 부재** → 각 메시지에 원형 아바타 + 발신자행(`.msg-sender`/`.msg-av`) 추가(소=초록·민=주황 이니셜, AI=파랑 그라데이션). 본인(소라)=우측 파란, 동료(민준)=좌측 흰, AI=좌측.
  - (c) 우상단 ‘⋯ 공유·설정’ 버튼이 **실제 제품과 불일치**(사용자 추가 지적) → 실제(feature-0003 `app.js:5938-5939`: 공유·설정이 사이드바 대화 `···` 메뉴로 일원화)에 맞춰 상단 버튼 제거 + 사이드바 대화에 `···`(gc-share) 이동, gc-share/tip 설명도 정합 수정. 상단 우측은 참여자 아바타 스택.
- **실제 제품 정합 검증 (Explore, feature-0003-agent-web-ui)**: 공유·설정=사이드바 `···` 메뉴(`app.js:5938`), 메시지 멘션=marked.js 평문 렌더(발표는 교육 목적상 강조 유지+대비 확보로 정합), 발신자=`.msg-avatar`(이미지/Identicon, AI=파랑). 상단 멤버 텍스트는 실제 미확인이라 아바타 스택으로 대체.
- **design 패널 (SUBAGENT, adversarial, 스크린샷 3장 정밀 검토)**: 판정 **FIX-FIRST**.
  - **반영**: 헤더 ‘멤버 2 · assistant’ 카운트 모호성(사람2+AI를 2토큰으로 뭉갬 + 실제 미확인 추측) → **참여자 아바타 스택**(소·민·AI 겹침)으로 교체. 재캡처 확인.
  - **deferred (발표 의도/전역 패턴 — 미반영, 근거 기록)**: ① 본인(파란) 말풍선의 멘션 케이스는 데모 시나리오(민준이 AI 호출)상 미등장 → `.msg.user .bubble .mention` 흰색 규칙은 방어적 보존. ② Assistant 말풍선 폭은 `.bubble` 전역 패턴(BEFORE부터) — 그룹대화 단독 변경 시 타 슬라이드와 불일치 우려로 보류. ③ 두 덱 제목/카피 차이는 **청중 차별화 의도**(index=일반 의사결정자, practitioner=실무자 온보딩).
- **시각 검증**: WSL Playwright headless chromium 으로 index·practitioner 그룹대화 슬라이드 before/after 캡처 — 멘션 가독성·발신자 구분·헤더 정상 확인(`/tmp/pcap/`). PB-0008 Windows 브리지는 relay 미기동(`doctor` ok:false)이나, 정적 발표 HTML 의 색·레이아웃 검증엔 headless 로 충분(화면 괴리 최소). 슬라이드 수 index 20→19·practitioner 12→11(슬라이드 삭제 반영).
- **panel**: SUBAGENT design 1관점(§18.8 UI/화면 → ux·design 매칭). 비파괴 발표자료, Minor.
- **Human Approval Needed**: 아니오 (Minor, 비파괴 docs, 사용자 직접 지시).

## REV-20260624T090355-ai-root-META-0009-presentation-title-rename [SKIPPED:trivial-text-rename]

- **cycle**: ai/root/META-0009-presentation-title-rename — 발표자료 제품명(제목) 표기 변경 (사용자 직접 지시)
- **changeset (pure-meta)**: `docs/presentation/index.html` · `docs/presentation/practitioner.html` · `meta/REVIEW.md`(본 entry). (영업/소개용 정적 발표자료 — 제품 코드·secret 무변경.)
- **변경 요지**: 제품명 한글 표기 **‘데이터 질문 어시스턴트’ → ‘데이터베이스 쿼리 어시스턴트’** (영문 ‘Database Query Assistant’ = DQA 의 직역). 제품명 표기 7곳 치환 — index.html 4곳(`<title>`·상단 브랜드·표지 `<h1>`·DESC.cover), practitioner.html 3곳(`<title>`·상단 브랜드·표지 `<h1>`).
- **유지(치환 안 함)**: 일반명사 ‘데이터 질문’(예: "사내 데이터 질문을 돕는", "대부분의 데이터 질문을 해결", 감사로그 액션 라벨, SCENARIO 대본) 4곳은 제품명이 아니므로 보존 — `grep` 으로 컨텍스트 확인 후 분리.
- **검증**: 구 제품명 잔존 0, 신 제품명 7곳(index 4·practitioner 3). WSL Playwright headless 로 표지 슬라이드 캡처 확인(브랜드·h1 정상 반영, `/tmp/pcap/title_after.png`).
- **panel SKIP 사유 (§18.4)**: 단순 표기 치환, 비파괴, 신규 동작 0. 구/신 문자열 분리(제품명 vs 일반명사)를 ground-truth grep 으로 검증.
- **Human Approval Needed**: 아니오 (Minor, 비파괴 docs, 사용자 직접 지시).

## REV-20260625T165205-ai-claude-doc-sync-20260625-163929 [SUBAGENT:doc-sync]

- **cycle**: ai/claude/doc-sync-20260625-163929 — `/_dqa:doc_sync` (06-25 머지 rollup, 베이스라인 e648ab0→HEAD b7862ef, PR#420~#436) 문서 정합. resume from doc-sync-20260625-160433(session-limit 중단 재개, 중단 세션은 delta 검출까지만·미커밋이라 idempotent 재실행).
- **changeset (pure-meta, META commit)**: `docs/STATUS.md` · `wiki/overview.md` · `wiki/Features/feature-0009-group-conversation.md` · `wiki/Log.md` · `wiki/hot.md` · `meta/REVIEW.md`(본 entry). (릴리즈노트 콘텐츠 + cache-buster 는 feature-0003 src/static operational → **별도 commit**.)
- **정합 요지**: ① STATUS 인덱스 행 0002(init 임베딩 지연 회귀 해소·한도 메시지 주체)·0003(역할/제품 프롬프트 자동작성·분석률 95% 자동완성·규칙 DB 커버리지·지식베이스 재편)·0011(P5a Step1~5c 완료·shim 4종 전량 제거) 06-25 승격 — 0009 는 자체 cycle 갱신분(09114ed) 유지. ② wiki/overview §2.1 표 **feature-0010/0011 행 누락 보강**(9→11행, ground-truth 정합) + 06-25 서사 ⑦~⑩. ③ feature-0009 카드 06-25 정합(안 읽음/@멘션 배지·메시지 좌우 정렬·owner 멤버 추방/차단). ④ Log append + hot.md refresh(actionable thread 보존).
- **SSOT 계약 준수**: STATUS 인덱스 모델 — rollup blockquote 추가 0(셀 누적 없음, ADR-0031 §1). mirror 정본 재서술 없이 행 요지·링크만.
- **타깃별 검증**: `node --check` release-notes-data.js OK · wiki feature 수 정합 grep(ground-truth `ls unit/feature-*`=11 = overview §2.1 표 11행 = Features 카드 11 = narrative "11-feature") · `bin/ssot-lint.sh` WARN-only(기존 tracked secret 백업 4건 — STATUS §3 블로킹·rotation 선행, 본 변경 무관 / wiki-sot 거짓SOT 0건) · 신규 wikilink 대상 카드(0010/0011) 존재 확인.
- **panel (SUBAGENT, adversarial 사실검증)**: general-purpose 1관점 — 환각/사실정확성/평이화/누락/STATUS정합 5축 대조(머지 커밋 + REPORT 실측). **VERDICT CLEAN** (BLOCKING 0). 부수 확인: 기존 hot.md "model_catalog…alias shim" 부정확 서술을 본 sync 가 정정. NIT 3건 비차단(의도된 06-24 서사 보존·정직한 잔여 drift 고지).
- **잔여 drift (정직 고지)**: `wiki/concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 후속 doc_sync 1회 필요(hot.md Active Threads 기록). 본 run scope 외(06-25 머지 drift 에 집중).
- **panel scope**: §18.8 — doc-only mirror/index 정합(핵심경로 코드 무변경)이나 사실 환각 위험이 있어 adversarial 1관점 수행. Minor·비파괴.
- **Human Approval Needed**: 아니오 (additive doc-sync mirror/index 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync 정책).

## REV-20260625T192007-ai-claude-doc-sync-20260625-192007 [SUBAGENT:doc-sync]

- **cycle**: ai/claude/doc-sync-20260625-192007 — `/_dqa:doc_sync` (no-arg 전 타깃 정합). 직전 doc_sync(163929, PR#420~#436 기준 16:55~17:01 콘텐츠 작성, 17:09 머지)가 그 **이후** main 병합된 06-25 user-facing 변경 5종을 브랜치 stale 로 누락 → 잔여 drift 정비. 베이스라인 HEAD=04862c0(PR#444 포함).
- **changeset (pure-meta, META commit)**: `docs/STATUS.md` · `wiki/Features/feature-0009-group-conversation.md` · `wiki/overview.md` · `wiki/hot.md` · `wiki/Log.md` · `meta/REVIEW.md`(본 entry). (릴리즈노트 콘텐츠 + cache-buster + feature-0003 companion docs 는 `unit/feature-0003/src/static` operational → **별도 commit**, owning feature-0003 operational gate.)
- **대상 머지(5)**: PR#440(908fade) 참가자 per-message 제품 선택·발화(REQ-GC-R7) · PR#438(1f370c4)+PR#444(334c858 R1) 처리 중 composer 비잠금/동시 run 고착·블로킹 해소 · PR#444(R3/R2) 1:1 인터럽트 재요청 + 그룹 @assistant 중복차단 · PR#437(1a69f70) @assistant 발신자 표시 정정 · PR#439(c8637f2) datasource 회로차단 사용자 안내 문구 분리(feature-0002).
- **정합 요지**: ① STATUS 인덱스 — feature-0002 행에 "회로차단 안내 문구 분리(고장 오인 해소)" 추가, feature-0009 행 라이브UX 절에 "composer 비잠금·1:1 인터럽트 재요청·그룹 중복차단" 추가(per-message 제품 선택은 직전 sync 가 이미 적재). ② feature-0009 카드 §2 상태·§3 핵심모델(열람≠발화에 per-message override 명시)·§3 라이브UX·§7 변경이력 정합. ③ overview 06-25 서사 ⑦(per-message 제품·composer)·⑩(동시 처리 고착·회로차단 안내) 보강. ④ hot.md Key Recent Facts/Recent Changes 보강(Active Threads 보존) + Log append.
- **SSOT 계약 준수**: STATUS 인덱스 모델 — rollup blockquote 추가 0(셀 누적 없음, ADR-0031 §1), 기존 행 요지에 절만 추가. mirror 정본 재서술 없이 요지·링크. `bin/ssot-lint.sh` WARN-only(기존 tracked secret 백업 4건 — STATUS §3 블로킹·rotation 선행, 본 변경 무관 / wiki-sot 거짓SOT 0 / archived 0).
- **타깃별 검증**: `node --check` release-notes-data.js OK(06-25 블록 9→14) · wiki feature 수 ground-truth 정합(`ls unit/feature-*`=11 = overview "11 개 feature"/"11-feature" = Features 카드 11 = _Index "11 개") · 변경 파일 12건 의도대로(디코이 .env*.bak*/.worktrees/artifacts 0) · cache-buster index/admin 양쪽 `?v=20260625c-rn-0625`.
- **panel (SUBAGENT, adversarial 사실검증)**: general-purpose 1관점 — 환각/귀속정확성/평이화·내부비노출/과장/누락 5축을 머지 본문 5건(908fade/1f370c4/c8637f2/1a69f70/334c858)과 전수 대조. **VERDICT CLEAN** (BLOCKING 0). 릴리즈노트 내부용어(myAskInFlight·_interruptCurrentRunForResend·KIND_THROTTLED 등) 누출 0, 누락 머지 0(PR#442 흡수·6104bf6 chore 제외 정당 확인).
- **잔여 drift (정직 고지)**: `wiki/concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 직전 sync 가 이미 고지한 항목, 본 run scope(06-25 머지 drift) 외. hot.md Active Threads 에 유지.
- **Human Approval Needed**: 아니오 (additive doc-sync mirror/index 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync 정책).

## REV-20260625T194905-ai-claude-doc-sync-autoland-policy [SUBAGENT:policy-coherence]

- **cycle**: ai/claude/doc-sync-autoland-policy-20260625-194905 — 사용자 직접 지시(2026-06-25): "`/_dqa:doc_sync` 는 백그라운드 실행 가능; 사용자 확인 없이 항상 PR→merge→배포까지 진행; 배포 누락은 장애." doc_sync 스킬 정의를 attended·unattended 무관 **외부영향 무확인 자동(PR→merge→deploy)** 로 전환하는 governance 정책 변경.
- **changeset (pure-meta, META commit)**: `.claude/commands/_dqa/doc_sync.md`(헤더 호출형태·불변제약 외부영향·Phase 5 Landing·Phase 6 배포·Phase 2 attended 한정·종료조건) · `.claude/commands/_dqa/README.md`(doc_sync 서브섹션 정책 bullet). 둘 다 `.claude/commands/*` = META path → verify META mode.
- **정책 요지**: ① landing/deploy 경로에서 AskUserQuestion(landing 분기·deploy confirm) 제거 — delta 있으면 `브랜치→분리 commit→push→PR→merge→ff-pull→cleanup` 끝까지 자동, 서빙 static 변경 시 배포 MUST. ② **§18.12(affirmative-required)·§12.2(deploy=confirm)의 doc_sync 한정 명시 override**(조문번호 인용) — '질문 표면 제거'가 아니라 affirmative-required 자체 면제. ③ 장애 경계 3분기: early-exit(delta 0)=정상 / META-only=배포 no-op 명시(silent skip 금지) / 서빙 static 변경 후 landing·배포 누락=장애. ④ unattended 시 Phase 2 content-scope fork 도 보수 기본값(질문 안 함), fail-closed 대기는 attended 한정.
- **게이트 불변(중요)**: verify-completion·BLOCKED 판정·worktree-first(§13.2.7 F0)·META commit 분류는 그대로 강제 — 자동화가 정확성 게이트를 우회하지 않음을 line 29·31 에 명문화(오히려 보강). override 는 외부영향 confirm 에만 한정.
- **panel (SUBAGENT, adversarial policy-coherence, 2 라운드)**: general-purpose 1관점 — 내부모순/과도완화/장애경계/참조정합(§18.12·§12.2·README·AGENTS)/표면화 5축. **1차 VERDICT ISSUES**(MAJOR 2: line16↔94 attended/unattended 정지 여지 + §18.12 조문 명시 override 부재·line29 열거 누락 / NIT 2: line33 silent-skip 모호·merge 표면화 토큰). **흡수 후 재검증 VERDICT CLEAN** — 4항목 전부 닫힘, 게이트 회귀 0(축2 게이트 방어는 명문화로 강화 확인).
- **검증 한계**: 정책 텍스트 변경(런타임 코드 무변경)이라 verify-completion 은 META mode check #9/#10/#11 만 — 정책 self-coherence 는 위 adversarial 2라운드로 직접 확인.
- **Human Approval Needed**: 아니오 (사용자 직접 지시의 skill-scoped 정책 변경, 텍스트-only·비파괴, 정확성 게이트 불변). 배포 불요(`.claude/commands/*` 는 서빙 산출물 아님).

## REV-20260626T080501-ai-claude-doc-sync-20260626-080501 [SUBAGENT:doc-sync]

- **cycle**: ai/claude/doc-sync-20260626-080501 — `/_dqa:doc_sync ultracode`(무인 스케줄, cron wrapper worktree, 전 타깃). 릴리즈노트 마지막 sync(a29a2f0 @ 2026-06-25 19:36) 이후 main 병합된 06-25 후속 버그픽스호(12 커밋, d90e1e2 까지)가 STATUS·wiki·릴리즈노트에 미반영 → 잔여 drift 정비. 베이스라인 HEAD=3e553e9(#455 포함).
- **changeset (pure-meta, META commit)**: `docs/STATUS.md` · `wiki/hot.md` · `wiki/Log.md` · `wiki/Features/feature-0009-group-conversation.md` · `meta/REVIEW.md`(본 entry). (릴리즈노트 콘텐츠 6항목 + cache-buster + feature-0003 companion docs 는 `unit/feature-0003/src/static` operational → **별도 commit**, owning feature-0003 operational gate.)
- **대상 머지(user-facing 6)**: 998376b 단계 보기 버튼 소실 수정 · 8728ade 좌측 대화 전환 크로스페이드 · 92753ab 공유 대화 join 불가(PG AmbiguousParameter) · 9b1dc16+36ad138+d90e1e2 안 읽음 배지 미감소 최종 근본원인(읽음 커서 id-space 불일치→항상 MAX(core_messages.id) 전진) · bec35bd @assistant 전송 후 입력창 미클리어 · feca44f assistant SQL dialect 교정+그룹 발신자 맥락 라벨(코드 agent-core/feature-0002, cross-cut 0009 귀속). 4737b76 optimistic 발신자 깜빡임 정정은 STATUS·wiki 반영(display-only flicker 라 릴리즈노트 제외).
- **정합 요지**: ① STATUS 인덱스 — feature-0009 행에 "공유 대화 join 수정·assistant dialect+발신자 맥락·optimistic 발신자 정정" 절 추가, feature-0003 행에 "좌측 대화 전환 크로스페이드·단계 보기 버튼 소실 수정" 절 추가(read-fix 계열 3건은 이미 셀 존재 — 중복 미추가). ② wiki hot.md — Recent Changes 의 gc-optimistic "(미머지)"→"(머지)" 정정 + 06-25 잔여 delta 1줄 보강 + last_updated 06-26(Active Threads 보존). ③ feature-0009 카드 §7 변경이력 1줄 append(2026-06-26). ④ Log.md rollup entry 1줄 하단 append(`## [2026-06-26] wiki-ingest …` [[feature-0009-group-conversation]]).
- **SSOT 계약 준수**: STATUS 인덱스 모델(ADR-0031 §1) — rollup blockquote 추가 0(셀 누적 없음), 기존 행 요지에 절만 append. mirror 정본 재서술 없이 요지·링크. `bin/ssot-lint.sh` WARN-only(기존 tracked secret 백업 4건 — STATUS §3 블로킹·rotation 선행, 본 변경 무관 / wiki-sot 거짓SOT 0 / archived 밖 0). delta 윈도(a29a2f0..HEAD)에서 ARCHITECTURE/SECURITY/DECISIONS/DOC_REGISTRY git diff 0건 → noChange(정직 무변경).
- **타깃별 검증**: `node --check` release-notes-data.js OK(06-25 블록 14→20) · wiki feature 수 ground-truth 정합(`ls -d unit/feature-*`=11 = overview/_Index/Architecture/Index "11" = Features 카드 11) · STATUS 테이블 행 무결성(삽입 텍스트 `|` 0 → 컬럼 보존) · 변경 파일 의도대로(디코이 `.env*.bak*`·`.worktrees/`·`artifacts/` 0) · cache-buster index/admin 양쪽 `?v=20260626-rn-0626`.
- **panel (SUBAGENT, ULTRACODE 3축 적대 워크플로)**: 타깃별(release-notes/STATUS/wiki) 분석가 → 적대적 검증자(각 변경안을 정본·코드·git diff 로 반증 시도) → 완전성 비평가(delta 12커밋 전수 커버리지 매트릭스). **VERDICT**: release-notes `pass`(rejected 0) · STATUS `pass`(replacesExisting 바이트 일치·인덱스 모델 준수 확인) · wiki `pass-with-corrections`(hot.md/카드 confirm; **Log.md 분석가 초안이 stale `[ts] op|role|path` 헤더+## Entries 직후 prepend 로 시간순 역전·실관례 위반 → 적대검증 REJECT → rollup 형식·하단 append 로 교정 적용**) · 완전성 비평 `go-with-fixes`(통째 누락 0; bec35bd 릴리즈노트 추가·Log 형식 교정 2건 land 전 반영 권고 → **둘 다 본 commit 에 반영 완료**).
- **잔여 drift (정직 고지)**: `wiki/concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 본 delta 윈도(06-25 후속 버그픽스) 밖 deferred 항목, hot.md Active Threads 에 유지(보존). conv-switch-fade(8728ade)의 feature-0003 `REPORT.md`(mirror) 미기재는 feature-cycle 소관(doc_sync 가 정본 미작성) — STATUS 인덱스 범위 밖 후속 권고로 유지.
- **검증 한계**: verify-completion 의 STATUS check(#5)·#1 은 v1.1 deferred 라 STATUS·wiki 정합을 보증하지 않음 → 위 타깃별 검증 + ULTRACODE 적대 워크플로로 직접 확인. landing(push/PR/merge)·deploy(서빙 static = 릴리즈노트 재배포)는 cron wrapper 소관(본 run 은 로컬 commit 까지).
- **Human Approval Needed**: 아니오 (additive doc-sync mirror/index 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책).

## REV-20260629T080501-META-0011-doc-sync-0629 [SKIPPED:doc-sync-index-mirror-backfill] — doc_sync 06-26 머지 backfill (STATUS 인덱스 + wiki 미러)
- **cycle**: ai/claude/doc-sync-20260629-080501 — `/_dqa:doc_sync`(스케줄 무인, 전 타깃, ULTRACODE). 직전 wiki sync(c11cc27 @ 06-26 08:36)·STATUS(f049fee 12:05) 이후 머지된 product-chip(f049fee)·ask-dedup(0818b0a/3595ea3)을 STATUS 인덱스·wiki 미러에 정합.
- **changeset (pure-meta, 전 파일 META path → verify-completion META mode)**: `docs/STATUS.md`(feature-0003 행 ask-dedup 1줄 append — product-chip 은 f049fee 가 이미 반영) · `wiki/hot.md`(Key Recent Facts/Recent Changes 에 product-chip·ask-dedup 2건 + last_updated 06-29, Active Threads 보존) · `wiki/overview.md`(06-26 서사 ⑪제품chip·⑫ask 중복 차단) · `wiki/Log.md`(하단 append 1줄) · `meta/REVIEW.md`(본 entry). 릴리즈노트(operational)는 별도 commit.
- **SSOT 계약 준수**: STATUS 인덱스 모델(ADR-0031 §1) — rollup blockquote 추가 0(셀 누적 없음), 기존 행 요지에 절만 append. mirror 정본 재서술 없이 요지·링크. `bin/ssot-lint.sh` WARN-only(기존 tracked secret 백업 — STATUS §3 블로킹·rotation 선행, 본 변경 무관). delta 윈도에서 ARCHITECTURE/SECURITY/DECISIONS/DOC_REGISTRY git diff 0건 → noChange(정직 무변경).
- **타깃별 검증**: `node --check` release-notes-data.js OK(별도 operational commit) · wiki feature 수 ground-truth 정합(`ls -d unit/feature-*`=11 = overview/Index/_Index "11") · STATUS 테이블 행 무결성(삽입 텍스트 `|` 0 → 컬럼 보존) · Log.md 하단 append(시간순 보존) · 변경 파일 의도대로(디코이 `.env*.bak*`·`.worktrees/`·`artifacts/` 0).
- **panel (SUBAGENT, ULTRACODE 적대 워크플로 6 에이전트)**: 완전성 비평가(독립 델타 재도출 — missedByOperator·operatorOverreach 모두 [], feature 수 11 정합, finalVerdict 일치) + ask-dedup/product-chip 콘텐츠 작성·현실정합(realityMatch:true) + 적대 반증 3종(completeness refuted:false · releasenote refuted:false·leaksInternals:false · nochange refuted:false — ARCH/SEC/DEC noChange 확정·product-chip RBAC 보존). ADR-WEB-0006 색인 보류(선별 MOC §2.1, ADR-WEB-0001/0003 도 미색인 — 패턴 일관).
- **잔여 drift (정직 고지)**: `wiki/concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 본 delta 윈도 밖 deferred, hot.md Active Threads 에 유지(보존).
- **검증 한계**: verify-completion 의 STATUS check(#5)·#1 은 v1.1 deferred → 위 타깃별 검증 + ULTRACODE 적대 워크플로로 직접 확인. landing(push/PR/merge)·deploy(서빙 static=릴리즈노트 재배포)는 cron wrapper 소관(본 run 은 로컬 commit 까지).
- **Human Approval Needed**: 아니오 (additive doc-sync mirror/index 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책).
