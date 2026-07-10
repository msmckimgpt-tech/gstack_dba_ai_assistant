---
doc_type: DQA_RESEARCH
initiative: parallel-work-structure
created_at: 2026-07-10
status: complete
schema_version: 1
research_mode: in-session-investigation
---

# RESEARCH — parallel-work-structure (병렬 AI 작업 충돌 구조 개선)

> **조사 방식 주의**: 본 문서는 `/_dqa:improve_research` 의 웹/서비스 리서치가 아니라,
> 2026-07-10 세션에서 수행한 **repo 내부 3방향 병렬 조사**(거버넌스 규정 분석 / git 충돌
> 이력 실증 / 코드·문서 핫스팟 구조 조사)와 **feature-0012 원본 세션 복원**(`/_template:resume`,
> 2026-07-10 10:27 중단 세션)을 융합해 적재한 것이다. 모든 수치는 조사 당일 실측.

## 0. 문제 정의

초고병렬 AI 작업(30일간 커밋 1,286건 · PR 428건 · 활성 worktree 21개 · 작업자 계열 3종
`ai/claude/`·`ai/claude-corp/`·`ai/root/`)에서 머지 충돌·재번호·stale 정정이 반복 발생.
최근 300커밋(8일 구간) 중 **3.7%(11건)가 명시적 충돌 봉합 커밋**.

핵심 결론: **worktree/branch 격리(AGENTS.md §13.2)는 이미 잘 작동한다.** 충돌은 격리
부족이 아니라, 격리된 브랜치들이 **같은 착지점**(거대 단일 파일 · 전역 순번 · 파일 끝
append)에 수렴하기 때문에 발생한다. 개선 방향 = 격리 강화가 아니라 **착지점 분해**.

## 1. Findings

### F-001 · 거대 단일 파일 핫스팟 (물리 충돌 1순위)
- `unit/feature-0003-agent-web-ui/src/static/admin.js` **17,671줄** — feature-0016 그래프
  로직 전체(약 3,800~7,200행 구간, 그래프 식별자 1,382회)가 단일 파일에 매몰. 30일 약 236회
  변경. **feature-0016 파생 브랜치 20+개가 전부 이 파일의 같은 구간을 수정**.
- `unit/feature-0003-agent-web-ui/src/app.py` **19,716줄** — 라우트 핸들러는 0(F-007 로
  추출 완료)이나 헬퍼·전역·비즈니스 로직 잔존.
- `app.js` 10,464줄 · `styles.css` 9,003줄 — 2차 충돌원.
- `unit/feature-0016-metadata-graph/src/` 는 사실상 빈 폴더(README+.gitkeep) — 그래프
  코드가 feature-0003 유닛에 무단 거주(소유권 착종).

### F-002 · § 섹션 번호 수동 선점 (실충돌 실측)
- `unit/feature-0016-metadata-graph/docs/TASK.md`(2,082줄)는 사이클마다 `## N.` 섹션을
  파일 끝 append. 번호는 각 작업자가 "현재 최대 +1"을 수동 계산 → **`## 33.` 2개,
  `## 56.` 2개 중복 실존**. 재번호 커밋 실측: `e79688f6`(§55→§56), `0f692942`(§32→§33).
- `TASK-`/`CHG-`/`REV-`/`LRN-`/`REQ-`/`AC-` 식별자는 §13.1 (v3.32.0/v3.34.x)에서 timestamp
  형식으로 전환돼 경합 제거됨. **§ 섹션 헤더 번호만 규약 밖에 잔존**.
- 같은 계열: `docs/DECISIONS.md` 의 레거시 `ADR-NNNN` 순번(순서 이미 불규칙: …0021,
  0026, 0025…), `_archive/<DOC>-archive-NNNN.md` 파일 순번(§5.5).

### F-003 · alembic 선형 체인 순번 경합 (실충돌 실측)
- `unit/feature-0002-agent-core/alembic/versions/` 39개, revision `0001`~`0039` 완전 선형.
- 커밋 `6263e641` 실측: feature-0016 이 `0036` 선점 → feature-0009 마이그레이션을
  `0036→0037` **수동 re-parent**(파일명·`revision`·`down_revision` 3곳 동시 수정).
- 자동 next-번호 할당기 없음(`bin/alembic-migrate.sh:71` 은 fallback 만). 병렬 브랜치가
  각자 `0040` 생성 시 multi-head 포크 — 이를 머지 전에 잡는 CI gate 부재.

