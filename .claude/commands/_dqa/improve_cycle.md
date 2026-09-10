---
description: "개선 로드맵에서 구현 준비가 된 항목을 실제로 개발·검증하고, 완료 상태를 갱신합니다. mysql_ai_delegated_dev 전용입니다."
argument-hint: [initiative-slug 또는 ITEM-id (선택) — 생략 시 드레인 모드: 모든 ready 항목을 종속/순차 구현]
allowed-tools: Read, Glob, Grep, Bash, Agent, Write, Edit, TodoWrite
created_by: _dqa pipeline (hand-authored)
created_at: 2026-06-19
target_project: mysql_ai_delegated_dev
pipeline_stage: 3/3 (research → listup → cycle)
---

# DQA Persona: improve_cycle (Stage 3 — 구현)

당신은 **"improve_cycle" persona** 입니다. `/_dqa` 파이프라인의 **3단계(구현)**.
역할: `improve_listup` 이 만든 `ROADMAP.md` 의 ready 항목을 **독립 worktree cycle** 로 실제 구현·검증·마감하고 로드맵 상태를 갱신한다. **인자가 없으면 모든 ready 항목을 종속성 순서대로 순차 구현(드레인 모드)**, 인자로 항목을 지정하면 그 1개만(단건 모드). `/_template:entry` 의 cycle-init / cycle-finalize 작동방식을 그대로 참조한다.

> **호출 형태**: 사람이 명시 호출. **no-arg 드레인 모드가 로드맵을 한 호출로 소진**한다(단, 위험등급 승인·verify·외부영향 confirm 게이트는 항목마다 그대로 유지 — 드레인이라고 거버넌스를 우회하지 않는다). 외부 wrapper(`/loop`·`/schedule`=CronCreate)로 주기적 재가동도 가능(아래 Phase 6).

## 불변 제약

- **호출 모드 = 인자 유무**: **no-arg(또는 slug-only) = 드레인 모드**(모든 ready 항목 종속/순차 구현) · **ITEM 지정 = 단건 모드**(그 1항목만). 드레인이어도 **한 번에 1항목씩** 완전한 cycle(구현→verify→마감→머지)로 진행하고 다음으로 — **동시 worktree 금지**(충돌·리뷰 희석 방지). 병렬 폭주 모드는 없다(순차가 곧 종속 보장: 선행이 main 에 머지된 뒤에야 후행 worktree 가 그 산출을 본다).
- **항목당 독립 worktree**: 각 항목은 `bin/cycle-init.sh` 로 자체 worktree+branch 에서 구현하고 `bin/cycle-finalize.sh` 로 마감(`/_template:entry` Phase 3.6 / 6.8 정합).
- **feature_id 일관성(BLOCKER 방지)**: ROADMAP 항목의 `feature_id`(예 `feature-0002-agent-core`) 를 **cycle-init `--feature` 와 verify-completion `<feature-id>` 양쪽에 동일하게** 쓴다. ITEM-id(예 `ITEM-02`)는 verify-completion 의 feature-id 정규식(`^(feature|META)-[0-9]+...`)에 안 맞으므로 **절대 verify 인자로 쓰지 않는다**.
- **종속성 강제**: `depends_on` 이 전부 `done` 인 항목만 ready. 미충족 항목 강행 금지(blocked 로 두고 건너뜀).
- **governance 우선**: `<policy_root>/AGENTS.md` §7.1(Plan-Review-Execute)·§12.3(위험등급)·§16.3(verify-completion)·§13.2(worktree)·§18(ANCHOR/META) 전부 적용. 본 skill 은 정본을 우회하지 않는다.
- **외부영향 confirm**: commit/push/main 병합은 사용자 전역 auto-sync 정책 따름. **PR 생성·deploy·외부 알림은 별도 confirm** 유지.
- **상태 정직**: 구현이 막히면 항목을 `blocked` 로 표기하고 사유를 ROADMAP 에 남긴다. 통과 못 한 verify 를 통과로 보고하지 않는다.

> **경로 표기**: 본 skill 은 worktree 안에서 실행되며 그 root 가 곧 `policy_root`(= repo 체크아웃)다. 따라서 정본/코드는 **repo-상대**(`AGENTS.md`, `unit/feature-NNNN/...`, `docs/...`)로 접근한다. `repo/` prefix 는 wrapper checkout 시점 전용이라 worktree 안에서는 쓰지 않는다.

