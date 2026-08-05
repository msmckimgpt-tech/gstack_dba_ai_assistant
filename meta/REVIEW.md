# META REVIEW

> META-layer 변경(`.claude/commands/`, `meta/`, `docs/improvements/` 등)의 검증 패널 기록. AGENTS.md §18.4 / §18.8 / §16.3 check #9.

## REV-20260702T110054-report-deck-hardening [SUBAGENT:report-deck-verification(codex + red team)] — report_deck 스킬 하드닝 (검증 라운드 6개 개선점 규율 승격)

- **cycle**: ai/claude/report-deck-2026-06-01_2026-07-02. 첫 실행(범위 2026-06-01~07-02 v1)을 사용자·`/codex`(독립 엔진)·red team(적대 감사)로 검증한 결과 반복 발생한 결함을 **스킬 규율로 승격**(1회성 패치가 아니라 다음 호출부터 자동 적용).
- **변경(META, pure-meta)**: `.claude/commands/_dqa/report_deck.md` — 불변제약 3 신규(성장톤↔정직성 경계 / 발표자·청중 분리+식별자 스크럽 / KPI 검증 축) + §5.2 전후 폴백 **인라인 SVG 도식 강제**(텍스트-only 금지) + §5.3 **배지 색+라벨+형태**(리스트 배지 포함) + Phase 4 EVIDENCE **측정조건·산식·배포근거·stale 엄밀성** + Phase 6 게이트 4 신규(정직성 경계 / 식별자 스크럽 / 전후 SVG / KPI 검증축) + 설계근거 하드닝 이력. `meta/REVIEW.md`(본 entry).
- **근거(검증 유래)**: codex [P1]×6(톤 과교정으로 미검증→"완료" 단정, KPI "완료" 모호, EVIDENCE 근거 압축) + [P2]×8(약어·코드중심 전후·배지 형태). red team [MAJOR](KPI "16" 도출 불투명·"검증됨" 오분류) + [MINOR](37% 산술오류·엔진 stale). 사용자 피드백(전후 시각 부실·발표자용 마지막 페이지·성장 지향 톤).
- **검증**: `bash -n` 불요(md). markdown 구조·앵커 정합. verify-completion META mode.
- **Human Approval Needed**: 아니오 — 소비자 스킬 규율 강화(비파괴 additive), 제품 런타임 동작 0. 전역 auto-sync 대상.

## REV-20260702T105343-report-deck-run-v1-review-fixes [SKIPPED:presentation-revision] — 외부 리뷰(codex + red team) 반영 (필수 3 + 후속 2)

