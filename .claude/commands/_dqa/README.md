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

## 부가: 유지보수·리포팅 persona (doc_sync · conversation_audit · report_deck)

위 1→2→3 파이프라인과 **별개**로, 같은 묶음에 standalone maintenance/reporting persona 를 둔다 — 머지된 작업↔문서 drift 를 정합하는 `doc_sync`, 라이브 대화 마찰을 진단·수정·출하하는 `conversation_audit`, 기간별 개발 진척을 비전문가 포함 상부보고 발표자료로 재구성하는 `report_deck`. **모두 파이프라인 단계가 아니므로 핸드오프 표에 넣지 않는다**(자동 후속 chain 없음 — 사람·스케줄이 필요 시 호출).

| skill | 호출 | 입력 | 산출 |
|---|---|---|---|
| `doc_sync` | 사람·스케줄(maintenance) | 타깃(릴리즈노트\|wiki\|정책문서) 또는 기준일(선택) | 정책문서·wiki·릴리즈노트 색인/서사/사용자향 노출 갱신 (정본 비대체) |
| `conversation_audit` | 사람·스케줄(maintenance) | 대화 한정(conversation-id\|product=\|account=\|기간) \| friction-id \| `--drain [N]`(선택) | 라이브 대화 마찰 진단(명시+암묵 이탈)→코드 거주 feature 수정·검증·출하 + `FRICTION_LEDGER.md` 갱신 |
| `report_deck` | 사람·스케줄(발표·보고) | 개발 일정 범위 `"YYYY-MM-DD ~ YYYY-MM-DD"` [버전] | `docs/presentation/<범위>/<버전>/{deck.html, SCRIPT.md, EVIDENCE.md}` — 배경·전후·근거·기대효과·리스크로 재구성한 상부보고 발표자료 (코드/정본 비대체) |

