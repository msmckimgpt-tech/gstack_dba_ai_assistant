---
doc_type: PRESENTATION_EVIDENCE
scope: project
status: active
source_of_truth: false
range: 2026-06-17 ~ 2026-07-08
version: v1
created_at: 2026-07-08
companion: ./deck.html
---

# 근거·확인필요 원장 — 2026-06-17 ~ 2026-07-08 · v1

> 발표 본문(deck.html)·스크립트(SCRIPT.md)의 모든 주장은 여기서 추적된다. **확인필요(§2)** 항목은 발표 시
> "완료/개선/검증"으로 단정하지 말고 "개발 완료 · 배포/효과는 측정·검증 예정"으로 정직하게 표현한다.
>
> **수집 채널**: ①git(main 반영분 기준, first-parent 414 커밋 · baseline = 2026-06-16 마지막 main 상태) ②정책·릴리즈노트(RELEASE_NOTES 06-30~07-07 블록·STATUS·SECURITY·LEARNINGS) ③unit feature 기록(feature-0016/0018→0003/0009/0012/0014/0015/0002/0007 REPORT·TASK·MODIFY·DECISIONS) ④개발 세션 transcript(보조 — 교차확인분만) ⑤이전 기간 발표자료(`docs/presentation/2026-06-01_2026-07-02/v1` — 연속성·중복 방지 baseline).
> 커밋 해시·PR#·CHG/ADR/TASK id 는 추적용 내부 참고이며 **청중 덱 본문 비노출**. 민감값(계정·비밀번호·토큰·접속좌표)은 원장에도 비노출.
>
> **범위 겹침 주의**: 이전 발표자료가 2026-06-01~07-02 를 다뤘다. 본 범위(06-17~07-08)는 06-17~07-02 가 겹치므로,
> 겹치는 항목은 **이어받음/완료**로 분류하고 서사는 "07-02 이후 무엇이 더 진전됐나"에 무게를 둔다. 07-02 이후가 이번 신규 축.

---

## 0. 이번 기간 KPI (표지·요약 수치의 근거·산식)

### E-000a · 진척한 기능 영역 = 13개
- **kind**: git
- **ref**: 범위 커밋 subject 의 고유 `feature-00NN` 토큰 집계 — feature-0016(98)·0003(44)·0009(22)·0012(12)·0002(9)·0018(8)·0011(8)·0013(4)·0015(2)·0014(2)·0017(1)·0010(1)·0007(1). 총 13개 영역.
- **status**: 검증됨 (git 이력, 재현 가능)
- **note**: 활동량은 feature-0016(관계도 뷰)에 압도적으로 집중. "13"은 커밋에 명시된 feature-id 만 집계.

### E-000b · 개발·머지 작업 단위(TASK) = 159건
- **kind**: git
- **ref**: 범위 커밋 메시지의 고유 `TASK-*` 식별자 수 = 159 (`git log --since=2026-06-17 --until=2026-07-08` subject+body). first-parent 병합 414건.
- **status**: **개발 이력 집계** (검증됨 아님 — 표기도 "개발 이력 집계"로 낮춤)
- **note**: **산식** = 커밋 메시지 고유 TASK 토큰 수. feature 수(13)·커밋 수(414)와 다른 축(1 TASK = 다수 커밋). 이전 기간 "16 묶음"과 축이 다르니 직접 비교 금지. 질문 시 이 규칙으로 방어.

### E-000c · 관계도에 자동 적재된 함수·프로시저 = 2,201개 (도달가능 4개 데이터소스)
- **kind**: git / unit-doc
- **ref**: feature-0016 REPORT routine-dbanalysis POST-DEPLOY(2026-07-06) — "라이브 backfill 2,201 routines / 도달가능 4 ds", PB-0008 라이브 PASS(accountdb ƒ/⚙ 198 전수 렌더). 후속 §56 full sync routines 16,410 전량 투영·errors 0(2026-07-08).
- **status**: 검증됨 (POST-DEPLOY 라이브 적재 + PB-0008)
- **note**: "2,201"은 07-06 시점 도달가능 4 ds 백필 수. §56(07-08)에서 full sync 16,410 투영으로 확대(전 ds). KPI 는 보수적으로 2,201(07-06 검증 시점) 사용.