- **cycle**: ai/claude/report-deck-2026-06-01_2026-07-02 (직전 revise 산출물의 외부 리뷰 반영).
- **외부 리뷰**: `/codex`(독립 엔진, [P1]×6 + [P2]×8) + red team 적대 감사(정량 주장 소스 1:1 교차확인, verdict SHIP-WITH-FIXES, BLOCKER 0). 두 리뷰 공통 지목 = 요약 KPI 취약 + 성장-톤 과교정으로 '확인필요→완료' 경계 침범.
- **반영(필수 3)**: (1) **KPI "16 묶음"** — 배지 '검증됨'→'개발 이력 집계 · 논리 작업 단위', "완료(개발 기준)" 한정, EVIDENCE E-001 에 **도출 산식 명시**(1,084+ 커밋 → 사용자 체감 논리 작업 단위 그룹핑; 9 feature + feature 미귀속 인프라 포함 → feature/커밋/TASK 수와 다른 축). (2) **톤 경계 재조정** — 리스크 표 "완료"→"완료 · 라이브 적용/검증 전", 마무리 "라이브 적용까지 검증"→핵심 인프라로 스코프 한정+나머지 순차 적용, SCRIPT agenda "완료·배포까지"→"개발 완료·핵심만 라이브 확인". (3) **EVIDENCE 정정** — E-012 "37%"→"약 35%(스냅샷)", U-003/E-010 WebGL·FPS→엔진 중립 + 그래프 렌더 엔진 교체(PR#528/ADR-004) 다음 기간 이월, E-009 배포 근거 basis 명시(운영 로그 원장 미인용).
- **반영(후속 2)**: 기술 약어 gloss(화이트리스트→허용 목록, 로드밸런서→분배기, 21개 모듈→21개 구성 단위), agenda 배지에 **형태 아이콘** 추가(색+라벨+형태 일관).
- **정직성 유지**: 성장 지향 톤은 유지하되, 미검증을 '완료/검증'으로 단정하던 표현만 정정 — 검증됨 ↔ 발전 과제 경계 재확립(정직성 아키텍처는 red team 이 '모범'으로 평가한 부분 보존).
- **재검증**: 14 슬라이드 · 외부참조 0 · 민감정보 0 · 과대주장 잔여 0 · agenda 배지 형태 아이콘 · HTML 균형 PASS. verify-completion META mode.
- **[SKIPPED] 사유**: 발표자료 콘텐츠 개정(정책·코드·정본 무변경). **Human Approval Needed**: 아니오 — main 랜딩은 사용자 판단.

## REV-20260702T101457-report-deck-run-v1-revise [SKIPPED:presentation-revision] — 사용자 리뷰 피드백 2건 반영 (전/후 시각 도식 강화 + 발표자 전용 내용 분리)

- **cycle**: ai/claude/report-deck-2026-06-01_2026-07-02 (직전 REV-20260702T025852 산출물의 리뷰 반영 개정).
- **피드백 반영**: (1) **전/후 비교 시각 부실** → 7개 기능 전부 **인라인 SVG 개념 도식**(전=회색 계열/후=accent, 좌→우 화살표)으로 교체 — 접속(경고→방패·2단계), 작업화면(텍스트→+/− 색 diff), 정확도(일회성→선순환 루프), 데이터소스(단일 DB→다중 DB＋게이트·상태점), 그룹(1:1→다인·@멘션), 지식그래프(평면 목록→노드 그래프·점선=추정/실선=신뢰), 무중단(단일 서버 중단→2대 롤링 중단0). 각 SVG `role=img`+aria-label. (2) **마지막 페이지 부적절**(발표자 전용 '확인 필요 색인' 슬라이드가 청중에 내부 코드·메모 노출) → **청중 덱에서 제거**(15→14 슬라이드, `마무리`가 마지막), 발표자 Q&A 대비는 `SCRIPT.md` [발표자 전용]+`EVIDENCE.md §2`로만. 아울러 청중 덱의 **내부 식별자 스크럽**(E-/U- 코드·EVIDENCE.md/SCRIPT.md·PB-0008·feature-000x·git 이력 제거, 배지는 평이어 "검증됨/확인 중/개발 완료").
- **변경(META, pure-meta, doc-only)**: `docs/presentation/2026-06-01_2026-07-02/v1/deck.html`(개정) · `SCRIPT.md`(발표자 전용 분리·딥링크 정정) · `meta/REVIEW.md`(본 entry). EVIDENCE.md 는 발표자·근거 문서라 U-/E- 코드 유지(의도).
- **재검증(Phase 6)**: 슬라이드 14 정합 · 부록/발표자용 슬라이드 0 · 내부 코드 노출 0 · 전후 도식 7 · 외부참조 0(자기완결) · 민감정보 0 · SVG role=img 14 · HTML 균형 · 구조·서사·디자인 언어(§5.0) 불변(디자인/시각효과만 강화). verify-completion META mode.
- **톤 패스(동 cycle 추가 반영)**: 사용자 피드백 "작업이 미흡하게 표현되기보다 발전 가능성으로" → 정직성(검증 vs 미검증 구분)은 유지하되 프레이밍을 **성장 지향**으로 전환. 배지 "확인 중"→"고도화 예정/수치 측정 예정", impact 우측 "단정하지 않는 것"→"앞으로 더 키울 발전 과제"(callout warn→일반), risk 슬라이드 "리스크·후속/남은 위험·할 일"→"개선 과제·발전 방향"(로드맵 프레이밍, "현재 수준→발전 방향"), 기능 effect·outro·SCRIPT 대사 동반. 과거 문제(배경 before) 서술의 "미흡/부족"은 개선 동기라 유지.
- **[SKIPPED] 사유**: 발표자료 콘텐츠 개정(정책·코드·정본 무변경). **Human Approval Needed**: 아니오 — 단 발표자료는 리뷰 콘텐츠, main 랜딩은 사용자 판단.

## REV-20260702T025852-report-deck-run-20260601-20260702 [SKIPPED:presentation-generation] — /_dqa:report_deck 검증 실행 산출물 (2026-06-01~07-02 개발 진척 발표자료 v1)

- **cycle**: ai/claude/report-deck-2026-06-01_2026-07-02 (base 2a4a8d3d). `/_dqa:report_deck "2026-06-01 ~ 2026-07-02"` 실행 — 스킬 end-to-end **검증 겸 실제 발표자료 생성**.
- **변경(META, pure-meta, doc-only)**: `docs/presentation/2026-06-01_2026-07-02/v1/{deck.html, SCRIPT.md, EVIDENCE.md}` 신규 + `meta/REVIEW.md`(본 entry). 코드·정본·정책 무변경(신규 버전 dir, 기존 자산 미덮어씀).
- **수집(5채널, 병렬 subagent)**: git main 반영분(16 논리 단위·1,084 커밋, baseline 44d42997@05-29) · 정책/릴리즈노트(배경·선택근거·운영영향·리스크) · unit feature 기록(feature-0003·0012·0014·0015·0016 등 배경/전후/시행착오/배포상태) · 개발 세션 transcript(보조·두 홈 하이픈-slug, 의사결정·시행착오) · 이전 발표자료(기간 스코프 report_deck 산출물 없음 — 제품 소개 index/practitioner 만 존재, 성격 상이).
- **정직성(확인 vs 확인필요)**: 확인 15건(무중단 zero-502 부하실증·그래프 서버조회 60x·DB재시작 오류0·백업복원 PASS·라우터 배포·다중DB/보안6대/협업/정확도수단 머지) / 확인필요 8건(정확도·FPS 수치 미측정·일부 라이브 배포·PB-0008 시각검증·자동롤백·transcript 단독 결정·문서 경미 불일치). **배포여부·테스트·성능수치·재발방지·전후자료·문서코드불일치 단정 금지** 준수 — 덱·스크립트가 EVIDENCE 원장과 1:1 정합.
- **자기검증(Phase 6)**: 외부 리소스 참조 0(자기완결 offline — CDN·원격폰트·원격이미지·외부JS 0) · 민감정보 0(계정·비번·토큰·접속좌표·개인정보) · focus-visible(신규)·prefers-reduced-motion·keep-all·색+라벨+형태 배지 28 · `--diff-*` before-after 오용 0 · backdrop-filter 미사용(주석만) · HTML 균형 · 슬라이드 15 정합. §5.0 디자인(봉투 토큰 상속+파생, 시스템폰트, 접근성-우선 clamp rem+문서스크롤 모드) 적용.
- **[SKIPPED] 사유**: 발표자료 **콘텐츠 생성**(정책 의미 변경 없음, 코드/정본 무변경) — 정책 코히런스 패널 불요(선례 REV-20260624T090355 presentation-title-rename 동일 계열). 콘텐츠 신뢰성은 `EVIDENCE.md` 원장 + Phase 6 자기검증으로 담보. 실 브라우저 시각검증(PB-0008)은 문서 exempt(check #13) + EVIDENCE U-002 로 확인필요 명시.
- **Human Approval Needed**: 아니오(additive doc-only, 제품 런타임 동작 0). 단 **발표자료는 리뷰 콘텐츠**이므로 main 랜딩 전 사용자 검토 권장(확인필요 8건 담당자 점검) — 본 실행은 스킬 검증 목적, 랜딩은 사용자 판단.

## REV-20260702T022910-report-deck-skill [SUBAGENT:report-deck-fit-review + design-trends-workflow] — `/_dqa:report_deck` 신설 (기간별 개발 진척 상부보고 발표자료 생성 persona)

- **cycle**: ai/claude/dqa-report-deck (base c5e259db). 사용자 요청(2026-07-02): 특정 개발 일정 범위("YYYY-MM-DD ~ YYYY-MM-DD")를 입력받아 그 기간 작업을 git·정책문서·unit 기록·개발 대화기록·릴리즈노트로 종합, **비전문가(기획·운영·관리) 포함 상부보고용 발표자료**(자기완결 HTML 덱 + 발표 스크립트 + 근거·확인필요 원장)를 `docs/presentation/<범위>/<버전>/` 에 생성하는 reporting persona 를 신설. 발표 형식은 세션 공동 설계(AskUserQuestion 4결정: 하이브리드 골격/고정 5블록/자산우선+폴백/3종 세트) + 상부보고·발표 웹 리서치(SCQA·피라미드·outcome-over-output·전후 병치)로 확정.
- **변경(META, pure-meta)**: `.claude/commands/_dqa/report_deck.md`(신규 — 불변제약 + 설계근거 + Phase 0~7 + EVIDENCE 스키마 + Phase 5 §5.0 디자인·시각효과 + Anti-pattern 8종 + 종료조건) · `.claude/commands/_dqa/README.md`(유지보수 persona 섹션을 doc_sync·conversation_audit·report_deck 3종으로 확장 + 산출물·규율 bullet + `.codex` 미러 없음 목록) · `CLAUDE.md`(`/_dqa` Skill routing 1줄 + 발표자료 산출물). 코드·정본(unit docs·docs/presentation 기존 자산) 무변경.
- **fit-review 패널 (SUBAGENT `improve-fit-reviewer` — 통과 아닌 결함 적발, SHIP-WITH-FIXES)**: BLOCKER 1 + MAJOR 2 + MINOR 2 전건 반영. **B-1(BLOCKER)** 개발 세션 transcript 경로가 밑줄(`mysql_ai_delegated_dev`) glob 이라 실제 하이픈 인코딩 log-dir(`-root-download-docker-mysql-ai-delegated-dev`)를 못 잡아 Channel 4 상시 빈손 → **cwd 의 `/`·`_`→`-` 치환 도출 규칙 + 두 홈(`~/.claude`·`/home/claude-corp/.claude`) + 변형(-repo/--worktrees-*) 스캔**으로 교정(실측: root 홈 156 jsonl·claude-corp 홈 99 jsonl 이 하이픈 dir 에 존재, 밑줄 dir 0). **M-1** `git log --all` 이 247 브랜치(미머지·폐기)를 끌어와 "확인 vs 확인필요" 오염 → **main 반영분 기준 + `--all` 은 누락탐지 보조·미머지=확인필요** 게이트. **M-2** 신규 `PRESENTATION_EVIDENCE` doc_type 정합 미검증 → SCRIPT.md frontmatter(`PRESENTATION_SCRIPT`)·deck.html `<meta doc_type>` 통일 + Phase 6 doc_type 게이트. **m-1** worktree 경로 `worktrees/`→`.worktrees/` §13.2.7 canonical. **m-2** 두 홈 스캔을 종료 체크리스트에 명문화. (거버넌스·요구사항·형식계승·계열관례 정합은 리뷰가 실측 확인 — 결함 아님.)
- **디자인 통합 (design-trends-workflow, 12 agents — 6차원 트렌드 리서치 + 프로젝트 봉투 실측 + 3렌즈 적대 검증 → grounded 스펙)**: 사용자 추가 요구("구조·맥락 유지, 디자인/시각효과는 프로젝트 작업과 정합하는 최신 웹 트렌드 적극 반영")를 Phase 5 §5.0 으로 인코딩. **구조·서사 불변 + 디자인만 현대화** 원칙 + (a) 매 호출 3중 필터 리서치 절차 (b) 정합성 봉투(실측: `--bg #f7f7f4`·단일 파랑 accent #2563eb·2겹 soft-shadow·Geist/D2Coding) (c) 채택/(d) 회피/(e) 모션·접근성·성능 지침. 적대 검증이 실측 교정: `--text-muted #807d72`=3.8:1 4.5:1 미달(장식 한정), `--diff-add/del` before-after 재사용 금지(다크 전용 흰 위 위반), color-mix 는 사용처 hex 폴백 2회 선언(미지원 시 무색 방지), IntersectionObserver→슬라이드 활성화 콜백(비활성 display:none), fit-scale=프로젝터 한정+저시력 clamp rem 폴백 병행(WCAG 1.4.4/1.4.10), focus-visible 신규 구축(덱 focus 규칙 0 = WCAG 2.2 위반 현존), backdrop-filter 신규 금지, 다운로드 웹폰트 base64 금지.
- **doc-only / 산출물 위치**: 본 skill 은 `docs/presentation/<범위>/<버전>/` 에만 생성(코드·정본 무수정, 기존 버전 미덮어씀). 커밋/파일 나열 금지 → 배경·전후·근거·기대효과·리스크 재구성, 확인 vs 확인필요 구분(EVIDENCE.md 원장), 민감정보(계정·비밀번호·토큰·접속좌표·개인정보) 미포함, PR·배포·외부발송 안 함.
- **검증**: markdown 구조 sanity(329줄·Phase 0~7·§5.0~5.4 헤더 정합) · 요구사항 커버리지 grep(배경·전후·선택근거·기대효과·리스크·확인필요·이전기간비교·화면흐름·8 anti-pattern·민감정보·자기완결·SCQA·폴백 전건 OK) · transcript 경로 실측 교정 확인 · 디자인 축(매 호출·봉투·3중 필터·color-mix·reduced-motion·focus-visible·IntersectionObserver·구조 불변) 존재 확인. verify-completion META mode.
- **Human Approval Needed**: 아니오 — additive reporting persona 신설(신규 파일 1 + 인덱스 2), 산출물은 `docs/presentation/` doc-only, 제품 런타임 동작 0, blast radius 낮음(코드·프롬프트·가드·RBAC·PII 무관). 사용자가 요청·공동 설계(AskUserQuestion)한 작업. 전역 auto-sync(commit/push/main 병합) 대상, PR·배포·외부발송은 미수행(외부영향 경계 유지).

## REV-20260701T230501-META-0018-doc-sync-0701 [SUBAGENT:doc-sync-adversarial-groundtruth] — 07-01 머지분 인덱스/미러/사용자향 표면 정합 (그래프 뷰 진화·라우터 모듈화 완료·권한 세분화, ULTRACODE)

- **cycle**: ai/claude/doc-sync-20260701-230501 — `/_dqa:doc_sync ultracode`(스케줄 무인, 전 타깃). 직전 sync(doc-sync-2305 @ 06-30 23:51, 43023fc/fc35932f) 이후 main 병합된 07-01 작업(feature-0016 그래프 뷰 진화·feature-0012 P5b 전체추출 완료·feature-0003 convswitch/graph-panel-perms)을 색인/미러/사용자향 표면에 정합. cron wrapper 가 push/merge/deploy 소관 — 본 run 은 로컬 commit 까지.
- **변경(META, pure-meta)**: `docs/STATUS.md`(§1 feature-0003/0012/0016-metadata-graph 행 07-01 갱신·date bump — 인덱스 모델, §5 카운트 무변경) · `docs/ARCHITECTURE.md`(§4 기능맵 0012 전체추출·0016 07-01 진화 clause / §6 의존맵 0012) · `docs/SECURITY.md`(§19 그래프 RBAC `kb.ingest.manual`→`metadata.graph.read` 정정 + 메타데이터 권한 5분할 색인·비파괴 함의·인가 PASS) · `docs/RELEASE_NOTES.md`(07-01 운영자 블록 2건 — 0016 그래프 진화·0012 추출완료, append-only) · `wiki/Features/feature-0016-metadata-graph.md`·`feature-0012-web-router-modularization.md`(카드 07-01 정합) · `wiki/Features/_Index`(수 13→17 stale 정정·0012/0016 행)·`Index`(13-feature→17-feature stale 정정)·`overview`(㉔~㉗ 07-01 서사)·`Architecture/Overview`(표·의존맵·07-01 서사) · `wiki/Log.md`(ledger)·`wiki/hot.md`(07-01 KRF/Recent Changes/Active Threads 보존) · `meta/REVIEW.md`(본 entry). 정본(unit docs·DECISIONS) 무변경.
- **SSOT 계약 준수(ADR-0031)**: STATUS 인덱스 모델 — rollup blockquote 0(기존 행에 07-01 clause append·feature-0012 는 stale '토대' 요지 교체, 신규 행 0). mirror(wiki) 정본 재서술 없이 요지·링크. `bin/ssot-lint.sh` 4 WARN(기존 tracked `.env*.bak*` — STATUS §3 블로킹·rotation 선행, 본 변경 무관·미stage) 불변, archived/wiki-sot 0. feature 카운트 ground-truth(디렉토리 18 / distinct 17) 전 narrative 정합 — 잔존 stale '13' 2건(`_Index` 수·`Index` compose blurb)도 정정.
- **타깃별 실질 검증**: feature 수 ground-truth(`ls -d unit/feature-*`=18 dir / distinct 17) ↔ narrative 정합·잔존 '13' 스윕(`_Index`/`Index` 정정). 신규 wikilink 대상(기존 카드) 존재. STATUS·ARCHITECTURE 표 행 컬럼수 정합. §19 SECURITY 갱신 anchor(REV-20260702T120000-graph-panel-perms) 실재. 릴리즈노트(operational) `node --check` PASS + vm 로드 generated=2026-07-01·7항목. (verify-completion META mode 는 check #1/#5 deferred → 위 직접 검증 + 아래 적대 패널로 보강.)
- **panel (SUBAGENT, ULTRACODE — ground-truth 3-agent 적대 추출 + 정본 재독 검증)**: (1) feature-0016 정본(REPORT/DECISIONS/TEST) 재독 — 07-01 델타 14항목 분류, user-facing vs internal(perf 6·camera-anim = internal-only, 릴리즈노트 제외), 암묵 관계 정직 프레이밍 확정(점선=추정/실선=신뢰/숨김=파단, 과대표현 회피), SECURITY 권한 5분할 needs-note(line 602 stale 확인). (2) feature-0012+0003 정본 재독 — 0012 100% behavior-neutral(byte-동치·프로덕션 응답 verbatim) 확인 → user-facing 릴리즈노트 제외 강제, ARCHITECTURE §4:56/§6:88 stale 확인, 0003 convswitch/graph 프론트 user-facing 분류 + 07-01 PB-0008 provenance. (3) cross-cut audit — 카운트 18/17 불변·§5 tally(review 5/in-progress 13) 재도출 정합·ADR-002/003 feature-local(repo DECISIONS 색인 대상 아님)·feature-0002 독립 07-01 작업 0·ssot-lint 4 WARN baseline.
- **ADR 색인 — no-op(정직 보고)**: feature-0016 unit DECISIONS 에 ADR-002(암묵 관계)·ADR-003(능동 분석 앵커 게이팅) 07-01 결정(Accepted) 존재하나 **feature-local ADR**(그 feature DECISIONS 가 정본, `source_of_truth: true`) — repo `docs/DECISIONS.md` 는 repo-wide 결정만 색인하는 관례라 대상 아님(grep 0). 불변제약 '신규 ADR 본문 미작성' 준수.
- **잔여 drift (정직 고지)**: ① feature-0016 번호 충돌(metadata-graph + zd-pg-pause-caddy 2 슬라이스) 미해소 — 사람 결정 보류(전 문서 명시 유지). ② `wiki/Decisions/_Index`·`wiki/Index` §2.4 가 ADR-0031·timestamp ADR·feature-local ADR-002/003 미반영(systematic mirror stale) — 본 07-01 delta 밖, 후속 mirror 백필 권고. ③ feature-0012 batch4(잔여 16 route) 프로덕션 재배포 검증 미완 — feature cycle 소관(RELEASE_NOTES 에 정직 명시).
- **검증 한계**: verify-completion STATUS check(#5)·#1 deferred → 위 타깃별 검증 + 3-agent 적대 ground-truth 로 직접 확인. landing(push/PR/merge)·deploy(서빙 static=릴리즈노트 재배포)는 cron wrapper 소관(본 run 로컬 commit 까지). 동반 operational(릴리즈노트+cache-buster)은 feature-0003 별도 operational-gate commit(check #13 PB-0008 = 콘텐츠 doc-only·무인 브리지 미가동 사유 TEST.md 기록).
- **Human Approval Needed**: 아니오 (additive doc-sync index/mirror 정합 + 사용자향 표면 갱신, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책). feature-0016 번호 충돌·wiki Decisions mirror 백필은 사람/후속 권고(보류 등재).

## REV-20260701T014032-visual-verification-gate [SUBAGENT:check13-adversarial-6hyp] — 웹/UI 변경 PB-0008 시각검증을 완료 hard gate 로 강제 (check #13 신규 + visual_verification_scope + §15.4.1 격상)

- **cycle**: ai/claude/visual-verification-gate (base 24dd588). 사용자 지시(2026-07-01) "시각검증은 항상 진행되어야 합니다. 스킬 및 기억에 구성해주세요." — 웹/UI 변경의 PB-0008 실 Windows 브라우저 시각검증을 선택이 아닌 **필수 완료 게이트**로 인코딩. 배경: AGENTS.md §15.4.1/§16.2 는 이미 "필수" 로 선언했으나 `verify-completion.sh` 에 강제 check 부재(선언적·WARN-only 의도)로 스킵이 통과되던 마찰. PB-0008 시각검증 자체는 본 지시 앞 turn 에서 metadata-bs-prefill 대상 PASS(실 브라우저 123테이블 중 120 prefill·Achievement DB값 일치·0 pending) 확인 완료.
- **변경(META, pure-meta)**:
  - `bin/verify-completion.sh`: **check #13 신규 구현** — 웹/UI 자산(`**/src/static/**`·`**/static/**` + 렌더트리 UI 확장자, `docs/`·`wiki/`·`.claude/` 제외) 변경 cycle 에서, 해당 자산이 속한 feature `docs/TEST.md` 의 **이번 staged diff** 에 `Windows-browser` Run(또는 미수행 사유) 추가 라인이 없으면 판정. 강제 수준은 wrapper `FIRST_REQUEST.md` `visual_verification_scope`(정규화: 주석/따옴표/대소문자) — `always`→FAIL(hard), 미선언→WARN(backward-compat). check #10/#11 처럼 **META short-circuit 앞에서 무조건 실행**. escape: `GSTACK_SKIP_VISUAL_VERIFICATION=1`. helper `is_web_asset`·`read_first_request_scope` 동반.
  - `AGENTS.md §15.4.1`: enforcement 문단을 "v1 WARN-only 예정"→"구현·격상(visual_verification_scope 기반 hard/WARN)" 으로 갱신 + 본 저장소 always 명시.
  - `FIRST_REQUEST.md`(wrapper, non-git): `visual_verification_scope: always` 선언(deploy_scope 패턴) — repo commit 밖 로컬 config.
  - `meta/REVIEW.md`: 본 entry.
  - 병행(별도, 이 commit 밖): 세션 memory `feedback_always_visual_verification.md`(기억 구성분).
- **적대 패널 (SUBAGENT, 6-가설 — 통과 아닌 결함 적발)**: VERDICT 1차 **FIX-THEN-SHIP** (BLOCKER 0 · MAJOR 4 · MINOR 2). 전부 수정 후 재검:
  - **M1(미탐, MAJOR) 수정**: whole-file substring(`grep -qiE`)이 주석·URL·이전 cycle stale 라인으로 통과 → **staged diff 의 추가 라인(`git diff --cached | grep '^\+' | grep -i windows-browser`)만 인정**. (격리 테스트 T4: 파일엔 있으나 diff 추가 없음 → FAIL 확인.)
  - **M2(오/미탐, MAJOR) 수정**: placement-only 분류 → `docs/**`·`wiki/**`·`.claude/**` 제외(프레젠테이션 `.html` 오탐 차단) + static 밖 UI 확장자(`styles.css`·`.jsx` 등) 포착(미탐 차단).
  - **M3(우회, MAJOR) 수정**: META/shared short-circuit 이 웹 자산을 건너뜀 → check #13 을 short-circuit **앞**에서 무조건 실행 + shared 분기 반영.
  - **M4(silent 격하, MAJOR) 수정**: `always # 주석`·`Always`·`"always"` 가 hard→WARN 로 조용히 격하 → 값 정규화(주석/따옴표 strip·소문자)로 해소. (검증: 6 변형 전부 MATCH-always.)
  - **m1(교차-feature vouch, MINOR) 수정**: CLI fdir 고정 → **웹 자산 경로에서 feature 도출**해 그 feature TEST.md 로 귀속.
  - **m2(WARN 문구, MINOR)**: M4 수정으로 자연 해소.
  - **견고 확인(반증 실패)**: set -e 하 크래시(check_13 이 `||` 좌변이라 억제 + `read_first_request_scope` pipefail-safe 하드닝), failed 카운터 정합, post-commit 조기 return.
- **검증**: `bash -n` PASS · check_13 격리 테스트(M1 diff/M2 분류/M4 정규화/scope별 FAIL·WARN/escape/no-web/docs-exempt) 전부 기대대로 · 본 cycle 자체는 웹 자산 미포함 → check #13 PASS(no web). verify-completion META mode(check #9/#10/#11/#13).
- **Human Approval Needed**: 아니오 — 사용자 명시 지시로 구성, 게이트 강화는 비파괴(기존 소비자는 미선언→WARN 유지, 본 저장소만 always), 신규 production 런타임 동작 0(개발-시점 검증 스크립트). deploy 무관(verify-completion.sh 는 컨테이너 미배포).
## REV-20260630T230501-META-0016-doc-sync-2305 [SUBAGENT:doc-sync-adversarial-5stream] — feature-0016-metadata-graph 전 문서 누락분 신설 + 무중단군 0014~0017 정합 + 06-30 머지 backfill (ULTRACODE)

- **cycle**: ai/claude/doc-sync-20260630-230501 — `/_dqa:doc_sync ultracode`(스케줄 무인, 전 타깃). 직전 sync(doc-sync-0630 @ 06-30 10:31, PR#471) 이후 main 병합된 feature-0014/0015/0016(metadata-graph+zd-pg-pause-caddy)/0017 신규 + feature-0002/0003 06-30 작업을 색인/미러/사용자향 표면에 정합. cron wrapper 가 push/merge/deploy 소관 — 본 run 은 로컬 commit 까지.
- **변경(META, pure-meta)**: `docs/STATUS.md`(frontmatter sources 0014-0017 + §1 feature-0016-metadata-graph 행 신설·feature-0002/0003 06-30 행·0015/0016-zd 라이브 실증·§5 카운트 13→17/review 5/in-progress 13) · `docs/ARCHITECTURE.md`(§4 metadata-graph 행 + §6 의존맵 0014-0017+metadata-graph 5행) · `docs/SECURITY.md`(§19 AGE/Cypher 질의면 boundary 색인) · `docs/RELEASE_NOTES.md`(운영자 블록 0015/0016-metadata-graph/0016-zd/0017) · `wiki/Features/feature-0016-metadata-graph.md`(카드 신설) · `wiki/Features/_Index`·`Index`·`overview`·`Architecture/Overview`(feature 카운트 13→17·디렉토리 18, 표/의존맵/06-30 서사) · `wiki/Log.md`(ledger) · `wiki/hot.md`(06-30 PM, Active Threads 보존) · `meta/REVIEW.md`(본 entry). 정본(unit docs·DECISIONS) 무변경.
- **SSOT 계약 준수(ADR-0031)**: STATUS 인덱스 모델 — rollup blockquote 0(기존 행에 06-30 절만 append, 신규 metadata-graph 행은 1줄 요지+정본 링크). mirror(wiki) 정본 재서술 없이 요지·링크. `bin/ssot-lint.sh` PASS(기존 tracked `.env*.bak*` 4건 WARN-only — STATUS §3 블로킹·rotation 선행, 본 변경 무관·미stage). feature 카운트 ground-truth(디렉토리 18 / distinct 번호 17) 전 narrative 정합.
- **타깃별 실질 검증**: feature 수 ground-truth(`ls -d unit/feature-*`=18 dir / distinct 17) ↔ 5 narrative 정합·잔존 '13' 스윕. 신규 wikilink 대상(feature-0016-metadata-graph 카드) 존재. STATUS·ARCHITECTURE·overview 표 행 컬럼수 정합. §19 SECURITY anchor=REVIEW REV-20260630-0001 실재. (verify-completion META mode 는 check #1/#5 deferred → 위 직접 검증 + 아래 적대 패널로 보강.)
- **panel (SUBAGENT, ULTRACODE 5-stream 적대 워크플로 wf_86043cdc — 정본 재독 적대 검증, 통과 아닌 결함 적발)**: (1) metadata-graph — needs_fix, **MAJOR 흡수**: 릴리즈노트 item1 이 엣지=0(게임 DB FK 미선언)인데 '테이블 연결 따라가기' 과대 → 가시 사실(스키마/DB 그룹핑·검색·노드 설명·컬럼)로 완화·관계는 '정의된 관계 있으면 표시' forward-looking 화. (2) zerodowntime — minor 흡수: 무중단 '주요 기능 멈추지 않음'이 스트리밍 예외(admin SSE/CSV) 초과 → '채팅 등 주요 작업 이어짐 + 일부 진행 중 작업 드물게 재시도' 완화; STATUS 0016-zd 라이브 메트릭(OK=134/ERR=0) 인덱스 altitude 로 정성화. (3) feature0003 — minor 흡수: overview 번호 ⓪→⑳ 정정. (4) feature0002 — clean: 릴리즈노트 신규 06-30 블록 배치(06-29 append 금지). (5) count-adr-audit — needs_fix, **MAJOR×2 흡수**: SECURITY 색인 §18(기존 그룹대화 점유)→§19 정정; citation anchor FUNCTION §4.3(투영-only)→REPORT/REVIEW(RBAC·화이트리스트) 정정.
- **ADR 색인 — no-op(정직 보고)**: 신규 feature 5개 unit DECISIONS.md 전부 빈 템플릿 스텁(feature_id: feature-xxxx-template, ADR-001 공란), docs/DECISIONS.md 에 0건 → 색인할 기존 ADR 없음(adrs_to_index=[]). 불변제약 '신규 ADR 본문 미작성' 준수 — 향후 feature 담당이 unit DECISIONS 채우면 그때 색인.
- **잔여 drift (정직 고지)**: ① **feature-0016 번호 충돌**(metadata-graph + zd-pg-pause-caddy 2 슬라이스가 0016 공유) — 비가역(브랜치/PR/문서 다수)이라 doc_sync 자율 재부여 금지, 전 문서에 '2 슬라이스' 명시 + 사람 결정 보류 등재. ② `wiki/Index.md:70`·`wiki/Decisions/_Index.md`(ADR-0001~0030/'31 entries')가 timestamp ADR 2건(06-29) 미반영 stale — 06-30 머지 delta 밖이라 본 run scope 제외, 후속 권고. ③ feature-0015/0016-zd REPORT.md Summary('배포 대기')가 TEST.md(라이브 PASS)와 내부 드리프트 — feature cycle 정본 소관(doc_sync 정본 미작성), STATUS 인덱스는 TEST(reality) 기준 정정.
- **검증 한계**: verify-completion STATUS check(#5)·#1 deferred → 위 타깃별 검증 + 5-stream 적대 패널 직접 확인. landing(push/PR/merge)·deploy(서빙 static=릴리즈노트 재배포)는 cron wrapper 소관(본 run 로컬 commit 까지). 동반 operational(릴리즈노트+cache-buster)은 feature-0003 별도 operational-gate commit.
- **Human Approval Needed**: 아니오 (additive doc-sync index/mirror 정합 + 신규 feature 카드 backfill, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책). feature-0016 번호 충돌 정리는 사람 거버넌스 결정 권고(보류 등재).

## REV-20260630T100000-META-0015-doc-sync-0630 [SKIPPED:doc-sync-index-mirror-alignment] — feature-0013 신규 + 06-29 저녁 머지 backfill 인덱스/미러 정합 + nl2sql concept stale 해소

- **cycle**: ai/claude/doc-sync-0630 — doc_sync(전 타깃, 직전 sync a644fcb/72c970f @ 2026-06-29 13:35 이후). feature-0013 관계 다이어그램 머지(PR#462/#469) + 06-29 저녁 user-facing(metadata-bs-*/share-*/glossary-role-*/new-conv-dedup/diff-lineno-leak)을 색인/미러/사용자향 표면에 반영.
- **변경(META, pure-meta)**: docs/STATUS.md(§5 등록 기능 12→13·in-progress 11→12 + frontmatter sources feature-0013 + feature-0013 행 라이브 PASS + feature-0003 행 paging/dedup/lineno 1줄) · docs/ARCHITECTURE.md(기능맵 §4 + 의존맵 §6 feature-0013 행) · wiki/Index·Features/_Index·overview·Architecture/Overview(feature 카운트 12→13 + feature-0013 행/서사) · wiki/Features/feature-0013 카드(머지 reality — status stub→active·maturity stub→minimal·§2 PB-0008 라이브 PASS·rd-h2/h3/h6) · wiki/concepts/nl2sql-flywheel.md(§2 ITEM-08/11 출시 반영 — hot.md flag 한 stale 해소) · wiki/hot.md(06-30 갱신, Active Threads 보존·nl2sql thread 해소) · wiki/Log.md(rollup append-only). 정본(unit docs·DECISIONS) 무변경.
- **검증**: ADR-0031 인덱스 모델 준수(정본 재서술 0·STATUS 셀 rollup blockquote 누적 0) · feature 카운트 ground-truth(`ls -d unit/feature-*`=13) 전 narrative 파일 정합·잔존 stale '12' 스윕 0 · `bin/ssot-lint.sh` PASS · 신규 wikilink 대상(feature-0013 카드) 존재. DECISIONS/SECURITY/PROJECT noChange(무변경 정직 보고). [SKIPPED] 사유: 순수 색인/미러/concept-stale 정합(정책 의미 변경 없음) — codex 패널 불요(선례 REV-20260629T043125-META-0014-doc-sync-0629 동일). 동반 operational(릴리즈노트)은 feature-0003 별도 commit(REV-20260630T100000-doc-sync-rn-0630).

## REV-20260629T043125-META-0014-doc-sync-0629 [SKIPPED:doc-sync-index-mirror-alignment] — STATUS·ARCHITECTURE·wiki 06-29 머지 backfill 인덱스/미러 정합

- **cycle**: ai/claude/doc-sync-20260629-130501 — doc_sync(06-29 머지 backfill, 직전 sync 6dee739/63874f2 @ 08:34 이후). feature-0012-web-router-modularization 머지(PR#456) + 답변 피드백 답변당 고유화(👍/👎) + 용어사전 대화 자율등록 + 용어 검토 큐 IA 중첩 + 첨부 wrong-bubble id-space 하드닝을 색인/미러/사용자향 표면에 반영.
- **변경(META, pure-meta)**: docs/STATUS.md(feature-0012 행 + 등록 기능 11→12 + 0002/0003 행 피드백·첨부 정합) · docs/ARCHITECTURE.md(기능맵 §4 + 의존맵 §6 feature-0012 행) · wiki/Index·Features/_Index·overview·Architecture/Overview(feature 카운트 11→12 + feature-0012 행) · wiki/Features/feature-0012 카드(머지 reality 정합 — status stub→active·maturity stub→minimal·갱신 06-25→06-29) · wiki/hot.md(06-29 갱신, Active Threads 보존) · wiki/Log.md(rollup append-only). 정본(unit docs·DECISIONS) 무변경.
- **검증**: ADR-0031 인덱스 모델 준수(정본 재서술 0·STATUS 셀 rollup 누적 0) · feature 카운트 ground-truth(`ls -d unit/feature-*`=12) 전 파일 정합 · 잔존 stale '11' 스윕 0 · 병렬 draft + 1차 적대 검증(wiki 누락 2건 적발→보정) + 보정분 7축 재검증 PASS. DECISIONS/SECURITY/PROJECT noChange(무변경 정직 보고). [SKIPPED] 사유: 순수 색인/미러 정합(정책 의미 변경 없음) — codex 패널 불요(선례 REV-20260625T013000-META-0010-doc-sync-0625 동일). 동반 operational(릴리즈노트)은 feature-0003 별도 commit(REV-20260629T041724-doc-sync-rn-0629).

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

## REV-20260629T121052-conversation-audit-skill [SUBAGENT:conversation-audit-skill]

- **cycle**: ai/claude/dqa-conversation-audit-skill — `/_dqa:conversation_audit` 신설(라이브 대화 마찰 진단·수정·출하 maintenance persona). doc_sync 와 동급의 standalone explicit-call·schedulable persona(research→listup→cycle 파이프라인 단계 아님). 원 요청: 서비스 대화를 직접 탐색해 명시 마찰의 근본원인 + 사용자 불만으로 끊긴 대화의 암묵 이탈(뉘앙스)을 구조적·추상적 프레임으로 진단·개선.
- **changeset (pure-meta, 전 파일 META path → verify-completion META mode check #9 게이트)**: `.claude/commands/_dqa/conversation_audit.md`(신규 — 불변제약 + 공유사전 C1~C5 + Phase 0~14 + 종료조건) · `.claude/commands/_dqa/README.md`(부가 유지보수 persona 섹션을 doc_sync·conversation_audit 2종으로 확장 + 외부영향 override 비승계 bullet) · `CLAUDE.md`(`/_dqa` 라우팅 1줄 + FRICTION_LEDGER 산출물) · `meta/REVIEW.md`(본 entry).
- **설계 요지**: ① 증상→레이어(L1~L8)→정본 역추적 + 5-whys 증거사다리 + 코드·DB라이브·전사 삼각측량으로 표층 row 패치 차단(재발경로 봉인). ② 3-입도 ID 사슬(signal_id→RC-id→friction-id; friction-id 는 근본 위치 파생 → 빈번 호출 중복회피 축). ③ 명시(E-\*) + 암묵(I-\*) 2층 신호, 양가토큰 disambiguation·궤적 우선·한국어 채팅체 정규화. ④ FRICTION_LEDGER 단일 정본 + 회귀 측정 폐루프(fixed 재corroboration → verified/regressed). ⑤ 위험등급 게이트(프롬프트/맥락/가드=Major, 보안경계/PII=Critical, unattended=Minor만 자율) — doc_sync override 비승계.
- **panel (SUBAGENT, 3인 적대 워크플로 — 통과 아닌 결함 적발)**: (A) improve-fit-reviewer(governance 인용·묶음 컨벤션·불변제약 건전성·위험게이트·내부모순 — VERDICT ISSUES BLOCKER0/MAJOR2/MINOR1/NIT2) · (B) general-purpose factual 디스크 정본 검증(backend discovery·정본 테이블·bin 스크립트 계약·deploy/healthz·corroboration 쿼리 실측 — VERDICT PASS-WITH-NITS, 존재하지 않는 메커니즘 전제·틀린 illustration 0, AGENT_RUNTIME_READ_BACKEND·core_messages·ask-worker·make up 서비스 누락·RO 유저 전부 디스크 정합 확인) · (C) general-purpose 완결성·뉘앙스 검증(원 요청 4요구 + 내부 일관성 — VERDICT CHANGES REQUESTED, BLOCKER-C1 + MAJOR-C2).
- **흡수한 BLOCKING/MAJOR (전건 반영)**: **BLOCKER-C1**(조용히 떠난 저흔적 침묵 이탈이 corroboration 게이트·Phase2 랭킹 양쪽에서 걸러져 영구 report-only — 사용자 1순위 요구 미충족) → Phase 7.4 "저흔적 이탈 예외" 분기 추가(빈도 아닌 rootcause_confidence high + 재발경로 data/config·ux + Minor → 국소-우선 fix-now, "명백한 구조결함" 정의 명문화, 과적합 가드 유지) · **MAJOR-C2**(Phase2 가 만족종료 vs 실패후침묵 구분 못 해 침묵이탈 미진입) → "실패 직후 침묵" cheap 프록시 신호 추가 · **MAJOR G1**(§10.3(secret) 오인용 — §10.3 은 read-scope) → `docs/SECURITY.md §1·§2` 로 교체 · **MAJOR G2**(신규 persona README/CLAUDE 미등록) → 묶음 인벤토리 등록 companion change.
- **흡수한 MINOR/NIT**: ledger status enum 에 `blocked:<reason>`·`awaiting-merge:PR#<n>` 추가(C5 단일정본 드리프트 해소) · Phase12 L6(모델·디코딩) 패널 렌즈 매핑 명시 · Phase2 account/product 한정 필터 명문화 · Phase14 종료보고에 doc_sync 권유 1줄.
- **수용(미수정) 기록**: (S1) Phase 헤더 레벨 `#` vs doc_sync `##` — 미관 차이, 기능 영향 0, 50줄 churn 회피 위해 수용 · (H1) Phase1 D0.4 예시 테이블명 `core_messages`/`core_conversations` — 리뷰어 B 가 "예: 로 framing·discovery-driven 로직·실제 정확한 illustration, 하드코딩 위반 아님" 으로 확인 → 수용.
- **검증 한계**: 본 스킬은 `.claude/commands/*`(서빙 산출물 아님) → 배포 no-op(silent skip 아님 — META path 명시). 런타임 코드 무변경이라 verify-completion META mode(check #9/#10/#11)만 — 스킬 self-coherence·governance 인용 정확성은 위 3인 적대 패널로 직접 확인(디스크 정본 대조).
- **Human Approval Needed**: 아니오 (additive META-tooling docs, 비파괴, 신규 production 동작 0, `.claude/commands/*` pure-meta. resume persona 가 기존 의도 완수 — Resume≠Re-scope, BLOCKER-C1 fix 도 스킬 자신의 명시 목적(암묵 이탈 포착) 충족이지 새 scope 아님).

## REV-20260629T123949-conv-audit-dogfood [SKIPPED:additive-meta-doc-clarification+ledger]

- **cycle**: ai/claude/META-0013-conv-audit-dogfood — `/_dqa:conversation_audit` dogfood 검증 run 에서 surface 된 스킬 마찰 4건 보강 + 첫 FRICTION_LEDGER entry. 실행: `account=mckim conversation="게임 스테이지 성공률 통계"` 대화 1건을 Phase 0~7 전구간 실행해 스킬 end-to-end 동작 확인.
- **changeset (pure-meta, META path)**: `.claude/commands/_dqa/conversation_audit.md`(Phase 1 D0.3 quoting·RO-replica / Phase 2 account 이름→FK 해소 / Phase 7.2 침묵이탈 corroboration 레퍼런스 SQL) · `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(신규 — report-only 2건) · `meta/REVIEW.md`(본 entry).
- **검증 run 결과(스킬이 정상 작동)**: discovery 가 라이브 backend(postgres, `AGENT_RUNTIME_READ_BACKEND=postgres`)·정본 테이블(`agent_runtime.core_messages`)·대상 대화를 실측 확정. 진단: turn1 스키마 추측 실패(`1049 Unknown database`)로 assistant give-up(E-AST) + turn2 표/서술 행수 불일치(I-FALSE) + 침묵 이탈(I-SIL). corroboration: idiosyncratic(distinct_conv=1). disposition: **report-only**(단일대화·Major·idiosyncratic → 과적합 가드 의도대로 자동수정 보류).
- **반영한 스킬 마찰 4건(실사용 surface)**: (1) Postgres `$$` dollar-quote 가 `sh -lc` 에서 셸 PID 로 오확장 → quoting·인증 escape 동작 패턴 명시 · (2) RO 강제를 `*-replica` 서비스 discovery 로 구체화 · (3) `account=<이름>`→`owner_account_id`(bigint) 매핑이 대화 backend 밖일 수 있음 → 별도 discovery·FK 추측 금지 · (4) 침묵이탈 corroboration 은 "ended-on-assistant" 단독이 ~95% 무차별 → "직전 턴 실패 결합" 레퍼런스 SQL 제공(과적합 역전 방지).
- **panel**: SKIPPED — 변경이 **Minor + 비핵심경로 + doc-only**(스킬 본문 명료화 + 신규 원장, 코드/런타임 무변경). quoting 패턴·corroboration 쿼리 형태는 dogfood run 에서 **라이브 실측으로 직접 검증**(psql replica 접속·집계 쿼리 실행)됨. §18.8 표 키워드 0건.
- **검증 한계**: `.claude/commands/*`·`docs/*` = 서빙 산출물 아님 → 배포 no-op. verify-completion META mode(check #9/#10/#11). FRICTION_LEDGER 2건은 report-only — 코드 수정·배포 없음(사람 plan 대기).

## REV-20260702T160000-migrate-fresh-image [SUBAGENT:deploy-migration-ordering]

- **cycle**: ai/claude/feature-0014-migrate-fresh-image — 배포 자동 마이그레이션이 신규 alembic 마이그레이션을 조용히 놓치던 회귀 근본 수정. 계기: TASK-20260702-aiops-panel 배포에서 마이그 0030(llm_usage.latency_ms)이 적용 안 된 채 deploy exit 0 → 수동 보정 필요. 근본원인: `bin/deploy-web.sh` 가 마이그레이션을 **이미지 빌드 전에** 실행 + `bin/alembic-migrate.sh` 가 `docker compose run agent`(stale 기본 이미지, 신규 마이그 파일 부재)로 head 감지 → "current==head, 적용 없음" 오판.
- **changeset (pure-meta, bin/ = META path → verify-completion META mode check #9 게이트)**: `bin/deploy-web.sh`(main() 에서 `build_image` 를 `migrate_phase` 앞으로 reorder + migrate_phase 가 `env MIGRATE_ALEMBIC_IMAGE=$IMAGE_REPO:$TARGET_SHA` 전달) · `bin/alembic-migrate.sh`(신규 `_alembic_sh` 헬퍼 — MIGRATE_ALEMBIC_IMAGE 설정 시 그 이미지로 `docker run --env-file` , 미설정 시 기존 `docker compose run agent` 폴백; gen_sql/stamp heads 통합; **gen_sql fail-loud rc 전파**) · `meta/REVIEW.md`(본 entry).
- **설계 요지**: ① build→migrate→recreate 순서(expand-before-swap 불변 유지 — build 는 swap 아님). ② 마이그레이션은 방금 빌드한 `mysql-ai-web:<sha>`(신규 마이그 파일 포함)로 실행 → head 정확 감지. ③ offline(--sql)·heads 는 DB 무연결이라 `.env*` KB PG 설정(존재분만)만 주입. ④ 폴백(env 미설정 standalone)은 기존 동작 유지(gen_sql inner cmd byte-동치).
- **panel (SUBAGENT, 1인 적대 — 5개 공격축 실측 검증)**: reorder 안전성(build 는 recreate 안 함·build후 migrate die 시 상태는 기존 flow 에서도 도달가능·expand-before-swap 유지) · env 주입(real+dry-run 실측 통과) · _alembic_sh(스로어웨이 baked 이미지 offline alembic heads/upgrade --sql 실측 통과·폴백 byte-동치) · 회귀엣지(TARGET_SHA/IMAGE_REPO 스코프·초기배포·standalone 무영향) · rollback 경로(build/migrate 도달 전 exit → 완전 무영향). **VERDICT BLOCKING 0 / NIT 4.**
- **흡수한 NIT**: **NIT-2 gen_sql silent-green**(2>/dev/null 이 docker/pip/alembic 실패를 빈 SQL 로 삼켜 upgrade false-green → swap 진행하던, 본 feature 가 없애려던 바로 그 클래스) → `gen_sql` 이 rc 전파 + `upgrade` 가 `if ! sql=$(gen_sql)` 로 die. 실측: 없는 이미지→"SQL 생성 실패 ABORT" EXIT=1(fail-loud), fresh 이미지→"current=0030==head" EXIT=0(정상 no-op).
- **수용·기록**: **NIT-1**(stamp 의 pip 처리가 gen_sql 규약으로 통일돼 fail-loud + `--no-cache-dir` 추가 — 기존 대비 strict improvement, "폴백 byte-동치" 는 gen_sql 한정이고 stamp 는 개선임을 명기) · **NIT-3**(빈 배열 `"${envargs[@]}"` under set -u 는 bash≥4.4 안전·실배포 호스트 전부 충족·codebase 동일 패턴 다수·`.env` 항상 존재로 실경로 비어있지 않음) · **NIT-4**(빌드 성공+swap 실패 후 last-good 태그 오염 가능 — PRE-EXISTING, reorder 무악화, 관찰 기록).
- **검증**: `bash -n`(deploy-web.sh·alembic-migrate.sh) PASS · MIGRATE_ALEMBIC_IMAGE 경로 3개 env-file 로 `alembic heads`=0030 실측 · fail-loud/no-op 2경로 실측 · 적대 패널 실측 5축. 다음 실배포에서 end-to-end 발동(현재는 0030 이미 적용됨 → no-op 확인).
- **Human Approval Needed**: 아니오 (배포 안전 강화 — silent-miss 회귀 차단 + fail-loud. 비파괴, 신규 production 동작 0, standalone/rollback/폴백 무영향. deploy_scope 무관 — 스크립트 로직 개선이라 실배포 시 자동 적용).
- **Human Approval Needed**: 아니오 (additive doc 명료화 + 진단 원장, 비파괴, 코드 변경 0).

## REV-20260702T230501-META-0019-doc-sync-0702 [SUBAGENT:doc-sync-adversarial-verify] — 07-02 머지분 인덱스/미러/사용자향 표면 정합 (그래프 뷰 상호작용/가시성 진화·AI 운영 관제 패널, ULTRACODE)
- **cycle**: ai/claude/doc-sync-20260702-230501 — `/_dqa:doc_sync ultracode`(무인 cron, 전 타깃). 직전 doc_sync(bb63b9f8/97004c49 @ 07-01 23:44) 이후 07-02 머지된 feature-0016 그래프 뷰 후속 진화 + feature-0003 AI 운영 관제 패널을 색인/미러/사용자향 표면에 정합. 정본(`unit/<id>/docs/*`) 재서술 없이 표면만 최신화(ADR-0031 인덱스 모델). landing/deploy 는 cron wrapper 소관(로컬 commit 만).
- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md` §1(feature-0003·0016-metadata-graph 행 date bump+요지 1구, 인덱스 모델·rollup 0) · `docs/ARCHITECTURE.md` §4(feature-0016 렌더러 Cytoscape 3.30.2/WebGL→AntV G6 v5(Canvas) 정정+07-02 진화, feature-0003 AI 운영 관제 패널 색인 note) · `docs/SECURITY.md` **신규 §20**(AI 운영 관제 패널 admin observability 경계 색인 — 신규 `console.aiops.read` admin 전용·`GET /api/admin/ai-ops`·`_pg_connect_ro` least-priv; §19 metadata-perm-hier 무변경 대비) · `docs/RELEASE_NOTES.md` 07-02 운영자 블록 2건(그래프 진화·AI 운영 관제 패널, append-tail) · wiki(`Features/feature-0016-metadata-graph` 카드 §2·마지막 갱신·§7 · `Features/feature-0003-agent-web-ui` 카드 §2.6·§1 · `overview` ㉘㉙ · `hot.md` · `Log.md`) · `meta/REVIEW.md`(본 entry).
- **panel (SUBAGENT, ULTRACODE 적대 워크플로 wf_61d9648b — 타깃별 finder + 적대 verifier)**: 릴리즈노트·STATUS·정책문서·wiki 4 타깃을 각각 finder(현실 git/code 근거 draft) → 적대 verifier(doc↔현실 delta 재검증·누출·인덱스모델·링크 무결성)로 검증. **3 delta 오류 적발·교정**: ① `docs/RELEASE_NOTES.md` append 방향(finder top-prepend → verifier 가 append-only·최신 하단 규약 적발 → bottom-append 로 정정) ② `docs/SECURITY.md` §20 'conversation_id 미노출' 사실오류(verifier 가 `ai_ops.py:165/193`·REVIEW A4 로 admin 노출 확증 → '신규 등급 아님·IDOR 없음'으로 교정) ③ `wiki/hot.md` rollup 'PB-0008 대부분 PASS' 과장(verifier 가 검증완료=ctxmenu·initview·search-badge / 배포 잔여=G6 교체·masonry·cam·rel-selfheal 로 구분 교정). 추가: wiki finder 가 STATUS/ARCH/SECURITY 를 noChange 로 오기재한 Log entry 를 실제 전체 changeset 반영으로 정정.
- **검증**: ADR-0031 인덱스 모델 준수(정본 재서술 0·STATUS 셀 rollup blockquote 누적 0) · feature 카운트 ground-truth(`ls -d unit/feature-*`=18 dir/17 id) 무변경(신규 feature 디렉토리 0) · `bin/ssot-lint.sh` PASS(4 WARN=기존 tracked secret, 불변) · §참조/anchor 무결성(SECURITY §19/§20 resolve) · 신규 wikilink 대상 존재. DECISIONS noChange(feature-0016 그래프 ADR-004~008 은 unit feature-local 정본 — repo DECISIONS 색인 아님, 정직 보고). PROJECT/CONVENTIONS noChange.
- **[SUBAGENT] 사유**: 색인/미러/기능맵 정합이나 SECURITY §20 신규 경계 색인·ARCHITECTURE 렌더러 정정 포함 → SKIPPED 대신 적대 워크플로 실검증(3 오류 적발). SECURITY §20 은 신규 authz 표면(`console.aiops.read`)의 boundary 색인이며 전체 위협모델 정본은 feature-0003 REVIEW.md(REV-20260702T140000-aiops-panel, security·authz BLOCKING 0)를 가리킴. 동반 operational(릴리즈노트 data.js+cache-buster+companions)은 feature-0003 별도 commit(REV-20260702T230501-doc-sync-rn-0702).
- **Human Approval Needed**: 아니오 (additive doc-sync 인덱스/미러/색인 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책. SECURITY §20 은 기존 배포된 표면의 경계 색인 — 신규 코드/동작 0).

## REV-20260707T110534-META-0020-doc-sync-0707 [SUBAGENT:doc-sync-adversarial-verify] — 07-02→07-07 델타 인덱스/미러/사용자향 표면 정합 (07-03·07-06 미landed doc_sync 통합 supersede + 07-04/07-07 추가분)
- **cycle**: ai/claude/doc-sync-20260707-110534 — `/_dqa:doc_sync`(수동·attended). 마지막 landed 릴리즈노트 5b1481bb(07-02 23:05) 이후 origin/main 에 69 머지가 쌓였으나 07-03·07-06 두 doc_sync 가 각각 rebase 충돌(07-03)·BG-Workflow 강제종료로 무커밋 성공 오판(07-06)으로 미landed → STATUS·릴리즈노트가 07-02 에 정체. 두 미방치 worktree(doc-sync-20260703-230501·doc-sync-20260706-230501)는 stale-base·불완전(07-06 초안 릴리즈노트 07-03 누락·wiki overview/hot/Log 미변경)·미검증이라 **rebase-salvage 대신 콘텐츠 harvest 후 supersede**, 현재 origin/main(3d2d070c) 기준 fresh 재구성으로 07-02→07-07 전체 창을 한 번에 정합. 정본(`unit/<id>/docs/*`) 재서술 없이 표면만 최신화(ADR-0031 인덱스 모델).
- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md` §1(feature-0002/0003/0007/0009/0016 행 date+요지, 인덱스 모델·rollup 0) · `docs/ARCHITECTURE.md` §4(feature-0003 행 aiops-ttft 앵커 0032/0033+step_gap KPI 재정의 정합[07-06 초안이 누락했던 WT3 적발분 복원]+런타임 설정 콘솔 note, feature-0009 행 window 공유, feature-0016 행 07-03~07 UX+§55) · `docs/RELEASE_NOTES.md` 07-03/04/06/07 기술 블록 tail append · wiki(`overview` ㉚~㊷ · `hot.md` Key Facts 6 + Recent Changes · `Log.md` wiki-ingest · `Features/feature-0002-agent-core`·`feature-0003-agent-web-ui`·`feature-0007-bedrock-llm-provider`·`feature-0009-group-conversation`·`feature-0016-metadata-graph` 카드) · `meta/REVIEW.md`(본 entry).
- **panel (SUBAGENT, 적대 검증)**: 두 미landed 초안(07-03 WT3=적대검증 통과 2커밋·07-06 WT6=미검증 초안)의 콘텐츠를 harvest 하되 현재 origin/main 대비 doc↔reality delta 를 적대 재검증. 07-06 초안이 WT3 의 ARCHITECTURE feature-0003 aiops-ttft 앵커 정정(0030→0032/0033+step_gap KPI)을 누락했음을 적발·복원. 07-07 tail(runtime-settings feature-0018·category-recursive-refine §55 ADR-021·edge-fallback)은 git log+정본 커밋(f581b2fe·10313ac9·81969e1f)에서 직접 추출. deploy-status·오귀속·ADR/마이그 번호(0031~0038·ADR-010~021)·INDEX 모델·append 방향·누출·hot.md Active Threads 보존 재확인.
- **검증**: ADR-0031 인덱스 모델 준수(정본 재서술 0·STATUS 셀 rollup blockquote 누적 0) · feature 카운트 ground-truth(`ls -d unit/feature-*`=18 dir/17 id) 무변경(feature-0018 은 독립 unit 없이 feature-0003 코드 거주 → 신규 디렉토리 0·신규 wiki 카드 불요) · `bin/ssot-lint.sh` PASS(4 WARN=기존 tracked secret, 불변) · `bin/wiki-lint.sh` 신규 broken link 0 · `node --check release-notes-data.js` PASS(operational 별도 commit) · §참조/anchor 무결성. DECISIONS noChange(feature-0016 ADR-010~021·feature-0007 ADR-002 는 unit feature-local 정본 — repo DECISIONS 색인 아님, 정직 보고) · SECURITY noChange(share-visibility-window §21/§21.4 는 소속 feature-0009 정본이 이미 반영·07-03~07 나머지 신규 authz/경계 0 — additive nullable 컬럼·gateway 내부 라우팅·feature-0018 권한은 소속 정본) · Index/_Index noChange(카드 18 안정). PROJECT/CONVENTIONS noChange.
- **[SUBAGENT] 사유**: 색인/미러/기능맵 정합에 ARCHITECTURE §4 앵커 복원 포함 + 두 미landed 초안 통합·supersede 판정에 적대 재검증 필요 → SKIPPED 대신 SUBAGENT 실검증. 동반 operational(릴리즈노트 data.js 07-03/04/06/07 4블록+cache-buster 20260707-rn-0707+companions)은 feature-0003 별도 commit(REV-20260707T110534-doc-sync-rn-0707, [SKIPPED:non-policy-doc]). aiops-ttft(step_gap)·gc-join-notice·share-visibility-window·runtime-settings·category-refine 는 원천 feature cycle 이 PB-0008 기록(각 정본) — 본 doc_sync 는 콘텐츠 데이터/캐시버스터만.
- **Human Approval Needed**: 아니오 (additive doc-sync 인덱스/미러/색인 정합, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책. ARCHITECTURE §4 는 기존 배포 표면의 alembic 앵커/기능맵 정밀도 정정 — 신규 코드/동작 0. landing/deploy=본 attended run 이 사용자 정책 2026-06-25 하에 자동 수행).

## REV-20260707T230501-META-0021-doc-sync-0707-2305 [SUBAGENT:doc-sync-adversarial-verify] — 07-07 후속(11:34 이후) 머지분 인덱스/미러/사용자향 표면 정합 (지식베이스 채택 인박스+ENUM 자율수집·콘솔 IA 통합·§56 그래프 sync 견고화·추론 강도별 예산, ULTRACODE)
- **cycle**: ai/claude/doc-sync-20260707-230501 — `/_dqa:doc_sync ultracode`(스케줄·무인). 직전 doc_sync(META-0020 @ 07-07 11:34, 04bf4a87 META/dfc64728 릴리즈노트)가 07-07 오전까지 반영 → 그 이후(11:37~19:33) main 병합 델타를 색인/미러/사용자향 표면에 정합. cron wrapper 가 push/merge/deploy 소관 — 본 run 은 로컬 commit 까지.
- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(인덱스 feature-0002/0003/0007/0016-metadata-graph 행 요지 append·0007 date bump, rollup 0)·`docs/RELEASE_NOTES.md`(07-07 후속 운영자 블록 tail append)·wiki(`Log.md`·`hot.md` Key Fact 2+Recent Changes·`Features/feature-0003-agent-web-ui` §2.7 표 3행·`Features/feature-0016-metadata-graph` §2/§6/§7·`overview.md` ㊸ 신설+㊵㊶ 보강)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260707T230501-doc-sync-rn-2305): 릴리즈노트 data.js 07-07 블록 +2항목+cache-buster `20260707b-rn-0707`.
- **panel (SUBAGENT, ULTRACODE 적대 워크플로 wf_731a14ae — 4 타깃 finder + 차원별 적대 verifier, 8-agent)**: 릴리즈노트/STATUS/wiki/정책문서 병렬 draft + 적대 검증. **2 delta 적발·교정**: ① 릴리즈노트 초안이 '용어사전 대화 자율수집'을 신규로 주장 → 2026-06-29 블록(라인 408·414)에 이미 landed 확인 → **코드값(ENUM) 측만으로 rescope**('용어사전' 표현 제거) ② §56 을 'ADR-022' 단일 참조 → 실제 ADR-022(RC1~4)+ADR-023(RC5 MSSQL label 정규화) split 확인 → 전 문서 **ADR-022~023** 정정.
- **검증**: ADR-0031 인덱스 모델 준수(정본 재서술 0·STATUS 셀 rollup blockquote 누적 0) · feature 카운트 ground-truth(`ls -d unit/feature-*`=18=`wiki/Features/feature-*.md`=18, feature-0018 은 unit 부재·코드 0002/0003 거주) · 삽입 wikilink 대상(feature-0002/0003/0016 카드) 존재 · `bin/ssot-lint.sh` 4 WARN(기존 secret) 불변 · 릴리즈노트 `node --check` PASS·블록순서(07-07>06>04>03>02)·평이화(내부용어 누출 0). DECISIONS/ARCHITECTURE noChange(§56 ADR-022~023 feature-local·기능맵 고수준 유지)·SECURITY noChange.
- **[SUBAGENT] 사유**: 색인/미러/사용자향 표면 정합(정책 의미 변경 없음) — 정책-doc(docs/wiki)이나 additive 정합이라 codex 패널 불요, ULTRACODE 적대 워크플로가 delta/reality 교차검증(선례 REV-20260707T110534-META-0020·REV-20260701T230501-META-0018 동일 계열). 동반 operational(릴리즈노트)은 feature-0003 별도 commit(REV-20260707T230501-doc-sync-rn-2305 [SKIPPED:non-policy-doc]).
- **잔여 권고(feature cycle 위임)**: ENUM 대화 자율수집(0beb02e3)은 06-29 용어사전 자율등록(PROJECT ADR-20260629T101500)과 대칭이나 프로젝트/피처 ADR 미승격·신규 권한 `kb.enum.curate` 는 SECURITY §19 미색인(sibling `kb.glossary.curate` 도 pre-existing 미색인 — 델타 도입 stale 아님). doc_sync 는 정책 본문 미작성 → owning feature-0002/0003 cycle 이 ADR 승격·SECURITY 색인 판단 권고.
- **Human Approval Needed**: 아니오 (additive doc-sync 인덱스/미러/색인 정합 + 사용자향 표면 갱신, 비파괴, 신규 production 동작 0, 전역 auto-sync + doc_sync 무확인 자동 정책. landing/deploy=cron wrapper 소관 — 본 run 은 로컬 commit 까지).

## REV-20260708T114241-daily-report-collect-script [SUBAGENT:daily-report-collect-adversarial-review] — /daily-report 사전 집계 스크립트 도입(기계적 수집·그룹핑·시간대 배정 자동화, AI 는 판단만 마감)
- **cycle**: ai/claude/daily-report-collect-script — 사용자 요청("/daily-report 를 더 효율적으로: 스크립트 사전 집계 → AI 는 다듬어 신속 전달"). `/daily-report` 가 매 호출마다 AI 가 손으로 하던 기계적 단계(날짜·커밋수집·보고일 경계 19:00 분류·TASK 그룹핑·시간대 배정·머지 접기·별첨 휴리스틱·각주)를 결정론적 스크립트로 이관하고, 스킬 절차를 스크립트-우선 흐름으로 재작성.
- **changeset (pure-meta, bin/*·.claude/* = META path → verify-completion META mode check #9 게이트)**: `bin/daily-report-collect.py`(신규 ~370줄 — git log window 수집→벽시계 경계 분류→TASK 키 3형식 그룹핑→시간대/전날야간/이월 배정→순수머지 접기+PR#dedup→제품/별첨 파일-경로 휴리스틱→각주 사전계산, 사람용 digest + `--json`) · `.claude/commands/daily-report.md`(§1 을 스크립트 호출로 대체·§2/§3 흡수·§4/§5 를 "스크립트 완료→AI 검토" 로 reframe, 판단 규칙 §4.1/§4.2/§6 및 불변제약 유지, 스크립트 실패 시 수동 git 폴백 명시) · `meta/REVIEW.md`(본 entry).
- **설계 요지**: ① 결정론=스크립트, 판단=AI 분업(스크립트는 요약 지어내지 않고 커밋 원문·changed·scope 만 실어 재료 제공; 머지·docs-only 도 버리지 않고 마킹만). ② 보고일 경계 19:00 을 벽시계 datetime 으로 정밀 판정(±1h margin fetch 후 Python 필터). ③ TASK 키 `TASK-NNNN`/`TASK-YYYYMMDD[Thhmmss]-slug`/`TASK §NN` 3형식 — date+slug 를 짧은 serial 보다 먼저 매칭해 `TASK-YYYYMMDD-A`/`-B` 오병합 방지. ④ 별첨은 힌트만(제품 소스 경로 유무), §4.2 확정은 AI.
- **panel (SUBAGENT, 1인 적대 코드리뷰 — 통과 아닌 결함 적발)**: general-purpose 리뷰어가 3개 날짜(07-07·07-02·빈 날짜) 실행 + raw `git log` 대조(counts 정확 재구성 49=49·100−45−15=40) + 합성 경계/걸침 케이스 구성. **VERDICT CHANGES RECOMMENDED (BLOCKER 0 / MAJOR 2 / MINOR 3 / NIT 4).**
- **흡수한 MAJOR (전건 반영)**: **MAJOR-1**(prev_night/before_1000 을 낀 구간 걸침 그룹이 `spans_multiple` 판정에서 빠져 조용히 오배치+미표시, digest 가 per-commit 날짜 은닉으로 AI 가 적발 불가) → `sections_hit`(표시 섹션 단위 걸침) 신설·`spans_multiple` 을 그 기준으로·⚠구간 걸침에 섹션 라벨+"§5 분할" 표기·digest 각 커밋에 `MM-DD HH:MM` 노출. 합성 2케이스(전날20시+당일11시 / 당일09시+14시)로 spans=True 발동 실증. **MAJOR-2**(명시 `--repo` 실패 시 조용히 스크립트 자기 repo 로 폴백→엉뚱한 repo 를 exit 0 성공 보고, 문서화된 exit-2 계약 死문) → `--repo` 명시 시 실패하면 즉시 exit 2(폴백은 인자 미지정일 때만). `--repo /tmp` 실측 exit=2.
- **흡수한 MINOR/NIT**: MINOR-3(`Merge .*into ` 광역 정규식이 "Merge X into Y" feature subject 오탐) → 머지 정규식을 `Merge (pull request|remote-tracking branch|branch)\b|merge origin/` 로 축소(parent>1 이 1차 신호) · MINOR-5(리베이스 트윈으로 순수머지 count 부풀림 45/24→dedup 40/22, commit_count 도 subject-dedup 기준·totals 를 정직 재구성) · NIT(`TASK § 56`/`TASK §56` 공백차 오분리 방지 정규화). MINOR-4(단일 tz 전제)는 `bucket_of` docstring 에 알려진 한계로 명문화.
- **검증**: `python3 -m py_compile` PASS · 07-06/07-07/07-02(전날야간14+10시이전12+이월15) 경계·그룹핑·각주 정확 · 빈날짜 exit 0("커밋 없음")·잘못된날짜 exit 3·비저장소 --repo exit 2 · 실행 ~50ms(100커밋 날짜) · 스킬 doc 상호참조(§4.1/§4.2/§5/§6) 무결·폴백 window 동일. **런타임 제품코드 무변경**(스킬/도구) → 배포 no-op(META path).
- **[SUBAGENT] 사유**: ~370줄 로직 스크립트 신규(정규식·경계 datetime·분류 휴리스틱)라 trivial-SKIPPED 부적합 — 선례상 substantive 변경은 적대 검증. 1인 적대 코드리뷰로 MAJOR 2건 포함 결함 적발·전건 반영. `.claude/commands/*`·`bin/*` = 서빙 산출물 아님 → verify-completion META mode(check #9/#10/#11) 만.
- **Human Approval Needed**: 아니오 (개발 보조 도구·스킬 개선, 비파괴, 신규 production 동작 0, pure-meta. 원 요청(사전 집계 스크립트화)을 그대로 완수 — 새 scope 아님. 전역 auto-sync 정책 하 PR 생성·머지·cleanup 은 사용자가 본 turn "finalize 까지 완수" 명시 승인).

## REV-20260708T230501-META-0022-doc-sync-0708 [SUBAGENT:doc-sync-adversarial-verify] — 07-08 머지분 인덱스/미러/사용자향 표면 정합 (§57 그래프 접힘 카드 시각화·§59 분석 기반 제품 분류 AI 제안→승인·메타데이터 콘솔 UX, ULTRACODE)
- **cycle**: ai/claude/doc-sync-20260708-230501 — `/_dqa:doc_sync ultracode`(스케줄·무인). 직전 doc_sync(META-0021 @ 07-07 23:05, 5aac2b28 META/ed42a378 릴리즈노트) 이후 07-08 main 병합 델타(14 non-merge)를 색인/미러/사용자향 표면에 정합. cron wrapper 가 push/merge/deploy 소관 — 본 run 은 로컬 commit 까지.
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(인덱스 feature-0002/0003/0016-metadata-graph 3행 date bump 07-08 + dated 요지 1구 append, rollup 0)·`docs/ARCHITECTURE.md`(feature-0016 셀 07-08 §57·§59 진화 note append — 구조·의존 불변)·`docs/RELEASE_NOTES.md`(07-08 운영자 블록 tail append)·wiki(`Log.md`·`hot.md` Key Fact 2+Recent Changes·`Features/feature-0016-metadata-graph` §2/§4/§7·`Features/feature-0003-agent-web-ui` §1/§2.8·`overview.md` ㊹㊺)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260708T230501-doc-sync-rn-0708 [SKIPPED:non-policy-doc]): 릴리즈노트 data.js 07-08 블록 3항목 + cache-buster `20260708-rn-0708`.
- **ULTRACODE 적대 검증(wf_3891a205, 6-agent write+adversarial-verify)**: 릴리즈노트·wiki·정책문서 각 타깃 write→적대 verify 파이프라인 — 3 타깃 전부 confirmed(BLOCKING/MAJOR/MINOR 0). 정본 대조 확증: §57(ADR-024 — SCHEMA_REF 1-hop 집계·3단 승격·마젠타·중간 줌 LOD, POST-DEPLOY PB-0008 상대 dim 358/361·마젠타 51·LOD 520)·§59(ADR-025 — Pending-only 스테이징·환각 3중 게이트·데몬 기본 OFF·allowlist 무변경, dry-run 11→10건 적재)·콘솔 ux2/polish. NIT 2(styles.css pre-existing 테스트 취약성·§56 ARCHITECTURE pre-existing 갭 — 둘 다 현 delta 창 밖·본 run 수정 의무 아님, 투명성 기록).
- **무변경 정직 보고**: `docs/DECISIONS.md` noChange(ADR-024~025 는 feature-0016 local 3-digit 정본 — repo 4-digit DECISIONS 색인 대상 아님, 선례 동일)·`docs/SECURITY.md` noChange(§59 는 신규 RBAC 경계 무생성 — 기존 `product.manage` 재사용·allowlist WebProductDatabases 무변경·이미 SECURITY §9.2 audit cascade 반영)·`wiki/Features/_Index`·`wiki/Index` noChange(신규 feature 0 — 17 active/카드 18/디렉토리 18)·`wiki/concepts` noChange(§59=기존 metadata 도메인 내부). ssot-lint EXIT 0(기존 secret 백업 WARN 만·불변·새 FAIL 0).
- **검증(타깃별 실질)**: 기능 카운트 grep 정합(17/18)·wikilink 전건 resolve·§ref/anchor resolve·STATUS 인덱스 모델(rollup 0)·ssot-lint PASS. verify-completion check #1/#5 deferred(v1.1)는 위 타깃별 검증으로 갈음.
- **[SUBAGENT] 사유**: 색인/미러/사용자향 표면 정합(정책 의미 변경 없음) — 정책-doc(docs/wiki) additive 정합이라 codex 패널 불요, ULTRACODE 적대 워크플로가 delta/reality 교차검증(선례 REV-20260707T230501-META-0021·REV-20260707T110534-META-0020 동일 계열).
- **Human Approval Needed**: 아니오 (색인/미러 additive, 제품 런타임 동작 0, pure-meta). doc_sync 사용자 정책(2026-06-25)상 landing 무확인 자동이나, 본 worktree 는 cron wrapper 가 push/merge/deploy 소관 — 로컬 commit 까지만.

## REV-20260709T114814-docsync-self-repair [SUBAGENT:doc-sync-self-repair-adversarial-review] — `/_dqa:doc_sync` 스킬에 멱등 자가수리(self-repair) 성격 도입 (reconcile-first·end-state 성공기준·canonical 배포 위임·소유권 경계)
- **cycle**: ai/claude-corp/docsync-self-repair — 사용자 요청("`/_dqa:doc_sync` 스킬이 자가 수리의 성질을 갖도록 구성할 수 있을까"). 직전 turn 에 cron wrapper `~/.local/bin/dqa-doc-sync-cron.sh` 의 하드코딩 배포(`docker compose build web`)가 feature-0014 토폴로지 개편(web-a/web-b+Caddy, `bin/deploy-web.sh` 정식 무중단) 이후 `no such service: web` 로 상시 실패 + rc=0 조용한 방치("또다시")를 근본수정(wrapper=정식 경로 위임+self-heal). 그 뒤 **스킬 자체**가 같은 실패 클래스에 멱등 수렴하도록 self-repair 성격을 스킬 정의에 도입.
- **changeset (pure-meta, `.claude/commands/*` = META path → verify-completion META mode check #9 게이트)**: `.claude/commands/_dqa/doc_sync.md`(불변제약 '멱등 자가수리' 원칙 신설 + Phase 0.4 canonical 진입점·서빙 static parity end-state probe·배포/landing 소유권 판정 discovery + Phase 1.0 reconcile-first sub-step + early-exit 계약 확장 + Phase 5 landing 소유권 경계 + Phase 6 배포 소유권 경계·(a/b) 판정·canonical 위임·end-state 검증 + 종료조건 2항) · `meta/REVIEW.md`(본 entry).
- **설계 요지 (self-repair = 멱등 수렴)**: 몇 번 돌리든 "docs + 라이브 서빙 surface = origin/main" 으로 수렴. ① **reconcile-first**: doc delta 계산 前 **서빙 static surface 파리티**(서빙 릴리즈노트/캐시토큰 vs 정본 static)를 첫 drift 로 점검(coarse 커밋라벨 비교는 오탐이라 배제). ② **end-state 성공기준**: 완료를 "commit" 이 아니라 "라이브 실제 서빙" 으로 판정, committed/serving 분리(§16.3 bring-up/access 동형). ③ **canonical 위임**: 배포를 프로젝트 canonical 진입점(named deploy 타깃/스크립트)에 위임, raw compose 재구성 금지 → 토폴로지 진화 drift 차단. ④ **컨텍스트/소유권 경계**: 갭 감지는 컨텍스트 무관, 실배포(수리)는 배포 소유자만 — cron(wrapper 소유)=감지·보고만, attended=스킬 수리 → wrapper self-heal 과 이중배포 없이 합성.
- **panel (SUBAGENT, 2-round 적대 정합성 리뷰 — improve-fit-reviewer, 통과 아닌 결함 적발)**: **1차 VERDICT=CHANGES RECOMMENDED (BLOCKER 0 / MAJOR 5 / MINOR 3 / NIT 1)** → 전건 반영 → **2차 VERDICT=SHIP (잔존 BLOCKER/MAJOR 0)**.
- **흡수한 MAJOR (전건)**: **M1**(④ 소유권 carve-out 이 헤더/불변제약/종료조건에 미전파 → "무인=무조건 배포/머지" 자기모순·cron racing 여지) → 3지점 전파. **M2**(④는 landing 위임 전제인데 Phase 5 push/merge 무조건 강제) → Phase 5 서두 landing 소유권 경계 신설(wrapper 낙관 ff-push 루프 racing 방지). **M3**(reconcile-first 갭을 coarse `GIT_COMMIT vs HEAD` 로 정의 → 고병렬 repo 상시 오탐 → attended zero-delta 무관 pending 코드 무확인 재배포=2026-06-25 override 범위초과) → 갭을 **서빙 static surface 파리티**로 한정, coarse 비교 명시 배제. **M4**(canonical ff-전진 대상 checkout 미명세 + `repo/` 미사용 규약 상충) → 배포호스트≠worktree 명세·ff-only 는 §13.2.4 carve-out(F0 밖)·`repo/` 접근은 규약 명시적 예외·비-ff/dirty fail-loud. **M5**(소유권 판정 fail-open + system-prompt 문자열 커플링) → 3분기 판정(명시신호/대화형/불명확무인) + **self-repair 배포만 fail-closed**(자기 changeset 자동배포 charter 는 보존 — 2차 리뷰가 charter 회귀 없음 확인)·env/flag 병행.
- **흡수한 MINOR/NIT**: m1(종료조건 delta0 항목 self-repair 예외 cross-ref) · m2(`deploy-web`→`deploy-<surface>`·`GIT_COMMIT` 리터럴 제거로 project-agnostic 복원) · m3(coarse probe 과대보고 — M3 로 동시해소) · NIT(zero-delta 재배포는 3(cache-buster)·1(deploy_scope) 무관·4·5만 명시). 2차 리뷰 신규 MINOR(Phase 5 item3 예외목록 '소유권 위임' 누락)도 반영.
- **검증**: verify-completion META mode — CHECK#10 PASS(worktree binding)·#11 PASS(ai/* worktree F0 외)·#13 PASS(web/UI 자산 무변경 skip)·#1~#8 skip(pure-meta §18.4)·**#9 는 본 entry 로 충족**. 문서-only 변경(스킬 정의)이라 런타임 코드·테스트 무영향, 배포 no-op(META path — 서빙 산출물 없음). 스킬 내부 자가수리 ①②③④·Phase 0.4/1.0/5/6 cross-ref 정합 자체검토.
- **[SUBAGENT] 사유**: governance persona 의 **동작 semantics 변경**(early-exit 계약·배포 소유권·자가수리 트리거)이라 trivial-SKIPPED 부적합 — 선례상 substantive 변경은 적대 검증. improve-fit-reviewer 2-round(결함 적발→반영→SHIP)로 MAJOR 5 포함 전건 적발·해소. `.claude/commands/*` = 서빙 산출물 아님 → META mode(#9/#10/#11/#13)만.
- **Human Approval Needed**: 아니오 (스킬 정의 문서 변경, 제품 런타임 동작 0, pure-meta, 비파괴). 사용자가 self-repair "전체 구현" 을 명시 승인. 전역 auto-sync 정책 하 commit/push/main-ff 자동(외부 알림·PR 아님 — 직접 ff-push, 배포 no-op).

## REV-20260710T180820-improve-parallel-structure [SUBAGENT:improve-fit-reviewer] — 병렬 AI 작업 충돌 구조 개선 로드맵 (initiative: parallel-work-structure)

- **scope**: `docs/improvements/parallel-work-structure/{RESEARCH,ROADMAP}.md` 신설 — `/_dqa:improve_listup` 산출. 병렬충돌 3방향 내부 조사(거버넌스·git 이력·핫스팟) + feature-0012 중단 세션 복원(`/_template:resume`) + 웹 리서치 2건(다중 AI 세션 사례 / 고속 머지 인프라, W-001~W-010)을 융합해 12개 ITEM·4 Phase·DAG 로드맵 구축.
- **검증**: improve-fit-reviewer **2-round 적대 리뷰**. 1차 NOT-SHIP — BLOCKING 2(B-1 feature_id 가 verify 정규식과 계약 파손 → META-NNNN 전환·혼합 changeset 분리 규약 신설 / B-2 §13.1 v3.35.1 merge-driver 허용 범위 왜곡 → 정식 개정을 선행 스텝으로 격상), MAJOR 5(AGENTS.md 개정 공통 규약 신설·편집 항목 01→03→06→07→12 완전 직렬화·REGISTRY 부트스트랩·ADR 인용 네임스페이스 정정·Major 등급 상향), NIT 12 전건 반영. 2차 SHIP-WITH-FIXES — 잔여 5곳(ADR bare 인용 3·.merge.lock 경로 전제 오류 2) 반영 완료(락 위치는 `git rev-parse --git-common-dir` 하위로 확정 — working tree 밖·전 worktree 공유). DAG 비순환·enables 역참조·§5 ready 목록·수치(23 include·236/198 변경횟수·META-0022 최대번호) 리뷰어 실측 대조 PASS.
- **META mode 판정**: changeset = `docs/improvements/**` + `meta/REVIEW.md` — pure-meta(§18.4), check #9 는 본 entry 로 충족. 런타임 코드·테스트 무영향, 배포 no-op.
- **Human Approval Needed**: 아니오 (로드맵 문서 신설 — 비파괴·코드 무수정). 단 **각 ITEM 의 구현은 별도 cycle 게이트**: Major 9종(01·03·04·06·07·09·10·11·12)은 착수 시 사람 승인 필수(§12.3, 무인 improve_cycle 자동 blocked), AGENTS.md 개정 5종은 DECISIONS 제안+사람 승인+template 전파 계획(§0 공통 규약).

## REV-20260710T182248-parallel-structure-drain-mode [SKIPPED:user-directive-transcription] — ROADMAP 연속 드레인 운영 모드 개정 (initiative: parallel-work-structure)

- **scope**: `docs/improvements/parallel-work-structure/ROADMAP.md` 개정 — §6 "연속 드레인 운영 모드" 신설(단일 세션 직렬·토큰 소진→continue 반복·§6.2 선형 실행 순서·§6.3 blocked 축소·§6.4 재개 프로토콜), Major 9종 사전 승인(§6.1, PLAN-APPROVED 상당) 및 ITEM-04/09/11 의 사람 게이트를 기계 게이트로 대체, §0/§2/§5/각 항목 guards 정합 갱신.
- **SKIPPED 사유**: 본 개정은 2026-07-10 사용자 명시 지시("단일 세션·병렬 없이, 토큰 소진까지 작업 후 continue 반복, 특별한 이슈 없으면 blocked 되지 않게 구성")의 **전사(transcription)** — 승인 판단의 주체가 사용자 본인이라 적대 패널의 판단 대상이 아님. 직전 2-round 적대 리뷰(REV-20260710T180820)의 구조·계약 검증은 유효 유지(항목 명세·DAG 무변경, 실행 모드만 추가). 잔존 사람 게이트 2곳(2단계 브랜치 삭제·명세 밖 확장)은 §6.1 한계로 의도적 보존 — grep 정합 검사 완료.
- **META mode 판정**: changeset = `docs/improvements/**` + `meta/REVIEW.md` — pure-meta(§18.4). 코드 무수정·배포 no-op.
- **Human Approval Needed**: 아니오 — 본 개정 자체가 사용자 지시의 문서화. 철회 조항(§6.1) 포함.

## REV-20260710T184956-drain-recursive-selfresume [SKIPPED:user-directive-transcription] — 드레인 재귀 자가 재호출 체인 (initiative: parallel-work-structure)

- **scope**: `bin/drain-continue-cron.sh` 신설(arm/check/disarm/status — 버스트 시작 +5h10m 재귀 앵커, 크론 체커 fire 직전 선-재-arm 으로 버스트 실패에도 체인 유지, TTL 40 백스톱, 완주 시 disarm) + ROADMAP §6.4 개정(사용자 continue ‖ 자동 재호출 이원 경로, ScheduleWakeup 금지 유지 — 상태파일 기반 호스트 크론으로만 재귀).
- **SKIPPED 사유**: 2026-07-10 사용자 지시 2차("continue 호출 +5시간 10분 자가 재호출, 재귀 구조") 의 전사. 헤드리스 호출 패턴은 dqa-doc-sync-cron.sh 의 2026-07-07 incident fix(BG_WAIT_CEILING_MS=0 + 외곽 timeout) 를 그대로 승계 — 신규 판단 없음. bash -n 문법 검사 + status/arm/disarm 라운드트립 검증(크론탭 설치·라이브 fire 는 운영 단계 — repo 밖, 본 cycle 산출물 아님).
- **META mode 판정**: changeset = bin/ + docs/improvements/ + meta/REVIEW.md — pure-meta(§18.4). 배포 no-op.
- **Human Approval Needed**: 아니오 — 사용자 지시의 구현. 체인 정지 수단(disarm·TTL) 내장.

## REV-20260710T231146-META-0023-parallel-id-hygiene [SKIPPED:roadmap-spec-transcription] — TASK.md § 섹션·ADR·archive 순번의 timestamp 전환 (id 위생 완결, ITEM-01)

- **cycle**: ai/claude-corp/META-0023-parallel-id-hygiene — `/_dqa:improve_cycle parallel-work-structure` 드레인 1번째 항목 (ITEM-01). **승인 근거: ROADMAP §6.1** (2026-07-10 사용자 지시, Major 사전 승인 — PLAN-APPROVED 상당).
- **changeset (pure-meta — AGENTS.md·docs/**·meta/** = META path, verify META mode check #9 게이트)**: `AGENTS.md` 3개 절 개정 — §13.1(사이클-append 문서 신규 최상위 섹션 헤더 `## <YYYYMMDDTHHMM>-<slug>`, 순번 `## N.` 신규 금지·기존 불변) · §5.5(아카이브 파일명 `_archive/<DOC>-archive-<YYYYMMDDTHHMMSS>.md` 초 단위 전환) · §6(신규 ADR timestamp-slug 만 유효 — 순번 fallback 폐지, 표+prose 2곳). `docs/DECISIONS.md`(ADR-20260710T231146-parallel-id-hygiene append — timestamp-slug 형식 자기 적용). `docs/improvements/parallel-work-structure/ROADMAP.md`(ITEM-01 status done + §5 재집계 — feature cycle 커밋 동봉, M3 규약). `meta/REVIEW.md`(본 entry).
- **SKIPPED 사유**: 본 개정의 what/entry_points/acceptance/guards 는 ROADMAP ITEM-01 에 완전 명세돼 있고, 그 명세는 improve-fit-reviewer **2-round 적대 리뷰**(REV-20260710T180820-improve-parallel-structure — 1차 NOT-SHIP → 전건 반영 → 2차 SHIP-WITH-FIXES)가 이미 검증했다. 구현은 그 명세의 전사(transcription)로 신규 판단 없음 — 기존 timestamp 규약(v3.32.0/v3.34.x)의 자연 확장, 아키텍처·제약·보안 무영향. §18.8 dispatch(auth/schema/UI/API/perf) 비해당.
- **acceptance 검증**: (a) AGENTS.md 3개 절 개정 diff 존재 ✓ (b) ADR 1건 append — 제안·승인 근거(§6.1) 기록 포함 ✓ (c) 기존 § 참조 무파손 — `grep -rn '## 5[0-9]' unit/*/docs/TASK.md` 39줄·md5 0a223f9a 개정 전후 불변 ✓ (소급 재번호 0 — guards 준수).
- **template base 전파(inbox) 계획** (§0 공통 규약 ii, §13.2.3-A 선례): 본 §13.1/§5.5/§6 개정 3종은 template 계보(v3.37.2) 후속 버전에 반영 후보 — ai-delegated-dev 템플릿 base 저장소 inbox 에 "사이클-append 문서 섹션 헤더·아카이브 파일명·ADR fallback 폐지의 timestamp 전환(소비자 mysql_ai_delegated_dev 선행 실증)" 1건으로 제출 예정. 전파 전까지 본 repo 한정 유효.
- **Human Approval Needed**: 아니오 — §6.1 사전 승인 소진(명세 내 범위). doc-only·비파괴·소급 재번호 없음. 배포 무관.

## REV-20260710T234500-META-0025-worktree-audit [SKIPPED:roadmap-spec-transcription] — worktree/branch stale sweep 자동화 + 라이브 sweep (parallel-work-structure ITEM-04)

- **cycle**: ai/claude-corp/META-0025-worktree-audit — `/_dqa:improve_cycle parallel-work-structure` 드레인 3번째 항목(ITEM-04, Major). **승인 근거: ROADMAP §6.1**(2026-07-10 사용자 지시 — Major 착수 + `--apply` 활성화 사전 승인, 기계 조건: 첫 리포트 생성→acceptance (b)(c) 검증→같은 드레인 내 활성화 전부 이행).
- **changeset (pure-meta — bin/**·docs/**·meta/** = META path)**: `bin/worktree-audit.sh` 신설(§13.2.3-A 구현: SAFE_REMOVE/LIKELY_ABANDON/NEEDS_REVIEW/ACTIVE 4분류 · merged 이중확인=ancestry ∨ merged-PR headRefOid==tip(squash 후 추가 커밋 오삭제 방지) · 통지 후 유예 상태파일(직전 리포트 노출분만 apply, W-009) · DIRTY/IN-USE 불가침 · Open PR 무조건 ACTIVE · root 잔여물 sudo 정리 재시도) + `bin/install-worktree-audit-cron.sh`(평일 08:40 리포트/08:50 apply, main checkout 앵커, 멱등 marker) + ROADMAP ITEM-04 done + 본 entry. AGENTS.md 무편집(직렬 체인 밖 — §13.2.3-A 구현 존재 표기는 ITEM-12 편승).
- **SKIPPED 사유 + 명세 밖 1건 투명 기록**: 판정 로직·가드는 §13.2.3-A 정본 + ROADMAP ITEM-04(2-round 적대 리뷰 기검증)의 전사. **명세에 없던 추가 가드 1건 — IN-USE(프로세스 CWD) 불가침**: 구현 중 라이브 실측으로 doc-sync cron 헤드리스 세션(23:05 발화, 커밋 전이라 clean/ahead=0)의 worktree 가 SAFE_REMOVE 로 오분류됨을 발견(§6.3-6 "SAFE_REMOVE 오판정" 계열) → blocked 대신 가드 보강으로 해소(보수 방향 확장 — 삭제 범위를 좁히는 변경이라 명세 밖 scope 확장 아님). 한계 명시: 타 계정 프로세스 CWD 비가시(DIRTY·ahead>0 로만 보호).
- **acceptance 검증**: (a) 드라이런 리포트 4분류 출력 — 217 브랜치: SAFE 187/ABANDON 27/REVIEW 1/ACTIVE 2 ✓ (b) merged 테스트 브랜치 1개(`ai/claude/task0211-env-ds`) `--apply --branch` 표적 제거, ls-remote 0 확인 ✓ (c) squash-merge 브랜치 `gh pr list` 병행 판정 SAFE_REMOVE 분류(예: attachment-fk-orphan=PR #258 tip 일치, hl-bake=PR #640) ✓ (d) open PR 브랜치(#558 node-role-viz) 무조건 ACTIVE ✓ (e) cron 설치(리포트+apply) + 로그 경로 — 첫 정기 실행은 익영업일 08:40 ✓. **라이브 full sweep**: 원격 ai/* 200→미머지·ACTIVE 잔존만(SAFE_REMOVE 소진), stale worktree 정리(IN-USE/DIRTY 제외) — 오판정 0(merged-only 비파괴).
- **"자동 orphan sweep 은 사이클 외" 기존 결정(AGENTS.md §13.2.3 Reviewer Concerns — template 측 절, 소비자 ADR-0020 과 무관)과의 관계**: 본 cron 은 개발 사이클이 아닌 **스케줄 maintenance**(doc_sync 와 동급 지위)로 비충돌 — 사이클 내 자동 sweep 을 도입한 것이 아니라, 사용자 수동 sweep 을 §13.2.3-A 가 이미 규정한 판정 기준대로 도구화한 것.
- **Human Approval Needed**: 아니오 — §6.1 이 `--apply` 활성화까지 명시 사전 승인(기계 조건 충족). 삭제는 merged-only 이중확인이라 비파괴(원격 브랜치 삭제라는 외부 영향은 §6.1 범위 내). 배포 무관.
## REV-20260711T042327-META-0028-status-autogen [SKIPPED:roadmap-spec-transcription] — STATUS.md 기능현황표 자동 생성 (parallel-work-structure ITEM-08)

- **cycle**: ai/claude-corp/META-0028-status-autogen — `/_dqa:improve_cycle parallel-work-structure` 드레인 5번째 항목(ITEM-08, Minor). 승인: ROADMAP §6.1.
- **changeset (pure-meta — bin/**·docs/**·.claude/**·meta/**)**: `bin/gen-status.sh` 신설(unit/*/docs/TASK.md frontmatter `feature_status`/`feature_status_date`/`feature_status_note` 수집 → STATUS.md `AI-EDITABLE:STATUS-TABLE` 마커 구간 표 재생성 · frontmatter 없는 feature 행 passthrough · `--check` 모드 · idempotent) + `docs/STATUS.md` 마커 구간 도입(구간 안 "수기 편집 금지" 주석 포함 — AGENTS.md 무편집, 직렬 체인 밖 유지) + `.claude/commands/_dqa/doc_sync.md` Phase 3 인덱스 모델에 autogen 경로 통합(frontmatter 갱신→gen-status 실행, 직접 행 편집 금지, 커밋 전 --check) + ROADMAP ITEM-08 done·ITEM-05 배포 검증 note + 본 entry.
- **명세 편차 1건 투명 기록**: ROADMAP what-1 은 frontmatter 키를 `status:`·`phase:` 로 예시했으나 기존 TASK.md frontmatter 의 `status:` 가 **문서 lifecycle**(active 등, 전 unit 공통) 로 이미 점유돼 있어 그대로 쓰면 의미 충돌 — `feature_status*` prefix 키로 구체화(명세 취지 동일·충돌 회피, "없으면 추가 규약" 조항 범위 내 보수적 해석).
- **acceptance 검증**: (a) 재현 브랜치(tmp-item08-proof)에서 feature-0004 TASK.md 에 임시 frontmatter → gen-status 가 해당 행 재생성(frontmatter 1·passthrough 17) 확인 후 브랜치 폐기·행 원복 (b) 마커 구간 밖 STATUS.md 본문 diff 0(전체 diff = 마커/주석 4줄 삽입뿐) (c) frontmatter 없는 feature 18행 passthrough 유지 (d) 연속 2회 실행 idempotent(diff 0, "변경 없음" 판정). guards 준수 — feature TASK.md frontmatter 실적용은 각 feature 다음 정규 사이클에 위임(이 cycle 은 메커니즘만).
- **Human Approval Needed**: 아니오 — Minor·doc/도구만·배포 무관. §6.1.
## REV-20260711T042631-META-0024-merge-hygiene [SUBAGENT:improve-fit-reviewer(2-round §18.8)] — rerere + append-only merge driver 브리지 (parallel-work-structure ITEM-03)

- **cycle**: ai/claude-corp/META-0024-merge-hygiene — 드레인 6번째 항목(ITEM-03, Major). 승인: ROADMAP §6.1 + §0 공통 규약(§13.1 개정 = 1급 선행 스텝, ADR-20260711T042631-append-doc-merge-driver 동봉).
- **changeset (pure-meta)**: `AGENTS.md` §13.1 개정(driver 허용 범위 확대 — 조건부: 3종 한정·말미-append 만 병존·그 외 merge-file 위임·union 금지 유지·rerere 한계 명기) · `docs/DECISIONS.md`(ADR) · `bin/setup-git-parallel.sh`(신설 — rerere 계정별 전역+driver clone-로컬 등록, 멱등·카운트 요약) · `bin/merge-append-doc.sh`(신설) · `.gitattributes`(신설 3종: unit MODIFY/REVIEW·RELEASE_NOTES — LEARNINGS 는 섹션-내부 삽입 구조라 제외) · `bin/verify-completion.sh`(is_meta_path .gitattributes + check #14 conflict-marker 전 모드 무조건) · ROADMAP ITEM-03 done · 본 entry.
- **§18.8 적대 패널 (SUBAGENT improve-fit-reviewer, 2-round — 게이트 스크립트 변경 guards 의무)**: 1차 **NOT-SHIP** — BLOCKING 2(B-1 폴백 exit 1 이 marker 없는 UU 로 theirs 은닉+clean-merge 케이스 개악 → `git merge-file` 위임으로 재작성 / B-2 무개행 블록 헤더 접합 corruption → 종단 개행 정규화), MAJOR 3(M-1 check #14 post-commit 이 merge-commit combined diff 에 블라인드 → 1st-parent diff / M-2 ADR unstaged / M-3 LEARNINGS 는 driver 성립 불가 → 대상 제외), MINOR 4(timestamp 정렬 폐기→연접·dedup, 오탐 회피 안내, setup 인자검증+카운트, §13.1 rerere 한계 이관) 전건 반영. 2차 **SHIP-WITH-FIXES** — 5개 fix 전건 독립 재현 FIXED 판정, 잔존 MINOR-1(§13.1 ② stale 문장)+NIT(4종→3종 3곳) 동일 커밋 반영 완료.
- **acceptance**: (a) 두 브랜치 MODIFY.md 말미 각자 CHG 블록 append → merge 무충돌 병존(2/2 블록 보존) (b) 본문 중간 동일라인 충돌 → 표준 marker 충돌(비겹침 mid+append 는 clean — default 동등 실증) (c) rerere 동일 충돌 재발 자동 해소("Staged ... using previous resolution" 실증; **한계 실측**: 구 exit-1 driver 경로 충돌엔 rr-cache 미기록 — merge-file 위임 후엔 기록됨을 패널이 재실측, ADR 에 보수 서술로 기록).
- **template base 전파(inbox) 계획**(§0 규약 ii): §13.1 driver 확대 개정 + check #14 + setup/driver 스크립트 3종을 template 후속 버전 반영 후보로 inbox 제출 예정(소비자 선행 실증).
- **Human Approval Needed**: 아니오 — §6.1(명세 내). driver 는 3종 문서 한정·오병합 금지 원칙 하 merge-file 동등 폴백. 배포 무관.
## REV-20260711T051500-META-0026-doc-fragments [SUBAGENT:improve-fit-reviewer(§18.8)] — TEST Run 기록 fragment 전환 1차 (parallel-work-structure ITEM-06)

- **cycle**: ai/claude-corp/META-0026-doc-fragments — 드레인 7번째 항목(ITEM-06, Major). 승인: ROADMAP §6.1.
- **changeset (pure-meta)**: `AGENTS.md` §5.3(Run 기록 fragment 규약 — `unit/<feature>/docs/test-runs.d/<TASK-또는-REV-id>.md`, frontmatter run_at(ISO8601)·session·scope·verdict, 기존 TEST.md §3 append 하위호환·소급 이동 없음) + §15.4.1/라우팅표/산출물표/DoD 체크리스트 stale 참조 6곳 정합 · `bin/verify-completion.sh` check #13(TEST.md 추가 라인 **또는** test-runs.d/ staged 추가 라인 인정 — OR 하위호환, FAIL 메시지 fragment 안내) · `.claude/commands/_dqa/doc_sync.md`(90일 컴팩션 절 — §5.5 아카이브·TEST.md 상단 참조 링크·불가침 경계) · ROADMAP ITEM-06 done · 본 entry. **changeset 분리 guard 준수** — 실제 feature 의 fragment 파일럿 적용은 각 feature 다음 정규 사이클(£0 규약).
- **§18.8 패널 (게이트 스크립트 변경 guards 의무)**: VERDICT **SHIP-WITH-FIXES** — ① OR 경로 우회면 없음(껍데기 fragment 는 기존 TEST.md 라인과 동일 honor 모델 — 등가, 약화 아님; 음성 케이스 FAIL 보존 재현) ② 경로 조작·교차-feature vouch 재유입 없음(tmd 파생 frag_dir = 자산 경로 기반 fid 귀속 유지, pathspec 컴포넌트 매칭) ③ 명세 정합(what-2 "신규 파일" vs 구현 "디렉토리 추가 라인" 편차는 실질 등가 — NIT 기록) ④ §5.5 timestamp 명명 정합. 잔존 MINOR-1(stale 참조 6곳)+NIT 3 전부 동일 커밋 반영.
- **acceptance**: (a) 재현 브랜치 — web asset+fragment 만 stage → check #13 PASS 후 폐기 (b) 기존 TEST.md-추가 방식 PASS(하위호환) + 음성 대조(둘 다 없음 → FAIL — 게이트 보존) (c) 병렬 두 브랜치 각자 fragment → merge 무충돌 (d) AGENTS.md·doc_sync 규약 diff.
- **template base 전파(inbox) 계획**(§0 규약 ii): §5.3 fragment 규약 + check #13 OR 개정을 template 후속 반영 후보로 inbox 제출 예정.
- **Human Approval Needed**: 아니오 — §6.1(명세 내). 하위호환 OR(일괄 강제 없음)·배포 무관.
## REV-20260711T053001-META-0027-merge-serialization [SUBAGENT:improve-fit-reviewer(§18.8)] — host-local merge mutex + 신선도 hard gate (parallel-work-structure ITEM-07)

- **cycle**: ai/claude-corp/META-0027-merge-serialization — 드레인 8번째 항목(ITEM-07, Major). 승인: ROADMAP §6.1 + §0 공통 규약(AGENTS.md §13.2.5 개정 — ADR-20260711T053001 동봉).
- **changeset (pure-meta)**: `bin/cycle-finalize.sh`(Step 0b flock mutex .git/.merge.lock 900s·EXIT trap 락 확정 해제·신선도 게이트 behind≥20 → gh_update_branch(gh 2.57+/gh api PUT 폴백)·CLEAN 재폴링 600s(MERGED 외부 머지 합류·HAS_HOOKS 진행·BLOCKED/DIRTY 자동 중단·VIEWFAIL 구분)·merge 직전 MERGED 재확인·Step 2 후 락 해제 — 머지 구간만 직렬화) · `bin/verify-completion.sh`(behind≥10 비차단 WARN) · `AGENTS.md` §13.2.5("사용자 수동 직렬화" → mutex+게이트 대체) · `docs/DECISIONS.md`(ADR-20260711T053001 + ITEM-06 §0 기록 사후완결 ADR-20260711T053000) · ROADMAP ITEM-07 done · 본 entry.
- **§18.8 패널 (2-round)**: 1차 VERDICT SHIP-WITH-FIXES — **MAJOR-1: 인용 ADR 2건·REV 부재**(본 세션이 ADR 을 임시 probe worktree 에 잘못 기록 → 정리 때 소실 — 정본 위치 재기입으로 해소. ITEM-03 M-2→06→07 **같은 클래스 3연속 재발**: "커밋 전 인용 무결성 체크" 를 아래 재발 방지에 기록) + MINOR 3(EXIT trap — detached auto-gc fd 상속 대비 / 폴링 중 외부 머지 MERGED 합류 / behind 계산 실패 fail-open 명시 WARN) + NIT(HAS_HOOKS 진행 취급·VIEWFAIL 구분·draft 안내) 전건 반영.
- **재발 방지(패널 권고 수용)**: 커밋 전 "ROADMAP note·REVIEW 가 인용하는 ADR/REV id 가 staged diff 에 실재하는지 grep 확인"을 사이클 마감 체크로 수행한다(이번 cycle 부터 적용 — 아래 검증에 포함).
- **acceptance**: (a) 락 홀더 존재 시 두 번째 finalize 대기 후 진행(flock 8s 홀드 재현) (b) **라이브**: probe PR #684(main~25 분기, behind=48)에서 게이트 발동 — 구버전 gh `update-branch` unknown-command **실결함 적발** → gh api PUT 폴백 구현 → probe2 PR #685 로 tip 갱신·behind→0 실증(머지 없이 close·브랜치/worktree 정리) — #684 는 CLEAN 폴링 경유 머지(probe 파일 = 증거 artifact 로 main 잔존) (c) MERGE_LOCK_TIMEOUT_SEC=3 명시 die (d) dry-run 게이트 print 우회 — 기존 흐름 보존.
- **인용 무결성 확인**: ADR-20260711T053000/053001 · REV-20260711T053001(본 entry) 전부 staged 실재 grep 확인.
- **Human Approval Needed**: 아니오 — §6.1(명세 내). 머지 안전장치 추가(비파괴·fail-safe 방향). 배포 무관.
## REV-20260711T051835-META-0029-wip-hotspot-policy [SUBAGENT:improve-fit-reviewer(§18.8)] — 핫스팟 WIP 상한 + 순차 머지 규약 + REGISTRY 부트스트랩 (parallel-work-structure ITEM-12)

- **cycle**: ai/claude-corp/META-0029-wip-hotspot-policy — 드레인 9번째 항목(ITEM-12, Major, AGENTS.md 직렬 체인 01→03→06→07→12 말단). 승인: ROADMAP §6.1 + §0 공통 규약(ADR-20260711T051835 동봉).
- **changeset (pure-meta)**: `AGENTS.md` §13.2.5-A 신설((a)동일 핫스팟 in-flight ≤2 권고 (b)REGISTRY hot_paths 필드 (c)순차 머지 원칙 — merge_order 사전 선언 (d)당일 랜딩 원칙) + §13.2.3-A 에 META-0025 구현 존재 표기 편승 · `bin/cycle-init.sh`(--hot-paths 인자 + REGISTRY 부트스트랩/entry 자동 기록(자기 블록만)/겹침≥2 soft 경고 — 실패는 경고만·cycle 비차단) · `docs/DECISIONS.md`(ADR) · ROADMAP ITEM-12 done · 본 entry. REGISTRY 자체는 repo 밖 운영 파일(§13.2.8 정본 경로) — 라이브 부트스트랩 완료.
- **acceptance**: (a) AGENTS.md 조항 diff (b) 겹침 시나리오(활성 sim entry + 겹치는 hot-paths 로 실제 cycle-init 실행) — 경고 발화 + rc=0 정상 진행 + entry 기록, 초판(07-11 05시)과 패널 반영 강화판(07-11 오전, distinct 지표 — "활성 브랜치 2개·나 포함 3개" 경고) 2회 실증, 시뮬 잔재 전부 정리 (c) REGISTRY 신설 + cycle-init 실행으로 hot_paths 포함 entry 기록(본 cycle 자기 entry 가 라이브 증거) (d) §13.2.8 과 모순 없음 — session_id 필드 스키마 additive(fallback `claude-session-<PID>` 로 §13.2.8 standalone 형식 준수).
- **§18.8 적대 패널 (SUBAGENT: improve-fit-reviewer, 2026-07-11)**: **1차 VERDICT = SHIP-WITH-FIXES**(BLOCKING 0 · MAJOR 4 · MINOR 5 · NIT 4 — sandbox 라이브 재현 포함). **머지 전 전건 반영 + 재검증**:
  - **MAJOR-1**(`{...} || log_warn` dead code — 실패 시 거짓 성공 로그, 라이브 재현) → `registry_record()` 함수화 + 전 단계 명시 `|| return 1` + rc 캡처 if/else. 재검증: root-소유 lock 으로 실패 유도 → 정직한 WARN + rc=0 + REGISTRY 무손상 + worktree 정상 생성.
  - **MAJOR-2**(제거→삽입 비원자 — 중간 실패 시 기존 entry 무경고 소실, 라이브 재현) → 제거+삽입 **단일 awk 패스** + 동일 디렉터리 mktemp + 삽입 grep 검증 후에만 mv.
  - **MAJOR-3**(finalize Step 6 "자동 이동 안 함" + 구스키마 안내 — 닫는 쪽 없는 라이프사이클) → finalize 에 **META-0029 스키마 자동 이동 구현**(Active→Closed + closed_at/PR, 동일 lock·mktemp→검증→mv, 실패 시 경고+수동 안내 폴백; 비-META-0029 형식은 기존 수동 안내 유지). 재검증: sandbox 사본 이동 실증. 본 cycle 의 finalize 실행이 첫 라이브 검증.
  - **MAJOR-4**(무잠금 RMW + 고정 .tmp — 병렬 lost-update) → `flock -w 10`(REGISTRY.lock, init/finalize 공유) + mktemp 고유명.
  - **MINOR 5~9 + NIT**: 겹침 지표를 경로쌍→**브랜치 distinct** 로 재설계(정책 준수 오탐 제거) · --help sed 범위 정정 · session_id fallback `claude-session-$PPID` · 자기 블록 제거 Active 한정(Closed 이력 보존) · N-12 .gitignore 조건부 등록 구현(본 배치 wrapper 는 git 밖 — 비적용 확인) · `<미선언>` placeholder 비교 제외.
  - 패널 적발 실패(통과) 항목: 타 세션 블록 오삭제 · prefix 오탐 · 재실행 중복 · 비차단 보장 · --hot-paths 미지정 회귀.
  - 잔여(후속, 비차단): 기존 활성 worktree entry backfill 전 게이트 사각(다음 cycle-init 부터 자연 편입) · dry-run 겹침 검사 미실행 · opened_at staleness 표기(finalize 자동 이동이 근본 원인 제거해 우선순위 하락).
- **guards 준수**: hard 차단 금지(전부 경고·가시화 — 실패 유도 테스트로 비차단 재확인) · REGISTRY entry 세션당 자기 블록만(타 블록 보존 패널 확인) · cycle-init 변경분 §18.8 패널 검증 완료(위).
- **인용 무결성 확인**: ADR-20260711T051835·REV-20260711T051835 staged 실재 grep(재발 방지 체크 — ITEM-07 M-1 계보).
- **Human Approval Needed**: 아니오 — §6.1(명세 내). soft 게이트만(비차단)·배포 무관.

## REV-20260711T142055-META-0030-drain-continuity [SUBAGENT:improve-fit-reviewer(§18.8, 4-round)] — 연속 드레인 "한 cycle 후 자발 중단" 해소 (parallel-work-structure 툴링)

- **cycle**: ai/claude-corp/parallel-drain-continuity-fix. **승인 근거: 사용자 명시 지시(2026-07-11)** — "실제 작업자 드레인의 메커니즘 개선이 필요하다". (12 ITEM 명세 밖 신규 툴링 수정이라 §6.1 표준범위가 아니라 직접 지시로 인가.)
- **근본원인**: 실 작업자 세션(`/_dqa:improve_cycle` 드레인, aiTitle "…병렬 작업 구조 개선")이 usage-limit 이 아니라 "이번 버스트 정리 → 다음 체인(+5h10m 크론)이 이어감"으로 **토큰 남은 채 자발 중단** → 12:14~14:27 유휴 관측. 원인 3중: (a) `drain-continue-cron.sh` 가 버스트 종료 사유 불문 **무조건 +5h10m 재발사** (자연/자발 종료도 5시간 잠), (b) `claude --continue`(cwd 최신 대화)라 무관 세션 **하이재킹**, (c) 컨텍스트 소진 핸드오프 부재. (Codex 는 실작업자 아님 — 사용자 확인.)
- **changeset (pure-meta)**: `bin/drain-continue-cron.sh`(재설계) · `docs/improvements/parallel-work-structure/ROADMAP.md`(§6.4 fire 개정 + §6.5 하드-스톱 연속성 규약 신설) · 본 entry. §5(워커 소유) 미접촉.
- **핵심 변경**:
  1. **always-fresh**: 세션 pin·`--continue`·`--resume`·`__FRESH__` 전부 폐기 → 매 fire `claude -p "<재앵커>"` 새 세션, §5+worktree(미커밋 diff 포함)에서 복원. 하이재킹·orphan·컨텍스트 누적사 원천 제거.
  2. **종료사유별 재발사**: usage-limit → `+5h10m`(TTL−1); **진전 → `+2m` 신속 재개**(구버전 무조건 +5h10m 유휴 해소); 무진전 `MAX_NOPROG`(6) 연속 → `+5h10m` 백오프. `*/5`+flock 이 폭주 자연 상한.
  3. **진전 판정 = 서명 커밋 창**: `git rev-list --branches --count --since=@start --grep=parallel-work-structure` — `--since` 로 pull 유입 과거커밋 제외 + `--grep` 로 동시 sibling worktree/cron 커밋(서명 없음) 제외 → 이 드레인이 만든 커밋만 계수.
  4. **usage-limit = 비-서술 3조건 AND**: 진전0 ∧ dur<90s ∧ 종단(최근 3 비공백줄) 한도문구. free-text 서술 오탐(→5h 유휴)을 차단. 한도 CLI 원문은 문서/스크립트에서 제거.
  5. **§6.5 연속성 규약**: 하드-스톱 4조건(usage-limit·context 소진·전-ready blocked·완주) 외 **자발 종료 금지** 명문화 — "다음 체인이 이어감" 선제 인계 서술을 실패모드로 규정.
- **§18.8 적대 패널 (SUBAGENT: improve-fit-reviewer, 4 라운드 — 각 라운드 findng 을 다음 라운드에서 반영)**:
  - **R1 = BLOCK**: B1(종료판정 grep 이 버스트 출력을 훑는데 문서가 트리거문자열 인용 → 오분류로 유휴 재발), B2/B3(세션 하이재킹·`__FRESH__` orphan 무한양산), M4(스핀가드 기간의존), M5(TTL).
  - **R2 = SHIP-WITH-FIXES**: B2/B3 해소(always-fresh) 확인. **N1**(진전=전역 커밋수 델타가 `git fetch`/외부 커밋을 진전 오인 → 스핀가드 무력) must-fix.
  - **R3 = SHIP-WITH-FIXES**: N2(usage-limit tail-3 미탐) 해소. **N1**(`--branches` 가 동시 sibling 커밋 계수)·**N3**(whole-log 2-grep 이 드레인의 한도/리셋 서술에 오탐 — N2 fix 로 악화) still-open.
  - **R4 = SHIP-WITH-FIXES**: 실 repo 검증(275커밋/7d 중 서명 21개만 계수, sibling 254 배제) — **N1·N3 CLOSED, 새 BLOCKER/MAJOR 없음**. 잔여 MINOR 2 + 권장 하드닝(N3 last-3 적용함).
- **accepted trade-off / 잔여 (패널 수용)**:
  - **N4(always-fresh 비용)**: 매 fire cold-start 재오리엔테이션 비용 + 미커밋 작업 세션간 비가시 — 하이재킹/컨텍스트死 제거를 위한 불가피 비용. 재앵커 프롬프트가 "미커밋 diff" 명시 확인 → 디스크상 미완작업은 다음 fresh 세션이 인지. §6.2 잦은커밋이 완화. **수용**.
  - **N1 잔여(MINOR, LOW)**: 서명 없는 순수-머지 버스트만 있는 경우 미탐 가능 — 단 6연속 필요하고 ITEM 커밋은 규약상 서명(관측 c2e6d995) → 실질 무위험. 향후 하드닝: 드레인 own-worktree HEAD 전진도 진전신호로. **문서화·수용**.
  - **오탐<미탐 설계선택**: usage-limit·진전 판정 모두 **미탐 편향**(미탐→무진전 백오프 +5h10m 로 수렴, 저위험 / 오탐→5h 유휴=원래 버그, 고위험). 의도적.
- **검증**: `bash -n` OK. git-backed stub dry-run 전수 PASS — 실 usage-limit(+310m/TTL−1)·N1 sibling 배제(newcommits=0)·N3 서술오탐0(진전/긴dur/종단요약)·last-3 epilogue 미탐 해소·무진전 백오프·always-fresh `-p`·continue-fallback. 라이브 깨진 구형 체인(claude-corp) **disarm 완료**, root 체인 미-arm(state 부재) 확인.
- **인용 무결성 확인**: REV-20260711T142055(본 entry) staged 실재.
- **Human Approval Needed**: 아니오(착수는 사용자 직접 지시). auto-exec 인프라 변경이나 **비파괴·fail-safe 방향**(오탐<미탐·스핀 백오프·TTL 백스톱·flock·*/5 상한). 배포 무관(호스트 크론 툴링). **PR 생성만 confirm 유지**.

## REV-20260711T150440-META-0031-drain-resume-continuity [SUBAGENT:improve-fit-reviewer(§18.8, 3-round: R4→R6)] — 드레인 재개를 always-fresh → **세션 재개 연속성** 으로 정정 (META-0030 supersede)

- **cycle**: ai/claude-corp/drain-resume-continuity. **승인 근거: 사용자 명시 지시(2026-07-11)** — "always-fresh(META-0030)는 매 fire 신규 세션이라 사용량 만료마다 직전 세션 컨텍스트/미완작업이 누락된다. 현 개발환경(Claude Code for VSCode)의 그 세션을 컨텍스트 보존한 채 재개하라(크론이 같은 세션 자동 재개)."
- **배경(오정합 정정)**: META-0030(e82c3118)은 §18.8 패널의 "세션 하이재킹" 지적에 always-fresh 로 **과교정**하며 사용자가 요구한 **연속성**을 버렸다 — 사용자 지적으로 발견. 본 cycle 이 이를 supersede.
- **changeset (pure-meta)**: `bin/drain-continue-cron.sh`(재설계 v3.1) · `docs/improvements/parallel-work-structure/ROADMAP.md`(§6.4 fire 재작성 + §6.5#2 정합) · 본 entry. §5(워커 소유) 미접촉.
- **핵심 변경 (always-fresh → 재개 연속성)**:
  1. **pin 된 워커 세션 `--resume` 재개**(연속성) — 사용량 만료해도 같은 세션이 컨텍스트 보존한 채 이어감. `RESUME_PROMPT` 로 §6.5 상기 + 맥락 옅으면 §5 복원 폴백.
  2. **하이재킹(B2) 결정론 회피**: arm 은 **자동탐지 금지**(명시 `--session-id`/기존 pin 보존만). 새 세션은 **미리 만든 UUID 로 `claude --session-id <uuid>`** 시작 → 그 uuid 그대로 재-pin(mtime "최신 jsonl" 추측 폐기 — 공유 slug 무관 세션 오-pin 방지).
  3. **컨텍스트死(B3) 처리**: 비-서술 3조건(진전0 ∧ dur<90 ∧ 종단3줄 "Prompt is too long") 감지 시에만 pin 해제 → 새 세션 재부트스트랩(무한 orphan 방지).
  4. **v2.2 유지**: 종료사유별 재발사(진전→+2m·usage-limit→+5h10m/pin 유지·무진전→백오프) · 진전=서명 커밋 창(`--since=@start --grep=parallel-work-structure`, N1) · 판정=비-서술 3조건(N3).
  5. **2단계 백오프(MINOR-1)**: 무진전 백오프가 "죽음"과 "놓친 usage-limit"을 구분 못 하므로, resume 세션의 1차 백오프는 **pin 유지**(+5h10m 리셋 대기 — 건강한 세션 성급히 안 버림), 리셋 후에도 무진전(streak≥2)이거나 fresh 실패면 그때 pin 해제. 사용자 핵심의도(컨텍스트 보존) 보호.
- **§18.8 적대 패널 (SUBAGENT: improve-fit-reviewer)** — META-0030 의 R1~R4 에 이어 본 정정의 R5·R6:
  - **R5 = BLOCK**: 세션 재개 복원 후 (a) 재-pin `newest_session_since`(mtime 최신 jsonl)가 공유 slug 의 orchestrator/사용자 세션을 오-pin → 하이재킹 **라이브 재현**, (b) context-death 미탐 시 죽은 세션 영원히 `--resume` 하는 영구 스톨.
  - **R6 = SHIP-WITH-FIXES**: 두 must-fix **CLOSED** 검증(newest_session_since 삭제·`--session-id` UUID 결정론 재-pin / NOPROG 백오프 pin 해제), 새 BLOCKER/MAJOR 0. 잔여 MINOR 2(놓친-usage-limit 시 pin 상실 → **2단계 백오프로 해소**; 미탐-context-death 회복 ~5h → 드묾·bounded 수용).
- **linchpin 스모크 (라이브)**: `claude 2.1.204 --session-id <새 uuid> -p` 가 정확히 `<uuid>.jsonl` 생성 실측(13466 bytes) → 다음 fire `[ -f <uuid>.jsonl ]` 매치 → `--resume` 연속성 성립 확인.
- **동시접근(수용된 trade-off)**: pin 된 세션이 VSCode 에 열린 채 cron 이 headless `--resume` 하면 한 대화 두 클라이언트. flock 은 cron 측만. §6.4 에 경고 명시, 사용자 승인(2026-07-11 "크론이 같은 세션 자동 재개").
- **검증**: `bash -n` OK. git-backed stub dry-run 전수 PASS — #B2(더 최신 DECOY 존재해도 pin==`--session-id` UUID)·usage-limit(pin 유지 +310m/TTL−1)·context-death(pin 해제)·2단계 백오프(1차 pin 유지·2차 해제)·resume/fresh 모드·pin jsonl 부재→fresh 폴백. newest_session_since 코드참조 0.
- **인용 무결성 확인**: REV-20260711T150440(본 entry) staged 실재.
- **Human Approval Needed**: 아니오(착수는 사용자 직접 지시·의도 정정). 비파괴·fail-safe(오탐<미탐, 2단계 백오프로 컨텍스트 보존 우선, TTL·flock·*/5 상한). 배포 무관(호스트 크론). **PR 생성만 confirm 유지**.

## REV-20260711T195353-META-0032-drain-reset-schedule [SUBAGENT:improve-fit-reviewer(§18.8, R7)] — usage-limit 재개를 고정 +5h10m → CLI 실제 리셋 시각 파싱으로 (parallel-work-structure 툴링)

- **cycle**: ai/claude-corp/drain-reset-schedule. **승인 근거: 사용자 명시 지시(2026-07-11)** — "토큰 갱신(19:20) 지났는데 continue fire 미작동, 수정".
- **라이브 버그(관측)**: 드레인이 15:15~16:25 정상 연속 작동(57d96d41 재개·ITEM-10 PR #702~707 머지) 후 **16:25:04 usage-limit**. mechanism 이 고정 +310m → `next_fire=21:35` 예약. 그러나 CLI 메시지 `resets 7:20pm (Asia/Seoul)` = 실제 리셋 **19:20** → 재개가 **~2h15m 늦음**. 원인: +310m 은 *한도-hit 시각(16:25)* 기준인데 5h 롤링 윈도우 리셋은 *윈도우 시작(~14:20)* 기준. 공유 quota 를 다른 VSCode 세션(당시 5개)이 함께 소비해 한도를 윈도우 초반에 맞으면 오차 큼.
- **changeset (pure-meta)**: `bin/drain-continue-cron.sh`(`parse_reset_epoch` 헬퍼 + `RESET_BUFFER_SEC` + usage_limit 분기) · `docs/improvements/parallel-work-structure/ROADMAP.md`(§6.4 usage-limit bullet) · 본 entry. §5(워커 소유) 미접촉.
- **수정**: usage-limit 확정(비-서술 3조건 — 오탐 게이트 불변) 후 CLI 메시지의 `resets <시각>` 파싱(`parse_reset_epoch`: `grep -oiE` + `date -d`, 자정넘김 +86400, `now+6h` 초과=파싱오류 폴백) → `next_fire = 리셋 시각 + RESET_BUFFER_SEC(300s)`. **파싱 실패/이상 시 기존 +310m 폴백**(byte-동치, 회귀 0). pin 유지·TTL−1·NOPROG/STREAK 리셋은 if/else 앞으로 hoist(불변).
- **linchpin(라이브)**: `date -d` 가 `7:20pm/9:20am/12:05am/12:30am/12:00pm/12:00am` + 대문자/공백 변형 파싱 확인.
- **§18.8 패널(R7) = SHIP**: 추가 로직 정확·게이트됨·회귀 없음. 엣지 전수 검증 — (a)TZ: host=메시지 TZ(KST) 일치·이상 시 6h 가드→폴백 (b)자정경계 +86400 정상 (c)usage_limit 오탐 결합 표면 없음(스케줄만 변경) (d)버퍼-조기 재-한도는 과거-리셋→6h초과→+310m 폴백으로 자기수렴(스핀 없음) (e)date -d 변형 전부 파싱. 잔여 MINOR 2(24h/hour-only format·TZ 토큰 미파싱)은 **둘 다 안전한 +310m 폴백으로 degrade** — 비차단, 후속 하드닝 옵션.
- **검증**: `bash -n` OK. dry-run — 미래리셋 "9:19pm"→next=21:24(리셋+300s, +310m 아님)·시각없음→+310m 폴백·과거→다음날→6h초과→폴백. **즉시 remediation**: 19:20 이미 지나 `arm --minutes 0` 재-arm → 19:50 `--resume 57d96d41` 재개 실측(드레인 라이브 복귀).
- **인용 무결성 확인**: REV-20260711T195353(본 entry) staged 실재.
- **Human Approval Needed**: 아니오(사용자 지시). 비파괴·fail-safe(파싱 실패 시 기존 +310m 폴백, 6h 가드). 배포 무관(호스트 크론 툴링). **PR 생성만 confirm 유지**.

## REV-20260712T012055-META-0033-drain-model-fallback [SUBAGENT:improve-fit-reviewer(§18.8, R8~R10)] — 모델별 한도 자동 opus 전환 + 무한핑퐁 flap 가드 (parallel-work-structure 툴링)

- **cycle**: ai/claude-corp/drain-model-fallback. **승인 근거: 사용자 명시 지시(2026-07-12)** — "세션이 쓰던 모델(Fable)의 한도가 소진됨, 다른 모델(Opus)로 전환하여 재개하도록 구성해달라".
- **라이브 버그(관측)**: 21:35 usage-limit → 00:40 정확히 리셋(META-0032 실증) 후 00:45~00:55 **매 fire 즉시 실패**(dur 2~78s, newcommits=0) — 로그 원문 `"You've reached your Fable 5 limit. /model to switch models."`. 계정 5h usage-limit 과 다른 **모델별** 한도라 기존 `usage_limit` 정규식에 안 잡히고 일반 무진전(noprog 3/6)으로 오분류.
- **즉시 remediation**: 크론 disarm(동시접근 방지) 후 `claude --resume 57d96d41 --model opus -p continue` 수동 실행 → **라이브 진전 실증**(main 이 PR #719 ITEM-10-p17, 이어서 `docs(item10): ITEM-10 라우터 모듈화 완료 판정` 커밋까지 진행, jsonl 지속 갱신).
- **changeset (pure-meta)**: `bin/drain-continue-cron.sh`(모델 감지·전환·flap 가드) · `docs/improvements/parallel-work-structure/ROADMAP.md`(§6.4 신규 bullet 2개) · 본 entry.
- **핵심 변경**:
  1. **`DRAIN_MODEL` state + `arm --model <alias>`**: 미지정시 기존값 보존(세션 pin 과 동일 패턴). fire 양쪽 경로(resume/fresh)에 `model_opts=(--model "$DRAIN_MODEL")` 조건부 배열 주입.
  2. **모델별 한도 감지**(`model_limit`, 비-서술 3조건 동일): `reached your .+ limit` AND `/model` → 현재 모델이 opus 아니면 **자동 opus 전환**+`+2m` 신속재시도(무진전/백오프 미카운트). 이미 opus 면 대안 없어 pin유지+고정`+5h10m`.
  3. **모델 접근불가 자동복귀**(`model_invalid`): `"may not exist or you may not have access to it"` 감지 → **즉시 계정 기본값(빈값)으로 복귀**+`+2m` 재시도. (미대응 시 깨진 모델값이 영구 고정돼 TTL 소진까지 무증상 정지 — §18.8 최초 MAJOR.)
  4. **`MODEL_FLAP` 핑퐁 가드**(§18.8 재검토 MAJOR): `model_limit`↔`model_invalid` 두 신속-재시도 경로가 서로 TTL/NOPROG 어느 것도 안 건드려 오갈 수 있음(opus 진짜 미보유 + 기본모델 한도 지속 시) — 3회 연속 시 **그 즉시 백오프로 전환**(TTL−1, model="", `+5h10m`, flap 리셋). progressed/usage_limit/context_dead/opus-already-limited 는 모두 flap 을 0 으로 리셋(정당한 반복은 핑퐁으로 오인 안 됨).
- **§18.8 적대 패널 (SUBAGENT: improve-fit-reviewer, 3라운드 — R8~R10, 앞선 세션의 R1~R7 에 이어)**:
  - **R8 = SHIP-WITH-FIXES**: 모델 감지·전환 로직 정확(정규식 교차오염 없음, `--model` 실제 전달 linchpin 확인, bash 5.2.21 `set -u` 빈배열 안전). **새 MAJOR**: opus 가 계정에 없으면(`"...may not exist or you may not have access to it"`) 감지 못 해 `DRAIN_MODEL="opus"` 가 영구 고정 → 매 fire 즉시실패가 일반 무진전으로 위장 → **TTL 소진까지(~8.6일) 무증상 정지** — 패널이 라이브 CLI 로 직접 재현.
  - **R9 = SHIP-WITH-FIXES**: `model_invalid` 자동복귀로 R8 MAJOR 닫힘 확인. **새 MAJOR**: 두 신속-재시도 분기(model_limit 자동전환 / model_invalid 복귀)가 서로 TTL/NOPROG 을 안 건드려 **무한 핑퐁**(opus 진짜 미보유+기본모델 한도 지속 시) — 상태기계 시뮬레이션으로 확인, "status 가 noprog=0 으로 영구 건강하게 보이며 2분마다 헤드리스 프로세스만 재기동" 지적.
  - **R10 = SHIP**: `MODEL_FLAP` 가드로 R9 MAJOR 닫힘 확인 — 3회마다 정확히 TTL−1 소모(시뮬 40 fire 전수 추적), 정상적 반복 한도(둘 다 유효 모델)는 flap 이 구조적으로 못 쌓임을 코드 경로 전수로 증명. MINOR 1(로그 문구 "비활성화"가 일회성 리셋인데 영구처럼 읽힘) → **반영**("이번 백오프 동안 중지…재발 시 재시도"로 정정).
- **검증**: `bash -n` OK. dry-run 전수 — model_limit→opus전환(+2m,flap1) · `--model opus` 실제 전달(echo-args linchpin) · opus도한도→pin유지+310m/TTL-1 · 진전경로 회귀없음(model값 유지) · usage-limit/context-death 오검출 없음 · model_invalid 즉시복귀 · 6회 교대 핑퐁 시뮬(TTL 40→39→38 유계) · 로그문구 정정판 재확인(1초 간격 격리 재현). **라이브**: 수동 opus 재개가 ITEM-10 완료 판정까지 실제 진전 실증(main 커밋 다수).
- **인용 무결성 확인**: REV-20260712T012055(본 entry) staged 실재.
- **Human Approval Needed**: 아니오(사용자 지시). 비파괴·fail-safe(모든 신규 경로가 TTL/NOPROG/MODEL_FLAP 중 하나로 유계 — 3라운드 패널이 반복 검증). 배포 무관(호스트 크론 툴링). **PR 생성만 confirm 유지**.


## REV-20260713T102249-META-0034-doc-sync-0713 [SKIPPED:doc-sync-index-mirror-additive] — 07-09~13 창 인덱스/미러/사용자향 표면 정합 (§57.4~76 그래프 성능·UX·§69 caveats·타임아웃 모달·MSSQL 쿨다운·feature-0012 완결)
- **cycle**: ai/claude/doc-sync-20260713 — `/_dqa:doc_sync`(수동·attended). 직전 doc_sync(META-0022 @ 07-08 a9d02e68) 이후 07-09~13 델타 정합. **직전 07-10 스케줄 doc_sync(doc-sync-20260710-230501, META-0023)가 로컬 commit 만 하고 wrapper 가 landing 실패(133 커밋 stale)** → 콘텐츠 harvest 후 supersede·origin/main(c02d81e0) 기준 fresh 재구성. landing/배포 소유=본 attended run.
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(인덱스 4행 — feature-0002/0003/0016-metadata-graph date 07-10 + feature-0012 review/07-12 완결·dated 요지 append·rollup 0·전 18행 passthrough·gen-status --check PASS)·`docs/RELEASE_NOTES.md`(07-09 추론예산 + 07-10 그래프/모달/§69/MSSQL 기술 블록 append)·`docs/ARCHITECTURE.md`(feature-0012 기능맵 완결 갱신 — 색인 mirror, 구조 결정 0)·wiki(`Log.md`·`hot.md` Key Facts 5+Recent Changes·`Features/feature-0016-metadata-graph` §7 변경이력·`Features/feature-0012-web-router-modularization` 상태/Open questions·`overview.md` ㊻㊼㊽㊾)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260713T102249-doc-sync-rn-0713 [SKIPPED:non-policy-doc]): 릴리즈노트 data.js 07-10 블록 7항목(generated 07-10) — cache-buster `?v=dev` 고정(빌드 `inject_asset_stamp.py` content-hash 주입, 수기 bump 없음).
- **07-10 run 대비 차이**: (a) **§69 AI caveats 사용자 릴리즈노트 편입** — 07-13 PR #744 T69.5 POST-DEPLOY 완수(cc_data_main 재생성 715/715·0 failed·옛 자기-불평 사실상 0·사용자 원 리포트 해소)로 라이브 관측 가능(07-10 run 은 T69.5 미완이라 REJECT). (b) cache-buster 수기 bump 제거(ITEM-09 what#3 `inject_asset_stamp.py` 빌드주입 도입 반영·소스 `?v=dev` 고정). (c) **feature-0012 완결(07-12)** 색인 추가(STATUS 행 review·ARCHITECTURE 기능맵·wiki 카드). (d) landing/배포 소유=스킬(attended, 07-10 run 은 cron wrapper 위임).
- **07-11~13 사용자향 0 확정**: 서빙 front-end 변경 2건 모두 refactor(ITEM-09 그래프 CSS/JS 세분화·admin.js 모듈 분리, behavior-neutral 브라우저 QA 대기)·나머지는 feature-0012 라우터 모듈화 완결(byte-동치)·META 툴링·AI 내비 문서(ROUTEMAP/CODE_NAVIGATION) — 릴리즈노트 신규 0.
- **검증(타깃별 실질)**: 기능 카운트 grep 정합(wiki 카드 18 = unit 18, `_template-card` 제외)·§ref/anchor·STATUS 인덱스 모델(rollup 0·gen-status --check PASS)·릴리즈노트 `node --check` + vm 구조검증(블록순서 07-10>07-09>…·스키마·누출0)·ssot-lint. verify-completion check #1/#5 deferred(v1.1)는 위 타깃별 검증으로 갈음.
- **무변경 정직 보고**: `docs/SECURITY.md` noChange(신규 RBAC/trust boundary/auth 표면 0 — MSSQL 18456 순회 skip+cooldown 은 agent→datasource outbound 회복력으로 §12 사용자 로그인 throttle 과 무관)·`docs/DECISIONS.md` noChange(window ADR-026~037 전량 feature-0016 local 3-digit 정본·feature-0012 신규 project 4-digit ADR 0)·`wiki/Index`·`wiki/Features/_Index` noChange(신규 feature 0 — 카드 18/디렉토리 18).
- **[SKIPPED] 사유**: 색인/미러/사용자향 표면 additive 정합(정책 의미·구조 결정 변경 0) — codex 패널 불요, doc_sync 가 정본(feature TASK/REPORT·git log·PR #744/#664) 대비 직접 대조 검증(선례 META-0022·0023 계열). 본 run 은 ULTRACODE 워크플로 미가동(attended inline) → [SUBAGENT] 대신 [SKIPPED:<서술>] 로 정직 표기.
- **인용 무결성 확인**: REV-20260713T102249-META-0034-doc-sync-0713(본 entry) staged 실재. 동반 operational REV-20260713T102249-doc-sync-rn-0713(feature-0003 REVIEW.md) staged.
- **Human Approval Needed**: 아니오 (색인/미러 additive·제품 런타임 동작 0·pure-meta). doc_sync 사용자 정책(2026-06-25)상 landing/배포 무확인 자동(attended 소유).


## REV-20260714T024534-META-0035-doc-sync-0714 [SKIPPED:doc-sync-index-mirror-additive] — 07-13 오후 머지 델타(#746~#770) 인덱스/미러/사용자향 표면 정합 (그래프 렌더러 PixiJS v8 전면 교체 §78~81·콘텐츠 밴드·feature-0019 메시지 편집 신규·describe_routine·graph-perm-split)
- **cycle**: ai/claude/doc-sync-20260714-020501 — `/_dqa:doc_sync ultracode`(스케줄·무인, cron wrapper). **landing/배포 소유=wrapper 위임**(system-prompt v3 명시: 스킬은 로컬 commit 까지·push/merge-to-main/deploy 는 wrapper 가 fetch→rebase→ff-push→web deploy+health). 직전 doc_sync(META-0034 @ 07-13 10:30 bafad813) 이후 07-13 오후~저녁(11:51~20:04) 머지 델타 정합.
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(인덱스 — feature-0002/0003/0016-metadata-graph 행 date 07-10→07-13+오후 요지 append·feature-0019 신규 행+frontmatter sources·rollup 0·전 19행 passthrough·gen-status --check PASS)·`docs/ARCHITECTURE.md`(feature-0016 기능맵 렌더러 현재상태 G6 v5(Canvas)→PixiJS v8+§78~81 마커 — 색인 mirror·구조 결정 0·07-02 날짜부 이력 불변)·`docs/SECURITY.md`(§19 graph.read 함의 정정 — 우산 kb.ingest.manual 이 편집 4키만 함의·graph.read 독립 분리, graph-perm-split 미러)·wiki(`Features/_Index.md` 카운트 17→18+feature-0019 행+feature-0016 렌더러·`overview.md` 카운트+㊿ 서사+§2.1 feature-0019 행·`hot.md` Key Facts 2+Active Threads+Recent Changes·`Log.md` 11 작업+1 wiki-ingest append·카드 feature-0016/0003/0002)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260714T024534-doc-sync-rn-0714 [SKIPPED:non-policy-doc]): 릴리즈노트 data.js 07-13 블록 +7항목(generated 07-13 유지) — cache-buster `?v=dev` 고정(Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web asset_stamp_verify 하드게이트·수기 bump 없음·§13.1 ITEM-09 what#3).
- **07-13 오전 run(META-0034) 대비 차이**: (a) 렌더러 §78 G6→PixiJS v8 는 그 run 이후 오후 착지+배포(라이브 PB-0008 PASS)라 이번에 mirror 정합 — ARCHITECTURE/wiki 카드/_Index/overview 렌더러 현재상태 정정. (b) feature-0019 메시지 편집 **신규 feature**(카드는 착지 브랜치가 07-13 오후 이미 생성 — 재생성 안 함·STATUS/_Index/overview 행+sources 만 추가). (c) SECURITY §19 graph.read 분리 정합(Critical 인가 경계 변경 — 07-13 오전 시점 미착지). (d) landing/배포 소유=wrapper(META-0034 는 attended 스킬 소유).
- **검증(타깃별 실질)**: 기능 카운트 grep 정합(unit feature dir 19 = wiki 카드 19 = _Index 표행 19 = overview §2.1 행 19)·STATUS gen-status --check PASS(passthrough 19·drift 0)·ssot-lint exit 0(4 WARN 기존 secret .env.bak-* — doc_sync 범위 밖)·§ref/anchor(ARCHITECTURE feature-0016 셀·SECURITY §19)·릴리즈노트 `node --check`+구조검증(operational commit). verify-completion check #1/#5 deferred(v1.1)는 위 타깃별 검증으로 갈음.
- **무변경 정직 보고**: `docs/DECISIONS.md` noChange(git diff bafad813..HEAD 빈결과 — §78 렌더러(feature-local ADR-004 supersede)·graph-perm-split(사용자 승인 B안)·read-only shape 전부 feature-local/승인이라 repo-level ADR 색인 대상 아님). feature-0016 FUNCTION.md §13 이 렌더러 flip 반쯤(G6 리드+PixiJS PLAN-APPROVED)이나 **unit 정본이라 doc_sync 미수정 — feature 사이클에 플래그**(§78 feature-local ADR-004 supersede 본문 미작성). `wiki/Index.md`·concepts noChange.
- **[SKIPPED] 사유**: 색인/미러/사용자향 표면 additive 정합(정책 의미·구조 결정 변경 0) — codex 패널 불요, doc_sync 가 정본(feature TASK/REPORT·git log·PR #746~#770) 대비 직접 대조 검증(선례 META-0022·0034 계열). ULTRACODE 4-도메인 병렬 분석 + 적대 재검증 후 반영.
- **인용 무결성 확인**: REV-20260714T024534-META-0035-doc-sync-0714(본 entry) staged 실재. 동반 operational REV-20260714T024534-doc-sync-rn-0714(feature-0003 REVIEW.md) 작성 — 별도 operational commit 으로 stage.
- **Human Approval Needed**: 아니오 (색인/미러 additive·제품 런타임 동작 0·pure-meta). landing/배포 소유=wrapper 위임 → 스킬 로컬 commit 만·push/merge/deploy 는 wrapper.

## REV-20260715T025509-META-0036-doc-sync-0715 [SKIPPED:doc-sync-index-mirror-additive] — 07-14 머지 델타 인덱스/미러/사용자향 표면 정합 (메시지 편집 Phase 1+2 완성·무중단 배포 커버리지·그래프 UX·애니메이션/계정탭·sysvar 과차단·grounding 봉인·graph-analyze-perm)
- **범위**: docs/STATUS.md(인덱스 4행 0002/0003/0016/0019 date 07-14+요지, rollup 0·passthrough·gen-status --check PASS)·docs/ARCHITECTURE.md(feature-0019 기능맵+의존맵 신규, DESIGN-fork-reference §7 참조 정합)·docs/SECURITY.md(07-14 graph-analyze-perm addendum — metadata.graph.analyze 실행 권한 분리)·wiki(hot Key Facts·Log append·카드 0019/0003/0002·overview 2026-07-14 서사+카운트 20·Index/_Index/Architecture Overview/Module-Map feature 카운트 20 정합).
- **[SKIPPED] 사유**: 색인/미러/사용자향 표면 additive 정합(정책 의미·구조 결정 변경 0) — codex 패널 불요, doc_sync 가 정본(feature TASK/REPORT/FUNCTION·git log 07-14·PR #766~#800) 대비 직접 대조 검증(선례 META-0034·0035 계열). ULTRACODE 4-도메인 병렬 draft→적대 재검증(wf_ebf9d553) + defect 3건 교정(ARCHITECTURE §참조 mis-resolve→DESIGN-fork-reference·wiki 현재상태 카운트 셀 4곳 stale→20) 후 반영.
- **DECISIONS noChange**: 07-14 feature ADR 은 feature-local(unit docs)·신규 repo-level ADR 0 → DECISIONS.md 미편집(색인 대상 없음). 신규 ADR 본문 미작성(보수 기본값).
- **정본 lag(보고)**: feature-0019 REPORT/TASK prose 가 git 현실(Phase 1+2 라이브)보다 뒤처짐 — mirror(STATUS/wiki)는 git+FUNCTION 스펙+PB-0008 실측을 진실로 반영, 정본 prose 갱신은 feature-0019 후속 cycle 권고(doc_sync 정본 미편집).
- **인용 무결성 확인**: 본 entry(META-0036) staged 실재. 동반 operational REV-20260715T025509-doc-sync-rn-0715(feature-0003 REVIEW.md) 작성 — 별도 operational commit 으로 stage.
- **feature-count**: ground-truth `ls -d unit/feature-*`=20·wiki 카드 20 — Index/_Index/overview/Architecture Overview/Module-Map 전 현재상태 카운트 20 정합(sweep clean).
- **Human Approval Needed**: 아니오 (색인/미러 additive·제품 런타임 동작 0·pure-meta). landing/배포 소유=wrapper 위임 → 스킬 로컬 commit 만·push/merge/deploy 는 wrapper.


## REV-20260716T010501-META-0037-doc-sync-0716 [SKIPPED:doc-sync-index-mirror-additive] — 07-15~16 머지 델타(37건) 인덱스/미러/사용자향 표면 정합 (feature 카운트 20→21·feature-0021 red-team 신규·그래프 클러스터 상세/우클릭/엣지·권한 원자화·ENUM 묶음 큐·agent-core 정확도)
- **cycle**: ai/claude/doc-sync-20260716-010501 — `/_dqa:doc_sync ultracode`(스케줄·무인, cron wrapper v3). **landing/배포 소유=wrapper 위임**(system-prompt v3 명시: 스킬은 로컬 commit 까지·push/merge-to-main/deploy 는 wrapper 가 fetch→rebase→ff-push→web deploy+health). 직전 doc_sync(META-0036 @ 07-15 03:03 8e6b2b76) 이후 07-15~16(01:00) 머지 델타 정합.
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/SECURITY.md`(**신규 §23** — feature-0021 'AI 추론' admin observability boundary 색인, §20 aiops-panel 동형 인덱스-모델 1줄 포인터·위협모델 재서술 0)·wiki(`Features/_Index.md` 카운트 20→21 2곳(헤더 active·개요 카드)·`overview.md` 카운트 2곳(서두 디렉토리 20→21·0001~0021·§2.2 baseline 20→21)+§2.1 표 feature-0021 mirror 행+2026-07-15(52) 서사·`Index.md` 카운트 2곳(요약 compose·MOC 링크 0020→0021·카드 21)·`Architecture/Overview.md` 헤더 카운트(20→21·0001~0021)+§2.3 기능맵/§2.4 의존맵 feature-0019/0020/0021 backfill(pre-existing drift 동반 정합)·`Module-Map.md` MOC 링크 상한 0021·`hot.md` Key Recent Facts 1 prepend+Recent Changes 1 prepend+last_updated 07-16(Active Threads/기존 fact 전부 보존)·`Log.md` per-feature 엔트리 7 + doc_sync wiki-ingest 1 append)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260716T010501-doc-sync-rn-0716 [SKIPPED:non-policy-doc]): 릴리즈노트 data.js 07-15 블록 7항목(generated 07-15) — cache-buster `?v=dev` 고정(Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트·수기 bump 없음·§13.1 ITEM-09 what#3).
- **[SKIPPED] 사유**: 색인/미러/사용자향 표면 additive 정합(정책 의미·구조 결정 변경 0) — codex 패널 불요, doc_sync 가 정본(feature TASK/REPORT/FUNCTION·git log 07-15~16·PR #801~#836·feature-0021 REVIEW/admin_reasoning.py) 대비 직접 대조 검증(선례 META-0034·0035·0036 계열). ULTRACODE 3-타깃(release-notes/wiki/policy-docs) 병렬 analyze→적대 verify 파이프라인(wf_01d7fc19-550, 6 agent) + 정본 독립 재검증(함정 #11 — 워크플로 verdict 불신뢰, count 산술·§ref·07-14 area·admin_reasoning 라우트/권한 직접 재확인) 후 반영.
- **SECURITY §23 근거(억지 편집 아님)**: feature-0021(affeea67)이 신규 read-only admin 관측 표면(`routers/admin_reasoning.py` 3 GET `/api/admin/reasoning/{guidance,redteam,notes}` + 신규 권한 `console.reasoning.read` admin 전용 게이트)을 출하했으나 feature cycle 이 SECURITY boundary 색인 등재를 누락(CODEBASE_MAP/ROUTEMAP/STATUS 만 갱신) — §20 'AI 운영 관제 패널 admin observability' 선례와 동형인 mirror drift. 인덱스 모델 준수(1줄 포인터·정본=feature-0021 REVIEW/FUNCTION·위협모델 재서술 0). 라우트/권한/least-priv(_pg_connect_ro·부분 degrade)·guidance_registry 단일 진실원본은 admin_reasoning.py 실측과 일치.
- **DECISIONS noChange**: git `8e6b2b76..HEAD -- docs/DECISIONS.md` 공집합. 07-15~16 결정(그래프·red-team·권한)은 전부 feature-local ADR(feature-0021 unit DECISIONS ADR-20260715T140000~2 등)·신규 project 4-digit ADR 0 → DECISIONS.md 미편집(색인 대상 없음). 신규 ADR 본문 미작성(보수 기본값).
- **STATUS noChange**: `bash bin/gen-status.sh --check` rc=0(frontmatter 2·passthrough 19·신규 0·변경 없음) — autogen 인덱스가 feature frontmatter 와 정합. feature frontmatter 는 feature cycle 소관(doc_sync 미편집)·인덱스 모델 rollup 누적 0. ARCHITECTURE(docs) 구조 결정 noChange(신규 컴포넌트=feature-0021 admin_reasoning 라우터는 ROUTEMAP/CODEBASE_MAP 가 이미 색인·구조 결정 아님)·PROJECT noChange(정체성 drift 0).
- **무변경 정직**: `docs/SECURITY.md` 권한 재구성분(원자화 §22.4·카테고리 §22)은 07-15 perm 커밋(8e01cc24/3354b38d)이 이미 반영 → 중복 정합 안 함(본 run 은 §23 관측 표면만 추가). CONVENTIONS.md·ROUTEMAP.md 도 그 커밋 반영분 — doc_sync 추가 정합 불요.
- **검증(타깃별 실질, verify check #1/#5 deferred 갈음)**: feature-count grep sweep — ground-truth `ls -d unit/feature-*`=21·`wiki/Features/*.md`(_Index/_template 제외)=21, 잔존 stale '20' live 카운트 0(Log 역사·feature-0020 name 제외)·8곳 전부 '21' 정합. §ref — SECURITY §23 의 §20/§14 참조 실재(행 606/403), §23 header 행 754. wikilink — 신규 [[feature-0021-redteam-review]]·[[feature-0019-message-editing]]·[[feature-0020-zd-deploy-all]] 카드 전부 실재. ssot-lint rc=0(4 WARN=기존 tracked secret .env.bak·doc_sync 범위 밖).
- **인용 무결성 확인**: 본 entry(META-0037) staged 실재. 동반 operational REV-20260716T010501-doc-sync-rn-0716(feature-0003 REVIEW.md) 작성 — 별도 operational commit 으로 stage.
- **feature-count**: ground-truth `ls -d unit/feature-*`=21·wiki 카드 21(feature-0021-redteam-review 신규가 20→21 유일 원인) — _Index/overview/Index/Architecture Overview/Module-Map 전 현재상태 카운트 21 정합(sweep clean).
- **Human Approval Needed**: 아니오 (색인/미러 additive·SECURITY §23=관측 표면 boundary 색인·제품 런타임 동작 0·pure-meta). landing/배포 소유=wrapper 위임 → 스킬 로컬 commit 만·push/merge/deploy 는 wrapper.

## REV-20260716T140735-META-0038-doc-sync-0716b [SKIPPED:doc-sync-index-mirror-additive] — 07-16 낮 머지 델타(PR #837~#853) 인덱스/미러 표면 정합 + 잔재 harvest + SECURITY §23 콘솔 IA 재구성 정정 (그래프 검색 확대/결과 목록·상세 [뒤로/앞으로] 탐색 UX·헤딩 hover-pan·feature-0021 콘솔 IA 재구성)
- **cycle**: ai/claude/doc-sync-20260716-010501 — `/_dqa:doc_sync`(attended, 사용자 명시 호출·landing/배포 스킬 소유). 직전 스케줄 run(01:05, wrapper 위임)의 **미landed 잔재 2 commit(META 0cc64c2b·operational eeabda19)을 origin/main(abfef224) 위로 rebase harvest**(feature-0003 docs companion 4파일 append-형 충돌 union 해소·잔재 내용 무손실) 후, 그 이후 07-16 낮 머지 델타(PR #837~#853, 34 commit) 정합을 본 commit 으로 확장.
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/SECURITY.md`(**§23 정정** — 07-16 콘솔 IA 재구성 반영: 표면 '시스템>AI 추론 탭'→'감사>AI 운영 현황>[추론] 서브탭'+지침/스킬은 '설정>프롬프트 서브탭' 분리·guidance 라우트 권한 console.reasoning.read→`system_prompt.global.read` 재사용(+?kind)·console.reasoning.read 감사 카테고리 재배치 — admin_reasoning.py 실측(guidance:52 system_prompt.global.read·redteam:121/notes:206 console.reasoning.read)과 feature-0021 FUNCTION 정본 대비 정합)·wiki(`Log.md` per-feature 엔트리 4 append[graph-search·graph-detail-nav·group-hoverpan·console-ia]·`hot.md` Key Recent Facts 1 prepend(기존 fact/Active Threads 보존)·`Features/feature-0021-redteam-review.md` 한줄요약 콘솔 표면 표기+상태 07-16)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260716T140735-doc-sync-rn-0716b [SKIPPED:non-policy-doc]): 릴리즈노트 07-16 블록 4항목(generated 07-16).
- **[SKIPPED] 사유**: 색인/미러/사용자향 표면 additive 정합(정책 의미·구조 결정 변경 0 — §23 정정도 정본(feature-0021 FUNCTION·admin_reasoning.py 코드 실측)이 이미 확정한 사실의 색인 반영) — codex 패널 불요, doc_sync 가 정본 대비 직접 대조 검증(선례 META-0034~0037 계열).
- **STATUS noChange**: `bash bin/gen-status.sh --check` rc=0 — autogen 인덱스가 feature frontmatter 와 정합(07-16 낮 작업은 전부 기존 feature 내 폴리시·신규 feature 0). **DECISIONS noChange**: 07-16 결정은 전부 feature-local·신규 repo-level ADR 0. **ARCHITECTURE noChange**: 신규 컴포넌트/구조 결정 0(잔재 커밋이 feature-0019/0020/0021 backfill 완료). **feature-count 21 불변**(신규 feature 0 — 카운트 sweep 대상 없음).
- **검증(타깃별 실질, verify check #1/#5 deferred 갈음)**: §ref — SECURITY §23 의 §20/§14 참조 실재. wikilink — Log 신규 엔트리의 [[feature-0016-metadata-graph]]·[[feature-0021-redteam-review]]·[[feature-0003-agent-web-ui]] 카드 전부 실재. ssot-lint rc=0 확인. 릴리즈노트 vm 구조검증(31 releases·07-16 4항목·07-15 이하 보존).
- **인용 무결성 확인**: 본 entry(META-0038) staged 실재. 동반 operational REV-20260716T140735-doc-sync-rn-0716b(feature-0003 REVIEW.md) 작성 — 별도 operational commit 으로 stage.
- **Human Approval Needed**: 아니오 (색인/미러 additive·§23 정정=정본 기확정 사실의 색인 정합·제품 런타임 동작 0·pure-meta). attended run — landing(분리 commit→push→PR→merge)·배포(`make deploy-web`)·end-state 서빙 검증까지 본 run 이 수행(2026-06-25 사용자 정책).

## REV-20260717T010501-META-0039-doc-sync-0717 [SKIPPED:doc-sync-drift-mirror-correction] — b8658bee(07-16 doc-sync) 이후 델타 2건(ds-test-gate-fix·redteam-rederive) 인덱스/미러 정합 — SECURITY §22.4 ds-conn-test 게이트 서술 정정 + wiki Log ledger append
- **cycle**: ai/claude/doc-sync-20260717-010501 — `/_dqa:doc_sync ultracode`(무인 스케줄, cron wrapper v3). **landing/배포 소유=wrapper 위임**(system-prompt v3: 스킬은 로컬 commit 까지·push/merge-to-main/deploy 는 wrapper 가 fetch→rebase→ff-push→web deploy+health). 직전 doc_sync(META-0038 @ da303d03 07-16b) 이후 델타 = b8658bee..HEAD 2건.
- **delta(신규 2건)**: (A) feature-0003 ds-test-gate-fix(PR #855/#856, 5cf4cfe3/87cbe5d8) — 작업화면 '연결 테스트' 버튼 미렌더 회귀 복구(라이브·POST-DEPLOY PB-0008). (B) feature-0002 redteam-rederive(PR #857, 581e82a2) — 자가검증 BLOCK 축 재도출(내부·라이브 미배포).
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/SECURITY.md`(§22.4 정정 — ds-conn-test 버튼 게이트 서술을 '동일 게이트/괴리 해소'(perm-atomic-split 07-15 작성)에서 실제 07-16 상태 '프론트 display-permissive `can()`·백엔드 `admin_test_datasource` console.access+datasource.test enforcement 불변'으로 정정. 경계 무변화·보안 무영향)·wiki(`Log.md` ledger append 3: ds-test-gate-fix fix·redteam-rederive feature·doc_sync wiki-ingest)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260717T010501-doc-sync-rn-0717 [SKIPPED:non-policy-doc]): 릴리즈노트 07-16 블록 fixed/work 1항목(연결 테스트 버튼 회귀 복구) + summary 1문장 — cache-buster `?v=dev` 고정(ITEM-09 what#3, 수기 bump 없음).
- **[SKIPPED] 사유**: 색인/미러 drift 정정(정책 의미·구조 결정·보안 경계 변경 0) — SECURITY §22.4 는 정본(feature-0003 REPORT ds-test-gate-fix·app.js 5cf4cfe3 diff)이 확정한 프론트-게이트 현실을 반영하는 mirror 정정이며 enforcement 경계 불변. codex 패널 불요, doc_sync 가 정본(feature-0002/0003 REPORT·git show 581e82a2/5cf4cfe3·feature-0002 REVIEW B1) 대비 직접 대조 + ULTRACODE 5타깃 병렬 analyze→scoped 적대 verify(wf_9ddde343, 8/9 agent CONFIRMED; wiki agent StructuredOutput 실패라 오케스트레이터 직접 처리) + 정본 독립 재검증(함정 #11 — 워크플로 status 드래프트의 passthrough backfill 은 governance(ADR-0031·META-0037 선례) 근거로 오케스트레이터가 override).
- **STATUS noChange(정직 보고 — 이번 run 미편집)**: `bash bin/gen-status.sh --check` rc=0. 단 2건의 잔존 drift 를 **감지·보고**(수리는 소관 밖): ① **feature-0021 빈 행** — TASK.md frontmatter 가 `feature_status_updated`(오타, gen-status 는 `feature_status_date` 를 읽음)+`feature_status_note` 부재라 gen-status 가 date/note 공란 생성. 수리는 `unit/feature-0021/docs/TASK.md`(=operational path, is_meta_path 아님) 편집+companion 게이트를 요구 → doc_sync 불변제약('정본 새로 작성 안 함')·META-0037 'feature frontmatter=feature cycle 소관'에 따라 **feature-cycle 소관**으로 이관(감지·보고). ② **passthrough 행(feature-0002/0003/0016) 07-14 고착** — 07-15/16 작업 미반영이나 ADR-0031 §1(STATUS rollup 누적 금지) + META-0037/0038 선례(인덱스 모델 rollup 누적 0)에 따라 **무확장**(상세는 정본 unit REPORT·wiki·릴리즈노트에 현행). 장기 수렴 경로=frontmatter 마이그레이션(feature-cycle).
- **ARCHITECTURE/DECISIONS noChange**: `git show --stat 581e82a2` — docs/ARCHITECTURE.md·docs/DECISIONS.md·feature-local DECISIONS 전부 무터치(신규 repo-level 4-digit ADR 0 → 색인 대상 없음, 신규 ADR 본문 미작성). 기능맵=기존 feature(0002/0003) 무변. **부수 관측(prior-window, 미수리)**: docs/ARCHITECTURE.md §4/§6 에 feature-0021 부재(07-15 신규, ARCHITECTURE last-touch 8e6b2b76 07-15) — 07-16 doc-sync 가 wiki 미러(§2.3/§2.4)만 backfill·docs/ARCHITECTURE.md 는 미반영한 wiki↔docs drift. 본 run 지정 델타(b8658bee..HEAD) 밖이라 미수리·보고만.
- **무변경 정직**: wiki feature-count 21 불변(신규 feature 0, sweep clean). feature-0002 wiki 카드 redteam-rederive entry 는 라이브 미배포+Log ledger 로 포착 → 카드 미편집(보수). release-notes 07-13 블록이 '연결 테스트' 버튼 최초 소개(type:new) → 재소개 아닌 fixed 프레이밍(중복 회피).
- **검증(타깃별 실질, verify check #1/#5 deferred 갈음)**: SECURITY §22.4 §참조 무결성(§22/§23 heading 실재)·정정 문구가 app.js 5cf4cfe3 diff(Boolean(state.user...)→can())·REPORT 와 정합. wikilink 신규 [[feature-0003-agent-web-ui]]·[[feature-0002-agent-core]] 카드 실재. feature-count sweep clean(ground-truth 21). 릴리즈노트 node --check PASS + vm(31 releases·07-16 5항목[admin 4·work 1]·07-15 보존 7·스키마 위반 0·누출 0) + verify_release_notes.mjs 33/34(1 FAIL=styles.css 스크롤 정규식 pre-existing baseline).
- **인용 무결성 확인**: 본 entry(META-0039) staged 실재. 동반 operational REV-20260717T010501-doc-sync-rn-0717(feature-0003 REVIEW.md) 별도 operational commit 으로 stage.
- **Human Approval Needed**: 아니오 (색인/미러 drift 정정·SECURITY 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).

## REV-20260721T010501-META-0040-doc-sync-0721 [SKIPPED:doc-sync-index-mirror-additive] — 275855ea(07-17 doc-sync) 이후 신규 머지 0 · reconcile-first 로 07-17(META-0039)이 prior-window drift 로 보고한 docs/ARCHITECTURE.md §4/§6 feature-0021 색인 부재 backfill (wiki↔docs 미러 drift 해소)
- **cycle**: ai/claude/doc-sync-20260721-010501 — `/_dqa:doc_sync ultracode`(무인 스케줄, cron wrapper v3). **landing/배포 소유=wrapper 위임**(system-prompt v3: 스킬은 로컬 commit 까지·push/merge-to-main/deploy 는 wrapper 가 fetch→rebase→ff-push→web deploy+health). 마지막 sync = META-0039 @ 275855ea(07-17). `git log 275855ea..HEAD`=0·`git rev-list origin/main..HEAD`=0(fetch 후) → **신규 머지 0**. 본 run 은 신규 델타 창이 아니라 reconcile-first(멱등)로 직전 run 들이 남긴 갭만 대상.
- **delta(확정 1건, reconcile-first)**: docs/ARCHITECTURE.md §4 현재 기능 맵 + §6 기능 간 의존성 맵에 **feature-0021-redteam-review 행 부재** — 07-15 신규 Major feature(affeea67·PR #819)인데 ARCHITECTURE last-touch=8e6b2b76(07-15 03:03, 머지 10.5h 전)로 미러 누락. 07-16 doc-sync 는 wiki 미러(Architecture/Overview §2.3/§2.4)만 backfill·docs/ARCHITECTURE.md 미반영, 07-17(META-0039 line 734)이 'wiki↔docs drift·prior-window·미수리·보고만'으로 명시 유보한 항목. 본 run 이 색인 backfill 로 해소(§4 2컬럼 행 + §6 4컬럼 행, feature-0019/0020 포맷 미러, 정본=feature-0021 FUNCTION.md §1~§3 + wiki Overview line 94/118).
- **changeset (pure-meta, docs/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/ARCHITECTURE.md`(§4·§6 feature-0021 색인 행 2개 additive — 5축 red-team choke-point·전 경로 fail-open·추론 강도 게이팅·alembic 0042 additive·console.reasoning.read·cross-cut 코드 거주 0002/0003/shared; 기존 행 무변·구조 결정/신규 ADR 0)·`meta/REVIEW.md`(본 entry). operational(릴리즈노트) 동반 commit 없음 — D1 refute(아래).
- **[SKIPPED] 사유**: 색인/미러 additive(기존 머지 feature 를 기능맵·의존성맵 표에 색인 추가) — 정책 의미·구조 결정·보안 경계·신규 ADR 0. 정본(feature-0021 FUNCTION.md·wiki Architecture Overview 미러)이 확정한 사실의 색인 정합이라 codex 패널 불요(META-0034~0037 additive 선례 동일 slug). 검증: ULTRACODE 워크플로(wf_c2874c2f-088) — 후보 4건 refute-first 적대 판정 + 완전성 critic → 확정 1건(D2) 독립 적대 재검증(edit_correct/scope_ok/anchor_ok 전부 CONFIRMED, 정본 grounding 대조 — task=redteam 계측·캡 8KB·haiku·fail-open 전건 근거 확인).
- **판정 요약(refute-first, 무인 conservative default — 무변경 정직)**: D1 릴리즈노트=REFUTED(#857 redteam-rederive 는 07-15 블록 '스스로 점검해 바로잡음'·'성급히 단정 감소'로 이미 공지된 자가검증의 내부 정교화·화면 변화 없음[REPORT PB-0008 N/A]·정책상 내부동작 비노출이라 추가 시 기존 항목 중복; 배포 게이트 미해소=feature-0002 TASK L31 미체크·#857 POST-DEPLOY 커밋 부재). D3 SECURITY=REFUTED(#857 도구 재호출 방어는 §14 datamark/sentinel·§23 sentinel 구획 기존 경계를 미러한 additive 방어심층·정본 feature-0002 REVIEW B1/W1/W2 in-cycle 완비·§23 은 revise 도구없음 주장한 적 없음·07-17 이 §23 의식적 미편집). D4 wiki 카드=REFUTED(#857 은 feature-0002 정본만 터치·카드 소스 feature-0021 FUNCTION.md 는 pre-rederive 서술 유지·stale/오류 없음·Log L206 이 이미 포착). critic: 신규 머지 0 재확인·feature-count 21 전 표면(wiki overview/Index/_Index/Architecture) 정합·in-scope 누락 델타 0.
- **STATUS noChange(감지·보고만, 소관 밖)**: `bash bin/gen-status.sh --check` rc=0. ① feature-0021 빈 행(TASK.md frontmatter 오타 `feature_status_updated`→`feature_status_date`)=operational·feature-cycle 소관(passthrough regime·META-0037/0039 선례). ② passthrough 행(0002/0003/0016) 고착·§5 카운트 prose(등록 17/디렉토리 18) stale=ADR-0031 no-rollup·passthrough regime 상 무확장. 셋 다 critic 이 in_scope=false 로 확인.
- **검증(타깃별 실질, verify check #1/#5 deferred 갈음)**: §참조/anchor 무결 — `## 5.`·`## 6.`·`### 의존 유형 정의` heading 실재, feature-0021 삽입 후 §4 전 21행 3파이프(2컬럼)·§6 전 21행 5파이프(4컬럼) 정합(awk 기계 점검). feature-count sweep clean(ground-truth `ls -d unit/feature-*`=21 디렉토리, ARCHITECTURE §4 21행). ssot-lint rc=0(4 WARN=기존 tracked secret 백업, 범위 밖·불변). git diff=docs/ARCHITECTURE.md +2행 단일·디코이 stage 0.
- **인용 무결성 확인**: 본 entry(META-0040) staged 실재. operational 동반 commit 없음(D1 refute — 서빙 static 무변경).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta·서빙 static 무변경). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).

## REV-20260722T010501-META-0041-doc-sync-0722 [SKIPPED:doc-sync-index-mirror-additive] — 8f3dd00b(07-21 doc-sync) 이후 델타(신규 머지 feature-0022 agent-scratch-workspace 2026-07-21 라이브 활성 + feature-0003 진행상황 실시간 전파) 인덱스/미러/색인 정합
- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(feature-0022 passthrough 인덱스 행 신규 — gen-status --check PASS·feature frontmatter 미편집)·`docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0022 색인 backfill, bootstrap=repo-level 정정)·`docs/SECURITY.md`(**§24 신규 색인** — assistant write-capable scratch DB 표면 boundary 색인, 정본 `unit/feature-0022/docs/{REVIEW,DECISIONS}.md` 포인터·§19/§23 동형·정책 본문 신규 저술 아님)·wiki(feature 카운트 21→22 8곳[overview 서두·§2.2·Index 요약/MOC·_Index 헤더/개요·Architecture/Overview 헤더·Module-Map]·overview §2.1 표 행+§1 (53) 타임라인·Architecture/Overview §2.3/§2.4 backfill·Features/_Index §2 MOC 행·Log.md wiki-ingest append·hot.md fact prepend)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260722T010501-doc-sync-rn-0722 [SKIPPED:non-policy-doc]): 릴리즈노트 07-21 블록 1항목(improved/work 진행상황 실시간 전파, generated 07-21) — cache-buster `?v=dev` 고정(ITEM-09 빌드 자동주입, 수기 bump 없음).
- **[SKIPPED] 사유**: 색인/미러 additive(신규 머지 feature 를 인덱스·기능맵·의존성맵·wiki 카운트/MOC/타임라인에 색인 추가 + SECURITY §24 는 feature-local 정본이 이미 확정한 신규 write 표면의 boundary 색인, §23 선례 동형) — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0038/0040 additive 선례 동일 slug). feature-0022 색인 상태는 정본 TASK.md `## 라이브 활성화` 섹션(TASK-0016~0020 [x]) 기준(REPORT.md deferred/15건 은 활성화 前 stale outlier — unit/*=operational feature-cycle 소관, doc_sync 미수리).
- **검증(타깃별 실질 + ULTRACODE 적대)**: gen-status --check rc=0(passthrough 보존)·STATUS/§4/§6/§2.3/§2.4/_Index/§2.1 신규 행 pipe 무결(escaped `\|` 제외)·wiki feature-count sweep stale-21=0·release-notes `node --check` PASS+블록 내림차순+누출0·신규 wikilink 대상 실재. **ULTRACODE 2-라운드 적대 검증**: (1) wf_b9eb441a 6-verifier 가 초안의 feature-0022 '기본 OFF/deferred' 오류(정본 TASK-0016~0020=배포·ENABLED=1·스모크 라이브 활성)·overview §2.1 표 누락·SECURITY 색인 누락·release-note area(common→work)·§2.4 short-form·bootstrap repo-level 8건 적발 → 정본 TASK.md 기준 전면 정정; (2) wf_97d7d599 3-verifier 정정 재검증 holdsAll=true(과잉교정 아님 — TASK-0011 e2e 잔여 정확 보존·§24 색인-only·정본 일치) + 잔여 테스트수 15→22 stale 1건 정정. 정본 독립 재검증(함정 #11).
- **인용 무결성 확인**: 본 entry(META-0041) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion 5) 별도 — 서빙 static 변경이나 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).

## REV-20260723T010501-META-0042-doc-sync-0723 [SKIPPED:doc-sync-index-mirror-additive] — cfa647df(07-22 doc-sync) 이후 델타 51 커밋 · 신규 머지 feature-0023-conversation-api-access(외부 AI용 Bearer 토큰 인증 + MCP 서버, 2026-07-22 배포·라이브 e2e 통과) 인덱스/미러/색인 정합 + SECURITY §25 신규

- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(feature-0023 passthrough 인덱스 행 신규 — gen-status --check PASS[passthrough 20→21]·feature frontmatter 미편집)·`docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0023 색인 backfill, deps feature-0003/0002/0005 = FUNCTION.md §10 정본)·`docs/SECURITY.md`(**§25 신규 색인** — 외부 AI Conversation API Bearer 토큰 인증/인가 표면 boundary 색인, 정본 `unit/feature-0023-conversation-api-access/docs/{REVIEW,FUNCTION}.md` 포인터·§3/§5/§6/§7.2/§19/§23/§24 정합·정책 본문 신규 서술 아님)·wiki(feature 카운트 22→23 8곳[overview 서두·§2.2·Index 요약/MOC·_Index 헤더/개요·Architecture/Overview 헤더·Module-Map]·overview §2.1 표 행+§1 (54) 타임라인·Architecture/Overview §2.3/§2.4 backfill·Features/_Index §2 MOC 행·Log.md wiki-ingest append·hot.md fact prepend+last_updated)·`meta/REVIEW.md`(본 entry). feature-0023 wiki 카드는 feature 커밋(d88714a8)이 self-add — 재생성 안 함. 동반 operational(feature-0003 별도 commit, REV-20260723T010501-doc-sync-rn-0723 [SKIPPED:non-policy-doc]): 릴리즈노트 07-22 블록 6항목(fixed/work 3·improved/work 3·generated 07-22) — cache-buster `?v=dev` 고정(ITEM-09 빌드 자동주입, 수기 bump 없음).
- **[SKIPPED] 사유**: 색인/미러 additive(신규 머지 feature 를 인덱스·기능맵·의존성맵·wiki 카운트/MOC/타임라인에 색인 추가 + SECURITY §25 는 feature-local 정본이 확정한 신규 인증/인가 표면의 boundary 색인, §23/§24 선례 동형) — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0038/0040/0041 additive 선례 동일 slug). feature-0023 라이브 상태는 정본 TASK.md TASK-0010[x](배포 66a48870 soak PASS·토큰→/api/ask 200·admin 403·무토큰 401)·TASK-0011[x](CLI web→web-a/web-b hotfix 570649c2) 기준. **무변경 정직**: DECISIONS noChange(feature-0023 결정은 feature-local REVIEW REV-20260722-0001~0003·빈 ADR-001 스텁 — 프로젝트 ADR 색인 불요)·feature-0021 빈 STATUS 행(line 69, frontmatter 오타 feature_status_updated·note 부재 = feature-cycle 소관, 함정 #14 detect-and-report). feature-0023 카드 §2 status 'draft(라이브 e2e 대기)'·FUNCTION frontmatter status:draft·TASK §4/§7 잔재 = unit/*=operational feature-cycle 소관(doc_sync 미수리·detect-and-report).
- **검증(타깃별 실질 + ULTRACODE 적대)**: gen-status --check exit 0(passthrough 보존 21)·ssot-lint exit 0(4 WARN pre-existing tracked-secret·wiki-sot/archived 위반 0)·STATUS/§4/§6/§2.3/§2.4/_Index/§2.1/MOC 신규 행 pipe 무결(total-pipe: STATUS 6·§4 3·§6 5·MOC 6·§2.1 5·§2.3 4·§2.4 5 — §2.1/§2.3 은 wikilink escaped `\|` 1개 포함, cell-breaking 미escape pipe 0)·wiki feature-count sweep stale-22=0(ground-truth 23·Module-Map L34 는 §2.2 TOC 앵커 false-positive)·release-notes `node --check` PASS+상위 8블록 내림차순(말단 '이전' sentinel 정상)+누출0·신규 wikilink/§참조(feature-0023 카드·SEC §3/§5/§6/§7.2/§19/§23/§24·TASK/FUNCTION/REVIEW) 실재. 정본 독립 재검증(함정 #11): FUNCTION.md §10 deps(0003/0002/0005)·REVIEW REV-0001~0003·코드 심볼(_get_account_by_api_token web_context.py:3053·_account_permissions:2793·_api_token_permission_denied:119·_ensure_web_api_tokens_schema _bootstrap_schema.py:2185) 실재 확인. **ULTRACODE 적대 검증**: wf_4ab4d814 3-타깃 병렬 분석→타깃-스코프 적대 verify(cross-fault 회피, 함정 #12) — RN 6 INCLUDE holds·8 EXCLUDE(feature-0023 개발자향·UI 없음 등) 사유 정확·wiki/정책 confirmed; 2 minor REFUTE 교정 반영(feature-0023 severity Major→Critical[정본 TASK.md L31 '위험도 Critical(인증/인가 신설)']·feature-0021 빈 행 line 65→69).
- **인용 무결성 확인**: 본 entry(META-0042) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion 5) 별도 — 서빙 static 변경이나 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).

## REV-20260724T010501-META-0043-doc-sync-0724 [SKIPPED:doc-sync-index-mirror-additive] — aac76889(07-23 doc-sync) 이후 07-23 델타 · 신규 머지 feature-0024-conversation-folders(대화 폴더·프로젝트 워크스페이스, Major/일부 Critical, 2026-07-23 Phase1+2a 라이브 완결) 인덱스/미러/색인 정합 + SECURITY §26 신규

- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(feature-0024 passthrough 인덱스 행 신규 hand-add — feature_status frontmatter 미보유라 gen-status 자동생성 0·gen-status --check PASS[passthrough 보존]·feature frontmatter 미편집)·`docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0024 색인, deps feature-0002/0003/0009 = FUNCTION.md §10 정본, max-depth 런타임설정=`shared/runtime_settings`·feature-0018 슬라이스 note)·`docs/SECURITY.md`(**§26 신규 색인** — 대화 폴더 per-user 격리·folder RBAC·restore IDOR·에이전트 컨텍스트 주입 표면 boundary 색인, 정본 `unit/feature-0024-conversation-folders/docs/{REVIEW,FUNCTION}.md` 포인터·§12.3/§19/§23/§24/§25 정합·정책 본문 신규 서술 아님)·wiki(feature 카운트 23→24 8곳[overview 서두·§2.2·Index 요약/MOC·_Index 헤더/개요·Architecture/Overview 헤더·Module-Map]·overview §2.1 표 행+§1 (55) 타임라인·Architecture/Overview §2.3/§2.4·Features/_Index §2 MOC 행·**Features/feature-0024-conversation-folders.md 카드 신규 생성**[feature 커밋 self-add 없음]·Log.md wiki-ingest append[run-date 07-24]·hot.md fact prepend+last_updated 07-24)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260724T010501-doc-sync-rn-0724 [SKIPPED:non-policy-doc]): 릴리즈노트 07-23 블록(new/improved/fixed·generated 07-23) — cache-buster `?v=dev` 고정(ITEM-09 빌드 자동주입, 수기 bump 없음·index/admin 편집 0).
- **[SKIPPED] 사유**: 색인/미러 additive(신규 머지 feature-0024 를 인덱스·기능맵·의존성맵·wiki 카운트/MOC/타임라인/카드에 색인 추가 + SECURITY §26 은 feature-local 정본이 확정한 신규 보안 표면의 boundary 색인, §23/§24/§25 선례 동형) — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0038/0040/0041/0042 additive 선례 동일 slug). feature-0024 라이브 상태는 정본 TASK.md late-append TASK-0012[x](PR #895→7f8e7a40 배포·deploy-web soak PASS·POST-DEPLOY PB-0008 라이브 e2e PASS)·folder-privacy/perms-broaden/ux 각 POST-DEPLOY 커밋(9392cf51/e3fec503/0a1378f3/1a2f2595) 기준(함정 #16 — TASK 상단 'in-progress'·REPORT 빈 스텁은 stale). **무변경 정직**: DECISIONS noChange(feature-0024 D1/D2/D4 = feature-local TASK.md line 23·프로젝트 ADR 색인 불요, ADR-0031 SSOT)·SECURITY §21 공유창 window 격리는 feature-0009 커밋 ffd87a52 self-update(doc_sync 미편집·확인만)·graph-node-reveal(feature-0016 2c4949c0)은 자체 POST-DEPLOY PB-0008 미기록('배포됨-미검증')이라 사용자 릴리즈노트 보류(wiki 기술 타임라인엔 merged 사실만 색인, 함정 #15). feature-0024 카드/FUNCTION frontmatter status·TASK 상단 잔재 = unit/*=operational feature-cycle 소관(doc_sync 미수리·detect-and-report).
- **검증(타깃별 실질 + ULTRACODE 적대)**: gen-status --check exit 0(passthrough 보존·카운트 +1)·STATUS/§4/§6/§2.3/§2.4/_Index/§2.1/MOC 신규 행 pipe 무결(total-pipe: STATUS 6·§4 3·§6 5·MOC 6·§2.1 5·§2.3 4·§2.4 5 — §2.1/§2.3 은 wikilink escaped `\|` 1개 포함)·wiki feature-count sweep stale-23=0(ground-truth 24)·신규 wikilink([[feature-0024-conversation-folders]] 카드 실재)·§참조(SEC §12.3/§19/§23/§24/§25) 실 heading resolve. 정본 독립 재검증(함정 #11): FUNCTION.md §10 deps(0002/0003/0018/0009+shared) 확인 — §6/§2.4 formal edge 는 house-style(§6 zero feature-0018 edge·runtime_settings→shared/) 로 {0002,0003,0009}+note 에 feature-0018 문서화. severity 정본 TASK.md line 22 '위험도 Major(일부 Critical)'. **ULTRACODE 적대 검증**: wf_ded08a66 3-타깃 병렬 분석→타깃-스코프 적대 verify(cross-fault 회피, 함정 #12) — RN major 1 REFUTE 반영(graph-node-reveal 배포게이트 미해소 → 사용자 릴리즈노트 hold, 함정 #15)·wiki minor 3(§2.4 short-id·Log run-date 07-24·PR #899 추가)·policy minor 2(SEC §26 cross-ref §19/§23/§24/§25 동형·ADR-001 스텁 인용 제거) 반영.
- **인용 무결성 확인**: 본 entry(META-0043) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion) 별도 — 서빙 static 변경이나 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).

## REV-20260727T010501-META-0044-doc-sync-0727 [SKIPPED:doc-sync-index-mirror-additive] — 4dc1dcbc(07-24 doc-sync) 이후 델타 76 커밋(전부 git-date 2026-07-24) · 신규 머지 feature-0025-worker-parallelism(워커 성능·병렬 처리 런타임 설정, Major, 2026-07-24 머지 PR #933·구현 완료·단위48+회귀166 PASS·§18.8 2렌즈 SHIP·배포후 PB-0008 잔여) 인덱스/미러/색인 정합

- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `docs/STATUS.md`(feature-0025 인덱스 행 — feature_status:in-progress frontmatter 보유[frontmatter-driven]라 `bash bin/gen-status.sh` 재생성으로 자동 삽입, sparse 행[date/note 부재]·gen-status --check PASS[frontmatter 3·passthrough 22·신규 0]·feature frontmatter 미편집)·`docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0025 색인, edge deps feature-0002/0003=FUNCTION.md 소비표 정본, runtime-settings=feature-0018 슬라이스·shared·docker-compose·feature-0016 워크로드=note house-style[feature-0024 미러])·wiki(feature 카운트 24→25 8참조/5파일[overview 서두·§2.2·Index 요약/MOC·_Index 헤더/개요·Architecture/Overview 헤더·Module-Map]·overview §2.1 표 행+§1 (56) 타임라인[07-24 창]·Architecture/Overview §2.3/§2.4·Features/_Index §2 MOC 행·Log.md wiki-ingest append[run-date 07-27]·hot.md fact prepend+last_updated 07-27; **feature-0025 카드는 feature 커밋 01c4ba44 가 self-add → 재생성 안 함**)·`meta/REVIEW.md`(본 entry). 동반 operational(feature-0003 별도 commit, REV-20260727T010501-doc-sync-rn-0727 [SKIPPED:non-policy-doc]): 릴리즈노트 2026-07-24 블록(improved/fixed·work 6·admin 2·generated 07-23→07-24) — cache-buster `?v=dev` 고정(ITEM-09 빌드 자동주입, 수기 bump 없음·index/admin 편집 0).
- **[SKIPPED] 사유**: 색인/미러 additive — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0040~0043 additive 선례 동일 slug). feature-0025 상태는 정본 TASK.md 위험도 Major·REVIEW.md REV-20260724T053235 SHIP(BLOCKING 0·MAJOR 2 in-cycle)·REPORT.md verify-completion PASS 기준(함정 #16 — TASK 체크리스트 TASK-0010/0011/0012 미체크는 REVIEW SHIP·git PR #933 머지 대비 lag, 실잔여=PB-0008 라이브[TASK-0012]). **무변경 정직**: SECURITY noChange(feature-0025 는 기존 §22 system.runtime.read/write 게이트 재사용·clamp=availability 방어심층[§82-class 풀 소진 재발 방지]·신규 access-control 표면 0 → 신규 §27 미작성; feature-0024 §26 은 진짜 신규 per-user 격리 표면이라 대조 성립)·docs/DECISIONS.md noChange(feature-0025 결정=feature-local ADR-0025-01~04·프로젝트 4자리 ADR 0; pre-existing `## ADR-0025` 는 별개 네임스페이스 무관)·passthrough 행 무확장(ADR-0031 §1). feature-0025 TASK.md frontmatter feature_status_date/note 부재(sparse 행 원인)=feature-cycle 소관(unit/*=operational, 함정 #14 detect-and-report).
- **검증(타깃별 실질 + ULTRACODE 적대)**: gen-status --check exit 0(신규 0·passthrough 22·frontmatter 3, feature-0025 sparse 행 1줄만 추가·기존행 churn 0)·STATUS/§4/§6/§2.3/§2.4/_Index/§2.1/MOC 신규 행 pipe 무결(§4 파이프3[2컬럼]·§6 파이프5[4컬럼])·wiki feature-count sweep stale-24=0(ground-truth 25·9 token-edit=8참조/5파일)·신규 wikilink([[feature-0025-worker-parallelism]] 카드 실재)·§참조 무결(arch4 REV-20260724T053235 실재). 정본 독립 재검증(함정 #11): FUNCTION.md deps(코드 거주 0002/0003/shared/compose·재사용 0018·워크로드 0016)·DECISIONS.md ADR-0025-01~04 실레코드·severity=TASK.md Major. **ULTRACODE 적대 검증**: wf_2676a918 3-타깃 병렬 분석→타깃-스코프 적대 verify(cross-fault 회피, 함정 #12) — wiki confirmed(결함 0)·정책 confirmed(minor 1: arch4 bare §18.8→REV-ID doc-qualify 교정 반영)·릴리즈노트 confirmed(minor 1: graph-emoji '제 색으로'→'검은 실루엣 없이 제 모습대로' 3종 그레이스케일 이모지 정합 교정 반영).
- **인용 무결성 확인**: 본 entry(META-0044) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion 5) 별도 — 서빙 static 변경이나 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).
## REV-20260728T010301-META-0045-doc-sync-0728 [SKIPPED:doc-sync-index-mirror-additive] — 01ad5060(07-27 doc-sync) 이후 델타 · 신규 머지 feature-0026-perf-observability(성능 관측 인프라, 측정 전용·사용자 가시 동작 변경 0, Minor, 2026-07-27 머지 396a9c67·단위 9 PASS·회귀 0·§18.8 3렌즈 패널) 인덱스/미러/색인 정합 + wiki 카운트 25→26 + docs/ARCHITECTURE §4/§6 backfill

- **changeset (pure-meta, docs/**·wiki/** = META path → verify-completion META mode check #9 게이트)**: `wiki/overview.md`(서두 카운트 25→26·0001~0026·§2.2 "25-feature"→"26-feature"·§2.1 표 feature-0026 행·§1 (57) 2026-07-27 타임라인[feature-0026 신규 + 07-27 사용자향 UX·모델 bundle: opus5·share-bar·detail-db-groups — house-style (54)(55)(56) 윈도우 UX bundle 선례])·`wiki/Features/_Index.md`(헤더 "25 active"→"26 active"·개요 "25 개 feature 카드"→26)·`wiki/Architecture/Overview.md`(헤더 표 25카드/0025→26/0026·§2.3 기능맵 feature-0026 행·§2.4 의존성 feature-0026 행)·`wiki/Architecture/Module-Map.md`(§2.2 MOC 포인터 0025→0026)·`docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0026 backfill — feature 커밋 396a9c67 이 STATUS/SECURITY/ROUTEMAP/CODEBASE_MAP/CODE_NAVIGATION 은 갱신했으나 ARCHITECTURE 미터치, 함정 #15 정합)·`meta/REVIEW.md`(본 entry). **feature-0026 카드·_Index MOC 행·wiki/Index.md(서두 26-feature·MOC 카드26)·wiki/Log.md·docs/STATUS.md·docs/SECURITY.md §27 은 feature 커밋 396a9c67 이 이미 self-add → 재생성 안 함.** 동반 operational(feature-0003 별도 commit, REV-20260728T010301-doc-sync-rn-0728 [SKIPPED:non-policy-doc]): 릴리즈노트 기존 2026-07-27 블록에 3항목 append(답변 모델 claude-opus·공유뷰 하단바·관계도 상세 DB그룹) — cache-buster `?v=dev` 고정(ITEM-09 빌드 자동주입, 수기 bump 없음·index/admin 편집 0·wrapper 헤더 수기 bump 지시는 07-12 이전 regime 부적용, 351ed406 동일 판정).
- **[SKIPPED] 사유**: 색인/미러 additive — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0040~0044 additive 선례 동일 slug). feature-0026 상태는 정본 TASK.md 위험도 Minor·REVIEW.md SHIP·FUNCTION.md §1(측정 전용·사용자 가시 동작 0·additive/fail-open) 기준. **무변경 정직**: docs/SECURITY.md noChange(§27 성능 관측 인프라 색인은 feature 커밋 396a9c67 이 이미 추가[2026-07-28]·신규 access-control 표면 0[console.aiops.read 재사용] → doc_sync 미편집)·docs/DECISIONS.md noChange(feature-0026 결정=feature-local·프로젝트 4자리 ADR 0)·docs/STATUS.md noChange(gen-status --check exit 0[frontmatter 4·passthrough 22·신규 0]·feature-0026 in-progress 행 존재+정확[TASK.md feature_status_note 미러])·passthrough 행 무확장(ADR-0031 §1).
- **검증(타깃별 실질 + ULTRACODE 적대)**: wiki feature-count sweep stale-25=0(ground-truth 26=ls unit/feature-*=26·wiki/Features/feature-*.md=26 cards·6 token-edit=8참조 중 stale 6[Index.md 2참조는 feature 커밋이 이미 26])·신규 wikilink([[feature-0026-perf-observability]] 카드 실재)·표 행 pipe 무결(overview §2.1 3열·Architecture §2.3 2열/§2.4 4열·docs §4 2열/§6 4열)·feature-0026 각 타깃 표 1행씩(중복 0). 정본 독립 재검증(함정 #11): perf 수치 141s/agent87.8s(62%)/redteam46.4s(33%)/~34s/AGE590만·12.5d=REPORT.md §17-21 실측·symbol PerfTimingMiddleware/INCLUDE_ORDER=250(admin_perf.py:23 실코드)/`_ans_breakdown`/`_rt_ms`/relationships_probe=TASK.md §2.1 실존·모델 라벨 claude-opus(model_catalog.py:93·기본값 haiku-4)·severity=TASK.md:56 Minor·단위 9 PASS=TASK.md:77. **ULTRACODE 적대 검증**: wf_c9bea2de 4-dimension 병렬 analyze→dimension-스코프 적대 verify(cross-fault 회피, 함정 #12) — wiki-count 6 CONFIRMED(rejected/missed 0)·wiki-rows 4 CONFIRMED·docs-policy 2 CONFIRMED·relnotes 3항목 CONTENT CONFIRMED(verifier 가 초안 07-28 date framing REJECT→07-27 기존 블록 append 로 정정, block date=배포일·generated=top-block date 관례 351ed406/85da43d9 선례).
- **인용 무결성 확인**: 본 entry(META-0045) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion TASK/MODIFY/FUNCTION/TEST/REVIEW) 별도 — 서빙 static(릴리즈노트) 변경이나 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).
## REV-20260727T190500-META-0046-cycle-privilege-adapter [SUBAGENT:general-purpose] — BLOCKING 3 · MAJOR 7 · MINOR 5 → 설계 선회 후 전건 해소/무효화
- Related Change: cycle 스크립트 권한 어댑터 (§13.2.10 신설 + `bin/lib/privilege.sh`),
  ADR-20260727T190000-cycle-privilege-adapter
- 번호 재배정: 착수 시 META-0045 로 잡았으나 병렬 doc_sync cycle 이 같은 번호를 먼저
  랜딩(REV-20260728T010301-META-0045-doc-sync-0728) → **META-0046** 으로 이관. 브랜치·worktree
  명(`ai/claude/meta-0045-privileged-cycle-scripts`)은 PR #971 이 이미 열려 있어 그대로 둔다.
- Panel: 보안·권한 렌즈 1개. "통과가 아니라 결함 적발" 명시 + 확신 없는 추측성 지적 금지 +
  실패 시나리오 제시 요구. 리뷰어가 **실제 sudoers/ACL 환경 확인 + 격리 sandbox(no-ACL)에서
  스크립트를 실행해 각 지적을 재현**했다 (대상 파일 md5 조사 전후 동일 확인).
- Trigger: 권한 승격 도입 = 보안 민감 변경. 승격 경로에 기계 생성 입력이 도달하는지,
  소유권·환경·PATH 회귀가 있는지 독립 검증 필요.

### 1차 구현(스크립트 전체 `sudo -E` 재실행)에 대한 BLOCKING 3건 — 실측 재현됨
- **B1 `--agent` 기본값이 `root`** — `sudo` 는 `-E` 를 줘도 `USER`/`LOGNAME` 을 runas 로
  항상 덮어쓴다(보존은 `HOME` 뿐). 재실행이 기본값 결정보다 앞서 브랜치가 `ai/root/<feat>` 로
  생성되고, **dry-run 프리뷰(`ai/claude-corp/…`)와 실제 실행이 어긋난다** — 사전 검증 무의미.
- **B2 기존 `eval` sink 가 root 로 실행** — `run_or_dryrun` 은 `eval "$@"`, `FEATURE_ID`
  검증은 `/`·공백·백슬래시만 막아 `;`·`$`·백틱 통과, `AGENT_NAME` 은 검증 전무.
  `--feature 'a;id>${PWD}pwn'` 로 **worktree 밖 uid 0 파일 생성 실증**. feature slug 를
  기계가 만드는 경로(entry dispatch, ROADMAP 파생)가 root 임의 실행에 도달.
- **B3 소유권 복원 불완전** — `chown -R` 대상이 체크아웃 디렉터리 하나뿐. no-ACL sandbox 에서
  `.git/worktrees/<name>`·`.worktrees`·`FETCH_HEAD`·`refs/heads/*` 가 root 소유로 남아
  cycle-init "성공" 직후 `git add` 가 `index.lock: Permission denied` 로 실패. 이후
  `PRIV_NO_SUDO=1` fallback 도 영구 실패하며 원인을 **"non-fast-forward?" 로 오진** —
  본 변경이 고치려던 오진 패턴의 재발.

### MAJOR 7건 (요지)
M1 `sudo -n true` 프로브가 `-E` 를 검증하지 않아 좁힌 sudoers 에서 `exec` 로 즉사(비차단
degrade 선언 위반) · M2 호출자-쓰기가능 디렉터리의 lock 경로를 symlink 검사 없이 `>` 로 열고
`chmod`/`chown`(링크 추종 → 임의 파일 절단·소유권 이전 실증) · M3 `secure_path` 가 `-E` 를
무시하고 PATH 교체 → `~/.local/bin` 의 `gh` 상실로 `gh not found` 하드 실패 · M4 sudo umask
0022 강제 + `.worktrees` 정규화 누락 → group-write 공유 배치 무력화 · M5 `priv_unreadable` 이
`-r` 만 봐서 0664 이후 남는 **쓰기** 거부는 다시 오진 · M6 finalize 가 복원을 아예 미호출
(init 과 비대칭, 안내문이 거짓) · M7 `-E` 전면 보존의 실질 위험은 loader(sudo 가 차단)가 아니라
`GIT_SSH_COMMAND`/`GIT_CONFIG_*`/`HOME` 이 root git 에 먹히는 것.

### 반영: 설계 선회 (사용자 재확인 후)
패널이 B3·M4·M6 에서 반복해 낸 권고 — "전체 승격을 버리고 권한이 실제로 필요한 구간만
`sudo`" — 를 채택했다. 실측 결과를 사용자에게 보고하고 방향을 재확인받아 선회.
- **B1·B3·M1·M3·M4·M6·M7 → 구조적 소멸**: `git`·`gh` 가 원 호출자로 실행되므로 `USER`
  덮어쓰기·root 산출물·PATH 교체·umask 강제·`-E` 환경 전파가 애초에 발생하지 않는다.
  `exec sudo` 가 없어 M1 의 즉사 경로도 없다.
- **B2 → 화이트리스트로 차단**: `FEATURE_ID`/`AGENT_NAME` `^[A-Za-z0-9._-]+$`,
  `BASE_BRANCH` `^[A-Za-z0-9._/-]+$`. 승격과 무관하게 존재했던 구멍이라 이 cycle 에서 닫았다.
  `AGENT_NAME` 기본값 `${SUDO_USER:-${USER:-ai}}` 로 외부 sudo 래핑에도 브랜치명 보존.
- **M2 → symlink 거부**: `priv_ensure_writable`/`priv_share_file`/`priv_share_dir` 진입 시
  `[ -L ]` 거부 + `chown --no-dereference`.
- **M5 → `priv_unwritable`/`priv_access_reason` 신설**: `read-denied`/`write-denied`/`ok`
  구분. 파일 `-w` 와 **부모 디렉터리 `-w`**(rewrite·lock 생성이 요구)를 함께 본다.
- **MINOR 반영**: `$0` → `${BASH_SOURCE[0]}` + `readlink -f`(symlink 경유 호출) ·
  `mktemp` 직후 `priv_share_file`(mv 전 — 접근 불가 창과 중간 실패 시 0600 영구화 제거) ·
  finalize 실패 분기에도 모드 되감기 · `registry_record` 조기 반환으로 raw
  `awk: Permission denied` 유출 제거 · 문구를 실제 계약에 맞춤.
- **MINOR 무효화**: "필수 인자 검증보다 승격이 먼저"·"idempotent 재실행 시 `chown -R` 이
  소유권 강탈" 은 승격·복원 제거로 소멸.

### 패널이 "결함 없음" 으로 확인한 것 (선회 후에도 유효한 근거)
`chown -R` 의 symlink 비추종(coreutils 9.4 실측 — 재귀 중 만난 링크는 링크 자체만, 타깃 불변) ·
재귀 가드 · 비승격 경로(`--help`/`--dry-run`/`--print-only`) · `set -euo pipefail` × 헬퍼
return code · flock fd 8/9 무간섭 · git dubious ownership 없음 · `chmod 0664` 대상이
REGISTRY 와 `.lock` 뿐(비밀정보 아님, `*.bak-*` 0600 불변) · post-commit hook 은
`verify-completion.sh` 만 호출하므로 §13.2.10 범위 한정과 실제 코드 일치.

### 재검증 (선회 후 — 라이브 실측 R1~R8)
- R1 `--agent` 기본값: dry-run == 실제 == `ai/claude-corp/*` (B1 해소)
- R2/R3 주입 payload(`a;id>${PWD}pwn`, AGENT_NAME 판): 검증에서 거부, 산출물 0 (B2 차단)
- R4 산출물 소유권: worktree·`.git/worktrees` 모두 호출자 소유, `git add` 성공 (B3 해소)
- R5 **실제 장애 재현 → 자동 복구**: REGISTRY 를 `root:root 0600` 으로 만들어 호출자 읽기
  불가 상태를 재현 → cycle-init 이 `chmod 0664` 1단계로 복구(소유권 이전 없이 ACL `mask`
  복원만으로 해결), 기록 성공, 결과 `0664` + `mask::rw-`
- R6 정상 상태: `[privilege]` 로그 0줄 = **sudo 호출 0회** (최소 개입 확인)
- R7/R8 `PRIV_NO_SUDO=1` + 장애 상태: 정확한 원인(`read-denied`) 보고 + raw awk 에러 없음 +
  **exit 0**(비차단 degrade 확인)
- 문법: 3파일 `bash -n` PASS. 폐기 심볼(`priv_reexec_as_root`/`PRIV_ORIG_ARGS`/
  `PRIV_INVOKER_*`/`PRIV_NO_REEXEC`) 잔재 grep 0건. 테스트 worktree·REGISTRY entry·권한
  전량 원복 확인.
- Verdict: **SHIP** — BLOCKING 0 잔존. 1차 설계의 결함은 범위 축소로 소멸했고, 승격과 무관한
  기존 `eval` 구멍은 이 cycle 에서 함께 닫았다.
- Open Questions: `verify-completion.sh`·post-commit hook 은 의도적으로 비승격이다. 그 경로에서
  공유 파일 접근이 필요해지면 §13.2.10 범위 한정을 재검토해야 한다(현재는 필요 없음 — 패널이
  hook 호출 그래프로 확인). template base 전파 시 no-ACL 소비자에서 R5 형태의 복구 경로를
  다시 실측할 것.

## REV-20260728T011500-META-0047-privilege-writethrough [SKIPPED:설계 결정이 상류 적대검증에서 이미 검증됨 — 본 cycle 은 그 결론의 적용]
- Related Change: 소비자 `bin/lib/privilege.sh` 를 write-through 로 정합화 (§13.2.10),
  REV-20260727T190500-META-0046 의 후속 항목 이행
- Panel skip 근거: 본 변경이 채택하는 설계(`replace_preserving_mode`)는 **이미 두 번 독립
  검증됐다** — ① template v3.40.0 이 hop 계층에서 도입하며 `stat`/`chmod` 왕복이 metadata
  에 lossy 함을 실측(ACL named entry 소실 · symlink lstat 0777 · uid/gid 미복원)으로
  확증했고, ② 그 결론이 v3.41.0 §13.2.10 규약으로 명문화됐다. 본 cycle 은 새 설계를
  제안하는 것이 아니라 소비자 선행 구현(초판 `chmod` 되감기)을 그 규약에 맞추는 적용이며,
  changeset 은 `bin/lib/privilege.sh` + 두 호출부 + AGENTS.md 문구다.
- 왜 초판이 `chmod` 였나 (정직한 경위): META-0046 착수 시점에 template v3.40.0 은 아직
  미커밋 상태(다른 세션 진행 중)여서 `replace_preserving_mode` 의 존재와 그 근거를 알지
  못했다. 소비자 환경에 default ACL 이 걸려 있어 `chmod 0664` 만으로도 `mask` 가 복원돼
  **증상이 사라졌고**, 그래서 초판이 통과했다. 즉 이 프로젝트에서는 실害가 없었지만
  ACL 없는 배치에서는 named entry 를 잃는 잠재 결함이었다.
- 검증 (라이브 실측):
  - **W1 metadata 보존** — REGISTRY 를 mode `0640` + named ACL `user:root:rw-` 로 설정한 뒤
    cycle-init 기록 → **`-rw-rwx---` 와 `user:root:rw-` 가 그대로 유지**. `mv` 방식이었다면
    mktemp 의 0600 이 남거나(또는 chmod 로 0664 로 넓어지고) named entry 가 부모 default
    ACL 로 대체됐을 지점이다.
  - **W2 복구 경로 무회귀** — `root:root 0600` 장애를 재현 → `priv_ensure_writable` 이
    `chmod 0664` 1단계로 복구, 기록 성공, 호출자 쓰기 가능 확인.
  - 문법: 3파일 `bash -n` PASS. `priv_share_file` 잔재는 헤더의 역사 서술 1건뿐(코드 0).
  - 테스트 worktree·REGISTRY entry·권한 전량 원복 확인.
- Open Questions: `priv_replace_preserving_mode` 와 `migrations/lib/common.sh::replace_preserving_mode`
  는 계층 분리(후자는 hop 전용 lib 으로 `log_*` 에 의존)로 인한 동일 계약 중복이다. 두 계층이
  공유할 최소 lib 로 승격하는 것은 template 측 별도 cycle 로 남긴다 — 소비자에서 선행 통합하면
  다음 template hop 과 충돌한다.

## REV-20260728T120500-ai-root-perf-decisions-doc [SKIPPED:non-policy-doc] — 성능 결정 ADR 기록
- Related TASK: _meta_ (docs/DECISIONS.md 단독 append)
- Reason: 사용자 결정(2026-07-28)인 **red-team 게이팅 불채택**을 프로젝트 ADR 로 고정하는
  append-only 기록. 정책 의미·구조 변경 0(이미 확정된 사용자 결정의 문서화), 코드·스키마·
  인가 경계 무변경 → §18.8 패널 불요(docs-only, 결정 자체는 사용자가 내렸다).
- 내용: ADR-20260728T120000-redteam-gating-not-adopted — 지연 46.4s/답변(전체 33%) 이지만
  revision 적용 24%(21/89)로 품질 기여 실측 + '즉시 답변' 버튼이 시간 판단을 사용자에게
  이미 위임 → 일괄 품질 하향 대신 현행 유지. 재검토 조건 명시.
- Timestamp: 2026-07-28T12:05:00Z

## REV-20260728T163000-ai-root-graph-cypher-volume [SUBAGENT:backend+qa] — 그래프 sync cypher 호출량 감축
- Related TASK: CHG-20260728T163000-graph-cypher-volume (feature-0002-agent-core, Major §12.3)
- 패널: 2렌즈 독립 fresh-context — (1) backend 정합성(캐시 생명주기·서명 정확성·실패 경로 추적), (2) QA 데이터 무결성(테스트 강도 · 변이 생존 실측).
- **판정: 초안 REJECT — 결함 8건 흡수 후 재검증.** 초안은 "그래프 최종 상태 동일" 을 주장했으나 **거짓**이었다(MAJOR-1).
- BLOCKER/MAJOR:
  - **MAJOR-1**(backend, 실행 입증) 정점 key 에 routine_type 부재 + `sig_cache` 1회 스냅샷 → 동명 FUNCTION/PROCEDURE 두 행 중 두 번째가 stale 항목과 일치해 재작성 skip → 최종 엣지가 종전(마지막 행 우선)과 달라지고 **sync 마다 승자가 뒤바뀌는 영구 flip-flop**. → 첫 방문 게이트.
  - **MAJOR-2**(backend) 서명 SET 예외 삼킴 → aborted tx 위에서 `_sync_row_guard` 가 성공 반환 → 다음 step 커밋이 조용히 ROLLBACK 으로 수렴 → **최대 500행 소실 + ok:true + 워터마크 전진**. → 전파.
  - **B3/MAJOR-3**(양 렌즈 독립 지적) `--full` 의 무조건 재조정 상실 · 운영 탈출구 없음 → 선조회에 실제 ROUTINE_USES 차수 추가(cypher 1회/74ms), 차수 불일치 시 서명 무관 재작성.
  - **B1/B2**(QA, 변이 실측) 초안 테스트 28 변이 중 **17 생존**. `sync_graph` 배선 0% 검증, fake 커서 `fetchall` 이 항상 빈 리스트라 선조회 루프 미실행 → 쓰기/읽기 속성명 불일치가 초록으로 통과(`refs_sig2` 생존). `psycopg.Cursor.__slots__`(feature-0029 B-1) 와 동일한 '라이브 100% 무효인데 초록' 결함면.
  - **M1**(QA) 교차 feature 회귀 실증: 2열 선조회 튜플 언패킹이 feature-0016 `test_metadata_graph_load_spread` 를 깨뜨림(HEAD 1 → 변경 후 2). CI 게이트가 feature-0016 을 돌리지 않아 미검출.
- MINOR: M3 부분엣지 영구 고착 창(REMOVE 선행으로 해소) · M2 선조회 실패 무음 · MINOR-1 중복 fqn 서명/엣지 불일치 · MINOR-2 scope 미필터 전량 덤프 · 서명 계산 위치로 인한 실패지점 이동.
- 조치: 8건 전부 코드 수정. 테스트를 `sync_graph` end-to-end harness 로 교체(11 → **31건**), 속성명 커플링을 정규식 동일성으로 잠금, 롤백 행의 캐시 오염을 end-to-end 로 검증. **역검증 16종 되돌림 → 생존 0**. feature-0016 회귀 복구 확인(HEAD 동일 1건만 잔존, 기존).
- 미채택/보류: `_props_set` 화이트리스트 우회(`refs_sig` 는 UI/LLM 비노출 내부 속성 — `_node_from_props` 가 고정 키만 선택함을 패널이 확인) 유지. `_cq` 제어문자 라운드트립 손실은 pre-existing(보수적 방향: 영구 재작성).
- Timestamp: 2026-07-28T16:30:00Z

## REV-20260728T190300-META-0048-resume-probe-anchored-prime [SKIPPED:라이브 전수 회귀로 대체 — 본 세션 사용자 지시로 subagent 미사용]
- Related Change: personas submodule gitlink a4c1221→153844e (`/_template:resume` 정본 개정 +
  `resume-probe.py` 신설) + `.codex/commands/_template/resume.md` 미러 동기화. pure-meta
  changeset (§18.4).
- 착수 근거 (사용자 요청): "`/_template:resume` 로 root ↔ claude-corp 계정 간 대화를 이어받는
  작업을 해 왔는데, 잘 작동하는 것처럼 느껴지지만 확신하지 않는다. 놓친 성능적·문맥적 이슈로
  잘못 작동하거나 병목이 되는 부분을 검토해 개선해 달라."
- 진단 방법: 이 프로젝트의 **실제 resume 호출 세션 58건을 전수 계량**(`<command-name>` 이
  `_template:resume` 인 세션의 호출 이후 구간 — tool 시퀀스·tool_result 바이트·토큰·사용자
  개입 turn·빈 결과·권한 오류). 스킬 텍스트를 읽고 추론한 것이 아니라 로그 실측이다.
- 적발 6종 (실측치):
  - **D1 Phase 2 전량 prime 이 물리적으로 불가능** — AGENTS.md 3,884행/255KB/~64K tok vs Read
    상한 25K tok (적재 실패 6회). 58 세션 중 **4개만** chunk 로 전량 강행(최대 202KB;
    cache_read 125M~351M tok), **54개는 조용히 생략**. 전량 요구가 준수되지 않으면서 정책
    미도달과 컨텍스트 폭발을 동시에 유발 — 같은 스킬이 세션마다 정반대로 동작.
  - **D2 조기 종료** — 맨 `continue` 37회/17세션(29%, 최다 8회), "제가 의도하지 않은 중단
    입니다" 2회, 동일 세션 내 resume 재호출 13회(최다 5회, 사용자가 잔여 체인을 손으로 나열).
  - **D3 arg 실사용 형태가 스펙에 없음** — title-only 44 / **title+snippet 11(19%)** /
    orig-prompt 2 / empty 1. Step 0 이 통짜 정규화만 하여 스니펫이 제목 토큰에 섞임.
    orig-prompt 1건은 실제 오식별 → 사용자 정정("다른 세션에서 진행되던 내용이 잘못
    전달되었습니다").
  - **D4 기계적 단계 재발명** — inline `python3 -c` heredoc **504회**(세션당 8.7), 세션로그
    Bash 호출 ~470회/997KB, 첫 사용자 대면 출력까지 최대 47 tool·7.5분.
  - **D5 조용한 빈 결과 384회**(세션당 6.6) — sudo 누락·grep miss·파싱 실패가 미구분.
  - **D6 cross-account 소유권 정책 미도달** — §13.2.10 이 존재하나 resume.md 미참조 + D1 로
    대부분 세션이 도달 못함 → 사용자가 "sudo 와 함께 진행해주세요" 2회 개입.
- 조치: ① Phase 2 를 **anchored prime** 으로 교체 — 집행 앵커(§16.3·§16.5·§13.2.4/.5/.7/.10·
  §18.3/.4/.8·§12.2/.3·§15.4.1)만 targeted read (실측 36,872B/~9.2K tok = **6.9배 절감**),
  Gate 를 "전량 읽었나"에서 "앵커 조문을 본문으로 확보했나"로 재정의. ② Phase 1·3 을
  `resume-probe.py` 위임(digest 재계산 금지). ③ arg 2-part 분해(title/anchors/directives) +
  앵커 조각화 + origin tie-break. ④ 6.3 turn 경계 무중단 연속 계약(하드스톱·checkpoint 명시).
  ⑤ 6.0-A cross-account 절 신설. ⑥ Codex shim 동기화.
- 검증 (라이브 실측 — subagent 패널 대신 **재현 가능한 전수 회귀**):
  - **R1 arg 전수 회귀**: 과거 57개 호출 arg 를 probe 에 재투입, ground truth = 그 세션이 조사
    구간에서 실제로 열어 본 원본 세션 UUID. **정확도 9/10 → 27/28(96.4%)** · `none`(미발견)
    **4 → 0** · `ambiguous` **42 → 24** · 확정(single) **9 → 28**. 남은 MISMATCH 1건은
    `feature-0011 P5a Step 4` 처럼 동일 feature 에 세션이 여럿인 본질적 모호 케이스로,
    `single-probable` 의 교차검증 의무가 잡는 지점.
  - **R2 과거 실패 사례 3종 재현**: title-only 요약형 → `single-probable` 정답 / title+anchor →
    `single` 정답(앵커 literal hit) / **과거 오식별(01a5f312)** → `single` 로 정답 `1cd3128f`
    확정 + 잔여 10건·중단 원인 복원. 오식별의 실제 구조는 "같은 텍스트를 본문에 인용한 세션과
    그 텍스트로 시작한 세션이 동점" 이었고 `origin` 위치 판정이 이를 가름(3.5 vs 2.0).
  - **R3 앵커 매칭 취약점 실측·해소**: 사용자가 옮긴 스니펫은 원문 개행이 공백으로 병합되고
    꼬리가 축약된다 — 143자 통짜 grep MISS / 앞 90자 HIT 로 절단 지점을 특정, 연속공백·문장
    부호 경계 조각화로 해소.
  - **R4 성능**: 283 세션 전량 스캔 `--list` **1.35초**, `--resolve` 1.0~14초(앵커 조각 수에
    비례). tracker 판정을 전량 grep → head 검사로 이동해 파일당 최대 28MB grep 제거.
  - **R5 스모크**: 3모드 rc 정상(list 0 / resolve 0 / session 0), 미발견 rc=4, AGENTS.md 부재
    rc=2 fail-loud, `--json` 파싱 OK. **no-arg read-only 부작용 0건**(probe 전후 git status 동일).
  - **R6 정합성**: `py_compile` PASS, 개정으로 폐기된 개념(`resume_tracker_set`/`self_session`/
    `Phase 3A Step 3`) 참조 잔재 **0건**.
- Panel skip 근거 (정직한 경위): 본 세션은 사용자가 "AgentTool 을 요청 없이 호출하지 말라"고
  명시한 컨텍스트라 §18.8 subagent 패널을 돌리지 않았다. 대신 위 R1~R6 을 실행했는데, 이 변경의
  주장(=대상 해소 정확도·prime 비용·조기 종료)은 **라이브 로그 재투입으로 직접 반증 가능한
  종류**이므로 리뷰어 의견보다 강한 근거다. 다만 패널이 볼 수 있었을 축(스킬 텍스트의 지시
  충돌·타 프로젝트 이식성)은 미검증으로 남는다 — 아래 Open Questions.
- Open Questions:
  - `entry.md` 의 Phase 2 Bootstrap Read(15 rows, "본문 전체 누적")는 **동일한 D1 결함을 그대로
    보유**한다. resume 는 위임 문구를 self-contained anchored prime 으로 바꿔 끊었으나, entry
    자체는 이번 범위 밖(사용자 요청은 resume). 별도 cycle 필요.
  - `ambiguous` 24건(42%)은 여전히 택일 질문을 유발한다. 근본 레버는 사용자가 중단 지점 한 줄을
    함께 주는 것(앵커 동반 시 8/8 정확)이므로 no-arg 목록 출력에 그 안내를 넣었다 — 실사용에서
    안내가 행동을 바꾸는지는 다음 사용 주기에 관찰.
  - 소비자 fan-out: 본 커밋은 **이 프로젝트 pointer 만** 갱신한다. 다른 소비자 3개는 각자
    `git submodule update --remote` 시 흡수(§13.2.4 — F0 외).
- Timestamp: 2026-07-28T19:03:00+09:00

## REV-20260729T010301-META-0049-doc-sync-0729 [SKIPPED:doc-sync-index-mirror-additive] — abc3e49f(07-28 doc-sync) 이후 델타 · 신규 머지 perf 3 feature(0027/0028/0029) 인덱스/미러 정합 + wiki 카운트 26→29 + docs/ARCHITECTURE §4/§6 backfill

- **changeset (pure-meta, docs/**·wiki/**·meta/** = META path → verify-completion META mode check #9 게이트)**: `docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0027/0028/0029 backfill — feature 커밋이 STATUS/wiki 카드/ROUTEMAP 은 self-add 했으나 ARCHITECTURE 미터치, 함정 #15)·`wiki/overview.md`(서두 카운트 26→29·0001~0029·§1 서사 "26-feature"→29·§2.1 표 0027/0028/0029 행·§1 (58) 2026-07-28 타임라인[perf 3 feature 신규 + 07-28 사용자향 UX·모델 bundle])·`wiki/Features/_Index.md`(헤더 "26 active"→29·개요 "26 개"→29)·`wiki/Architecture/Overview.md`(헤더 표 26카드/0026→29/0029·§2.3 기능맵 3행·§2.4 의존성 3행)·`wiki/Architecture/Module-Map.md`(§2.2 MOC 포인터 0026→0029)·`wiki/hot.md`(Last Updated 07-29·Key Recent Facts prepend·Active Threads 등 기존 섹션 전부 보존)·`wiki/Log.md`(본 정합 ledger)·`meta/REVIEW.md`(본 entry). **feature-0027/0028/0029 카드·_Index MOC 행·wiki/Index.md(29-feature·카드29)·wiki/Log.md 개별 엔트리·docs/STATUS.md 행 은 feature 커밋(149c2efa/6af769e4/d4d868d3)이 이미 self-add → 재생성 안 함.** 동반 operational(feature-0003 별도 commit, REV-20260729T010301-doc-sync-rn-0729 [SKIPPED:non-policy-doc]): 릴리즈노트 기존 2026-07-28 블록에 6항목 append.
- **[SKIPPED] 사유**: 색인/미러 additive — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0040~0045 additive 선례 동일 slug). perf 3 feature 상태는 정본 TASK.md 위험도(0027 Minor~Major 경계·0028/0029 Major 경계)·frontmatter feature_status 기준. **무변경 정직**: docs/STATUS.md noChange(gen-status --check rc=0[frontmatter 8·passthrough 21·신규 0]·0027/0028/0029 행 이미 존재·정확)·docs/SECURITY.md noChange(§27 feature-0026·§28 model-access 이미 self-add·perf 3 feature 인가 불변)·docs/DECISIONS.md noChange(ADR-20260728T120000 redteam-gating·ADR-20260727T190000 cycle-privilege 이미 델타에 self-add·4자리 프로젝트 ADR 0 → wiki Decisions 미러 무변경)·passthrough 행 무확장(ADR-0031 §1). **알려진 pre-existing drift(defer·이번 run 밖)**: docs/STATUS.md §5 prose "등록 17/디렉토리 18"(reality 28/29)는 feature-0016 번호충돌 사람결정 보류 마커 이래 frozen·전 doc_sync 미터치·정본 STATUS 표 행/wiki 카드/카운트는 fresh → 사람이 0016 번호 결정 후 갱신(doc_sync 자율 scope 밖).
- **검증(타깃별 실질 + ULTRACODE 2-round 적대)**: wiki feature-count sweep stale-26=0(ground-truth 29=ls unit/feature-*·wiki/Features/feature-*.md=29 cards·6 token-edit=8참조 중 stale 6[Index.md 2참조는 feature 커밋이 이미 29])·신규 wikilink([[feature-0027/0028/0029]] 카드 실재)·pipe 무결(§4 2열|=3·§6 4열|=5·overview §2.1|=5·Architecture §2.3|=4/§2.4|=5)·각 타깃 표 1행씩(중복 0). §-qualify(ARCH 신규행 bare § 0·DECISIONS.md ADR·TASK.md §2.1 doc-qualify). gen-status --check rc=0·ssot-lint rc=0(4 WARN=pre-existing baseline). 정본 독립 재검증(함정 #11): model.access RBAC=feature-0003(1b9ee97a Task-Cycle·커밋본문 'feature-0007 R2'는 동기 리뷰 참조일 뿐 코드 귀속 아님)·사용기록 백엔드=feature-0002(e5860932)·self-check=feature-0021(3e2aae93). **ULTRACODE 적대 2-round**: R1 wf_63a962eb(3-타깃 analyze→타깃-스코프 verify, cross-fault 회피 함정 #12) — RN item3 좌우 오귀속·item5 즉시반영·wiki timeline/hot feature-0007 오귀속·ARCH thinking ADR 과귀속 4건 적발·전건 정본 재검증 후 교정. R2 wf_b705e7ba(3 diverse-lens on applied diff) — 3렌즈 clean·minor 2 교정(wiki §2.4 feature-0028 에 feature-0002 dep 정본 §6 미러 정합·hot.md trailing newline)·STATUS §5 defer 정당 재확인.
- **인용 무결성 확인**: 본 entry(META-0049) staged 실재. 동반 operational commit(feature-0003 release-notes-data.js + companion TASK/MODIFY/FUNCTION/TEST/REVIEW) 별도 — 서빙 static(릴리즈노트) 배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만).
- **Human Approval Needed**: 아니오 (색인/미러 additive·구조/보안 경계 불변·제품 런타임 동작 0·pure-meta). 무인 스케줄 run — landing(push/merge)·배포·end-state 서빙 검증은 cron wrapper v3 소유(스킬 로컬 commit 만·감지·보고만).
## REV-20260729T091700-ai-root-ui-copy-bloat [SKIPPED:프로젝트 학습 기록 1건 append — 제품 코드 무변경]
- Related TASK: (project-level) docs/LEARNINGS.md — LRN-20260729T091700-ai-root-ui-copy-bloat
- Trigger: changeset 이 `docs/LEARNINGS.md` append 전용 (§18.8 키워드 비매칭, 제품 코드·정책 계약 무변경)
- Timestamp: 2026-07-29T18:17:00+0900
- Verdict: PASS
- Human Approval Needed: no

### 기록 근거
사용자가 **반복 관측된 현상**으로 지목했다 — "장황하고 현학적이며 지루한 설명문이 UI 에
추가되는 현상이 프로젝트 개발 중 지속적으로 확인되고 있습니다". 직전 사례(feature-0021 추론
탭 안내 260자 → 57자, CHG-20260729-0007)를 단발 교정으로 끝내면 다음 기능 cycle 에서 같은
방식으로 재발한다. §11.2 학습 기록 정책에 따라 `mistake` 로 남기고, 사용자 피드백으로 확인된
학습이므로 `verified: true` 를 붙였다.

### 기록에 담은 것 — "다시 하지 않으려면 무엇을 알아야 하나"
- **근본 3축**: (a) 설명 대상이 사용자의 필요가 아니라 *구현자의 지식*, (b) FUNCTION.md·PR
  문장이 그대로 UI 로 복사되며 문서 톤이 따라옴, (c) 정확성 게이트만 있고 **분량 게이트가 없어**
  "틀린 말이 아니면" 전부 통과.
- **판별 규칙**: UI 안내에 넣지 않는 4종(조작법·타 화면 경로·내부 계약·설계 정당화)과 넣는
  2종(무엇인지 1문장 · 비가역/비용 경고).
- **실측 기준선**: 교정본 57자 · 현행 잔여 4건(335/224/168/141자)을 §8.1 제안으로 함께 기록해,
  다음에 정리할 때 대상이 이미 특정돼 있게 했다.

### 한계 (정직 표기)
`docs/LEARNINGS.md` 는 §10.2 **참조 읽기**(최근 10건 권장)라 매 세션 자동 로드가 아니다. 기록만
으로 재발이 막힌다고 보지 않는다 — 상시 게이트로 올리려면 `docs/CONVENTIONS.md` 에 UI 카피
규약 한 줄이 필요하고, 그것은 프로젝트 수준 rewrite 문서(§13.1)라 사용자 결정 사항으로 남긴다.

## REV-20260730T010301-META-0050-doc-sync-0730 [SKIPPED:doc-sync-index-mirror-additive] — 8b0c7ea3(07-29 doc-sync) 이후 델타 · 신규 머지 feature-0030 인덱스/미러 정합 + wiki 카운트 29→30 + docs/ARCHITECTURE §4/§6 + SECURITY §29/§30 backfill

- **changeset (pure-meta, `docs/**`·`wiki/**`·`meta/**` = META path → verify-completion META mode check #9 게이트)**: `docs/ARCHITECTURE.md`(§4 기능맵·§6 의존성맵 feature-0030 backfill — feature 커밋 030a5ff1 은 ROUTEMAP/STATUS/wiki 카드·MOC·Index 카운트·Log·hot 을 self-add 했으나 ARCHITECTURE 미터치, 함정 #15)·`docs/SECURITY.md`(§29 실행 타임아웃 연장 승인 = `conversation.extend.{own,any}` 신규 권한 코드 2 + own 7역할 1회 backfill·비용 유발 승인 표면 / §30 지식베이스 메타데이터 제품 스코프 경계 = 접근DB allowlist 강제·cross-product 주입 격리, 신규 권한 코드 0)·`wiki/overview.md`(서두 카운트 29→30·0001~0030·§2.2 "29-feature"→30·§2.1 표 feature-0030 행·§1 (59) 2026-07-29 타임라인[feature-0030 신규 + 07-29 사용자향 UX bundle house-style])·`wiki/Features/_Index.md`(메타표 "29 active"→30·§1 개요 "29 개"→30)·`wiki/Architecture/Overview.md`(메타표 29카드/0029→30/0030·§2.3 기능맵 1행·§2.4 의존성 1행)·`wiki/Architecture/Module-Map.md`(§2.2 MOC 포인터 0029→0030)·`wiki/hot.md`(Last Updated 07-30·Key Recent Facts prepend·Active Threads 등 기존 actionable thread 전부 보존)·`wiki/Log.md`(본 정합 ledger, 파일 맨끝 append·실관례 형식 함정 #5)·`meta/REVIEW.md`(본 entry). **feature-0030 카드·`wiki/Features/_Index.md` MOC 행·`wiki/Index.md` 카운트 2참조(이미 30)·`wiki/Log.md` 개별 엔트리·`docs/STATUS.md` 행(gen-status frontmatter-driven) 은 feature 커밋 030a5ff1 이 이미 self-add → 재생성 안 함(함정 #20 tell: `git show --stat` 로 self-add 표면 선확인).** 동반 operational(feature-0003 별도 commit, REV-20260730T010301-doc-sync-rn-0730 [SKIPPED:non-policy-doc]): 릴리즈노트 신규 2026-07-29 블록 13항목 prepend.
- **[SKIPPED] 사유**: 색인/미러 additive — 정책 의미·구조 결정·신규 ADR·enforcement 경계 변경 0. codex 패널 불요(META-0040~0049 additive 선례 동일 slug). feature-0030 severity=**Major**(정본 `unit/feature-0030-ask-timeout-extension/docs/TASK.md:59` 위험도 필드)·`feature_status: in-progress`(frontmatter)·기본값 **ON**(`AGENT_TIMEOUT_EXTENSION_ENABLED` default=1, `shared/runtime_settings.py`) + 배포 80cc7aeb 후 PB-0008 라이브 검증 PASS(TASK.md §7 전항 [x]) — '기본 OFF' 아님(함정 #16 분리 병기). feature-local **결정**(DECISIONS.md 9줄 빈 스텁 → 'ADR' 라벨 미사용, 함정 #18b).
- **무변경 정직**: `docs/STATUS.md` noChange(`gen-status --check` rc=0 [frontmatter 9·passthrough 21·신규 0]·feature-0030 행 이미 존재·정확 / passthrough 행 무확장 = ADR-0031 §1 rollup 누적 금지·META-0037/0038 선례, 함정 #14)·`docs/DECISIONS.md` noChange(델타 43 non-merge 커밋 메시지 전수 `ADR-` grep 0건 → 신규 프로젝트 4자리 ADR 0 → wiki Decisions 미러 무변경)·`docs/PROJECT.md`/`docs/TEMPLATE_UPGRADE.md` noChange(394b987d 의 `template_version` v3.40.0→v3.43.0 frontmatter 1줄 self-bump 뿐)·`docs/LEARNINGS.md`/`docs/ROUTEMAP.md`/`docs/improvements/conversation-audit/FRICTION_LEDGER.md` noChange(델타 커밋 f36a2165·770c436b·274174e5·d605874e·4e9d03f9·69db6792·43eac41d·030a5ff1 이 self-update 완료)·`docs/SECURITY.md` §8.2/§8.2.1/§8.6 재색인 안 함(08172c93 self-add). cache-buster 무편집(`?v=dev` 고정·빌드 자동주입, 함정 #9 — wrapper 헤더의 수기 bump 지시는 07-12 ITEM-09 이전 regime 이라 부적용).
- **검증(타깃별 실질 + verify 한계 명시)**: wiki feature-count sweep stale-29=**0**(ground-truth 30 = `ls -d unit/feature-*`; 갱신 6참조/4파일 — `Index.md` 2참조는 feature 커밋이 이미 30)·신규 wikilink 대상 실재([[Features/feature-0030-ask-timeout-extension]])·pipe 무결(ARCH §4 line74 `|`=3 / §6 line118 `|`=5 / wiki §2.3 line103 `|`=4 / §2.4 line136 `|`=5 / overview §2.1 line291 `|`=5, 형제 행 feature-0029 와 동일)·SECURITY §번호 충돌 0(직전 최댓값 §28 → §29/§30 신설, doc_sync 의 top-level 절 신설은 cfa647df(§24)·aac76889(§25)·4dc1dcbc(§26) 선례)·§-qualify(ARCH 신규행 bare § 0 — `AGENTS.md §18.8.2`·`SECURITY.md §29`·`TASK.md §2.1` doc-qualify, 함정 #19b)·`gen-status --check` rc=0·`ssot-lint` rc=0(4 WARN = tracked `.env*.bak*` pre-existing baseline). **verify-completion 한계**: check #1·#5(STATUS)는 v1.1 deferred 라 STATUS·wiki 정합을 보증하지 않음 → 위 타깃별 기계 검증으로 대체.
- **적대검증(ULTRACODE R1, wf_0663e5aa — 9 에이전트: 3-타깃 analyze → 타깃별 2 diverse-lens verify, cross-fault 회피 함정 #12)**: 6 verifier 전원 `holdsAll=false` 로 결함 적발 — MAJOR 3(① RN item8 제품 선택기 위치 '입력창 아래' 오안내 = 2-렌즈 독립 합치 → 위치 중립 서술로 교정 ② `docs/CONVENTIONS.md §12` 번호 충돌을 draft 가 'noChange·정합 불요' 로 오종결 = 2-렌즈 합치 → 아래 report-only 로 승격)·MINOR 6(RN summary 13항목 중 11만 서술·item13 '기본 접힘' 오기·item13 07-27 중복 → 전건 교정 / wiki §2.4 per-call 상한 '불변' 오기 → 코드 `agent_core.py:5218-5220` `_ext_llm_timeout = max(max(5, AGENT_TIMEOUT_SEC), 900)` 근거로 '15분 천장까지만 상향' 정정 / Log entry 델타 커밋 수 '~40' → '43 non-merge' 정정 / ARCH bare `§18.8.2` → doc-qualify / SECURITY §29 carve-out misattribution → '사용자 결정 2026-07-29'[정본 `unit/feature-0030-.../docs/REVIEW.md:14-16`] 로 정정, **§30 의 carve-out 표기는 정본이 실제로 carve-out 을 명시하므로 유지**). 오케스트레이터가 정본 독립 재검증(함정 #11) 후 전건 반영. 워크플로 분석 에이전트의 무단 파일 mutation 0(commit 전 `git status` 확인, 함정 #5/#21f 재발 없음).
- **report-only(doc_sync 자율 scope 밖 — §13.1 프로젝트 수준 rewrite 문서 구조 변경은 사람이 반영)**: ① **`docs/CONVENTIONS.md` top-level `## 12.` 번호 충돌(in-window 신규)** — 394b987d 가 :535 에 `## 12. 사용자 대면 텍스트 (UI copy, v3.43.0+)` 를 self-add 해 기존 :473 `## 12. 마이그레이션 안전 — expand/contract` 와 충돌. `CONVENTIONS §12`=expand/contract 로 읽는 살아있는 참조가 `AGENTS.md:402`·`bin/deploy-web.sh:269/659/931`(하드 ABORT die 메시지)·CONVENTIONS 내부 :497/:524/:532 에 실재 → 배포 게이트가 인용하는 번호라 모호성 해소 필요. 같은 커밋이 verify-completion check #13→#18 재번호로 동종 충돌을 self-handle 한 선례가 있으므로 신규 UI-copy 절을 미점유 번호로 재번호하는 것이 정합안이나, doc_sync 가 직접 재번호하지 않고 제안·보고로 남김. ② **`docs/LEARNINGS.md` `LRN-20260729-0001` 3중 ID 충돌** — :24(mistake, d605874e)·:376(pattern, 274174e5)·:393(quirk, 770c436b) 이 서로 다른 3개 교훈에 동일 ID. AGENTS.md §13.1 이 경고한 병렬 순번 충돌(권고 = timestamp+branch 형식, 같은 윈도우의 `LRN-20260729T091700-...` 는 규약 준수)이고 외부 참조가 이미 갈라짐(`unit/feature-0003-.../docs/REPORT.md:1821` vs `FUNCTION.md:2194`). LEARNINGS 는 append-only + `unit/*/docs/*` 는 operational(함정 #14b)이라 doc_sync 가 양쪽 동시 수리 불가 → 보고. ③ **`unit/feature-0030-ask-timeout-extension/docs/FUNCTION.md:35-36`·`TASK.md:85-87`** 이 codex P1-3(REVIEW.md REV-20260729-0001)이 revert 한 pre-review 설계('LLM 타임아웃 2층/3층 전부 해제')를 잔존 서술 — 코드·REVIEW·REPORT·wiki 카드는 per-call 900s 상한 유지가 정본. `unit/*/docs/*`=operational → feature-cycle 소관. ④ **`docs/STATUS.md §5 prose "등록 17/디렉토리 18"**(reality 30) 는 feature-0016 번호충돌 사람결정 보류 마커 이래 frozen·전 doc_sync 미터치(함정 #21e) → 사람이 0016 번호 결정 후 갱신. ⑤ `wiki/Architecture/Overview.md §3 특징` 진화 목록이 2026-07-01 에서 동면(0019~0030 미반영) — 서사 리라이트라 색인 정합 범위 밖.
- **reconcile-first(자가수리 ①)**: doc delta 계산 *전* 서빙 static surface 파리티 확인 — 라이브 서빙 `release-notes-data.js` md5 `1fa39008…` == `origin/main` 동일 파일 md5 **일치** + `/healthz` 200(자가서명 TLS, `curl -k --resolve`) → **배포 갭 없음**. 배포 이미지 커밋 라벨 vs 브랜치 HEAD 같은 coarse 비교는 고병렬 머지로 상시 오탐하므로 갭 근거로 쓰지 않음.
- **landing/배포 소유권(자가수리 ④)**: 실행환경 헤더가 LANDING/DEPLOY OWNERSHIP v3 를 명시 위임 → doc_sync 는 현재 `ai/claude/doc-sync-20260730-010301` 브랜치에 **로컬 commit 까지만**. push·main ff-머지·docker 배포는 wrapper 소유(이중 landing/배포 racing 방지). 서빙 static(릴리즈노트) 변경 있음 → wrapper 배포 시 `inject_asset_stamp.py` content-hash 재주입으로 새 콘텐츠 서빙. `committed` != `serving` — end-state 는 wrapper 배포 후 확정.
- Timestamp: 2026-07-30T01:03:01+09:00
## REV-20260729T120000-ai-root-inference-detail-metrics [SUBAGENT:backend] — inference_ms 내부 분해 계측
- Related TASK: CHG-20260729T120000-inference-detail-metrics (feature-0002-agent-core, Minor §12.3)
- 패널: fresh-context 적대 리뷰 1렌즈(계측 정합성 + 테스트 강도 + 라이브 SQL 실행 검증). BLOCKER 0.
- **판정: 초안 REJECT — 결함 9건 흡수 후 재검증.** 문서가 주장한 기능(비정상 경로 커버)이 **실재하지 않았고**, 잔차가 체계적으로 과소평가되고 있었다.
- MAJOR:
  - **M-1** "비정상 종료 경로에도 분해를 싣는다"는 거짓 — `_slim_result` allowlist + meta 없는 mirror 로 **영속 경로 없음**(죽은 코드). 주장 철회 + 제거, 미커버로 명시.
  - **M-2** 같은 자리를 `break` 정상 경로도 지나는데 now_perf 가 메시지 저장·큐레이션(25~35초) 뒤 → 잔차 범벅(이 계측이 피하려던 오도).
  - **M-3(설계)** `llm_ms` 가 `_call_llm` 래퍼 전체를 측정 → 첨부 로드·messages 재조립·settings DB 읽기·usage INSERT 가 llm_ms 로 청구돼 **찾으려던 잔차가 사라지고** 기준선과 비교 불가 → ContextVar 로 provider 왕복만 집계.
  - **M-4(산술)** §3b-3 `avg(ms/n)` → 라이브 실증 228ms 를 9,025ms(40배) 과대보고 → `sum(ms)/sum(n)`.
  - **M-5(테스트)** 순수 빌더만 검증해 누산 배선 0% — 변이 5종 전부 생존.
- MINOR: 누산이 LLM 오류 try 본문 안(성공 라운드가 provider 오류로 둔갑) · finally 무가드(원 예외 대체) · **모델 제어 도구명이 meta_json JSON 키로 유입 → NUL 시 jsonb 실패를 mirror 가 삼켜 답변 행 소실**(라이브 재현) · 문서만 있고 쿼리 없던 llm_usage 교차검증 · 도달 불가 상태를 검증하던 테스트.
- 조치: 9건 전부 수정. 테스트 7 → **16건**(빌더 + 누산기 계약 + 소스 배선 계약), 패널 생존 변이 6종 되돌림 **생존 0**. feature-0002 전체 스위트 회귀 0.
- 패널이 clean 판정한 축: red-team 의 `inference_ms` 포함 관계(영속 경로 기준 정확) · 누산기에 red-team LLM/도구 미유입 · 스코프/클로저(모든 early return 이 도달 불가) · try/finally 제어흐름 · 라운드당 1회 누산(empty_retries 포함 정확) · 쓰기 경로 상한(40자·top-6, 최악 ~550B) · 신규 SQL 문법·빈 입력 동작.
- Timestamp: 2026-07-29T12:00:00Z

## REV-20260730T193000-ai-root-init-prologue-metrics [SUBAGENT:backend] — init_ms 프롤로그 계측 + 잔차 노출
- Related TASK: CHG-20260730T190000-init-prologue-metrics (feature-0002-agent-core, Minor §12.3)
- 패널: fresh-context 적대 1렌즈(계측 정합성 · 라이브 SQL 실행 · 변이 실측). BLOCKER 0 / MAJOR 5 / MINOR 3.
- **판정: 초안 REJECT — 8건 흡수 후 재검증.** 초안의 "기존 `init_detail` 키 무변경" 주장이 라이브에서 반증됐다.
- MAJOR: ① bool 플래그가 기존 §3b(`jsonb_each_text` 전 키 `::float`)를 죽임(라이브 재현) → 수치 키. ② §3b-0 이 구/신 행 혼합 모집단을 평균해 other_pct 를 과소보고(9구+1신에서 "2%") → 신규 키 필터. ③ 롤업은 무조건·leaf 는 예외 시 누락 → `max(Σleaf, 롤업)` 아니면 knowledge 전체(최대 6,924ms)가 거짓 미귀속. ④ `ds_resolve_ms` 가 지배 경로에서 엉뚱한 함수 측정(복수 vs 단수) → 누산. ⑤ 12 변이 중 7 생존(소스 문자열 검색의 한계).
- MINOR: eval 경로 미기록(§3b-0 왜곡) · 멀티 span 이 단일보다 좁음 · 빌더 비멱등.
- 조치: 8건 전부 수정. 테스트 10 → 17건, 역검증 12종(초안 5 + 패널 생존 7) 생존 0. feature-0002 전체 스위트 회귀 0. §3b-0 라이브 실행 확인.
- 패널 clean: 선언 이동(early-return 9곳 무해·재진입 없음) · 롤업 전제(63행 오차 ≤0.3ms) · span 상호배타 · 영속 경로(직전 cycle dead-code 미재발) · 프론트 무영향.
- Timestamp: 2026-07-30T19:30:00Z

## REV-20260731T010301-META-0051-doc-sync-0731 [SKIPPED:doc-sync-index-mirror-additive] — 7fd73e3e(07-30 doc-sync) 이후 델타 52 커밋 · 신규 머지 feature-0031~0034 인덱스/미러 정합 + wiki 카운트 30→34 + docs/ARCHITECTURE §4/§6 + SECURITY §31/§32
- 변경 성격: 색인·미러 additive(정본 재서술 0). 정본(`unit/<id>/docs/*`)은 미변경 — doc_sync 는 정본을 쓰지 않는다.
- 타깃별 실질 검증: wiki feature 카운트 ground-truth 대조 PASS(`ls -d unit/feature-*`=34 · 카드 34 · stale '30' 잔존 0건 grep 전수) · 신규 wikilink 4건 대상 파일 존재 PASS · `bin/gen-status.sh --check` rc=0(idempotent) · `bin/ssot-lint.sh` 4 WARN(기존 `.env.bak-*` secret·불변, 신규 0) · SECURITY §31/§32 heading resolve PASS.
- 적대검증(ULTRACODE wf_b0e71477 — 6분면 analyze → 분면-스코프 refute, 12 에이전트·1.61M tok): 5 MAJOR + 9 MINOR 반영. 주요 교정 — ① SECURITY feature-0007 절의 'on-prem 잔류 lane 0'/'LOCAL_LLM 참조 0' 이 정본 REVIEW P2-2·P1-3 과 모순(KB 임베딩은 여전히 로컬 Ollama bge-m3, `_select_llm_provider()` Local gateway 층 잔존·미결) → 층 구분 서술로 정정 ② ARCHITECTURE feature-0016 임베딩 pass 상한 '1000→300행' 이 출하값(600행·배치 100→25)과 모순 → 정정(정본 TASK T-EC2 문면은 내부모순·report-only) ③ feature-0025 카드의 '7일 stale·결정적 정렬' 이 정본(24h·mtime DESC)과 반대 → 정정 ④ wiki 0031 행의 'Stage 0~3 하루 1단계 승격' 이 'Stage 3 은 운영자 승인 전용' 을 누락 → 3표면 정정 ⑤ Log/hot 의 '신규 4건 전부 배포 검증 대기' 가 feature-0032 PB-0008 PASS 와 모순 → 정정 ⑥ ARCHITECTURE feature-0025 ADR 범위 06~08→05~08 ⑦ SECURITY §32 P1 3건 구성 정정.
- 무변경 정직: `docs/DECISIONS.md` noChange(이번 창 신규 4자리 project ADR 0 — ADR-003·ADR-0025-05~08·ADR-0031-* 는 전부 feature-local 정본) · `docs/RELEASE_NOTES.md` noChange(07-13 이후 10회 연속 doc-sync 미터치 = 사실상 폐지 regime, 무인 런이 타깃을 자기 재량으로 되살리지 않음 — report-only) · `docs/PROJECT.md`/`CONVENTIONS.md` noChange · STATUS passthrough 21행 무확장(ADR-0031 §1 셀 누적 금지).
- report-only(§13.1 사람/feature-cycle 소관): feature-0031~0034 의 `feature_status_date`/`feature_status_note` 부재로 STATUS 신규 4행이 sparse(feature-0025 와 동일 — doc_sync 는 정본 frontmatter 를 쓰지 않는다) · `docs/STATUS.md` frontmatter `source_of_truth: true` ↔ DOC_REGISTRY '인덱스 only' 모순 · `docs/ARCHITECTURE.md` `## 8.` 절 번호 2회 중복 · feature-0031 ADR-0031-07 thin 하한 '40' ↔ 코드/REVIEW '20' 내부모순 · feature-0016 TASK T-EC2 '300행/서브배치 ≤5회' ↔ 출하 600행 내부모순 · project ADR-0031 ↔ feature-0031 ADR-0031-* ID 네임스페이스 충돌 실현 · `wiki/Glossary/_Index.md` Entry 수 24↔26(prior-window drift) · wiki Decisions ADR 카운트 2참조 stale(prior-window).
- landing/배포 소유 = wrapper 위임(무인 cron) → 로컬 commit 까지만. reconcile-first: 라이브 서빙 static 파리티 갭 0(라이브 `generated`=2026-07-29 = 커밋 전 origin/main 일치).

## REV-20260731T093000-ai-root-query-embed-degrade-visibility [SUBAGENT:backend] — 질의 임베딩 강등 가시화 + 타임아웃 재조정
- Related TASK: CHG-20260731T090000-query-embed-degrade-visibility (feature-0002-agent-core, Minor §12.3)
- 패널: fresh-context 적대 1렌즈(런타임 실행 + 라이브 SQL + 변이 실측). **BLOCKER 1 / MAJOR 3 / MINOR 5**.
- **판정: 초안 REJECT — 기능이 실제로 동작하지 않았다.**
  - **BLOCKER-1** 발행부 소요 필터(`v >= 0.1`)가 강등 플래그 0.0 을 탈락시켜 **언제나 "강등 0%"** 보고. 종전 무음보다 나쁜 거짓 안심. 런타임 실증(성공 시 published 에 키 존재 / 강등 시 published={}).
  - **MAJOR-1** 5s 근거가 **16자 질의 한 종류** 측정이었다 — 지연은 입력 길이 비례(5,712자 4,172ms). 라이브 최대 5,996자에서 경계. "중간 체제 미관측" 주장도 반증. → 12s.
  - **MAJOR-2** 콘솔 spec default 가 20 잔존 → 표시 불일치 + '초기화' 가 변경을 조용히 되돌림.
  - **MAJOR-3** 변이 7 중 2 생존(발행 순서 이동 · §3b-1 삭제) — 소스 문자열 검색의 한계. **직전 cycle 의 동일 교훈을 문서에 적어놓고 재생산.**
- 조치: 8건 전부 수정. 테스트 6 → 9건(발행 필터를 소스에서 추출해 실제 평가 + config↔spec parity + 소비처 존재). 역검증 5종 생존 0. 전체 스위트 회귀 0.
- 패널 clean: 발행 순서 · 게이트 스코프(fail-safe) · 잔차 상호작용 · 타임아웃 blast radius · 재시도 증폭 없음 · §3b-1 SQL · §3b 비회귀 · 프론트 무영향.
- Timestamp: 2026-07-31T09:30:00Z

## REV-20260804T010301-META-0052-doc-sync-0804 [SKIPPED:doc-sync-index-mirror-additive] — 2df27587(07-31 doc-sync) 이후 델타 26 비-머지 커밋 · 신규 머지 feature-0035~0038 인덱스/미러 정합 + wiki 카운트 34→38 + docs/ARCHITECTURE §4/§6 + SECURITY §33/§34/§35
- 변경 성격: 색인·미러 additive(정본 재서술 0). 정본(`unit/<id>/docs/*`)은 미변경 — doc_sync 는 정본을 쓰지 않는다.
- 타깃별 실질 검증: wiki feature 카운트 ground-truth 대조 PASS(`ls -d unit/feature-*`=38 · 카드 38 · stale '34' 잔존 **0건** grep 전수 8참조/5파일 sweep) · `wiki/Features/_Index.md`·`wiki/overview.md` §2.1 표 각 38행 · `wiki/Architecture/Overview.md` §2.3/§2.4 + `docs/ARCHITECTURE.md` §4/§6 에 feature-0035~0038 전원 등재 · `bin/gen-status.sh --check` rc=0(frontmatter 17 · passthrough 21 · 신규 0 — idempotent) · `bin/ssot-lint.sh` 4 WARN(기존 `.env.bak-*` secret·불변, 신규 0) · SECURITY §33/§34/§35 heading resolve PASS.
- 적대검증(ULTRACODE wf_c3ba6dd3 — 5타깃 analyze → 타깃-스코프 refute 2렌즈, cross-fault 회피 함정 #12): 오케스트레이터가 **정본 독립 재검증**(함정 #11) 후 3건 교정 반영 — ① `docs/ARCHITECTURE.md` feature-0038 행 `admin.js 14,007→13,058줄(-949)` → **13,057줄(-950)**(`git show a54704bb^:…/admin.js | wc -l`=14007 vs `git show a54704bb:…`=13057 실측; 정본 3중 불일치 13,050/13,058/13,057 은 report-only) ② `export 접두 5개` → **4개**(정본 `unit/feature-0038-frontend-modularization/docs/MODIFY.md:36` 문면) ③ `admin.html 무변경` → `admin.html \`<script>\` 배선 무변경(포인터 주석 1줄만)`(`git show --numstat a54704bb` = admin.html 1/1 실측 + 정본 CHG-20260803T193000 Files). **반증 채택**: verifier 의 `docs/STATUS.md` frontmatter `sources:` 4엔트리 백필 요구는 오케스트레이터 실측으로 **기각**(0035~0038 4건 모두 이미 등재 — `grep -c` 각 1).
- `docs/STATUS.md`: 기능현황표(gen-status 마커 구간)는 **무변경**(`--check` rc=0, 표 38행=ground truth). 표 아래 **미머지 활성 worktree note 만** 정정 — 문면이 열거한 `feature-0002·0003·0009`(모두 `ahead=0`) 는 실측 부재이고 현행 활성 worktree 는 6개(`ai/claude/feature-0007-llm-timeout-align`·`ai/claude/feature-0012-web-router-modularization`·`ai/claude-corp/feature-0016-node-role-viz`·`ai/claude-corp/feature-0038-c3-audit-settings`·`ai/root/perf-cycle-label-fix`·`ai/root/ssot-roadmap-refresh`) → DOC_REGISTRY In-flight 정책대로 note 갱신(셀 누적 0, ADR-0031 §1 준수).
- 무변경 정직: `docs/DECISIONS.md` noChange(이번 창 신규 4자리 project ADR 0 — feature-local ADR 만 증가) · `docs/PROJECT.md` noChange · `docs/RELEASE_NOTES.md` noChange(07-13 이후 doc-sync 미터치 = 사실상 폐지 regime, 무인 런이 타깃을 자기 재량으로 되살리지 않음 — report-only) · STATUS passthrough 21행 무확장. `docs/CONVENTIONS.md` 는 feature-0038 프론트 분할로 소멸한 `styles.css` 단독 서술 1곳만 정정(신규 규약 제정 0).
- report-only(§13.1 사람/feature-cycle 소관): feature-0035/0036/0037 의 `feature_status_date`/`feature_status_note` 부재로 STATUS 행 sparse(doc_sync 는 정본 frontmatter 를 쓰지 않는다) · `docs/CONVENTIONS.md` §10·§12 절 번호 각 2회 중복(내부 자기참조 `§12` 가 모호) · feature-0038 정본의 admin.js 라인수 3중 불일치(13,050 / 13,058 / 실측 13,057) · `docs/PROJECT.md` §9.2 서비스 목록 5종 ↔ 실제 compose 괴리 · `docs/STATUS.md` §5 전체 진행률 본문이 등록 기능 17 로 표 38행과 괴리 · `docs/ARCHITECTURE.md` `## 8.` 절 번호 2회 중복(prior-window) · project ADR-0031 ↔ feature-local ADR-0031-* ID 네임스페이스 충돌(prior-window).
- reconcile-first(자가수리 ①): 라이브 서빙 static 파리티 갭 **0** — 커밋 전 `curl -k https://localhost:443/static/release-notes-data.js` sha256 = `origin/main` blob sha256(`5d380993…`, 152,900B) 일치.
- landing/배포 소유 = wrapper 위임(무인 cron v3) → 로컬 commit 까지만. push/merge/deploy 는 wrapper.
- Timestamp: 2026-08-03T16:03:01Z
## REV-20260805T010301-META-0053-doc-sync-0805 [SKIPPED:doc-sync-index-mirror-additive] — 34ee7448(08-04 doc-sync, META-0052) 이후 델타 36 커밋(17 머지, git-date 전부 2026-08-04) · 신규 머지 feature-0039 색인 + wiki 카운트 38→39 + docs/ARCHITECTURE §4/§6 + SECURITY §36/§37 + feature-0038 완결 stale 정정
- 변경 성격: 색인·미러 additive + stale 정정(정본 재서술 0). 정본(`unit/<id>/docs/*`)은 미변경 — doc_sync 는 정본을 쓰지 않는다.
- 타깃별 실질 검증: wiki feature 카운트 ground-truth 대조 PASS(`ls -d unit/feature-*`=39 · 카드 39 · stale '38' 잔존 **0건**, 전 wiki grep 전수 sweep 8참조/5파일 = Index 2·_Index 2·Architecture/Overview 1·Module-Map 1·overview 2) · 표 행수/파이프 균일성 기계 검증(`wiki/overview.md` §2.1 39행 전부 파이프 5 · `wiki/Architecture/Overview.md` §2.3 39행 전부 파이프 4 · §2.4 35행 전부 파이프 5 · `docs/ARCHITECTURE.md` §4 feature-0039 행 파이프 3 · §6 파이프 5, 형제 행과 동일) · 신규 wikilink 18건 전건 resolve · 신규 §참조 전건 heading resolve(`AGENTS.md` §15.4.1:1419 · §18.8:2474 · §8.1:304 · `docs/CONVENTIONS.md` §14:556 · `docs/SECURITY.md` §36:1085 · feature-0016 `TASK.md` §82:2405 · feature-0039 `FUNCTION.md` §9) 및 §4/§6 교차문서 참조 doc-qualify house-style 준수(bare §NN 0) · `bin/gen-status.sh --check` rc=0("frontmatter 18 · passthrough 21 · 신규 0") · `bin/ssot-lint.sh` rc=0(4 WARN 전부 pre-existing tracked `.env*.bak*`, 본 변경 무관).
- 적대검증(ULTRACODE `wf_048fd776` — 3타깃 병렬 analyze → 타깃-스코프 refute 렌즈, cross-fault 회피): 오케스트레이터가 **정본·라이브 독립 재검증**(함정 #11) 후 초안 결함 **3건 교정** — ① **초안이 feature-0039 를 "배포·root crontab 4줄 제거 미수행 · 그 창에는 백업이 하루 2회" 로 서술(정본 TASK.md 체크박스 근거)했으나 라이브 실측은 반대**: `repo-ops-scheduler-1` Up 6h **healthy** · 그래프 sync 증분 30분 주기 rc=0(2026-08-05 00:30·01:00 로그) · 호스트 root crontab 의 해당 4줄은 feature-0039 이관 주석으로 대체돼 제거(병행 실행 창 없음) → `docs/ARCHITECTURE.md` §4 · `docs/SECURITY.md` §36 · `wiki/hot.md` Active Threads 3곳을 실측 사실로 교정하고 정본 체크박스 lag 은 report-only 로 이관(함정 #16 역케이스 — 상태 under-claim 방지) ② `wiki/Features/_Index.md` 카운트 edit 의 `before` 가 after 값(`39 active`)으로 잘못 적혀 무-op 이 될 것을 apply 전 count 검증으로 적발·수정 ③ 초안이 놓친 표면 2건을 오케스트레이터가 보강(아래).
- 오케스트레이터 추가 정합 2건(초안 미검출): ① **`docs/DOC_REGISTRY.md`** — `ca02c608`(template v3.44.0)이 신설한 `docs/CODE_REVIEW.md`(`source_of_truth: true` · `domain: [review, quality, safety]`)가 도메인→정본 지도에 없어 SSOT 계약 §1 색인 갭 → '코드 리뷰 판정 기준' 1행 추가(reference = `AGENTS.md` §18.8.1 포인터). 신규 결정 본문 작성 아님. ② **`docs/STATUS.md`** 표 아래 미머지 worktree note — 열거 6건 중 2건 해소(`ai/claude-corp/feature-0038-c3-audit-settings` 머지 후 브랜치 삭제 · `ai/claude/feature-0007-llm-timeout-align` ahead=0) → 4건으로 실측 갱신(선례 34ee7448 동형).
- `docs/STATUS.md`: 기능현황표(gen-status 마커 구간)는 **무변경**(`--check` rc=0, 표 39행 = ground truth 39; feature-0039 행은 feature 커밋 `e632c8f5` 가 gen-status 로 self-add 완료). 기존 passthrough 행 dated backfill 없음(ADR-0031 §1 · META-0037/0038 선례). 표 밖 worktree note 만 정정.
- feature 커밋 self-add 표면 재작성 0(`git show --stat e632c8f5 -- wiki/ docs/` 선확인): `wiki/Features/feature-0039-ops-scheduler.md`(카드) · `wiki/Features/_Index.md` MOC 행 · `wiki/Log.md` feature entry · `docs/STATUS.md` 행 · `docs/CODEBASE_MAP.md` · `docs/LEARNINGS.md`. doc_sync backfill 잔여만 처리 = wiki 카운트 8참조/5파일 · `wiki/overview.md` §2.1 행 + §1 (62) 타임라인 · `wiki/Architecture/Overview.md` §2.3/§2.4 행 · `docs/ARCHITECTURE.md` §4/§6 행(feature 커밋 미터치 — 함정 #15 재현) · `docs/SECURITY.md` §36/§37 · hot · Log.
- `docs/SECURITY.md` 절 **2개 신설**(최댓값 §35 → §36/§37): §36 = feature-0039(호스트 root 실행 근거 소멸 · docker 소켓 마운트 명시 배제 · `../artifacts` 전체 쓰기 → `backups`·`metadata-graph` 2 디렉터리 축소 · MySQL 암호 argv → `--defaults-extra-file` · AGE 복원 리허설 DR 회복), §37 = feature-0003·0002 슬라이스(프롬프트 자동작성 요약 접지 축의 실효 활성화 = 노출 내용 확장 · 발화자 발화시점 각인 = 대화기록 귀속 무결성). 양 절 모두 신규 권한 코드 0 · 신규 라우트 0 · boundary 색인이며 정책 본문 신규 서술 아님.
- 무변경 정직: `docs/DECISIONS.md` noChange(이번 창 결정 3건은 전부 feature-local `unit/feature-0039-ops-scheduler/docs/DECISIONS.md` — 프로젝트 4자리 ADR 신규 0) · `docs/PROJECT.md` noChange · `docs/CONVENTIONS.md` noChange(§14 는 `ac20cb04` self-add · `ca02c608` 은 `template_version` 1줄만) · `docs/RELEASE_NOTES.md` noChange(2026-07-13 `bafad813` 이후 doc-sync 13회 연속 미터치 = 사실상 폐지 regime) · `docs/CODEBASE_MAP.md`·`docs/LEARNINGS.md` noChange(feature 커밋 self-add 완료) · `index.html`/`admin.html` 캐시버스터 편집 0(ITEM-09 빌드 자동주입 — 수동 bump 는 무효 churn + `asset_stamp_verify` 게이트 무력화).
- report-only(§13.1 사람 / feature-cycle 소관): `docs/CONVENTIONS.md` top-level 절 번호 충돌 2쌍 pre-existing(`## 10.` @204·404 · `## 12.` @473·535, 절 순서도 12→13→12→14 역전 — `bin/deploy-web.sh` die 메시지가 `CONVENTIONS §12`=expand/contract 를 인용하므로 재번호는 사람 결정) · `docs/STATUS.md` §5 prose "등록 17(디렉토리 18)" 이 ground truth 39 와 괴리(feature-0016 번호 충돌 사람결정 보류 이래 frozen defer, 표 본문은 정확) · `docs/PROJECT.md` 서비스 목록 stale(compose 실제 22 서비스) · feature-0039 `TASK.md` §3 `TASK-20260804T104800-cutover`·§7 `(deploy-backed)` 체크박스가 라이브 완료 상태와 lag · feature-0038 `REVIEW.md` REV id 시각 표기 drift(`REV-20260805T*` 인데 커밋 git-date 2026-08-04) · `docs/{STATUS,DOC_REGISTRY}.md` `template_version: v3.34.1`(다른 template-owned 문서는 v3.44.0).
- reconcile-first(자가수리 ①): 라이브 서빙 static 파리티 갭 **0** — 편집 전 `curl -k https://localhost/static/release-notes-data.js` 가 `HEAD`(=`origin/main` `ca02c608`) blob 과 byte-identical(sha256 `eafdf81ff343968e8b06…`), 서빙 asset stamp `?v=a746b1cbe3e2`(빌드 주입 content-hash). 따라서 배포 갭 없음 → early-exit 예외 미적용.
- landing/배포 소유 = wrapper 위임(무인 cron v3) → 로컬 commit 까지만. push/merge/deploy 는 wrapper. 릴리즈노트(operational)는 별도 커밋으로 분리해 feature-0003 full gate 통과.
- Timestamp: 2026-08-04T16:03:01Z
## REV-20260806T010301-META-0054-doc-sync-0806 [SKIPPED:doc-sync-index-mirror-additive] — aa46e677(08-05 doc-sync, META-0053) 이후 델타 13 머지 + 직접커밋 1(git-date 전부 2026-08-05) · wiki 카드 3종 stale 정정(feature-0011 P5a 종결·0036 판정 출하·0038 후속 Phase A~B3) + docs/ARCHITECTURE §4/§6 + SECURITY §38 + STATUS 색인 정정
- 변경 성격: 색인·미러 additive + stale 정정(정본 재서술 0). 정본(`unit/<id>/docs/*`)은 미변경 — doc_sync 는 정본을 쓰지 않는다.
- 타깃별 실질 검증: wiki feature 카운트 ground-truth 대조 PASS(`ls -d unit/feature-*`=39 · 카드 39 · 이번 창 신규 feature **0건**이라 카운트 편집 불요 — `wiki/Features/_Index.md` '39 active' · `wiki/overview.md` '39 개 feature unit' 전수 재확인) · ARCH 편집 행 파이프 균일성 기계 검증(§4 = 4 파이프 · §6 = 6 파이프, 형제 행 동일) · 신규 wikilink 전건 resolve(`unit/feature-003{6,8}/docs/{REPORT,REVIEW,TASK}.md` 4건 실파일 존재 확인 — wiki→unit 상대경로) · 신규 §참조 전건 heading resolve · `bin/gen-status.sh --check` rc=0("frontmatter 18 · passthrough 21 · 신규 0", 표 무변경) · `bin/ssot-lint.sh` rc=0(4 WARN 전부 pre-existing tracked `.env*.bak*`) · `bin/wiki-lint.sh` 22 findings = **baseline 동일**(악화 0).
- 적대검증(ULTRACODE `wf_d0b1fd46` — 5축 병렬 analyze → 축-스코프 refute 렌즈, cross-fault 회피): 제안 62건 중 **58건 적용 · 4건 무-op skip**(`wiki/Features/_Index.md` 25~28 = 타 축이 동일 라인 선적용, count=0 으로 기계 적발 — 함정 #12 중복 편집 방지 동작 확인). 검증자 교정 5건 전부 반영: `wiki/Log.md`·`wiki/hot.md` 3건(**윈도우 머지 건수 14→13 실측 정정** — `8b0eefa5` template v3.44.1 은 머지가 아닌 직접커밋 / `verify_*.mjs` 40→41개) · `wiki/Features/feature-0003-agent-web-ui.md` 1건(app.js 8,080줄 실측 vs app/ 6모듈 5,512줄 — "추출분이 잔존분보다 크다" over-claim 철회) · 릴리즈노트 1건(별도 operational 커밋).
- 오케스트레이터 직접 정합(워크플로 `analyze:docs-policy` 축이 API 오류로 실패 → 대체 수행): ① **`docs/ARCHITECTURE.md` §4** feature-0036 행(2026-07-31 초판에서 정지 — ADR-0036-08 판정 순환 차단 실측 7,896콜/62.8%/91노드/평균 87회 → 시간당 148→~14콜 · ADR-0036-09/10 판정 표시 출하·`--tag-*` 상태 태그·대조 기준 구분 라벨 · ADR 범위 01~07→01~10 · cross-cut 코드 거주에 feature-0003 추가) + feature-0038 행(후속 Phase A~B3 = app.js 11,119→8,082줄 기점 대비 -27% · `app/` 4→6모듈) ② **§6 의존성맵** feature-0036 deps 에 feature-0003 추가(배지 렌더 거주) + feature-0038 비고 `app/*.js` 4→6모듈 ③ **`docs/SECURITY.md` §38 신설**(최댓값 §37 → §38) = 첨부 변경 사실의 코드-권위화(부재 단정 차단이 부정 단정 추가가 아님 · 신규 0건이면 세 블록 미주입 · 목록은 floor 이지 ceiling 아님) + 비신뢰 파일명 flatten/datamark sentinel 제거/저장본 불변 + 판정 표시의 해시-일치 게이트 + feature-0011 미배선 GDPR legal-erasure 사양본 보존 결정(ADR-20260805T153000 §1). 신규 권한 코드 0 · 신규 라우트 0 · boundary 색인이며 정책 본문 신규 서술 아님.
- **오케스트레이터 독립 발견 prior-window drift 2건**(워크플로 축과 수렴 확인 후 적용): ① `docs/STATUS.md` §5 전체 진행률이 **2026-06-30 이후 미갱신**("등록 기능 17(디렉토리 18) · review 5 · in-progress 13") → 실측 38 번호/39 디렉토리 · review 8 · in-progress 31 로 정정(직전 run 이 report-only 로 이관했던 항목 — 표 본문은 정확했고 prose 만 stale) ② 미머지 활성 worktree note 4건 → **5건**(`ai/claude/feature-0002-agent-core` ahead=1 누락 · `feature-0007-llm-timeout-align` 은 ahead=0 이라 정당 제외) + 실측일 2026-08-06.
- feature 커밋 self-add 표면 재작성 0(`git diff aa46e677..HEAD -- docs/ wiki/` 선확인): `docs/STATUS.md` feature-0038 행(2026-08-05 self-add) · `docs/DECISIONS.md` ADR-20260805T153000 본문 · `wiki/README.md` mirrors/sources 대상범위 절 · `docs/LEARNINGS.md` · `docs/improvements/{conversation-audit/FRICTION_LEDGER,ssot-consolidation/ROADMAP}.md` · docs/* `template_version` v3.44.1 — 전부 미터치.
- `docs/STATUS.md`: 기능현황표(gen-status 마커 구간)는 passthrough 행 4건만 갱신(feature-0002·0003·0011 + worktree note)하고 `--check` rc=0 유지. frontmatter 보유 feature 의 행 직접 편집 0 · 정본 frontmatter 수리 0(ADR-0031 §1 · META-0037/0038 passthrough regime). rollup blockquote 누적 0. frontmatter `sources:` 에 feature-0035~0039 5건 backfill.
- 무변경 정직: `docs/DECISIONS.md` noChange(ADR 본문 self-add 완료 · 신규 결정 작성 금지 · 색인 절 부재) · `docs/PROJECT.md` · `docs/CONVENTIONS.md` · `docs/DOC_REGISTRY.md`(창 내 신규 `source_of_truth: true` 문서 0건 — `--diff-filter=A` 전수 확인) · `docs/RELEASE_NOTES.md`(폐지 regime) · `index.html`/`admin.html` 캐시버스터 편집 0(ITEM-09 빌드 자동주입 — `?v=dev` 고정).
- report-only(§13.1 사람 / feature-cycle 소관): feature-0036 `TASK.md:70` `- [ ] TASK-0021 PB-0008 시각 검증` 체크박스가 라이브 PASS(`test-runs.d/REV-20260805T190000-verdict-badge.md`)와 lag · feature-0011 카드 §4 `TASK.md — 작업 큐 (active)` 가 정본 `State: done` 과 불일치 · feature-0038 카드 §4 ssot ROADMAP 실측일 stale · wiki 카드 frontmatter `status:` (feature-0011 `stub`·feature-0036 `draft`) 는 `maturity` 만 승격하고 미변경(키 의미 분리 — 사람 확인 대상) · `docs/CONVENTIONS.md` 절 번호 충돌 2쌍 pre-existing · `docs/DOC_REGISTRY.md:59` In-flight 예시 `feature-0010` stale · `wiki/Architecture/Overview.md` §2.4 feature-0036 deps 가 ARCH §6 정본과 부분 불일치.
- reconcile-first(자가수리 ①): 라이브 서빙 static 파리티 갭 **0** — 편집 전 `curl -k --resolve mysql-ai.company.local:443:127.0.0.1 https://.../static/release-notes-data.js` 가 `origin/main` blob 과 byte-identical(`diff` 무출력), edge `/healthz` 200, 서빙 stamp `?v=c1043dc07849`. 배포 갭 없음 → early-exit 예외 미적용.
- landing/배포 소유 = wrapper 위임(무인 cron v3) → 로컬 commit 까지만. push/merge/deploy 는 wrapper. 릴리즈노트(operational)는 별도 커밋으로 분리해 feature-0003 full gate 통과.
- Timestamp: 2026-08-06T01:03:01Z
