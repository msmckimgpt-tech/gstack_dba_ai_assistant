# `/_dqa` — 지속 개선 파이프라인 (Delegated-dev Quality & Advancement)

현재 제품(사내 DBA AI Assistant)의 **지속 개선**을 발굴 → 정합 review·로드맵화 → 구현의 3단계로 운영하는 skill 묶음. 각 단계는 다음 단계로 **문서 핸드오프**한다(대화 맥락 의존 0).

```
/_dqa:improve_research   →   /_dqa:improve_listup   →   /_dqa:improve_cycle
 (사람 호출)                   (AI 자율 호출)             (사람 호출·스케줄)
  RESEARCH.md                  ROADMAP.md                 코드 + status 갱신
```

## 단계 계약 (핸드오프)

| 단계 | skill | 호출 | 입력 | 산출 |
|---|---|---|---|---|
| 1 발굴 | `improve_research` | 사람 | 초점(선택) | `docs/improvements/<initiative>/RESEARCH.md` |
| 2 정합·로드맵 | `improve_listup` | AI 자율/사람 | RESEARCH.md | `docs/improvements/<initiative>/ROADMAP.md` |
| 3 구현 | `improve_cycle` | 사람·스케줄 | ROADMAP.md | 코드(worktree cycle) + ROADMAP status 갱신 |

## 산출물 위치 규약

```
docs/improvements/
├── _TEMPLATE-ROADMAP.md          # listup 산출 스키마 템플릿
├── <initiative-slug>/
│   ├── RESEARCH.md               # 1단계 산출 (발굴 findings)
│   └── ROADMAP.md                # 2단계 산출 (standalone 로드맵, status 보유)
└── ...
```

- **initiative-slug**: 개선 이니셔티브 단위(예 `dba-ai-nl2sql`, `nl2sql-accuracy`). research 가 결정.
- **RESEARCH.md / ROADMAP.md** 는 cross-cutting **project-level** 자산이라 `unit/<feature>/docs/` 가 아닌 `docs/improvements/` 에 둔다. 로드맵의 **각 항목**이 구현될 때 비로소 feature cycle(`unit/feature-NNNN/` 또는 worktree)로 내려간다.

## 설계 원칙

1. **재발명 금지선**: research 가 "이미 있는 것 vs 빈 곳"을 file:line 으로 확정 → 빈 곳만 후보.
2. **정합 게이트**: listup 이 6축(아키텍처·제약·보안/RBAC·성능/비용·재사용·측정)으로 채택/조건부/보류/기각. 모든 후보를 채택하지 않는다.
3. **측정 선행**: 효과 증명 수단(평가 harness)을 그것에 의존하는 성능항목들의 선행으로 끌어올린다.
4. **종속성 DAG**: 로드맵은 비순환 의존 그래프 + 위상정렬된 Phase.
5. **항목당 1 cycle, 순차 드레인**: improve_cycle 은 항목 1개당 독립 worktree cycle(격리·리뷰 비희석). **no-arg 호출은 ready 를 종속/순차로 전부 소진(드레인)**, ITEM 지정은 단건. 동시 worktree 는 금지(순차가 종속 보장).
6. **governance 우선**: 3단계 모두 `repo/AGENTS.md` 정본·worktree-first·verify-completion·외부영향 confirm 을 그대로 따른다. `/_template:entry` 의 cycle-init/cycle-finalize 작동을 참조.

## 상태 모델 (스케줄링 근거)

ROADMAP 의 각 항목 `status` 필드: `pending → in-progress → done`(또는 `blocked`). improve_cycle 이 이를 갱신하므로, ROADMAP.md 자체가 **단일 진행 원장**이다(별도 ledger 불필요). "다음 ready 항목" = (status=pending ∧ depends_on 전부 done) 중 (Phase asc → risk_grade asc → id asc). **드레인 모드는 항목이 done·머지될 때마다 이 집합을 재계산**해 풀린 deps 를 잡는다(매 반복 main 최신본 ROADMAP 기준).

## 비고 (계약·제약)

- **feature_id 계약(필수)**: ROADMAP 각 항목은 `feature_id`(기존 `unit/<feature>` 확장이면 그 id, 신규면 `feature-NNNN-<slug>`)를 갖는다. improve_cycle 이 `cycle-init --feature` 와 `verify-completion <feature-id>` 양쪽에 이 값을 쓴다. ITEM-id(`ITEM-02`)는 verify-completion 정규식(`^(feature|META)-[0-9]+...`)에 안 맞으므로 cycle 인자로 쓰지 않는다.
- **무인 모드 안전선**: improve_cycle 무인(/loop·cron) 실행은 **Minor 항목만 자율 진행**. Major/Critical 은 §7.1·§12.3 에 따라 사람 plan 승인이 필요하므로 `blocked: needs-human-plan-approval` 로 멈춘다. PR 생성·deploy 도 confirm(무인은 commit/push 까지).
- **드레인 vs 외부 스케줄**: no-arg 드레인 모드가 한 호출로 ready 를 순차 소진하므로 단순 전체 구현엔 외부 스케줄러 불필요. 외부 wrapper(`/loop`·`/schedule`=CronCreate)는 무인 정지 후 재가동·정기 점검·신규 항목 픽업용. improve_cycle 자체는 예약 안 함.
- **경로 표기**: 산출 문서·스킬 본문의 코드/정본 경로는 **repo-상대**(`AGENTS.md`·`unit/...`·`docs/...`). `repo/` prefix 는 wrapper checkout 전용이라 worktree 안에서 안 쓴다.
- **Claude 전용 entrypoint**: 본 `_dqa` 묶음은 `.claude/commands/` 에만 둔다(CLAUDE.md 정책). Codex 미러(`.codex/commands/`)는 두지 않는다.