### F-004 · append-only 문서의 물리(텍스트) 충돌
- append-only 정책(§5.2, F3: timestamp+session-ID 필수)은 **의미 충돌**만 막고, 파일 끝
  동시 append 의 **텍스트 충돌**은 못 막음. 실측: `7c653ea8`(TEST.md Run 충돌 양측 재배치),
  `a77180ca`(병합 후 conflict marker 잔존 커밋).
- 30일 변경빈도 상위가 전부 이 계열: feature-0003 TASK.md 291회 · MODIFY.md 277회 ·
  REVIEW.md 275회 · TEST.md 229회. 전역 `docs/STATUS.md` 109회(모든 feature 가 같은
  기능현황표의 행을 편집), RELEASE_NOTES.md(시간순 블록 append).

### F-005 · 머지 파이프라인 — 직렬화·신선도 장치 부재
- merge queue 없음. 현행 관행 = PR UNSTABLE→CLEAN 폴링 후 머지(`gh pr merge`). 머지
  시점에 main 이 이미 전진(일 18.6 PR)해 있어 **낡은 base 로 통과한 테스트로 머지되는
  semantic drift** 상존. §13.2.5 는 동시 push race 를 "사용자 수동 직렬화"로 위임.
- main drift 대응은 "rebase 권유(사용자 confirm)"뿐 — hard gate 아님.
- 참고 제약: branch protection API 403(advisory) — GitHub merge queue 사용 불가 플랜.
  단 **모든 작업자가 동일 호스트**에서 실행되므로 host-local 락(flock) 직렬화 가능.

### F-006 · stale 브랜치·worktree 누적
- 원격 브랜치 223개, 미머지 73개. 실측: `hl-isolated` 41 behind, `feature-0002-agent-core`
  129 behind/0 ahead(방치). behind 클수록 머지 충돌 확률·규모 증가 — "예약된 충돌".
- §13.2.3-A 가 판정 기준(SAFE_REMOVE/LIKELY_ABANDON/NEEDS_REVIEW)과 `bin/worktree-audit.sh`
  구조를 이미 규정했으나 **미구현**. orphan sweep 은 사용자 수동(AGENTS.md §13.2.3
  Reviewer Concerns — 소비자 `docs/DECISIONS.md` 의 ADR 번호와 무관한 template 측 결정).
- 부수 quirk: sudo-docker pytest 가 worktree 에 root 소유 `__pycache__` 를 남겨
  `git worktree remove` 가 Permission denied 로 실패(수동 sudo rm 필요).

### F-007 · feature-0012 잔여 workstream (원본 세션 fdd3a4b6 복원, 2026-07-10 10:27 중단)
- **완료 실측**: route 핸들러 148개 전량 → 23개 라우터 추출(PR #506/#513/#516 머지,
  app.py `@app` 라우트 0). origin/main 359커밋 동기화(코드 clean 병합), 전 라우터
  `ruff --select F821` clean(b59eb547 push, worktree clean).
- **잔여 3건** (세션 마지막 TodoWrite 정본):
  1. **[BLOCKED] 프론트 분할** `TASK-0012-10` — admin.js 30일 237커밋 + feature-0016
     활성 브랜치 ~10개 병렬로 의도적 보류. F-001 과 동일 지점.
  2. **web_context 헬퍼 이동**(완전 thin-app) — DI seam 선행이 원래 monkeypatch 블로커.
  3. **DEFER 핸들러 byte-동치 DI-rework** — pre-auth gate/long-poll/txn ~43(+fail-soft 3).
- **세션 교훈(정정 기록)**: batch 추출의 "byte-neutral" 주장이 name-resolution 관점에서
  불완전 — bare-name 잔존이 **라이브 500 3종**을 유발했고 타 워커가 `ruff F821` 감사로
  수습. → 이후 추출/이동 게이트에 `ruff --select F821` 필수.

### F-008 · app.py 꼬리 배선 블록 = 단일 직렬화 지점
- 라우터 import + `app.include_router(...)` 23개가 `app.py` 꼬리(약 19,639–19,716행)에 밀집.
  모든 라우터 추출·추가 작업이 같은 꼬리 블록을 편집 → 라우터 신설마다 경합.