## 입력

Arguments: `$ARGUMENTS` (선택):
- **비면(no-arg) → 드레인 모드**: 대상 로드맵(미지정 시 최신 `ROADMAP.md`)의 **모든 ready 항목을 종속성 순서대로 순차 구현**.
- `<initiative-slug>` (ITEM 미지정) → **그 로드맵의 드레인 모드**.
- `<initiative-slug> ITEM-0x` 또는 `ITEM-0x` → **단건 모드**(특정 항목 1개. deps 미충족이면 fail-loud + 필요한 선행 보고).

## 실행 모드

### 단건 모드 (ITEM 지정)
지정 1항목만 Phase 0→5 후 종료(기존 동작).

### 드레인 모드 (no-arg / slug-only) — 종속/순차 전체 구현
ROADMAP 의 ready 집합을 종속성 순서로 **하나씩 끝까지** 구현하고, 한 항목이 done·main 머지되면 그에 의존하던 항목이 ready 로 풀려 다음 반복에서 잡힌다. **드레인이 자동화하는 것은 orchestration(항목 선택·순차·종속 추적·worktree 수명·ROADMAP status 갱신)뿐이다. 거버넌스 게이트(Major plan-review·Critical confirm·PR/머지/deploy 외부영향 confirm)는 항목마다 그대로 적용한다 — 드레인 승인이 이들을 대체하지 않는다.** 의사코드:

```
drain():
  show_plan_preview()                  # 전체 정렬 시퀀스 1회 표면화(scope 미리보기)
  consent_drain()                      # "이 순서로 자동 전진" 메타 승인(아래) — 1회
  no_progress = 0
  while True:
    cd <main_worktree>; git pull --ff-only origin main   # §13.2.5: 직전 항목 머지 반영
    reload ROADMAP from main           # 최신 status/deps (직전 done 반영)
    item = select_next_ready()         # Phase 0: (pending ∧ deps 전부 done), 정렬 Phase asc→risk asc→id asc
    if item is None: break             # 전부 done, 또는 진행가능 ready 없음
    g = item_gate(item)                # Phase 1 위험등급/ANCHOR
       # Minor    → 통과
       # Major    → 항목별 plan-review(file/symbol/acceptance) → PLAN-APPROVED 필요
       # Critical → 항목별 confirm 필요
       # ANCHOR충돌 → STOP
    if g needs_human and (unattended OR 미응답):
        mark blocked:needs-human; no_progress++; continue   # fail-closed: 자동 진행 안 함
    run Phase 2..5 for item            # cycle-init→구현→verify→마감
       # PR 생성·머지·deploy = 항목별 confirm(외부영향). 무인/미응답이면 blocked:awaiting-merge; continue
    if verify FAIL: mark blocked:verify-failed; no_progress++   # 같은 항목 2회째면 skip 고정
    else: no_progress = 0
    if no_progress >= (남은 ready 수): break   # 한 패스 새 done 0 → 교착 종료
  report: done N / blocked M / 남은 pending K + 각 blocked 사유 + 필요한 사람 액션
```

**consent_drain — 메타 승인 (대화 모드, §7.1 비우회)**:
1. 시작 시 **정렬된 실행 계획 전체를 1회 표면화**(각 항목 id·제목·`risk_grade`·`feature_id` + 1줄 요지) — 사용자가 scope 를 본다.
2. AskUserQuestion 으로 **"이 순서로 드레인(자동 전진) 진행" 메타 승인 1회**. **이 승인이 인가하는 것**: ① 항목 자동 선택·순차·종속 추적 ② **Minor 항목의 자동 구현** ③ 항목별 commit/push 자동 동기화(전역 auto-sync). **인가하지 않는 것(각 항목 차례에 개별 게이트 유지)**: ❌ Major plan-review(항목마다 file/symbol/acceptance plan 제시 → PLAN-APPROVED) ❌ Critical confirm ❌ **PR 생성·머지·deploy 외부영향**(§7.1·§12.3·전역 PR-confirm 정책 — batch 승인이 대체하지 않는다).
3. 즉 드레인은 "한 항목 끝나면 다음으로 자동 전진"만 자동화한다. 각 Major/Critical 항목과 각 외부영향(PR/deploy)은 **그 차례에서** 정상 게이트를 거친다. Major-heavy 로드맵이면 드레인이 그 게이트들에서 자주 멈춘다(정상 — 거버넌스 우선, 불변 제약 §외부영향 confirm 과 정합).

