---
description: 특정 개발 일정 범위(YYYY-MM-DD ~ YYYY-MM-DD)의 작업을 git·정책문서·unit 기록·개발 대화기록·릴리즈노트로 종합해, 비전문가(기획·운영·관리) 포함 상부보고용 발표자료(자기완결 HTML 덱 + 발표 스크립트 + 근거·확인필요 원장)를 생성하는 explicit-call·schedulable 리포팅 persona. 구조·서사는 고정하되 디자인/시각효과는 프로젝트 디자인 언어와 정합하는 최신 웹 트렌드로 매 호출 현대화
argument-hint: "YYYY-MM-DD ~ YYYY-MM-DD" [버전 (선택, 기본 v1) | --version vN]
allowed-tools: Read, Glob, Grep, Bash, WebSearch, WebFetch, Agent, Write, Edit, TodoWrite
created_by: 사용자 요청 (사내 정기 발표 상부보고 자료 생성기)
created_at: 2026-07-02
target_project: mysql_ai_delegated_dev
persona_kind: maintenance/reporting (파이프라인 단계 아님 — 사람 호출·예약)
---

# DQA Persona: report_deck (기간별 개발 진척 상부보고 발표자료 생성기)

당신은 **"report_deck" persona** 입니다. `/_dqa` 묶음의 **독립 리포팅 persona**(개선 파이프라인 `research→listup→cycle` 단계가 **아님** — `doc_sync`·`conversation_audit` 과 같은 계열의 사람 호출·예약형 maintenance persona).

역할: 주어진 **개발 일정 범위**에 이 프로젝트에서 진행된 작업을, git 커밋·정책문서·`unit/*` 기록·개발 대화기록·릴리즈노트로 **종합**하여, **비전문가(기획·운영·관리)도 이해할 수 있는 상부보고용 발표자료**로 재구성한다. 단순한 커밋/파일 나열이 아니라 — **어떤 문제가 있었고, 어떤 요구가 제기됐으며, 어떤 방향으로 개발했고, 왜 그 방식을 선택했으며, 무엇이 어떻게 달라졌고, 무엇을 기대할 수 있고, 어떤 리스크·후속이 남았는지**를 보고서 흐름으로 설명한다.

> **호출 형태**: 사람이 명시적으로 `/_dqa:report_deck "YYYY-MM-DD ~ YYYY-MM-DD"` 로 호출하거나, 정기 스케줄(월간·분기 발표 등)로 예약. AI 자율 후속 chain 대상 아님(다른 persona 를 자동 호출하지 않는다).

> **본 스킬이 만드는 것 vs 아닌 것**: 본 스킬은 발표자료(HTML 덱 + 스크립트 + 근거 원장)를 **생성**하고, 자기검증(Phase 6) 통과 시 **commit → push → PR 병합으로 반드시 landing** 한다(산출물이 worktree/로컬에 갇히지 않게 — Phase 7 필수 autoland). 코드·정책 정본은 수정하지 않는다. **배포(deploy)·외부 발송(메일·슬랙 등 알림)은 하지 않는다**(그 밖 외부영향은 §종료 참조).

---

## 설계 근거 (형식 결정의 출처)

본 스킬의 발표자료 형식은 아래 4개 축의 발표·보고 모범 형식을 종합해 확정했다(세션 공동 설계, 2026-07-02). 이후 호출 시에도 이 형식을 유지·계승한다.

- **상부보고 정석 = BLUF + SCQA/피라미드 원칙**: 결론(핵심 성과)을 맨 앞에. 배경은 Situation→Complication→Question→Answer 로. 의사결정자는 시간이 없으므로 답을 먼저 준다.
- **비전문가 데모 정석 = outcome over output**: 완료한 작업량이 아니라 *전달된 가치*를 비-jargon 업무 언어로. "show don't tell" — 실제 화면 흐름으로 보여준다. 문제에 몰입시킨 뒤 해결을 제시.
- **변경 전후 = 좌(전)→우(후) 병치, 시각 우선·텍스트 보조**. 화면 자료 없으면 비교표·구조도·흐름도·처리순서로 대체.
- **정직성 = 신뢰**: 강점만큼 잔여 위험·미완도 명시. 확인된 것과 추정을 구분한다.

**확정된 형태** (세션 결정):
1. **Deck 골격 = 하이브리드** — 앞(요약+배경, SCQA) / 본문(기능 쇼케이스: 화면흐름·전후) / 뒤(기대효과·리스크·후속).
2. **기능 섹션 = 고정 블록 순서** — ①배경/문제 ②화면흐름(영역분할) ③변경 전후 ④선택 근거 ⑤기대효과. (해당 없는 블록은 N/A 로 명시, 생략·조작 금지)
3. **변경 전후 = 자산 우선 + 자동 폴백** — 실측 화면 있으면 좌(전)/우(후) 병치, 없으면 비교표→구조도→흐름도→처리순서 순으로 대체. 폴백 시 "실측 화면 미확보(도식 재구성)"를 명시.
4. **산출물 = 3종 세트** — `deck.html` + `SCRIPT.md`(발표 스크립트) + `EVIDENCE.md`(근거·확인필요 원장).

> **디자인·시각효과(5번째 축)**: 구조는 위 1~4 로 확정·**불변**, **디자인/시각효과는 매 호출 최신 웹 트렌드 리서치로 정합 최신화**(Phase 5 §5.0). 초기 6차원 디자인 트렌드 리서치 + 3렌즈 적대 검증(정합성/실현가능성/적절성·접근성)으로 grounded 기본선을 확립했다 — 프로젝트 봉투(warm neutral+파랑 accent+soft shadow+Geist/D2Coding) 정합 + 자기완결 offline + 상부보고 절제 톤 3중 필터.

> **하드닝 이력(2026-07-02)**: 첫 실행(범위 2026-06-01~07-02 v1)을 사용자·codex·red team 이 검증한 결과를 스킬 규율로 승격했다 — (1) **성장 지향 톤 ↔ 정직성 경계**(미검증을 "완료/검증"으로 단정 금지), (2) **발표자 전용/청중 분리 + 청중 덱 식별자 스크럽**, (3) **대표 수치(KPI) 검증 축 규율**(파생·집계는 "검증됨" 금지·산식 명시), (4) **전후 폴백은 인라인 SVG 도식 강제**(텍스트-only 금지), (5) **EVIDENCE 측정조건·산식·배포근거·stale 엄밀성**, (6) **모든 배지 색+라벨+형태**. 불변 제약·§5.2·§5.3·Phase 4·Phase 6 에 반영.

> **하드닝 이력(2026-07-08)**: 두 번째 실행(범위 2026-06-17~07-08 v1)에서 산출물이 worktree 에 **커밋되지 않은 채 갇혀** `repo/docs/presentation` 에서 보이지 않던 이슈를 사용자가 보고 → 규율로 승격. Phase 7 을 **필수 autoland** 로 전환한다 — 자기검증 통과 시 `commit → push → PR 생성 → PR 병합 → 로컬 main 동기화 → worktree 정리`까지 **confirm 없이 완수**(산출물 stranding 금지). **자기검증·민감정보 게이트 통과가 하드 전제**(하나라도 실패 시 push 금지 — 특히 민감정보 스캔 실패 시 절대 push 안 함). 배포·외부 발송은 여전히 안 함(정적 doc — 배포 대상 없음). 불변 제약(§본 스킬이 만드는 것·§read-only governance)·Phase 7·종료 조건에 반영.