### F-009 · 저비용 git 장치 미활용
- `rerere` 미활성(반복 충돌 해소 기록 재사용 없음). append-only 문서용 path-scoped
  merge driver 미사용 — §13.1(v3.35.1)이 전체파일 `merge=union` 은 금지하되 path-scoped
  custom driver 를 2순위 해법으로 명시(정책 정합 여지 있음).

### F-010 · 거버넌스 성숙도 (개선 방향의 제약 조건)
- §13.2 격리(F0~F3)·REGISTRY·FOREIGN_CHANGE_ALERT·cycle-init/finalize 는 성숙하게 작동.
  cycle 스크립트는 브랜치/worktree 만 관장하고 **번호 공간·문서 착지점은 관장하지 않음**
  — 이것이 남은 공백. 중앙 번호 할당기(reservation registry)는 AGENTS.md §13.1 말미
  (template 측 "ADR-0022" 인용 — 소비자 DECISIONS.md 번호공간과 별개)에서 기검토 후
  보류됨(재론 시 근거 필요).

## 2. 후보 개선안 (요약 — 정합 review 는 ROADMAP.md)

| # | 후보 | 근거 finding |
|---|---|---|
| C-01 | TASK.md § 섹션 헤더 timestamp-slug 전환 + ADR/archive 순번 정리 | F-002 |
| C-02 | alembic multi-head CI gate + re-parent 자동화 | F-003 |
| C-03 | rerere 활성 + append-only 문서 path-scoped merge driver(과도기) | F-004, F-009 |
| C-04 | `bin/worktree-audit.sh` 구현 + stale sweep 자동화(cron) | F-006 |
| C-05 | 라우터 자동 등록(pkgutil) — app.py 꼬리 경합 제거 | F-008 |
| C-06 | append 문서 fragment(항목당 1파일) 전환 — 1차: TEST.md Run 기록 | F-004 |
| C-07 | host-local merge mutex(flock) + 신선도(behind) hard gate | F-005 |
| C-08 | STATUS.md 기능현황표 자동 생성 | F-004 |
| C-09 | admin.js 그래프 모듈 분리(static/graph/ ES 모듈) — TASK-0012-10 해제 | F-001, F-007-1 |
| C-10 | web_context 헬퍼 추출(완전 thin-app) | F-007-2 |
| C-11 | DEFER 핸들러 byte-동치 DI-rework | F-007-3 |
| C-12 | app.js/styles.css 전면 분할 | F-001 |
| C-13 | REGISTRY hot-path 선언 + WIP 상한 | F-001, F-010 |
| C-14 | GitHub merge queue 도입 | F-005 |
| C-15 | § 번호 중앙 할당기(reservation registry) | F-002, F-010 |

## 3. 웹 리서치 — 외부 사례 검증 (W-findings, 2026-07-10 추가)

> 사용자 요청으로 추가 수행: "초고병렬 개발·다중 AI 세션 개발" 유사 사례 웹 리서치
> (WebSearch 24회 + 원문 WebFetch 검증 19회, 2개 병렬 리서치 에이전트). 확인된 1차
> 소스만 수록.