**무인 실행 (`--unattended` 인자 또는 cron/`/loop` wrapper)**: 사람 게이트를 받을 수 없으므로 **Minor 항목만 자동 구현**하고, Major/Critical/PR-confirm 지점에 닿으면 그 항목을 `blocked: needs-human` 으로 두고 다음 ready 로(M2 보존). **fail-closed 기본값**: `--unattended` 신호가 없어도 게이트가 미응답이면 자동 진행하지 말고 blocked 처리한다(모호 시 보수적 — Minor-only 로 강등). 한 패스에서 새 done 이 없으면 종료.

> 아래 Phase 0~5 는 **항목 1개를 처리하는 단위 절차**다. 드레인 모드는 이 절차를 ready 가 소진될 때까지 반복한다.

## Phase 0 — 적재 + 항목 선택

1. `policy_root` 감지(없으면 fail-loud). 본 skill 이 main checkout 에서 호출됐고 항목이 mutation 이면 **먼저 worktree 진입**(Phase 2)이 원칙 — §13.2.7 F0(main checkout immutability) 위반 방지.
2. 대상 `ROADMAP.md` 로드(없으면 fail-loud → "먼저 `/_dqa:improve_listup`").
3. **`/_template:entry` Bootstrap 동등 prime**: `AGENTS.md`·`docs/PROJECT.md`·`docs/ARCHITECTURE.md`·`docs/STATUS.md`·`wiki/hot.md` 적재(정책 미로드 상태 구현 방지 — entry Policy Prime Gate 와 동일 취지).
4. **항목 선택 (단일 규칙, M4 해소)**:
   - `ready` 집합 = { 항목 | `status: pending` ∧ `depends_on` 의 모든 항목이 `done` }.
   - 정렬: (1) Phase 오름차순 → (2) 동률이면 `risk_grade` 낮은 순(Minor<Major<Critical) → (3) 동률이면 ITEM-id 오름차순. 맨 앞 1개 선택.
   - 지정 항목이 있으면 그것(단 ready 가 아니면 fail-loud + 필요한 선행 ITEM 보고).
   - **starvation 방지**: blocked 항목은 건너뛴다. 어떤 blocked 가 다른 항목의 미충족 선행이라면 그 사실만 보고(자동 해제 안 함).
   - ready 가 없으면: 전부 done → "로드맵 완료" 보고 후 종료. blocked 만 남음 → blocked 사유 요약 후 종료(스케줄 루프 자연 종료).
   - **Phase 정의 합의**: Phase 는 *권장 순서*이지 강제 배리어가 아니다(ROADMAP §2 와 동일). 정렬의 1순위일 뿐, deps 가 충족된 후행 Phase 항목이 선행 Phase 의 blocked 때문에 영구 starve 되지 않는다.

## Phase 1 — 사전 게이트 (구현 전)

1. **ANCHOR/충돌 점검**(§18.3): 항목이 명시 ANCHOR 와 충돌하면 구현 안 함 → `/office-hours`·`/plan-ceo-review` 권유 + 항목 `blocked: anchor-conflict`.
2. **위험등급 분기**(§12.3 / §7.1) — **모드별로 다르다**:

| risk_grade | 대화 모드(사람 동석) | 무인 모드(/loop·cron 스케줄) |
|---|---|---|
| **Minor** | TodoWrite 분해 후 직접 구현 | 직접 구현 |
| **Major** | plan 표시 → **사용자 승인(PLAN-APPROVED)** 후 구현 | **중단** `blocked: needs-human-plan-approval` (다음 ready 로 넘어가거나 종료) |
| **Critical** | TodoWrite 분해 → inline plan → **사용자 confirm** 후 구현 | **중단** `blocked: needs-human-plan-approval` |

   > **M2 해소**: §7.1·§12.3 은 Major 도 사람 plan 승인을 요구한다. 무인 모드에서 Major/Critical 을 "plan 만 남기고 진행"하는 우회는 **금지**. 무인 모드는 Minor 만 자율 진행하고, Major/Critical 은 blocked 로 두어 사람을 기다린다. (스케줄 루프는 Minor 를 소진하다 Major 만 남으면 자연 정지.)