- **무엇을 정합**: 정본(`unit/<id>/docs/*`·`docs/DECISIONS.md`)은 그대로 두고, 그 **색인·서사·사용자향 표면**(`docs/STATUS.md`·wiki·릴리즈노트)만 최신화한다. 정본과 모순되면 정본을 진실로 삼아 색인을 고친다.
- **commit 분류 주의**: wiki(`wiki/*`)·정책문서(`docs/*`)는 META path → doc-only 분리 commit + verify META mode. **릴리즈노트가 owning feature 의 `unit/<feature>/src/static/...` 에 살면 operational** 이라 META mode 가 아니다 — 별도 commit + owning feature operational gate(check #9 는 `unit/<fid>/docs/REVIEW.md`). 자세한 분기는 `doc_sync.md` Phase 4.
- **산출물 위치 규약**: 본 persona 는 새 산출물 경로를 만들지 않는다(기존 `docs/`·`wiki/`·릴리즈노트 산출물 in-place 갱신). META REVIEW index 는 project-wide 규약(`meta/REVIEW.md` + `meta/reviews/<ts>-<agent>.md`, §18.10.1) 또는 operational 시 `unit/<fid>/docs/REVIEW.md`.
- **landing/배포 무확인 자동(사용자 정책 2026-06-25 — doc_sync 한정 override)**: doc_sync 는 attended·unattended(백그라운드/cron) 무관하게 `PR→merge→배포`까지 **무확인 자동 진행**한다(전역 'PR·deploy=confirm' fail-closed 의 doc_sync 한정 예외 — improve_cycle 의 무인 안전선과 다름). delta 가 있는데 landing 누락, 또는 서빙 static(릴리즈노트) 변경 후 배포 누락 = **장애**. 멈추는 경우는 early-exit(delta 0)·verify FAIL·BLOCKED 뿐(정확성 게이트는 우회 안 함). 자세한 건 `doc_sync.md` 헤더·Phase 5/6.
- **conversation_audit 외부영향(중요 — doc_sync override 비승계)**: conversation_audit 은 프롬프트·맥락조립·가드·PII 경로(Major~Critical)를 건드려 blast radius 가 크다 → **기본 confirm 유지**(commit/push 만 전역 auto-sync). doc_sync 식 무확인 override 는 **Minor deploy 에만** 적용 가능하고 **Major/Critical(프롬프트·가드·RBAC·PII)은 override 불가 — §12.3 사람 승인 절대**. 진단 단일 정본은 `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(append; 코드 거주 feature `REPORT.md` 엔 cross-ref 1줄). 수정 후 STATUS·wiki 정합은 `doc_sync` 위임(자동 chain 금지). 자세한 건 `conversation_audit.md` 헤더·불변제약·Phase 0~14.
- **report_deck 산출물·규율**: `docs/presentation/<범위>/<버전>/` 에만 생성(코드·정본 무수정, 기존 버전 미덮어씀). 커밋/파일 나열 금지 → 배경·변경 전후·선택 근거·기대효과·리스크로 재구성하고, **확인 가능 vs 확인 필요를 구분**(모든 주장은 `EVIDENCE.md` 로 추적, 배포·테스트·성능수치·재발방지·전후자료·문서코드불일치는 단정 금지)한다. git 은 **main 반영분 기준**(미머지=확인필요), 개발 대화기록은 하이픈-slug 로 **두 홈**(`~/.claude`·`/home/claude-corp/.claude`) 스캔. 내부 용어는 일반 용어로 풀고, 민감정보(계정·비밀번호·토큰·접속좌표·개인정보)는 미포함. 입력 범위는 이전 기간과 비교(신규/이어받음/완료). **디자인/시각효과는 매 호출 최신 웹 트렌드를 프로젝트 봉투·자기완결 offline·상부보고 절제 톤 3중 필터로 반영(구조·서사 불변)**. commit `docs(presentation):`, **PR·배포·외부발송 안 함**. 자세한 건 `report_deck.md`.
- **`.codex` 미러 없음**: 본 묶음 정책대로 `doc_sync.md`·`conversation_audit.md`·`report_deck.md` 모두 `.claude/commands/_dqa/` 에만 둔다.

## 비고 (계약·제약)

- **feature_id 계약(필수)**: ROADMAP 각 항목은 `feature_id`(기존 `unit/<feature>` 확장이면 그 id, 신규면 `feature-NNNN-<slug>`)를 갖는다. improve_cycle 이 `cycle-init --feature` 와 `verify-completion <feature-id>` 양쪽에 이 값을 쓴다. ITEM-id(`ITEM-02`)는 verify-completion 정규식(`^(feature|META)-[0-9]+...`)에 안 맞으므로 cycle 인자로 쓰지 않는다.
- **무인 모드 안전선**: improve_cycle 무인(/loop·cron) 실행은 **Minor 항목만 자율 진행**. Major/Critical 은 §7.1·§12.3 에 따라 사람 plan 승인이 필요하므로 `blocked: needs-human-plan-approval` 로 멈춘다. PR 생성·deploy 도 confirm(무인은 commit/push 까지).
- **드레인 vs 외부 스케줄**: no-arg 드레인 모드가 한 호출로 ready 를 순차 소진하므로 단순 전체 구현엔 외부 스케줄러 불필요. 외부 wrapper(`/loop`·`/schedule`=CronCreate)는 무인 정지 후 재가동·정기 점검·신규 항목 픽업용. improve_cycle 자체는 예약 안 함.
- **경로 표기**: 산출 문서·스킬 본문의 코드/정본 경로는 **repo-상대**(`AGENTS.md`·`unit/...`·`docs/...`). `repo/` prefix 는 wrapper checkout 전용이라 worktree 안에서 안 쓴다.
- **Claude 전용 entrypoint**: 본 `_dqa` 묶음은 `.claude/commands/` 에만 둔다(CLAUDE.md 정책). Codex 미러(`.codex/commands/`)는 두지 않는다.