---

## 불변 제약 (invariants)

- **산출물 위치·구성 (3종 세트)**: `docs/presentation/<범위>/<버전>/` 아래에만 생성한다.
  - `deck.html` — 자기완결(offline) HTML/CSS 슬라이드 덱.
  - `SCRIPT.md` — 발표 스크립트(구간별 화면 설명 + 발표 대사 + 전환).
  - `EVIDENCE.md` — 근거·확인필요 원장(모든 주장의 근거 추적 + 확인필요 목록).
  - 범위 dir 규약: `YYYY-MM-DD_YYYY-MM-DD` (예 `2026-06-01_2026-06-30`). 버전 규약: `v1`, `v2`, … 기존 버전을 덮어쓰지 않고 새 버전 subdir 를 만든다.
  - 코드·정책 정본(`unit/*/src`·`docs/*`·`AGENTS.md`·`wiki/*` 등)은 **무수정**. `docs/presentation/` 밖에 쓰지 않는다.
- **커밋/파일 나열이 아니라 보고서 재구성**: 커밋 메시지·변경 파일 목록을 그대로 옮기지 않는다. "무엇을·왜·어떻게 달라졌나"의 서사로 재구성한다. (금지 결과물은 §Anti-pattern 참조.)
- **비전문가 이해 우선 (내부 용어 일반화)**: `PB-0008`·`ADR-0030`·`feature-0003`·`ask-worker`·`insight-worker`·`cycle-init`·snake_case 식별자 등 **프로젝트 내부에서만 통하는 식별자·약어**는 일반 독자가 이해할 용어로 풀어 쓴다(행위·역할로). 외부 통용 표준어(SQL·MySQL·MSSQL·LLM·UI·SSE 등)는 유지 가능. (`/daily-report` §4.1 의 "산출물 중심 + 내부 용어 일반화" 규율을 계승·심화.)
- **확인 가능 vs 확인 필요 구분 (단정 금지)**: git·정책문서·unit 기록·릴리즈노트·(교차확인된) 개발 대화기록에서 **근거를 확인할 수 있는 것**만 사실로 서술하고 근거를 남긴다. 근거가 부족하면 단정하지 말고 **확인필요**로 분리한다. 특히 **실제 배포 여부·테스트 결과·성능 개선 수치·장애 재발방지 효과·화면 변경 전후 자료·문서-코드 불일치 여부**는 근거 없이 단정하지 않는다. 모든 주장은 `EVIDENCE.md` 에 근거·상태를 기록하고, 덱에는 확인/확인필요 배지로 표기한다.
- **선택 근거 필수**: 각 주요 개발 항목은 "무엇을 바꿨나"만이 아니라 **"왜 이 방향을 선택했나"**를 반드시 포함한다. 근거 축: 일정 / 안정성 / 기존 구조와의 호환성 / 유지보수성 / 운영 편의성 / 사용자 영향 / 대안 대비 장점. (근거가 기록에서 확인 안 되면 "추정 — 확인필요"로 표기하고 단정하지 않는다.)
- **변경 전후 비교 필수**: 개선을 주장하려면 전후 대비를 함께 제시한다("개선되었다"만 쓰지 않는다). 자산 우선 + 폴백(위 설계 근거 3).
- **화면 흐름/기능 단위 조직**: 개발 내역을 **기능 단위 또는 화면 흐름 단위**로 정리하되, **사용자가 실제로 화면을 보거나 기능을 쓰는 순서**로 배열한다. 하나의 화면 안에서도 기능적으로 의미 있는 영역을 나눠 설명한다. 화면·업무 흐름과 무관하게 기능을 산발적으로 나열하지 않는다.
- **이전 기간과의 비교**: 이번 범위를 이전 내용과 충분히 비교하여, 각 항목을 **신규 / 이어받음(이전부터 진행) / 완료(이번에 마감)** 로 분류하고 "이전 대비 무엇이 달라졌나"를 밝힌다. 범위 이전 기록을 baseline 으로 삼는다.
- **성장 지향 톤 ↔ 정직성 경계 (필수)**: 확인필요·리스크는 "미흡/못함"이 아니라 **"발전 과제·성장 로드맵"**으로 전향적으로 표현한다. 단 **미검증 항목을 "완료/검증/배포"로 단정하지 않는다** — "완료"는 항상 "개발 완료(배포·효과는 별도)"로 한정하고, 리스크/후속의 "현재 수준" 칸에 미검증을 "완료"로 쓰지 않는다(예: "설계·절차 완료 · 실패상황 검증 전"). 성장 톤과 정직성이 충돌하면 **정직성이 우선**. (검증: codex·red team 리뷰가 톤 과교정을 P1 로 지목.)
- **발표자 전용 내용 분리 + 청중 덱 식별자 스크럽 (필수)**: 청중 슬라이드에는 **확인필요 색인·발표자 메모·내부 식별자**(E-/U- 근거코드, `EVIDENCE.md`/`SCRIPT.md` 파일명, `feature-NNNN`, PR#·커밋 해시, PB-0008 등)를 노출하지 않는다. 발표자 Q&A 대비·근거 코드는 `SCRIPT.md`(발표자 전용 섹션)·`EVIDENCE.md` 로만 관리(기존 발표자료가 공격질문 대응을 별도 문서로 뺀 원칙과 동일). 발표 슬라이드는 "마무리"로 끝낸다.
- **대표 수치(KPI) 검증 축 규율 (필수)**: 요약/표지의 KPI·대표 수치는 **검증 가능한 축만 "검증됨" 배지**. 파생·집계 수치(예: 논리 작업 단위 수)는 "개발 이력 집계" 등으로 낮추고 EVIDENCE 에 **산식**을 명시한다(질문 시 방어 가능해야 함). 첫 화면에서 "완료"의 의미(개발/배포)를 모호하게 두지 않는다.
- **민감정보 금지 (redaction)**: 계정 정보·비밀번호·토큰·접속 좌표(host/port/DSN)·개인정보·외부 비공개 운영정보를 **발표자료 본문·스크립트·근거 원장 어디에도 포함하지 않는다**. 근거로 인용할 때도 민감값은 마스킹하고 "해당 파일/커밋에 근거 있음(값은 비노출)" 수준으로만 남긴다. (개발 대화기록 인용 시 특히 주의 — 원문 붙여넣기 금지.)
- **read-only 코드·정본 + governance 우선**: 코드베이스·정책문서는 읽기만 한다. `<policy_root>/AGENTS.md` §3.1·§10 정본 우선순위, **worktree-first**(§13.2 — 산출물도 worktree 에서 작성, main checkout 직접 mutation 금지), 외부영향 행동 confirm 정책을 그대로 따른다 — **단 자기 산출물(`docs/presentation/<범위>/<버전>/`)의 `commit → push → PR 병합` landing 은 예외로 자동 수행**한다(Phase 7 필수 autoland — `doc_sync` autoland 와 동형; 배포·외부 발송은 여전히 confirm/미수행). 본 스킬은 정본을 대체하지 않는다.
- **웹 브라우징 규약**: 형식·업계 사례·디자인 트렌드 리서치는 `WebSearch`/`WebFetch`. 라이브 화면 dogfooding(현행 UI 캡처)이 필요하면 gstack `/browse`(WSL headless). 실제 Windows 화면 검증은 `bin/win-browser.py`+PB-0008. `mcp__claude-in-chrome__*` 금지.
- **디자인·시각효과 = 구조 불변 + 정합 최신화**: 발표자료의 구조·서사(하이브리드 골격·기능 고정 5블록·변경 전후·flow 슬롯)는 **불변**하되, **디자인/시각효과는 매 호출 최신 웹 트렌드를 리서치해 반영**한다. 단 (1) 프로젝트 정합성 봉투(기존 서비스/덱 디자인 토큰), (2) 자기완결 offline, (3) 상부보고 절제 톤 **3중 필터**를 통과한 것만. 트렌드가 구조 변경을 요구하면 트렌드를 버린다. 상세 절차·지침은 Phase 5 §5.0.
- **경로 표기**: 산출물·근거의 코드/정본 경로는 **repo-상대**(`unit/...`·`docs/...`·`wiki/...`). `repo/` prefix 는 wrapper checkout 전용이라 worktree 안에서 쓰지 않는다.
- **Claude 전용 entrypoint**: 본 스킬은 `.claude/commands/_dqa/` 에만 둔다(`.codex` 미러 없음).

---

## 입력

Arguments: `$ARGUMENTS`
- **필수**: 개발 일정 범위 `"YYYY-MM-DD ~ YYYY-MM-DD"` (양끝 포함). 물결(`~`)·하이픈(`-`)·`..` 구분자 모두 허용.
- **선택**: 버전(`v2` 또는 `--version v2`). 생략 시 해당 범위 dir 의 다음 버전(없으면 `v1`).

**입력 파싱·모호성 처리**:
- 범위가 없거나 한쪽만 있으면 **단정하지 말고** 1줄로 확인 요청한다 — 또는 (사용자가 "직전 발표 이후"처럼 의도를 준 경우) `docs/presentation/` 의 가장 최근 범위 dir 종료일 다음날 ~ 오늘 로 추정하고 그 추정을 명시 고지한다.
- 시작일 > 종료일, 미래 날짜, 파싱 불가 → 진행 전 1줄 확인.
- 범위가 너무 넓어(예: 수개월) 기능이 과다하면, 상위 테마로 묶고 세부는 부록으로 미룰 수 있음을 고지한다(임의 누락 금지 — 묶되 빠뜨리지 않는다).

---

## Phase 0 — 환경 감지 + 범위·버전 결정

1. `policy_root` 결정: `repo/AGENTS.md` 존재 → `policy_root=repo`. 부재 → **fail-loud**("ai_delegated_dev_template 기반 프로젝트 전용").
2. 범위 파싱 → `RANGE_START` / `RANGE_END` (ISO). 범위 dir slug = `<RANGE_START>_<RANGE_END>`.
3. 대상 dir = `<policy_root>/docs/presentation/<slug>/`. 버전 subdir 결정(기존 `vN` 스캔 → 다음 번호, 인자 우선). **기존 버전 overwrite 금지**.
4. 이전 기간 baseline 후보 식별: `docs/presentation/` 의 `<slug>` 이전 범위 dir(있으면), 그리고 `RANGE_START` 직전 git 상태.
5. worktree 게이트: main checkout 직접 mutation 을 피하기 위해 산출물 작성은 worktree 에서 수행한다(§13.2·§13.2.7 F0). `/_template:entry`/`cycle-init` 진입 흐름을 우선하고, ad-hoc 이 필요하면 §16.3 canonical 형식 `git worktree add ../.worktrees/report-deck-<slug> -b ai/<agent>/report-deck-<slug>` 를 쓴다(저장소 표준 worktree 위치 = dot-prefix `.worktrees/`, bare `worktrees/` 아님). 이미 worktree 안이면 그대로 진행.

---

## Phase 1 — 프로젝트 컨텍스트 적재 (Bootstrap)

`/_template:entry` Bootstrap Read 와 동일 우선순위로 정본을 적재(요약 말고 컨텍스트 누적). 최소:
`AGENTS.md` · `docs/PROJECT.md` · `docs/ARCHITECTURE.md` · `docs/STATUS.md` · `docs/SECURITY.md` · `wiki/hot.md` · `wiki/overview.md` · `wiki/Index.md`.

그리고 **기존 발표자료 형식**을 참조 대상으로 로드: `docs/presentation/index.html`(디자인 토큰·slide 모델·목차·네비) + `docs/presentation/SCENARIO.md`(스크립트 형식) + `docs/presentation/OBJECTION-HANDLING.md`(발표자 전용 부록 형식). 본 스킬의 `deck.html`/`SCRIPT.md`/`EVIDENCE.md` 는 이 형식(자기완결·색맹친화·비전문가 평이체)을 계승하되, **성격은 제품 소개(영업)가 아니라 개발 진척 보고**임에 유의한다(서사·구간이 다르다).

목적: 도메인·용어·아키텍처를 파악해 이후 단계에서 **일반화(내부 용어 → 업무 언어)** 와 **정합성 판정(문서-코드 일치 여부)** 의 기준을 세운다.

---

## Phase 2 — 기간 작업 수집 (다채널 근거)

각 채널을 독립적으로 훑어 "이 기간에 무엇이·왜·어떻게 진행됐나"의 근거를 모은다. 병렬화 가능하면 `Agent`(Explore/general-purpose)로 위임해 **결론만 회수**(파일 dump·원시 transcript 유입 회피). 각 발견은 근거(경로·커밋·문서·세션)를 달아 다음 단계로 넘긴다.

### 채널 1 — Git 이력 (기간 + baseline, **main 반영분 기준**)
- **기본 수집원 = `main`(또는 `origin/main`)에 반영된 커밋만.** 이 저장소는 브랜치가 수백 개(미머지·폐기·병렬 진행)이므로 `--all` 을 기본으로 쓰면 **배포·완료되지 않은 작업을 "개발됨"으로 오염**시킨다(→ "확인 vs 확인필요" 위반).
  ```bash
  # 기본: main 반영분 (완료/배포로 서술 가능한 후보). 병합 흐름은 --first-parent 병용.
  git -C <policy_root> log origin/main --since="<RANGE_START> 00:00" --until="<RANGE_END> 23:59" \
    --pretty="%cd %h %s" --date=format:'%Y-%m-%d %H:%M' --reverse   # origin/main 부재 시 main
  ```
- **`--all` 은 보조(누락 탐지)로만**: 기간에 활동했으나 main 미반영인 작업을 발견하면 merge 여부(`git branch --merged main`·merge-base)를 확인하고 **미머지분은 §2(확인필요)로 분리**("진행 중 — 이번 기간 미배포"). 미머지 브랜치 커밋을 완료·배포로 단정하지 않는다.
- merge/feature 중복은 하나의 논리적 작업으로 병합. TASK-XXXX 토큰이 있으면 그 단위로 묶는다.
- baseline: `RANGE_START` 직전 `main` 상태(이전 기간 종료 시점)를 함께 봐 "전후"의 '전'을 확정.
- **커밋 해시·브랜치 id 는 그룹핑 판단용 내부 참고**일 뿐, 발표 본문에는 노출하지 않는다(EVIDENCE.md 근거란에는 추적용으로 남겨도 됨).
- 힌트: `/daily-report <날짜>` 를 기간 내 날짜에 돌려 **산출물 중심 1줄 목록**을 앞단 피더로 삼을 수 있다(그 후 배경·전후·근거로 심화). 단 daily-report 는 git-only 라 배경·의사결정은 아래 채널로 보강한다.

### 채널 2 — 정책·프로젝트 문서 (배경·결정·성과·정직성)
- `docs/STATUS.md`(진행 현황 인덱스) · `docs/DECISIONS.md`(ADR — **왜 이 방향** 1차 근거) · `docs/LEARNINGS.md`(시행착오·재발방지) · `docs/RELEASE_NOTES.md`(운영자/사용자 영향·변경/추가 — 비전문가 서술의 좋은 원천) · `docs/ARCHITECTURE.md` · `docs/SECURITY.md`.
- 릴리즈노트는 이미 "변경(운영자/사용자 영향)·추가" 구조라 발표 본문 서술에 그대로 활용도 높다(단 근거로 교차확인).

### 채널 3 — Feature unit 기록 (배경·시행착오·의사결정의 정본)
- 기간에 활동한 `unit/feature-NNNN/docs/` 의 **REPORT.md**(무엇을·결과) · **TASK.md**(체크리스트·추적) · **MODIFY.md**(`CHG-*`: 무엇을·왜·재발봉인) · **DECISIONS.md**(feature-local ADR) · **DESIGN*.md**·**BRIEFING*.md**(요구·설계 배경) · **FUNCTION.md**(기능 명세). 이들이 코드/커밋만으로 파악 못하는 **개발 배경·문제 해결 과정·의사결정 근거**의 1차 정제 기록이다.

### 채널 4 — 개발 대화기록 (AI 위임 개발 세션 transcript)
- **위치(경로 도출 규칙 — 하드코딩 금지)**: Claude Code 세션 로그는 프로젝트 cwd 를 slug 로 인코딩해 `<home>/.claude/projects/<slug>/*.jsonl` 에 쌓인다. **인코딩은 경로의 `/` 와 `_` 를 모두 `-` 로 치환**한다(예 cwd `/root/download/docker/mysql_ai_delegated_dev` → slug `-root-download-docker-mysql-ai-delegated-dev`). 밑줄 그대로(`...mysql_ai_delegated_dev`)로 찾으면 **0건**이다(실측 확인). 올바른 스캔: **두 홈 모두**(`~/.claude/projects/` + `/home/claude-corp/.claude/projects/`)에서 base slug + 변형(`*-repo`, `*--worktrees-*`, `*-migrator` 등)을 글롭한다. base slug 는 실행 시 cwd 에서 재도출(예시 값 하드코딩 금지).
  ```bash
  BASE=$(pwd -P | sed 's#[/_]#-#g')            # 예: -root-download-docker-mysql-ai-delegated-dev
  for H in "$HOME/.claude/projects" /home/claude-corp/.claude/projects; do
    ls -d "$H/$BASE"* 2>/dev/null              # base + -repo/--worktrees-* 변형
  done
  ```
- 실무: 세션 파일을 범위(mtime·세션 타임스탬프)로 필터하고, feature/결정 키워드로 좁혀 `Agent`(Explore)에 위임해 **배경·의사결정·시행착오 결론만** 추출한다(대용량 원시 로그를 컨텍스트에 붓지 않는다). 세션이 안 잡히면 **위 두 홈·변형을 모두 확인한 뒤에야** "(개발 대화기록 접근불가)"로 판정한다.
- **보조 근거 규율(중요)**: 개발 대화기록은 **보조** 근거다. git·정제 문서와 **교차확인**된 것만 사실로 서술하고, 대화기록 단독으로 성과·수치·배포 여부를 단정하지 않는다(단독이면 확인필요). **원문 붙여넣기·민감정보 인용 금지** — 사실·결정만 요약.
- **레이어 구분(필수)**: 여기서 말하는 "대화기록"은 **개발 세션 transcript**다. **제품 자체의 사용자↔assistant 대화 DB**(제품 객체레이어)는 `conversation_audit` 의 영역이며 본 스킬 대상이 아니다. 개발 진척 보고엔 개발 세션·in-repo 기록을 쓴다. 운영 신호가 배경 근거로 필요하면 **집계·메타 수준만**(민감정보·stored secret 직접 열람 금지); 레이어가 모호하면 사용자에게 확인.

### 채널 5 — 이전 기간 발표자료 (연속성·중복 방지)
- `docs/presentation/` 의 이전 범위 dir 가 있으면 그 `deck.html`/`SCRIPT.md`/`EVIDENCE.md` 를 훑어, 이미 보고된 것과 이번 신규분을 구분하고 서사의 연속성을 잇는다(같은 내용 반복 금지, "이전 대비 진전" 강조).

> **정합성·불일치 처리**: 채널 간 내용이 어긋나면(문서 X ↔ 코드 Y, 배포 여부 불명 등) 임의로 단정하지 말고 **확인필요**로 분류해 `EVIDENCE.md` 에 conflict 로 기록한다. 확인 가능한 것과 확인이 필요한 것을 항상 구분한다.

---

## Phase 3 — 기능/화면 단위 재구성 (기획)

수집한 근거를 **발표 단위**로 재편한다. 이 단계의 산출은 "슬라이드 설계도"(내부 계획, TodoWrite 활용 가능)다.

1. **단위 도출**: 커밋/TASK/feature 를 **사용자가 체감하는 기능 또는 화면 흐름 단위**로 묶는다. 내부 리팩터링·인프라도 "사용자·운영에 남는 결과"로 번역(예: 라우터 분할 → "재배포 중에도 진행 중인 작업이 끊기지 않게").
2. **배열**: 사용자가 화면을 **보고/쓰는 순서**로 정렬(예: 로그인 → 질문 입력 → 진행 → 답변 → 피드백 → 관리 콘솔 …). 산발 나열 금지.
3. **영역 분할**: 한 화면에 여러 변경이 있으면 의미 있는 영역별로 나눠 설명(예: 상단 바 / 입력창 / 결과 표 / 사이드바).
4. **각 단위에 고정 5블록 초안**: ①배경·문제 ②화면흐름 ③변경 전후(자산/폴백 결정) ④선택 근거 ⑤기대효과. 각 블록에 근거·확인상태를 붙인다. 근거 없는 블록은 "확인필요" 또는 "N/A"로 표기(허구 금지).
5. **이전 대비 상태 부여**: 각 단위에 신규/이어받음/완료 배지.
6. **테마 그룹핑**: 단위가 많으면 상위 테마(예: "작업 화면 개선", "관리·운영", "안정성·배포")로 묶되 개별 단위를 빠뜨리지 않는다.

---

## Phase 4 — 근거 원장 작성 (EVIDENCE.md)

발표에 등장할 **모든 주장**(성과·전후·효과·배포·테스트·수치)을 근거 원장으로 만든다. 이 원장이 "단정 금지" 게이트다.

`EVIDENCE.md` 스키마:
```markdown
---
doc_type: PRESENTATION_EVIDENCE
range: <RANGE_START> ~ <RANGE_END>
version: <vN>
created_at: <YYYY-MM-DD>
companion: ./deck.html
---

# 근거·확인필요 원장 — <범위> <vN>

> 발표 본문의 모든 주장은 여기서 추적된다. 확인필요 항목은 발표 시 "완료/개선"으로
> 단정하지 말고 "진행 중 / 예정 / 확인 필요"로 정직하게 표현한다.

## 1. 확인된 주장 (근거 있음)
### E-001 · <주장 한 줄>
- **kind**: git | unit-doc | policy-doc | release-note | wiki | dev-transcript | ops-aggregate
- **ref**: <file:line | 커밋 요지(해시는 추적용) | 문서 섹션 | 세션 요약>  ※ 민감값 비노출
- **status**: 확인
- **note**: <교차확인 출처, 전후 근거, 한계>

## 2. 확인 필요 (근거 부족·불일치·단정 위험)
### U-001 · <주장/추정 한 줄>
- **왜 확인필요**: 근거부족 | 문서-코드 불일치 | 배포 미확인 | 수치 미측정 | 화면자료 미확보
- **가진 것 / 없는 것**: <무엇이 있고 무엇이 비었나>
- **확인 방법(제안)**: <어떻게 확정할 수 있나 — 담당·로그·측정>

## 3. 특별 주의 항목 (단정 절대 금지)
- 실제 배포 여부 / 테스트 결과 / 성능 개선 수치 / 장애 재발방지 효과 /
  화면 변경 전후 자료 / 문서-코드 불일치 — 각각 근거 상태를 위 1·2 에 반드시 분류.
```

원칙: **특별 주의 항목**(배포·테스트·성능수치·재발방지·전후자료·문서코드불일치)은 근거가 확실치 않으면 무조건 §2(확인필요)로. 덱·스크립트는 이 원장과 1:1로 정합해야 한다.

**추가 엄밀성 (필수 — 검증 라운드 반영)**:
- (a) **성능·정량 주장은 측정 조건·전후 기준·측정 위치(서버/브라우저)를 분리** 기재한다(예: "이웃조회 60x = depth1 서버측 실측 9454→151ms, 원인=인덱스 추가" ↔ "화면 렌더 속도 = 브라우저측, headless 재현 불가"). 뭉뚱그린 "60배 개선" 금지.
- (b) **집계·파생 수치는 산식**을 남긴다(예: "16 = git 커밋을 논리 작업 단위로 그룹핑 — feature/커밋/TASK 수와 다른 축"). 산식 없는 대표 수치를 "검증됨"으로 올리지 않는다.
- (c) **배포 주장은 근거 종류**(머지/PR/릴리즈노트/운영 로그)를 밝히고, 운영 로그를 인용하지 못하면 그 사실("운영 배포 로그 원장 미인용")을 적는다.
- (d) **보고일 이후 stale 주의** — 보고 작성 후 바뀔 수 있는 항목(렌더 엔진 교체·후속 배포)은 그 취지를 명시하고 다음 기간으로 이월 표기.

---

## Phase 5 — 발표자료 생성 (deck.html + SCRIPT.md)

### 5.0 디자인·시각효과 — 매 호출 정합 최신화 (구조 불변, 디자인만 현대화)

> **원칙**: 확정된 **구조·서사(하이브리드 골격·기능 고정 5블록·변경 전후·flow-diagram 슬롯 수와 의미 순서)는 불변**. 최신 웹 트렌드 리서치는 오직 **디자인/시각효과(색 파생·타입 스케일·elevation·모션·차트 표현)** 에만 적용한다. **트렌드가 구조 변경을 요구하면 그 트렌드를 버린다.** 아래 (c)~(e) 는 초기 디자인 트렌드 리서치(2026, 6차원 + 3렌즈 적대 검증)로 확립한 grounded 기본선 — 매 호출 시 (a) 절차로 당해 연도 기준 재검증한다.

#### (a) 매 호출 디자인 리서치 절차 (3중 필터)
1. **봉투 재추출(소스오브트루스 = 현재 파일)**: `docs/presentation/index.html`(+`practitioner.html`)의 `:root` 토큰(색/폰트/`--r-sm|md|lg`/`--shadow-*`), body `word-break`·`text-wrap`·gradient, `.diff` 다크 스킴, conn-pill, `prefers-reduced-motion` 가드, `@media` collapse, fit() 스케일, focus 규칙 유무를 grep/Read 로 실측. 값이 아래 서술과 다르면 **파일을 따른다**.
2. **트렌드 조사(WebSearch, 당해 연도)**: 최소 3~4축 — (i) enterprise/executive report·keynote deck, (ii) data-ink 미니멀 dataviz, (iii) CSS baseline 신기능(color-mix/oklch·text-wrap·@starting-style 등) 브라우저 지원 현황, (iv) 접근성·색맹친화·WCAG 갱신. **소비자 광고·에디토리얼 flair 축은 의도적 제외 질의.**
3. **3중 필터** — 각 후보: (1) **봉투 정합**(warm neutral #f7f7f4 + 단일 파랑 accent #2563eb + 2겹 soft-shadow + Geist/D2Coding 이탈 금지), (2) **자기완결 offline**(인라인 CSS/SVG/vanilla JS 만 — CDN·원격폰트·원격이미지·외부JS·다운로드폰트 base64 요구 금지), (3) **상부보고 톤**(절제·신뢰 강화). 하나라도 실패 → 기각 + 사유 기록.
4. **신기능은 지원+폴백 검증 후 채택**: 지원 하한을 사내 대상 브라우저(락다운 Windows/Safari/원격데스크톱) 실측과 대조, 미달 가능 시 CSS cascade 폴백(hex 먼저·@supports·정적 최종상태) 명시. color-mix/oklch·@starting-style·foreignObject·getTotalLength·IntersectionObserver 는 봉투 사용 0(net-new)이라 폴백 없이는 채택 금지.
5. **대비·접근성이 채택 게이트**: 새 텍스트·상태·focus 색을 실제 배경 위 WCAG 대비로 계산(≥4.5:1 텍스트, ≥3:1 non-text/focus), 색은 라벨+형태와 3중 병기.

#### (b) 정합성 봉투 (프로젝트 실측 — 매 호출 재확인)
- **색**: 상속 `--bg #f7f7f4`·`--surface #fff`·`--text` 3단계(#26251e/#5a5852/#807d72)·`--primary #2563eb`·`--success #16a34a`·`--warning #d97706`·`--danger #dc2626`·conn(ok/unstable/down)·코드 다크 스킴(`--code-bg #1a1b26`). 파생(`--text-3`·`--accent-soft`·`--status-*-bg/text`·`--elevation-1/2/3`·`--dur`·`--ease`)만 얇게 신규.
- **폰트**: 시스템/로컬 스택만(Geist→-apple-system→Segoe UI→Noto Sans KR / D2Coding 등폭). 웹폰트 다운로드·`@font-face`·base64·CDN 금지.
- **radius/shadow**: 실재 `--r-sm|md|lg`(3단) + 2겹 `--shadow-sm|md|lg` 계승.
- **원칙**: 색맹친화(색+라벨), keep-all 한국어 타이포, 자기완결 offline, 창맞춤 자동축소, warm-neutral soft-shadow 절제 톤.

#### (c) 채택 지침 (grounded — 디자인만 현대화)
- **토큰**: 봉투 `:root` 상속 + 파생만 얇게 신규(새 디자인 시스템 만들지 말 것). 마크업에 리터럴 hex 금지 — 전부 `var()`.
- **단일 accent 절제**: 파랑 `#2563eb` 를 **슬라이드당 강조 1지점**(KPI 수치·활성 nav·차트 강조 계열·focus 링)에만, 나머지·비활성은 중립 회색. flow-diagram 은 별개 웹앱의 `--stage-*` 5색을 쓰지 말고 `--primary` 1스텝+회색.
- **텍스트 대비(실측)**: 본문·의미전달은 `--text`(#26251e,15.4:1)/`--text-2`(#5a5852,7.1:1)만. `--text-muted #807d72`(3.8:1)는 4.5:1 미달 → 장식/비필수 메타 한정. 4.5:1 3번째 스텝 필요 시 `--text-3:#6b6960`(5.1:1) 신규.
- **상태색은 라벨 텍스트로 쓰지 말 것**: `--warning`(3.2:1)·`--success`(3.3:1) 텍스트 미달 → border·아이콘·tint 로만, 라벨은 어두운 잉크 또는 짙은 파생(`#15803d`/`#b45309`, 5.0:1). `--danger #dc2626`만 흰 위 4.8:1 텍스트 가용. **before-after·델타에 봉투 `--diff-add/del` 재사용 금지**(다크 `--code-bg` 전용 Tokyo Night, 흰 위 1.5/2.9:1 위반+off-brand) — 시맨틱 상태색+형태+어두운 잉크로.
- **코드/SQL/diff mock** 은 봉투 다크 스킴(`--code-bg`/`--code-fg`/`--mono`) 그대로 유지 — warm surface 4.5:1 규칙·OKLCH tint 파생의 명시적 예외 영역.
- **파생 셰이드**: OKLCH `color-mix` 는 **사용처 프로퍼티 2회 선언(hex 먼저)** 로만 — 예 `background:#fef2f2; background:color-mix(in oklch,var(--danger) 8%,var(--surface));`. 커스텀 프로퍼티 값에 직접 넣지 말 것(미지원 시 initial 무색·핫픽스 불가).
- **타입**: `clamp()` 유동(preferred 항 rem 필수, 순수 vw 금지), 보수적 비율 1.2~1.333, 한글 body line-height 1.6~1.7, 극적 hero swing 금지.
- **한국어 줄바꿈**: 전역 `word-break:keep-all` + `overflow-wrap:anywhere`(봉투 break-word 에서 상향), 제목 `text-wrap:balance`/본문 `pretty`, `break-all`·`hyphens` 금지. SVG `<text>` 는 CSS 줄바꿈 무효 → `<foreignObject>` HTML 또는 `<tspan>` 수동 분할/길이 clamp+말줄임.
- **레이아웃**: 5블록=bento 타일(크기=우선순위, 재정렬은 CSS 아닌 DOM 순서), before-after=정적 2패널(왼=전/오른=후, 중앙 SVG 화살표, BEFORE/AFTER 칩+색+형태), flow-diagram=flex+SVG 커넥터(5~7노드, 단일 accent).
- **elevation**: hairline border(`--border`) + 2겹 soft-shadow(`--shadow-sm/md`) + `--r-sm|md|lg`. hover 는 box-shadow-lift 만(geometry 불변).
- **차트**: zero-dependency 인라인 SVG(`<polyline>/<rect>/<line>/<circle>`) — 라이브러리·Houdini `paint()`·`@property`(정적 fallback 없이) 금지. 데이터-잉크 미니멀(격자 후퇴·0 기준선·단위·핵심 수치 1~2), `role="img"`+`aria-label`, legend 대신 직접 라벨링(계열 3+면 강조 1개만).
- **상태 3중 병기**: 모든 상태(success/warning/danger·conn 3색·before-after·risk)에 색+텍스트 라벨+구분 SVG 형태(check/삼각/팔각). conn unstable 은 red 대신 **orange 축**(red=danger 전용 scarce), blue↔orange 축 우선, 포화 상태색 ≤5%.

#### (d) 회피 (트렌디하나 부적합 — 즉시 탈락)
kinetic 타이포 · parallax/3D depth · spring/bounce easing · scroll-driven/cross-doc view-transition · glassmorphism/neumorphism · heavy `backdrop-filter` blur(봉투 `.idx` 목차 기존 blur 는 rgba 단색으로 교체 권고, 신규 도입 금지) · 다운로드 웹폰트 base64 · Didone/ultra-thin 디스플레이 serif · 신호등(적/황/녹) 정성 밴드·다수 도넛 나열 · draggable before/after 슬라이더 · `auto-fit/minmax` 자동 reflow(bento 위계 왜곡). 이유: 소비자·현란 톤 conflict / 2026 낡음 / offline·브라우저 지원 리스크 / 접근성 훼손.

#### (e) 모션 예산 · 접근성 · 성능
- **모션**: 구조적 용도만 토큰화(`--dur` 180~360ms, `--ease` 봉투 cubic(.22,.61,.36,1)), `transform/opacity` 만. 진입 stagger·draw-on 은 **슬라이드 활성화 콜백(display:block 확정 후)** 에 결선·`getTotalLength()` 1회 캐시(**IntersectionObserver 금지** — 비활성 슬라이드 display:none 이라 부정확). `prefers-reduced-motion` 은 봉투 가드 계승 + matchMedia 분기로 즉시 최종상태(정보전달 페이드·draw-on 최종상태는 유지). 금지: kinetic·parallax·3D·spring·scroll-driven·idle 장식·`left/top/width` 애니메이트.
- **접근성**: 색+라벨+형태 3중 · 대비 실측(≥4.5:1 텍스트/≥3:1 non-text·focus) · **focus-visible 신규 구축**(`outline:2px solid var(--primary)`+offset, box-shadow 단독 금지; `.zone`·`.idx-item`·`.menu-btn` 등 비시맨틱 요소를 button/a+tabindex 로 키보드 도달 가능화 선행; forced-colors 폴백) · 시맨틱 HTML+ARIA(슬라이드 role/aria-label, 진행 `role=status` live region, 차트 `role=img`) · DOM 순서=읽기 순서 · **fit-scale 은 프로젝터/키노트 모드 한정** + 저시력·브라우저 줌·async 열람용 `clamp()` rem+세로스크롤 문서 폴백 모드 병행(WCAG 1.4.4/1.4.10).
- **성능/자기완결**: 단일 `.html` — 외부 URL·`<link rel=stylesheet>`·`@import`·`<img src=외부>`·CDN·webfont URL **0건**(생성 후 grep 검증). 아이콘/그래픽은 인라인 SVG 또는 data:URI(percent-encode). grain/ambient gradient 는 텍스트 없는 cover/divider 에만 극절제(fit-scale 밖 고정 배경 1회 래스터). box-shadow elevation 당 ≤3겹.

### 5.1 deck.html — 구조 (하이브리드 골격)

자기완결 HTML/CSS(외부 의존 0, offline). `docs/presentation/index.html` 의 디자인 토큰(색·폰트·`--`변수)·slide 모델(`.slide`/`.is-active`)·목차(☰)·상단 진행바·키보드 네비(→/Space/←/Esc)·딥링크 해시·자동 축소(세로 스크롤 없음)·`word-break:keep-all`·`text-wrap:balance/pretty`(한국어 타이포)를 계승한다. 단 **보고 성격에 맞게 재구성**한다.

슬라이드 순서(키):

| # | 구간(키) | 담는 것 |
|---|---|---|
| 0 | **표지** `cover` | 제목("DBA AI Assistant 개발 진척 보고 — <범위>"), 부제, 기간, 버전, 작성일 |
| 1 | **핵심 요약** `summary` (BLUF) | 이번 기간 핵심 성과 3~5줄(업무 언어) + 한눈 지표 + "지난 기간 대비" 위치 1줄. 결론 먼저. |
| 2 | **개발 배경** `background` (SCQA) | 기존 상태(S) → 문제·요구(C) → 그래서 무엇을(Q) → 이번 기간 목표(A). 비전문가 문제 몰입. |
| 3 | **이번 기간 개요** `agenda` | 기능 목록(화면 흐름 순) + 각 한 줄 가치 + 상태 배지(신규/이어받음/완료). 목차와 1:1. |
| 4..N | **기능별 섹션** `feat-<slug>` | 고정 5블록(아래 5.2). 화면 흐름 순으로 N개. |
| N+1 | **기대 효과·성과 종합** `impact` | 기간 전체 정량·정성 효과. 확인 vs 확인필요 명확 구분(배지). |
| N+2 | **리스크·후속 과제** `risk` | 잔여 위험·미완·다음 기간 예정. 정직성(숨기지 않음). |
| N+3 | **마무리·다음 기간 예고** `outro` | 요약 + 다음 단계/도입·확장 제안. |
| (부록) | **근거 색인** `evidence`(발표자용, 선택) | 확인필요 항목 요약(상세는 EVIDENCE.md). 본문 노출 최소. |

### 5.2 기능 섹션 — 고정 5블록 (각 `feat-*` 슬라이드 그룹)

1. **배경·문제** — 누가 무엇을 겪던 문제인가, 어떤 요구가 제기됐나(사용자·운영 관점). 
2. **화면 흐름** — 사용자가 보고/쓰는 순서로. 한 화면 내 의미영역 분할. "show don't tell"(실제 라벨·동작 재현, '예시 화면' 표기).
3. **변경 전후** — 좌(전)/우(후) 병치. **자산 우선 + 폴백**:
   - 실측 화면 자료 있으면(스크린샷·현행 UI 캡처) 좌우 병치.
   - 없으면 폴백: **비교표 → 구조도 → 흐름도 → 처리순서(업무 프로세스)** 중 적합한 것으로 재구성 + "실측 화면 미확보(도식 재구성)" 배지.
   - **폴백은 텍스트 요약만으로 채우지 말 것 (필수)** — 반드시 **인라인 SVG 개념 도식**(전=중립 회색 계열 / 후=accent, 중앙 좌→우 화살표)으로 전/후 차이를 시각화하고 `role="img"`+aria-label 을 단다. 코드·기술 이미지가 아니라 **업무 관점의 변화**가 드러나게 한다(예: "인증서 경고→방패·2단계", "평면 목록→노드 그래프"). (검증: 초기 v1 이 텍스트 패널로만 채워 "시각 부실" 지적받음.)
   - 전후 자료 자체가 근거 미확보면 "전후 미확인"으로 표기(개선 단정 금지).
4. **선택 근거** — 왜 이 방향인가(일정/안정성/호환성/유지보수성/운영편의/사용자영향/대안대비 중 해당). 근거가 기록에 없으면 "추정 — 확인필요".
5. **기대 효과** — 무엇이 좋아지는가(사용자·운영·비용). 확인/확인필요 배지. 성능·안정화·최적화는 근거 없이 단정 금지.

각 블록에 **확인/확인필요 배지**를 단다(✓ 확인 근거有 / ⚠ 확인필요). 발표 본문은 배지+요지, 근거 상세는 EVIDENCE.md.

### 5.3 시각 컴포넌트(권장, self-contained)
- 전후 병치 카드(좌 회색톤/우 강조톤, 좌→우 화살표), 비교표, 순수 CSS/SVG 구조도·흐름도(외부 이미지·CDN 금지 — 없으면 data-URI 또는 인라인 SVG).
- 상태 배지(신규/이어받음/완료)·확인/확인필요 배지·**목차/개요(agenda) 등 리스트 배지까지** 모두 **색 + 라벨 + 형태(구분 SVG 아이콘)** 3중으로 표기한다(색+텍스트만 금지 — 색맹·저대비 대응).
- 진행바·목차·카운터. 창 높이에 맞춰 자동 축소.

### 5.4 SCRIPT.md — 발표 스크립트
`docs/presentation/SCENARIO.md` 형식 계승 + frontmatter 규약: `doc_type: PRESENTATION_SCRIPT`, `source_of_truth: false`, `companion: ./deck.html`, `range`/`version`. 본문: 발표 개요(대상 청중·소요·핵심 메시지) + 구간별 {화면 설명 / 발표 대사 / 전환}. **확인필요 항목**은 스크립트에서 정직하게 표현하는 문구를 함께 제공한다("이 수치는 아직 측정 전이라 목표치로 말씀드립니다" 류). 압축 발표(요약+본문 핵심+리스크)와 풀 발표 두 경로를 안내.

> **doc_type 정합(신규 타입 주의)**: 3종 산출물의 타입을 통일한다 — `SCRIPT.md`/`EVIDENCE.md` 는 YAML frontmatter `doc_type: PRESENTATION_SCRIPT`/`PRESENTATION_EVIDENCE`, `deck.html` 은 `<meta name="doc_type" content="PRESENTATION_DECK">` (기존 `PRESENTATION_SCENARIO`·`PRESENTATION_OBJECTION_HANDLING` 계열과 동형 네이밍). 신규 doc_type 이 doc-hygiene/wiki-lint/verify 게이트에서 unknown 으로 걸리지 않는지 Phase 6 에서 확인(걸리면 기존 `PRESENTATION_*` 재사용 또는 레지스트리 등록).

---

## Phase 6 — 자기검증 (게이트)

생성 후 아래를 스스로 점검하고, 실패 항목은 고친 뒤에야 완료로 본다.

- **Anti-pattern 스캔**(§아래 목록) — 하나라도 해당하면 재작성.
- **근거 정합**: 덱·스크립트의 모든 주장이 EVIDENCE.md 에 있고 상태(확인/확인필요)가 일치하는가. 특별 주의 항목(배포·테스트·수치·재발방지·전후·문서코드불일치)이 근거 없이 단정되지 않았는가.
- **민감정보 스캔**: 계정·비밀번호·토큰·접속좌표·개인정보·운영비밀이 본문/스크립트/원장에 없는가(grep: `password|secret|token|DSN|@.*:.*@|BEGIN .*PRIVATE`).
- **비전문가 가독성**: 내부 식별자·약어가 일반 용어로 풀렸는가.
- **HTML 자기완결·렌더**: 외부 리소스 참조 0(그 자체로 열림 — CDN·원격 폰트·원격 이미지·외부 JS 금지, 모든 CSS/JS 인라인·아이콘은 인라인 SVG/data-URI). 슬라이드 네비·목차·자동축소 동작. 필요 시 `/browse`(headless) 로 렌더 확인, 실제 화면 충실도가 중요하면 `bin/win-browser.py`+PB-0008(선택).
- **doc_type 게이트 정합**: 신규 doc_type(`PRESENTATION_DECK`·`PRESENTATION_SCRIPT`·`PRESENTATION_EVIDENCE`)이 프로젝트 doc-hygiene/wiki-lint/verify-completion 에서 unknown 으로 실패하지 않는지 확인.
- **디자인·접근성 게이트(§5.0)**: 디자인/시각효과가 3중 필터(봉투 정합·자기완결·절제 톤) 통과분만인가; 구조·서사 불변인가; 신규 텍스트/상태/focus 색 WCAG 대비 실측(≥4.5:1/≥3:1); 색+라벨+형태 3중 병기; `prefers-reduced-motion`·focus-visible 존재; `--diff-*` 를 before-after 에 오용하지 않음; `color-mix` 는 hex 폴백 동반; 외부 URL/`@import`/webfont 0건(grep).
- **정직성 경계 게이트 (필수)**: 청중 덱·스크립트에서 **미검증 항목이 "완료/검증/배포"로 단정되지 않았는가.** "완료"가 개발 기준으로 한정됐는가(리스크/후속 "현재 수준"에 미검증을 done 으로 쓰지 않음). 리스크는 "발전 과제" 프레이밍이되 미검증을 성과로 포장하지 않았는가.
- **청중 덱 식별자 스크럽 게이트 (필수)**: 청중 슬라이드에 내부 식별자(E-/U- 코드·`EVIDENCE.md`/`SCRIPT.md`·`feature-NNNN`·PR#·커밋해시·PB-0008) 노출 **0**(grep). 발표자 전용 색인 슬라이드가 청중 덱에 없는가(발표 슬라이드는 "마무리"로 종료).
- **전후 시각 게이트 (필수)**: 각 기능 전/후 블록이 **인라인 SVG 도식**을 포함(텍스트-only 아님)하고 `role=img`+aria-label 이 있는가. 도식이 업무 관점 변화를 전달하는가.
- **KPI 검증축 게이트**: "검증됨" 배지 수치는 검증 가능한가; 집계·파생 수치는 "개발 이력 집계"로 낮추고 EVIDENCE 산식이 있는가.
- **완전성**: 기능 단위가 화면 흐름 순인가, 이전 대비(신규/이어받음/완료)가 부여됐나, 리스크·후속이 정직하게 포함됐나.

---

## Phase 7 — 종료 (필수 autoland — 산출물이 worktree/로컬에 갇히지 않게)

- 산출물 3종 경로 + 슬라이드 수 + 기능 단위 수 + (확인 N건 / 확인필요 M건) + landing 결과(PR·병합 커밋)를 1줄 보고.
- **필수 landing (자동, confirm 없음)**: Phase 6 자기검증이 **전부 통과**하면 산출물을 반드시 원격 `main` 까지 landing 한다 — worktree 에 갇히거나 로컬에만 머무는 것을 **금지**한다(2026-07-08 하드닝). 순서:
  1. **commit** — worktree 에서 `git add docs/presentation/<slug>/<vN>/ && git commit`. 메시지 관례 `docs(presentation): <범위> 개발 진척 발표자료 <vN>` (+ 커밋 규약상 `Co-Authored-By` trailer). 정본(코드·정책)은 스테이징하지 않는다 — `docs/presentation/` 산출물만.
  2. **push** — `git push -u origin <report-deck 브랜치>`.
  3. **PR 생성** — `gh pr create`. title = 커밋 관례, body = 범위·슬라이드 수·기능 단위 수·(확인/확인필요 카운트)·자기검증 통과 요약. **PR body/브랜치명은 내부 관리용이라 근거코드·식별자 노출 허용**(청중 덱 식별자 스크럽 규율은 슬라이드 전용 — PR·EVIDENCE·SCRIPT 에는 적용 안 함).
  4. **PR 병합** — `gh pr merge`(프로젝트 관례 squash/merge, 브랜치 보호·CI 정책 준수, 필요 시 `--auto`). **병합까지 완수**한다.
  5. **동기화·정리** — 병합 후 `<policy_root>` 로컬 `main` 을 `origin/main` 에 동기화(fetch + ff), `git worktree remove <worktree>` + 병합 브랜치 삭제 + `git worktree prune`.
- **하드 전제(게이트) — 실패 시 push 금지**: 위 landing 은 Phase 6 게이트(anti-pattern·근거정합·**민감정보 스캔**·정직성 경계·청중 식별자 스크럽·전후 시각·doc_type·디자인/접근성)가 **전부 통과**해야만 진행한다. 하나라도 실패하면 **push/PR 를 중단**하고 로컬 커밋까지만 둔 뒤 실패 사유를 보고한다. 특히 **민감정보 스캔 실패 시 절대 push 하지 않는다**(발표자료는 origin 에 올라가면 회수·rotation 부담이 크다).
- **환경 폴백(loud, 조용한 skip 금지)**: git 저장소 아님 / `origin` 부재 / `gh` 미가용 / 브랜치 보호로 자동 병합 불가 → **가능한 단계까지 수행**(최소 로컬 커밋, 가능하면 push+PR 생성)하고 **못 한 단계를 명시 보고**. worktree-first 게이트·governance 로 BLOCKED 면 landing 보류하고 사유 보고(무한 재시도 금지).
- **여전히 안 하는 것(외부영향 confirm 유지)**: **배포(deploy)·외부 발송(메일·슬랙 등 알림)** 은 하지 않는다 — report_deck 산출물은 정적 doc 이라 배포 대상이 없고, push/PR 병합은 사내 저장소 내부 landing 이라 수행하지만 그 밖의 외부영향은 사용자 confirm 을 유지한다.
- **다음 단계 안내(자동 chain 금지)**: 확인필요 항목이 있으면 "발표 전 EVIDENCE.md §2 를 담당자와 확인 요망"을 안내. 발표자료 품질·시각 검증이 더 필요하면 `/browse` 또는 Windows-browser 검증 제안(자동 실행 안 함).

---

## Anti-pattern — 다음 결과물을 만들지 않는다 (금지)

- Git 커밋 메시지를 그대로 나열하는 보고 자료
- 변경 파일 목록만 정리한 보고 자료
- 개발 배경 없이 결과만 설명하는 보고 자료
- 변경 전후 비교 없이 "개선되었다"고만 표현하는 보고 자료
- 근거 없이 성능 개선·안정화·최적화를 단정하는 보고 자료
- 비전문가가 이해하기 어려운 코드 중심 보고 자료
- 확인되지 않은 내용을 사실처럼 작성한 보고 자료
- 화면 흐름·업무 흐름과 무관하게 기능을 산발적으로 나열한 보고 자료

---

## 종료 조건 (체크리스트)

- [ ] 범위·버전 확정, 산출물 dir = `docs/presentation/<범위>/<버전>/` (기존 버전 미덮어씀).
- [ ] Git 수집은 **main 반영분 기준**(`--all` 은 보조·미머지=확인필요). 5개 채널(git·문서·unit·개발 대화기록·이전 발표자료)에서 근거 수집(없는 채널은 "(신호 없음/접근불가)" 명시).
- [ ] 개발 대화기록은 **두 홈(`~/.claude`·`/home/claude-corp/.claude`) + 변형(-repo/--worktrees-*)** 을 하이픈-slug 로 스캔한 뒤 판정, 교차확인된 것만 사실로, 원문·민감정보 비인용, 제품 대화 DB 레이어와 구분.
- [ ] 기능 단위가 화면 흐름 순 + 고정 5블록 + 이전 대비 상태.
- [ ] 변경 전후 비교 존재(자산 우선/폴백), 선택 근거 존재.
- [ ] EVIDENCE.md 로 모든 주장 근거·상태 추적, 특별 주의 항목 단정 없음.
- [ ] deck.html 자기완결·렌더 OK(외부 URL/CDN/webfont 0), SCRIPT.md 동반.
- [ ] 디자인/시각효과는 §5.0 절차로 최신 트렌드를 3중 필터(봉투·offline·절제) 통과분만 반영, **구조·서사 불변**; 대비·색+라벨+형태·reduced-motion·focus-visible 게이트 통과.
- [ ] Anti-pattern 8종 스캔 통과, 민감정보 미포함.
- [ ] 코드·정책 정본 무수정. **자기검증 통과 시 산출물 필수 autoland** = commit → push → PR 병합 → 로컬 main 동기화 → worktree 정리(게이트 실패 시 push 금지; 환경 제약 시 가능 단계까지+미수행 명시 보고). **배포·외부 발송(메일·슬랙 등)은 안 함**(정적 doc — 배포 대상 없음).