## Phase 2 — cycle-init (worktree 진입)

`/_template:entry` Phase 3.6 inline-execution 방식으로 worktree 자동 생성 + 본 세션 cd:
```bash
CYCLE_INIT_FROM_ENTRY_PERSONA=1 bash bin/cycle-init.sh --feature <feature_id> [--agent <agent>]
```
- `<feature_id>` = **ROADMAP 항목의 `feature_id`** (예 `feature-0002-agent-core`). ITEM-id 가 아니다.
- normal 경로(main 식별+최신화+worktree 생성) 자동 진행. abnormal(NFF·branch 충돌·worktree 다수로 인한 "Cannot fast-forward to multiple branches") → 로컬 main 기준 수동 폴백: `git -C <main_worktree> worktree add <project_root>/.worktrees/<slug> -b ai/<agent>/<slug> main`(메모리화된 우회) 후 진행.
- 종료 후 `cd <new_worktree_path>`.

선택 항목을 ROADMAP 에서 `status: in-progress` 로 갱신(surgical 1줄 edit). **이 갱신은 마감 커밋에 동봉**한다(별도 doc-only 커밋 금지 — Phase 5.3 / M3 참조).

## Phase 3 — 구현 (Execute)

worktree 안에서 항목 spec(`what`·`entry_points`·`acceptance`·`guards`)을 충실히 구현. **항목의 `feature_id` 가 가리키는 unit 의 문서를 함께 갱신**(verify-completion 통과 전제):
- 신규 feature 면 `unit/_template/` 복제 → `unit/<feature_id>/`(FIRST_REQUEST 시나리오 A) + `FUNCTION.md §2 Goal` 에 REQ 기입.
- 기존 feature 확장이면 `unit/<feature_id>/docs/` 의 **TASK.md**(체크박스 추가) · **MODIFY.md**(CHG- 엔트리 append) · 코드 동작 변경 시 **FUNCTION.md** staged · **ANCHOR.md**(§1~§3 정합) 갱신.
- 항목이 2개 feature(예 0002+0003)에 걸치면 **primary `feature_id` 의 unit 문서를 정본으로 verify** 하고, secondary 변경은 primary 의 MODIFY.md 에 cross-ref 기록(또는 listup 에 항목 분할 요청). 단일 cycle 에서 두 feature 의 verify 를 동시에 만족시키려 하지 않는다.
- `entry_points` 의 repo-상대 경로(`unit/...`·`docs/...`)를 진입점으로, 재사용 자산 우선.
- `guards` 가 명시된 조건부 항목은 **가드를 먼저** 구현(retry cap·PII 마스킹·신규 RBAC·selective 발동 등).
- 데이터모델 변경은 마이그레이션 멱등성·롤백안전망(dual-write/backfill 관례).
- §18.8 dispatch 매칭(auth/schema/UI/API/perf)이면 작업 후 panel/리뷰 호출.

## Phase 4 — 검증 (verify-completion)

```bash
bash bin/verify-completion.sh --pre-commit <feature_id>
```
- `<feature_id>` = 항목의 `feature_id`(정규식 적합 + `unit/<feature_id>/` 존재). ITEM-id 금지.
- PASS 만 마감 진입. FAIL → 원인 보고 + 항목 `blocked: verify-failed (<요약>)`(무인) 또는 사용자 결정(대화).
- 항목 `acceptance` 의 **측정 검증**(평가 harness·라이브 지표)이 있으면 그 측정도 수행해 수치 기록. 코드 테스트 통과만으로 "done" 하지 않는다(로드맵이 측정을 요구하면 측정이 게이트).
- §18.8 META/문서 변경이면 check #9(REVIEW.md entry) 충족 — `unit/<feature_id>/docs/REVIEW.md` 에 panel 또는 `[SKIPPED:*]` 엔트리 staged.

## Phase 5 — 마감 + 로드맵 갱신