### E-000d · 웹 코드 정리 = 148개 경로 → 21개 모듈 (잔여 0)
- **kind**: git / unit-doc
- **ref**: feature-0012 REPORT/TASK — app.py 모놀리스 148 route 핸들러 전량을 21개 도메인 APIRouter 로 byte-동치 추출, 잔여 `@app` 라우트 0, app.py ~29K→18,917줄. route-parity 골든·프로덕션 응답 byte-동치 검증.
- **status**: **개발 완료(잔여 0)** — 표기는 "개발 완료", "전부 라이브 배포 완료"로 단정 금지(→ U-006).
- **note**: batch1-3 라이브 배포·검증 완료(blue-green soak PASS). **batch4(잔여 16 route)는 추출 완료·재배포 검증 후속**. 로그인 QA 게이트 미수행. KPI 배지는 "개발 완료 · byte-동치 검증"(배포 아님).

---

## 1. 확인된 주장 (근거 있음)

### E-001 · [답 조율] 대화별 추론 강도 4단계 선택기 (사용자)
- **kind**: git / unit-doc / dev-transcript(보조)
- **ref**: RELEASE_NOTES 07-06(reasoning-effort, Major) · feature-0003 MODIFY CHG-20260706T013532. 낮음/일반/높음/매우 높음, 대화별 영구 저장(KV), 비-thinking 모델 비활성. 요청 단위 `extra_body.thinking.budget_tokens` override.
- **status**: 확인 (배포 PR #594 + **PB-0008 PASS** postverify — "+"메뉴·4단계 팝업·새로고침 후 유지·pageerror 0)
- **note**: **예산 매핑** 낮음=2,000 / 일반=**무주입(no-override)** / 높음=10,000 / 매우높음=16,000 (모델 하드리밋 내). '일반'=무주입은 **의도된 회귀 방지(B1)** — 고정값을 넣으면 선택기를 안 건드린 Sonnet 대화가 기본 16,000→축소로 조용히 강등되기 때문. 라이브 gateway probe 로 override 실동작 확인(1,024예산→~2,073자 reasoning vs 16,000→~6,914자). transcript(1a79fcb7) 교차확인.

### E-002 · [답 조율] 관리 콘솔 런타임 설정 + 추론 강도별 예산 (운영자)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-07(runtime-settings, feature-0018, Major) + 07-07 후속(추론 강도별 예산). feature-0003 MODIFY CHG-20260706T094937 / CHG-20260707T130000. 시스템>설정: 실행 타임아웃·MCP 타임아웃·모델별 추론 예산·강도별 예산. DB 정본+런타임 스냅샷, live/restart 하이브리드, env-fallback(미override 시 byte-동치), `system.runtime.read/write` 권한+audit.
- **status**: 확인 (배포 PR #602/#607/#609 + **PB-0008 PASS** — 저장→DB→감사→리셋 왕복·강도별 섹션 렌더)
- **note**: 저장 경로 500(감사 allowlist 신규 action 미등록) **핫픽스 후** PASS(PR #604). UX 재설계(정렬 grid+commit-bar)는 재사용 위젯 정렬 붕괴 교훈(LRN-20260707-0001) 반영, 사용자 "가시성 대폭 개선" 확인. '일반'은 강도별 예산에서도 제외(무주입 유지).

### E-003 · [함께 보기] 공유 가시성 [from,to] window + 보안 봉인 (기능·보안)
- **kind**: git / unit-doc / policy-doc / dev-transcript(보조)
- **ref**: RELEASE_NOTES 07-04(share-visibility-window, Critical) · SECURITY.md §21/§21.1~21.5 · feature-0009 MODIFY CHG-20260704T130000 · FUNCTION AC-GC-A20~A27. '여기부터/여기까지'로 `[from,to]` window 만 노출, 가려진 구간을 뷰·LLM recall·fork 3면 물리 배제(loader 단), fail-closed, join stamp never-widen(재공유 widen 403).
- **status**: 확인 (기능·보안 **개발 완료** — make test 28 신규 PASS + 적대 7-렌즈 패널). **단 라이브 시각검증은 U-003.**
- **note**: 초기 구현이 recall 로 누출(적대 패널 M1 적발) → recall 까지 태그 확장해 봉인(SECURITY §21.4). 사용자 결정(07-03) "라이브룸+멤버 필터". §21.5 수용 잔여(첨부 clip 근사·존재 오라클(내용 미노출)·PG 전용·사람이 구두 전달하는 사회적 경계). "물리 배제"는 인젝션으로도 없는 행을 못 끌어냄이 핵심.

### E-004 · [자율 지식] 용어사전 대화 자율등록 + 검토 큐 (이어받음→확장)
- **kind**: git / unit-doc / policy-doc
- **ref**: RELEASE_NOTES 06-29 · DECISIONS.md **ADR-20260629T101500**(glossary-conversation-autoregistration) · feature-0003 MODIFY CHG-20260629-glossary-*. AI 가 대화에서 용어 후보 제안 → 신뢰도 ≥0.85 자동 등록·미만 검토 큐, 역할 분리·유사어 참조, `kb.glossary.curate` 권한, 대화 답변 차단 안 함(best-effort).
- **status**: 확인 (자동등록 13 테스트 PASS; 역할 드롭다운 필드명 버그 **PB-0008 재검증 PASS** — 옵션 2→10)
- **note**: "자동 학습 금지"는 원래 **의도된 거버넌스**(용어가 답변 프롬프트에 주입 → 지식오염면). ADR 이 하이브리드 자동승급+전수 감사+가역으로 해소(오염방지 유지하며 자율성 부여). 역할 단일화(single-ui)는 서빙본 검증, 인증화면 사용자 확인 권장.

### E-005 · [자율 지식] ENUM 코드사전 자율수집 + 채택 인박스 통합 (신규)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-07 후속(0beb02e3) · feature-0003 MODIFY CHG-20260707-kb-candidate-adoption · alembic 0039(enum_feedback). 대화 답변 직후 `(table.column)` 코드↔라벨 후보 LLM 추론(≥0.9 자동승급·미만 검토 큐), `enum_dictionary.source`(manual|auto)·`kb.enum.curate` 권한. 용어+ENUM+샘플 검수를 "채택 인박스" 단일 트리아지로 통합.
- **status**: 확인(개발 완료) — 코어 14 + 웹경계 9 테스트 PASS, 호스트 스위트 1,581 PASS. **단 PB-0008 라이브 = U-004(POST-DEPLOY 이연).**
- **note**: 채택은 "as-is"(이번 사이클 편집-후-채택 없음). 콘솔 IA 통합(채택 인박스·샘플 검수를 각 사전 하위 2차 보기로)·5서브뷰 디자인 폴리시는 UI 단독·RBAC 0. 메타데이터 콘솔 redesign/polish/ux2 호스트 스위트 1,662 PASS·0 회귀(polish 는 적대 시각리뷰 산물).

### E-006 · [관계도 지도] 평면 목록 → 대화형 노드 그래프 (착수→대폭 확장)
- **kind**: git / unit-doc / policy-doc / dev-transcript(보조)
- **ref**: RELEASE_NOTES 06-30~07-07(feature-0016 다수 블록) · SECURITY §19 · feature-0016 REPORT/DECISIONS(feature-local ADR-002~023) · STATUS feature-0016 행. AGE 그래프 DB cutover(06-30, 무손상·무중단 롤링) → 렌더러 진화(canvas-2D→WebGL→AntV G6 v5, ADR-004)·초기 스키마-우선 진입+미니맵·masonry/shelf 배치·자유 드래그·z-order 정합.
- **status**: 확인(개발 완료, **부분 라이브 검증**) — 실데이터 기준선 8,122 테이블/91 스키마/~20 ds. G6 엔진 교체 **PB-0008 PASS**(graph-g6b, 실 Windows, 236 노드·36 클러스터)·우클릭 상세 **PB-0008 PASS**(graph-ctxmenu, 2026-07-02)·graphux9/10 PB-0008 PASS.
- **note**: **일부 후속 증분(masonry·카메라 팬·자유배치·z-order·rel-selfheal)은 PB-0008 라이브 잔여 → U-005.** "관계형=SSOT, AGE=재생성 가능한 투영" 불변식. G6 채택 근거: 무료(MIT)·중첩 combo·결정론 배치(force 재도입 기각 — 셔플 결함 유발).

### E-007 · [관계도 지도] 노드 이해 — 역할 표식·함수/프로시저·AI 능동 분석
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-03(node-role-viz)·07-06(routine backfill/DB 단위 분석) · feature-0016 ADR-010(역할)·016(routine)·003/017(AI 분석 앵커·refine). 8종 역할(기준정보/계정/거래/로그/매핑/설정/통계 등) 색(Okabe-Ito 색맹친화)+아이콘+범례, 함수/프로시저 ƒ/⚙ 노드+읽기/쓰기 엣지, 우클릭 AI 능동 분석(앵커-상대 관련도 게이팅), DB 단위 일괄 분석, refine-not-override.
- **status**: 확인(routine backfill·DB 단위 분석 **POST-DEPLOY + PB-0008 PASS** 2026-07-06) / (역할표식·refine 는 단위·적대패널 PASS, 라이브 PB-0008 = U-005)
- **note**: 앵커 게이팅 실증 — 부모 스키마(형제 123개) 탈락 = fan-out 지배경로 차단 정량 확인. 역할 back-fill 은 LLM 재호출 없이 휴리스틱(비용 억제).

### E-008 · [관계도 지도] 관계 추론·자기교정·데이터흐름·크로스-DB
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-01(암묵 관계 추론+자기교정)·07-04(크로스-DS Phase B)·07-07(§56 크로스-DB 루틴 sync) · feature-0016 ADR-002(추정→신뢰/파단)·019(크로스-DS)·022/023(sync 근본수정). FK 미선언 DB 에 이름·구조 휴리스틱으로 추정 엣지(점선), 성공한 대화 JOIN 관찰+데이터겹침 프로브로 weight 강화/감쇠(신뢰=실선·파단=숨김), FK=권위적 불변, 수동 큐레이션 trust/break.
- **status**: 확인(§56 크로스-DB 루틴 sync **POST-DEPLOY e2e PASS** 2026-07-08 — full sync routines 16,410 투영·errors 0·크로스 ROUTINE_USES 1,041·case_purged 6,320 잔여 0, **PB-0008 AI 직접 수행 PASS** 실 Windows Chrome)
- **note**: **정직 회귀 스토리** — 07-01 발표한 자기교정이 config export 누락(NameError)을 광범위 except 가 삼켜 06-29~07-02 3일간 insight 파이프라인 전체가 조용히 정지 → 근본수정+AST 회귀가드(ADR-007). 크로스-DS 는 프로브 불가라 보수적(높은 유사도 임계·신뢰만 AI 주입·수동 승급); 데몬 OFF 로 SHIP(eventual). → 일부 U-005.

### E-009 · [관계도 지도] 성능 — 서버측 이웃조회 인덱싱 (측정조건 분리)
- **kind**: git / unit-doc
- **ref**: feature-0016 REPORT graphux3(post-cutover). **서버측**(AGE 쿼리, web-container 서버측 계측): 테이블 depth1 9,454ms→151ms·depth2 18,564→300ms, 스키마 depth1 2,673→159ms, 원인=이웃 순회 인덱스 추가. graphux4 raw-graphid 재작성 depth2 660→~208ms(서버측). 동기화 부하: 배치 커밋으로 fsync ~57,000→~114.
- **status**: 확인 (**서버측 실측** — "이웃 조회 약 60배" = depth1 9,454→151ms 서버측)
- **note**: **측정 위치 필수 구분** — 이 수치는 전부 **서버측**. **화면 렌더 FPS 는 headless/WSL 측정 불가, 실 하드웨어에서만 검증(→ U-007)**. "60배"를 화면 체감 속도로 오해 금지. 이 항목은 이전 기간(06-30)에도 언급 — 이어받음.

### E-010 · [AI 관제] AI 운영 현황 패널 + LLM 계측 확장 (신규)
- **kind**: git / unit-doc / policy-doc
- **ref**: RELEASE_NOTES 07-02(aiops-panel)·07-03(ds-avg-latency, aiops-ttft) · SECURITY §20 · feature-0003 MODIFY CHG-20260702-aiops-panel 등. 관리>감사>'AI 운영 현황' 탭: worst-of 상태 배너·KPI·Attention·활동 feed·계측 커버리지, `/api/admin/ai-ops`(`console.aiops.read`, admin 전용·read-only). 활동 클릭 상세(작업·모델·토큰·비용·지연·연결 대화 딥링크)·keyset 페이징.
- **status**: 확인(개발 완료) — 패널 10/10 + 페이징 15/15 + step-gap make test 1,430 PASS. 데이터소스 평균 연결 응답시간 **배포+PB-0008 PASS**(2026-07-03). **단 패널 자체 라이브 = U-008.**
- **note**: 지연 KPI(p50/p95)를 전체 왕복(답변 길이 비례)에서 **단계 간 간격(step_gap)**으로 재정의(alembic 0033). 계측 커버리지 각주(provider usage 없는 경로)로 "총비용" 오독 방지. **재정의 KPI 는 배포후 트래픽 축적 필요(U-008)**. 최초 시도가 dead 코드 계측(LRN-20260703-0001 적대리뷰 적발·되돌림) 후 정본 구현.

### E-011 · [안정성] 무중단 배포 — Caddy + web 2-replica 롤링 (라이브 실증)
- **kind**: git / unit-doc / release-note
- **ref**: RELEASE_NOTES 06-30(feature-0014) · feature-0014 REPORT/TEST/ANCHOR · STATUS feature-0014 행(review, "라이브 컷오버 완료"). web-a/web-b 2 replica + Caddy LB 1대씩 롤링, `bin/deploy-web.sh`(직렬화·TLS/마이그 preflight·post-soak 자동롤백), :18080 폐기·:443 단일화.
- **status**: 확인 (**라이브 컷오버 완료** 2026-06-30, 사용자 승인 · 부하 실증) — 이어받음/완료
- **note**: **측정 조건 명시** — 단일 replica 롤링 force-recreate 중 정상 클라(10s) 부하 **104/104 HTTP 200·0 실패·최대 0.27s**. 단, **단일 호스트·라이브 사용자 1명 조건**(프로덕션 스케일 SLA 아님). --max-time 4 공격적 더블 recreate 의 10/121 타임아웃은 클라 4s 캡 artifact(502 아님). 자동 롤백·SSE pre-drain 은 미수행(→ U-006). 이전 기간에도 보고 — 이어받음.

### E-012 · [안정성] DB 재시작 무중단 + 코드 모듈화 완료 (라이브 실증)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 06-30(feature-0016-zd-pg-pause-caddy) · feature-0016-zd TEST · feature-0012(모듈화, E-000d). pgbouncer PAUSE→PG recreate→RESUME(RESUME trap 보장), reconcile_caddy(변경시만 recreate).
- **status**: 확인 (PG 재시작 **라이브 실증** — RW OK=134/ERR=0, 최대 큐대기 14s(에러 아님), RESUME 후 paused DB=0)
- **note**: **측정 조건** — pgbouncer 경유 RW 부하 루프(~55s) 중 PG primary force-recreate, 단일 호스트. pgbouncer admin_users 적용엔 1회 recreate(짧은 RW blip) 필요, 이후 near-zero. **doc 시점차**: feature-0016-zd REPORT Summary 는 "배포·라이브 검증 대기"로 남아있으나 TEST.md 는 라이브 실증 완료 기록(→ 정합성 conflict C-2). 모듈화 잔여=U-006.

### E-013 · [안정성] insight-worker 안정화 + 용도별 LLM 라우팅 (운영자)
- **kind**: git / unit-doc / policy-doc(LEARNINGS)
- **ref**: RELEASE_NOTES 07-03(insight 부하분산·heartbeat·table grouping·LLM fallback)·07-04(llm-routing-interactive-split)·07-07(edge 폴백 차단) · feature-0002/0007 REPORT/MODIFY · LEARNINGS LRN-20260707-0001. 샤드 그룹화(대표 1건 LLM 분석+형제 LLM-free 전파)·긴-cycle heartbeat(30s throttle)·probe 격리/circuit-open skip·요청레벨 fallback(claude-corp→root→edge)·용도별 라우팅(실시간=claude 24/7 / insight 배치=시각 기반).
- **status**: 확인 — 대화 답변 edge 폴백 차단 **LRN Verified**(배포후 live probe: chat→cloud 확인·gemma 도달불가). insight heartbeat "배포후 docker healthy 복귀 확인". graceful 종료 stop 18s<30s grace·ExitCode=0.
- **note**: **정직 회귀 스토리** — 가용성 위해 넣은 edge(gemma) 폴백이 07-07 역효과: 두 계정 rate-limit 시 대화가 소형 맥락 모델로 조용히 강등, ~30K 토큰 히스토리 절단, AI 가 자신있게 맥락 상실 답변("맥락을 잃어버렸나요?" 사용자 신고). 교훈=라우팅 폴백은 능력 동등 or clean-fail(조용한 강등 금지). edge-free alias+회귀가드 테스트로 봉인.

### E-014 · [함께 보기] 공유 링크 참여 알림 + 답변 리뷰 UX (부수)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-03(gc-join-notice)·07-04(말풍선 ☰ 통합) · feature-0009/0003 MODIFY · feature-0003 share-mermaid/point-scroll(CHG-20260629T143914/181648). 공유 링크 참여 시 '참여 알림' pill+기존 멤버 unread, 말풍선 액션 ☰ 통합(👍/👎만 외부), 공유뷰 mermaid 반응형 렌더.
- **status**: 확인(공유뷰 mermaid **PB-0008 실 Windows PASS**) — join-notice 는 적대리뷰 BLOCKING(참여이벤트가 LLM 히스토리 오염) 봉인, PB-0008 미실측(부수 항목). point-scroll rail PB-0008 잔여.
- **note**: join-notice 는 `__event__` sentinel 로 LLM 히스토리 배제(unread 집계는 유지). 부수 UX — 청중 덱에서는 §함께 보기 보조로만 언급.

### E-015 · [부수] 답변 피드백 답변당 고유화 · 관계도 다이어그램(mermaid) 답변 (이어받음)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES(피드백 id-space)·feature-0003 CHG-20260629T014345/022055(alembic 0021/0022) · feature-0013(mermaid 관계 다이어그램, STATUS done+PB-0008 PASS). 피드백 👍/👎 답변당 사용자별 고유(unique index+upsert)·새로고침 복원·변경 가능, 두 message-id 공간 모호성 해소.
- **status**: 확인 — 피드백 curation 15/15 테스트 PASS(데이터 계층, PB-0008 미주장). feature-0013 mermaid PB-0008 PASS(Chrome 149).
- **note**: 청중 덱 비핵심 — 자율 지식/함께 보기 서사의 보조 근거로만.

---

## 2. 확인 필요 (근거 부족·불일치·단정 위험 — "완료/검증/배포"로 단정 금지)

### U-001 · 사용자 체감 개선폭 (속도·정확도·편의) 정량치
- **왜 확인필요**: 수치 미측정. 추론 강도·관계도·자율지식 모두 "수단·기능"까지 확인, "사용자 체감 몇 % 향상"은 실사용 관찰 전.
- **가진 것 / 없는 것**: 있음=기능 배포·PB-0008(일부). 없음=사용자 만족도·과업시간 단축·정확도 향상 수치.
- **확인 방법**: 실사용 로그·설문·A/B, 다음 기간 측정.

### U-002 · NL→SQL 답변 "정확도 향상 수치" (이전 기간 이월)
- **왜 확인필요**: 수치 미측정 — 이전 발표자료에서도 "측정 수단 확보, 수치는 다음 기간"으로 이월된 항목. 이번 기간에도 미측정.
- **가진 것 / 없는 것**: 있음=평가 harness·용어/ENUM 사전 자율수집·하이브리드 검색(정확도 "수단" 강화). 없음=전·후 정확도 %.
- **확인 방법**: eval A/B(feature-0016 T5.1 등) 실행 후 수치화.

### U-003 · 공유 가시성 window — 라이브 시각검증 (Critical)
- **왜 확인필요**: 배포/라이브 시각검증 미완. 기능·보안은 개발 완료(28 테스트+적대 7렌즈 봉인)이나 **PB-0008 미실측**(doc 명시).
- **가진 것 / 없는 것**: 있음=코드·테스트·적대 패널·SECURITY §21. 없음=실 Windows 브라우저에서 ☰ 메뉴·범위 배너·windowed 뷰 육안 확인.
- **확인 방법**: 배포 후 PB-0008 실 Windows 시각검증. §21.5 수용 잔여(존재 오라클·PG 전용·사회적 경계)도 함께 안내.

### U-004 · 채택 인박스·ENUM 코드사전 — 라이브 시각검증
- **왜 확인필요**: PB-0008 = POST-DEPLOY(statically baked) 로 이연, 라이브 PASS 미주장(doc 명시).
- **가진 것 / 없는 것**: 있음=코어 14+웹 9 테스트·호스트 1,581 PASS·콘솔 redesign 1,662 PASS. 없음=배포후 실화면 육안.
- **확인 방법**: 배포 후 PB-0008.

### U-005 · 관계도 뷰 일부 증분 — 라이브 시각검증 (G6 교체 후속·자유배치·역할표식·의미클러스터·크로스-DS)
- **왜 확인필요**: 다수 후속 증분이 코드+적대패널(§18.8) PASS 이나 **PB-0008/라이브 cadence 잔여**(wiki hot.md·REPORT 명시). 의미 임베딩 클러스터는 **eventual**(배포 직후 affix, 몇 cycle 후 채워짐), 크로스-DS 는 데몬 OFF SHIP(AUTO flip+임베딩 populate 후).
- **가진 것 / 없는 것**: 있음=일부 PB-0008 PASS(g6b·ctxmenu·초기뷰·검색·routine-dbanalysis·§56 sync). 없음=masonry·카메라 팬·자유배치·z-order·역할칩·rel-selfheal 데이터 정정 라이브 육안, 의미클러스터 실채움.
- **확인 방법**: 배포 후 PB-0008 + insight cadence 경과 후 재확인.

### U-006 · 무중단 자동 롤백·SSE pre-drain·라우터 batch4 재배포·백업 자동화 라이브
- **왜 확인필요**: 설계·개발은 됐으나 라이브 실증/재배포 잔여(doc "미수행"/"후속"). batch4(잔여 16 route) 추출 완료·재배포 검증 전, 로그인 QA 게이트 미수행.
- **가진 것 / 없는 것**: 있음=자동롤백 절차·batch4 추출·백업 cron/리허설 스크립트. 없음=실패 상황 자동롤백 실증·batch4 라이브 재배포·백업 cron 라이브 설치 확인.
- **확인 방법**: 배포 리허설(자동롤백 유발)·batch4 재배포+로그인 QA·cron 설치 후 관측.

### U-007 · 관계도 화면 렌더 속도(FPS) — 실 하드웨어 체감
- **왜 확인필요**: **측정 위치 불가** — FPS 는 headless/WSL 에서 실 GPU 미측정(doc 명시 "실 FPS 는 사용자 실 하드웨어 재측정이 유일 검증").
- **가진 것 / 없는 것**: 있음=서버측 쿼리 60x·브라우저측 headless 프리즈 ~9s→~0-80ms. 없음=실 운영자 하드웨어 체감 FPS.
- **확인 방법**: 운영자 실 PC 브라우저 프레임 트레이스.

### U-008 · AI 운영 현황 패널 — 라이브 + 지연 KPI 트래픽 축적
- **왜 확인필요**: 패널 배포후 PB-0008 이연, 재정의 지연 KPI(step_gap)는 "배포후 트래픽 축적" 필요(wiki hot.md).
- **가진 것 / 없는 것**: 있음=10/10·15/15 테스트, ds-avg-latency PB-0008 PASS. 없음=패널 실화면·재정의 KPI 실트래픽 검증.
- **확인 방법**: 배포 후 PB-0008 + 실트래픽 축적 관측.

---

## 3. 특별 주의 항목 (단정 절대 금지 — §1/§2 로 분류 완료)

- **실제 배포 여부**: 라이브 배포·컷오버 근거 종류 명시 = 머지/PR + POST-DEPLOY 기록 + PB-0008(일부). **운영 프로덕션 부하 로그는 원장에 미인용**(단일 호스트·라이브 사용자 1명 조건). 배포 미완/재배포 잔여 = E-000d·U-006. 배포됨=E-011/E-012/E-003(기능)/E-001/E-002/E-000c.
- **테스트 결과**: 인용된 PASS 는 make test/컨테이너 스위트·적대 패널(§18.8)·PB-0008. 미검증 = U-003~U-008.
- **성능 개선 수치**: E-009(서버측 이웃조회 60x·측정위치=서버)·E-011(부하 104/104·조건=단일replica 롤링)·E-012(RW 134/0·조건=~55s 루프). **화면 FPS=U-007(측정불가).** 뭉뚱그린 "N배 빨라짐" 금지 — 항상 측정위치·조건 병기.
- **장애 재발방지 효과**: rel-selfheal 3일 조용한 정지 근본수정+AST 가드(E-008), edge 폴백 맥락손실 봉인+회귀가드(E-013), '일반'=무주입 B1 회귀가드(E-001). **"효과 실증"이 아니라 "가드 도입"까지 확인** — 재발 0 실증은 관측 이연.
- **화면 변경 전후 자료**: 실측 스크린샷은 unit TEST/evidence 에 존재(PB-0008 PASS 항목). **덱은 실측 화면 미첨부 → 전/후는 인라인 SVG 개념 도식(업무 관점) + "실제 화면 대신 개념 도식" 명시**(민감정보·계정 노출 회피).
- **문서-코드 불일치(conflict)**:
  - **C-1**: RELEASE_NOTES 06-30 은 무중단 컷오버를 "운영자 confirm 게이트/보류"로 기술, STATUS(후행)는 "라이브 컷오버 완료"로 기술 → **STATUS 가 최신 상태**(시점차, 모순 아님). 덱은 "완료"로 서술하되 조건(단일호스트·사용자1) 병기.
  - **C-2**: feature-0016-zd REPORT Summary "배포·라이브 검증 대기" vs 같은 unit TEST.md "라이브 실증 완료" → TEST.md 가 실측 기록. 덱은 "라이브 실증(측정조건 병기)"로, 단정은 E-012 note 대로.
  - **C-3**: transcript 는 feature-0018 을 feature-0003(웹 UI)에 귀속 → "feature-0018 은 별도 폴더 아님, 코드가 feature-0003/0002 에 거주하는 cross-cutting 라벨"(정합). 청중 덱은 식별자 비노출이라 무관.
  - **C-4(거버넌스, 청중 비노출)**: STATUS §5 "feature 번호 0016 이 2 슬라이스(metadata-graph + zd-pg-pause-caddy) 공유 — 번호 충돌·사람 결정 보류". 제품 결함 아님(추적 라벨 문제) — 청중 덱 비노출.
  - **C-5(청중 비노출)**: feature-0016 그래프 서사 근거(ADR-002~023)는 `docs/DECISIONS.md` 아닌 **unit feature-local DECISIONS**에 거주(doc_sync "DECISIONS noChange"). 정본 위치만 다름.