### W-001 · 격리는 업계 표준, 그러나 충돌을 없애는 게 아니라 머지 시점으로 지연시킬 뿐
Anthropic Claude Code(worktree 1급 기능, "세션당 worktree"), Cursor(/worktree·best-of-N),
OpenAI Codex(태스크당 격리 컨테이너), Devin(managed VM) 전부 태스크당 격리 실행으로 수렴.
그럼에도 대규모 실측(AgenticFlict, arXiv:2604.03551 — 59K repo·142K agentic PR)에서
**에이전트 PR 충돌률 27.67%**. → 격리(우리 §13.2)는 필요조건일 뿐, 머지 규율이 본체.
[https://code.claude.com/docs/en/worktrees · https://cursor.com/docs/configuration/worktrees
· https://openai.com/index/introducing-codex/ · https://arxiv.org/abs/2604.03551]

### W-002 · 머지 불변식 "최신 base 와 합친 상태가 green 인 커밋만 mainline 에" (Not Rocket Science Rule)
bors(2013)→GitHub Merge Queue→Zuul→Uber SubmitQueue 모든 구현의 공통핵. 도구 없이도
"push 직전 fetch+rebase+테스트, 선점당하면 재시도" non-force-push 직렬화로 같은 불변식
유지 가능(sketch.dev "Lightweight Merge Queue" 실사례). 주의: GitHub Actions
`concurrency` group 은 pending 을 1개만 유지해 FIFO 머지 큐 대용이 못 됨(공식 논의 확인).
[https://mergify.com/blog/the-origin-story-of-merge-queues ·
https://sketch.dev/blog/lightweight-merge-queue ·
https://github.com/orgs/community/discussions/12835]

### W-003 · GitHub Free private repo 는 branch protection·merge queue 둘 다 불가 (확정)
merge queue 는 public repo(전 플랜) 또는 **Enterprise Cloud private** 전용 — Team 플랜
조차 불가. branch protection 도 Free 조직 private 는 불가(우리 403 관측과 일치). 대안:
Mergify App(활성 기여자 5인 이하 private 무료, 단 외부 App 에 repo 권한 필요) /
self-hosted bors-ng(archived — 유지보수 리스크) / 스크립트 직렬화(W-002).
[https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
· https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches]

### W-004 · "append 단일 파일 = 인위적 직렬화 지점" — fragment 가 검증된 표준
towncrier(pip·pytest·Twisted: 항목당 1파일 → 릴리즈 시 컴파일)·reno(OpenStack: "merge
conflict 걱정 없이" 가 명시된 설계 목표)·GitLab(커밋 trailer — 파일 0개)·Kubernetes(PR
본문 release-note 블록). git-중심 파이프라인엔 파일 분리(towncrier형)가 가장 이식 쉬움.
[https://towncrier.readthedocs.io/en/stable/ · https://docs.openstack.org/reno/latest/ ·
https://docs.gitlab.com/development/changelog/]

### W-005 · 마이그레이션 병렬 충돌: "heads==1 CI 게이트" + "의도적 충돌 파일" 이중 방어가 표준
Alembic 커뮤니티 표준 = CI 에서 `alembic heads` 단일성 검사(+throwaway DB
upgrade/downgrade 사이클). django-linear-migrations 는 앱별 `max_migration.txt`(최신
마이그레이션명 기록)로 **병렬 브랜치 머지 시 git 충돌이 반드시 나게 설계** — fail-fast
철학의 대표 사례, `rebase_migration` 명령으로 자동 해소. Rails 는 순번 충돌 때문에 2.1
부터 timestamp 로 전환한 역사를 공식 문서화.
[https://ldirer.com/blog/posts/practical-checks-alembic-migrations ·
https://adamj.eu/tech/2020/12/10/introducing-django-linear-migrations/ ·
https://guides.rubyonrails.org/v3.2/migrations.html]

### W-006 · 충돌 확률의 근본 변수 = 동시 진행량 × 브랜치 수명 (정량 근거)
Uber SubmitQueue 논문(EuroSys'19) 실측: **동시 변경 16건이면 충돌 확률 약 40%**. DORA:
고성과 팀 = 활성 브랜치 3개 이하 + 하루 내 trunk 병합. Claude Code 커뮤니티 가이드
다수: 동시 세션 실효 상한 2~4(초과 시 리뷰 불능·rate limit). 우리 feature-0016
graphux 2~10+ 병렬은 이 임계 초과 — stale worktree·번호 충돌이 정확히 그 증상.
[https://dl.acm.org/doi/pdf/10.1145/3302424.3303970 ·
https://dora.dev/capabilities/trunk-based-development/]

### W-007 · "쓰기는 단일 스레드, 병렬화는 지능에" + fresh-context 리뷰어
Cognition 의 정식화: 2025 "Don't Build Multi-Agents"("Actions carry implicit decisions,
and conflicting decisions carry bad results") → 2026 "Multi-Agents: What's Actually
Working"(작동 패턴 = "writes stay single-threaded" + clean-context 리뷰 루프 — PR당 ~2
버그 적발). Anthropic 공식 Best Practices 도 Writer/Reviewer 세션 분리("A fresh context
improves code review") 명문화. Devin Review 도 "coding·review 에이전트가 사전 컨텍스트를
공유하지 않을 때 최고 성능".
[https://cognition.com/blog/dont-build-multi-agents ·
https://cognition.com/blog/multi-agents-working ·
https://code.claude.com/docs/en/best-practices]

### W-008 · 순차 머지 규율 + semantic conflict 경계
Augment 가이드: "Merge sequentially, not simultaneously — 1개 머지 후 잔여 브랜치를
갱신된 main 위로 rebase"(놀람 충돌을 한 번에 1브랜치로 한정). Graphite: "textual clean
merge 라도 semantic conflict 는 남는다 — 테스트+사람(diff 열람) 리뷰는 비타협".
다수 에이전트가 갱신하는 공유 체크리스트/조정 파일 자체가 충돌 표면이 된다는 관측도
복수 소스에서 확인(우리 ROADMAP·REGISTRY 류 문서도 해당).
[https://www.augmentcode.com/guides/multi-agent-ai-system-code-development ·
https://graphite.dev/guides/ai-code-merge-conflict-resolution]

### W-009 · stale 브랜치 자동 정리의 공통 안전장치 4종
GitHub Actions 생태계 정리 봇들의 공통 규약: ① open PR 소속 제외 ② N일 무커밋 기준
③ **dry-run 이 기본값** ④ 삭제 전 통지 + 유예기간. 로컬 worktree 정리에도 그대로 이식
가능.
[https://github.com/cbrgm/cleanup-stale-branches-action ·
https://github.com/marketplace/actions/remove-stale-branches]

### W-010 · 병목은 코드 생성이 아니라 리뷰 용량·태스크 분해 품질
Simon Willison: "the bottleneck is how fast I can review results" — 병렬로 돌릴 것은
리뷰 비용 낮은 태스크(리서치·scout·유지보수). 실패 사례: 모호한 태스크("refactor the
backend")를 3 에이전트에 주면 상충하는 재해석 3개가 나와 아무것도 못 머지(battyterm).
머지 전 테스트 게이트만으로 "에이전트가 뭔가 부쉈다" 비율 ~80% 감소 보고.
[https://simonwillison.net/2025/Oct/5/parallel-coding-agents/ ·
https://dev.to/battyterm/5-lessons-from-running-ai-coding-agents-in-parallel-53on]

### 우리 계획과의 대조 (검증 요약)
| 우리 후보 | 외부 검증 |
|---|---|
| C-06/C-08 fragment·autogen | W-004 표준 확인 — **강화 채택** |
| C-02 alembic gate | W-005 표준 확인 + **의도적 충돌 파일 패턴 추가 채택** |
| C-07 merge mutex | W-002 불변식·실사례 확인, W-003 으로 GH MQ 대안 배제 확정 — **채택 유지** |
| C-04 stale sweep | W-009 안전장치 4종을 guard 로 수입 |
| C-13 WIP 상한 (당초 defer) | W-006 정량 근거 + W-008 순차 머지 — **채택으로 승격** |
| C-14 GitHub merge queue (reject) | W-003 으로 불가 확정 (Mergify 만 재론 트리거) |
| C-01 § timestamp | W-005 Rails 순번→timestamp 전환 역사와 동형 |
| 격리 강화 불요 판단 | W-001/W-007 — 격리는 충분, 머지 규율·착지점이 본체 |

## 4. 재측정 방법 (효과 검증 기준선)

본 initiative 의 효과는 30일 후 동일 방법으로 재측정해 비교한다:
```bash
# (repo checkout 에서) 충돌 봉합 커밋 비율
git log --oneline -300 | grep -ciE 'conflict|충돌|재번호|renumber|re-parent|stale 정정'
# 핫스팟 상위 30
git log --since='30 days ago' --name-only --pretty=format: | sort | uniq -c | sort -rn | head -30
# 브랜치 부채
git branch -r | grep -c 'ai/'; git branch -r --no-merged origin/main | grep -c 'ai/'
```
기준선(2026-07-10): 충돌 봉합 11/300(3.7%) · 원격 ai/* 223(미머지 73) · TASK.md § 중복 2건.

> **스냅샷 조건 명기(재현성)**: 브랜치·커밋 수치는 fetch 시각과 측정 체크아웃에 민감하다
> (같은 날 main 체크아웃 실측 223/73 vs 본 worktree 실측 200/55 — sweep·머지 진행에 따라
> 변동). 재측정 시 **main 체크아웃에서 `git fetch --prune` 직후** 실행하고 실행 시각(KST)
> 을 함께 기록해 동일 조건으로 비교한다. 파일 변경횟수도 30일 창의 이동에 따라 ±10%
> 변동(admin.js 201→236 관측) — 절대값보다 순위·추세로 비교.