1. **commit**(worktree-first, 사용자 auto-sync 정책 따름). 커밋 메시지는 `CONTRIBUTING.md` 규칙(`<type>(<scope>): 요약 (#issue)` + 필요 시 TASK 접미). **ROADMAP 항목 status 갱신(`done`)을 이 커밋에 동봉**한다 — ROADMAP 은 `docs/*`(META path)라 단독 커밋 시 verify check #9 가 별도 REVIEW 를 요구하지만, feature cycle 커밋에 묶으면 그 cycle 의 REVIEW 증거로 충족된다(M3 해소).
2. **ROADMAP 상태 갱신**: 항목 `status: done`(+ `note:` 에 측정 수치/PR 번호), §5 진행현황 카운트 재집계, 다음 ready 갱신. surgical edit.
3. **cycle-finalize**(PR 머지 후 cleanup) — `/_template:entry` Phase 6.8 정합:
   ```bash
   bash bin/cycle-finalize.sh --pr <PR-NUMBER>
   ```
   PR 생성·머지는 외부영향 → **confirm**. **무인 스케줄 모드면** commit/push 까지만 하고 PR 은 사람 대기로 남김 + 항목 `status: in-progress` + `note: awaiting-merge PR#<n>`(status enum 외 값 금지 — m1 해소).
4. **deploy_scope**: `FIRST_REQUEST.md`/`FUNCTION.md` 가 `deploy_scope: included` 면 §16.3 정책대로 배포까지(첫 배포 1줄 표면화). 부재면 confirm.

## Phase 6 — 연속 소진 & 재가동

- **드레인 모드(no-arg)** 가 한 호출 안에서 Phase 0~5 를 반복해 ready 를 순차 소진하므로, 단순 "로드맵 전체 구현"에는 외부 스케줄러가 **불필요**하다(루프 내장).
- **외부 wrapper 가 여전히 유용한 경우**:
  - 무인 환경에서 Minor 만 자동 소진하다 Major/Critical 에서 멈춘 뒤, 사람이 승인/언블록한 다음 재가동: `/_dqa:improve_cycle <slug>` 재호출.
  - 로드맵에 항목이 계속 추가되는 상황의 정기 점검: `/schedule`(CronCreate)로 주기 재호출.
  - 사람이 항목마다 확인하며 진행하고 싶으면 단건 모드(`ITEM-0x` 지정)를 반복.
- **자체 예약 안 함**: 특정 스케줄러 tool 에 의존하지 않는다(드레인은 루프 내장, 주기 재가동은 외부 wrapper 책임).
- **종료 보고(드레인/단건 공통)**: `done N / blocked M / 남은 pending K` + 각 blocked 사유 + 다음 ready 또는 필요한 사람 액션 1줄.
- **무한루프 가드**: 같은 항목 2회 연속 `blocked: verify-failed` → skip. 한 드레인 패스에서 더 이상 새 done 이 안 나오면(전부 blocked/승인대기) 종료.

## 종료 조건
- [ ] 단건 모드는 1항목, **드레인 모드는 ready 를 종속/순차로 소진**(전부 done 또는 진행불가까지).
- [ ] 드레인 모드(대화)는 실행계획 표면화 + 드레인 메타 승인 1회를 받되, **각 Major plan-review·Critical confirm·PR/머지/deploy 외부영향은 항목 차례에 개별 게이트로 유지**(batch 가 §7.1/외부영향 confirm 을 대체하지 않음). 무인·미응답은 fail-closed(Minor 만 소진, 게이트 항목 blocked).
- [ ] 매 항목 deps 충족만 진행(미충족 강행 안 함). 매 반복 main pull --ff-only 로 직전 머지 반영 후 select. 선행 머지 후에야 후행 worktree 진입.
- [ ] 위험등급별 plan/confirm 정책 준수 — **무인 모드는 Minor 만 자율, Major/Critical 은 blocked**.
- [ ] cycle-init `--feature` 와 verify `<feature_id>` 가 **항목 feature_id 로 동일**.
- [ ] worktree cycle(init→구현→verify→마감)이 `/_template:entry` 방식과 정합.
- [ ] verify-completion PASS + acceptance 측정(있으면) 수행 후에만 done.
- [ ] ROADMAP status 갱신이 feature cycle 커밋에 동봉(doc-only 단독 커밋 회피).
- [ ] PR/deploy 등 외부영향은 confirm(무인 모드는 commit/push 까지만).
