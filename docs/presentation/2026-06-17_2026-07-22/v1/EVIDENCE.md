---
doc_type: PRESENTATION_EVIDENCE
scope: project
status: active
source_of_truth: false
range: 2026-06-17 ~ 2026-07-22
baseline: 2026-05-19 ~ 2026-06-17
version: v1
created_at: 2026-07-21
companion: ./deck.html
---

# 근거·확인필요 원장 — 2026-06-17 ~ 2026-07-22 · v1

> 발표 본문(deck.html)·스크립트(SCRIPT.md)의 모든 주장은 여기서 추적된다. **확인필요(§2)** 항목은 발표 시
> "완료/개선/검증"으로 단정하지 말고 "개발 완료 · 배포/효과는 측정·검증 예정"으로 정직하게 표현한다.
>
> **수집 채널**: ①git(main 반영분 기준, first-parent 머지 521 PR · baseline = 2026-06-16 마지막 main 상태) ②정책·릴리즈노트(RELEASE_NOTES **07-10 까지 게재** — 07-11~07-22 는 미게재 doc-sync 브랜치 잔류) ③unit feature 기록(feature-0016/0019/0020/0021/0022/0012/0018→0003/0002/0007 REPORT·TASK·MODIFY·DECISIONS·REVIEW) ④개발 세션 transcript(보조 — 교차확인분만) ⑤이전 기간 발표자료(`docs/presentation/2026-06-17_2026-07-08/v1` — 겹치는 범위·연속성 baseline).
> 커밋 해시·PR#·CHG/ADR/TASK id 는 추적용 내부 참고이며 **청중 덱 본문 비노출**. 민감값(계정·비밀번호·토큰·접속좌표)은 원장에도 비노출.
>
> **이전 기간 비교 baseline(사용자 지정)**: 이번 범위(06-17~07-22)의 "이전 대비(신규/이어받음/완료)" 판정 기준을 **2026-05-19 ~ 2026-06-17**(직전 등길이 기간)로 설정한다. 그 기간은 **개별 대화 UI 다듬기(첨부·CSV·감사 드로어)·권한 체계(권한 트리·점진 공개·own/any)·데이터소스 관리(관리 UI·연결 상태)·안정화(insight livelock 수정)** 위주였고, **그룹/공유 협업·자율 지식·관계도 그래프·무중단 배포·추론 강도·메시지 편집·답변 자가검증은 전무**했다(git 실측: baseline 고유 feature 영역 8 vs 본 범위 18). 즉 이번 범위의 서사는 "개별 대화 기능 다듬기 → 협업·지식·관계도·신뢰·운영 플랫폼으로 도약".
>
> **범위 겹침 주의**: 직전 발표자료가 2026-06-17~07-08 을 다뤘다. 본 범위는 그 시작일과 같고 **07-08~07-22 를 2주 확장**하므로, 06-17~07-08 항목은 직전 deck 을 계승(이어받음/완료)하고 **서사 무게는 07-08 이후 신규 축**(메시지 편집·답변 자가검증·첨부 근거정합·PixiJS 렌더러 교체·콘솔 IA·무중단 커버리지 완성·AI 작업공간)에 둔다.

---

## 0. 이번 기간 KPI (표지·요약 수치의 근거·산식)

### E-000a · 진척한 기능 영역 = 18개 (지난 기간 8개)
- **kind**: git
- **ref**: 범위 커밋 subject+body 의 고유 `feature-00NN` 토큰 집계 = 18(0002·0003·0006·0007·0009·0010·0011·0012·0013·0014·0015·0016·0017·0018·0019·0020·0021·0022). baseline(05-19~06-16) 동일 집계 = 8.
- **status**: 검증됨 (git 이력, 재현 가능) — 단, 파생 성격이라 "개발 이력" 병기
- **note**: 활동량은 feature-0016(관계도 뷰)에 압도적 집중. "18"은 커밋에 명시된 feature-id 만 집계(활동 강도 아님). baseline 8 대비 확장은 그룹대화·관계도·무중단·메시지편집·자가검증·작업공간 등 신규 축 유입.

### E-000b · 개발·반영된 작업 단위(TASK) = 229건 (반영 PR 521건)
- **kind**: git
- **ref**: 범위 커밋 메시지의 고유 `TASK-*` 식별자 수 = 229 (`git log --since=2026-06-17 --until=2026-07-22` subject+body). first-parent 병합(PR) = 521.
- **status**: **개발 이력 집계** (검증됨 아님 — 표기도 "개발 이력 집계"로 낮춤)
- **note**: **산식** = 커밋 메시지 고유 TASK 토큰 수. feature 수(18)·PR 수(521)와 다른 축(1 TASK = 다수 커밋·1 PR = 1 논리 변경). 직전 기간 "159 TASK"(06-17~07-08)와는 범위가 다르니 직접 비교 금지(본 범위가 2주 더 김). 질문 시 이 규칙으로 방어.

### E-000c · 관계도에 자동 적재·군집한 데이터 객체 = 23,465개 (군집 3,652개)
- **kind**: git / unit-doc
- **ref**: feature-0016 content-cluster POST-DEPLOY(2026-07-13, PR #746/#748 → 87767ebe) — objects **23,465** / clusters **3,652** / error 0, AGE 수렴 cc_data_main Table 141/141·Routine 217/217. **PB-0008 실 Windows PASS**(그룹 138 중 컨텐츠 밴드 95 렌더·window error 0).
- **status**: 검증됨 (서버측 파이프라인 POST-DEPLOY + 밴드 렌더 PB-0008)
- **note**: **측정 위치 구분** — "23,465 objects / 3,652 clusters"는 **서버측 클러스터 파이프라인** 집계(테이블·컬럼·함수·프로시저 통합), 밴드 렌더는 **실 Windows 브라우저**. 직전 기간 KPI "함수·프로시저 2,201"(07-06 도달가능 4 ds)에서 축이 확장됨(전체 객체·군집). 이 숫자를 "함수만"으로 오독 금지.

### E-000d · 배포 중 사용자 접속 중단 = 0회 (무중단 운영)
- **kind**: git / unit-doc / release-note
- **ref**: feature-0014 REPORT/TEST(06-30 라이브 컷오버) + feature-0020 deploy-all(07-14, PR #780/#782 → eaba795a) POST-DEPLOY(웹·워커 healthy·엣지 /healthz 200·게이트웨이 무접촉). 부하 실증: 단일 replica 롤링 중 정상 클라 104/104 HTTP 200·0 실패·최대 0.27s(feature-0014). PG 재시작 중 RW 134/ERR 0(feature-0016-zd).
- **status**: 검증됨 (**부하 시험** — 단일 호스트·라이브 사용자 1명 조건)
- **note**: **측정 조건 필수** — 프로덕션 스케일 SLA 아님(단일 호스트). deploy-all 확장(워커·게이트웨이·엣지)은 배포 exit 0·healthy 확인됨. **단 "워커 자동 롤백"은 미실증(→ U-014)**. 무중단 자체는 06-30 이후 이어받음/완료.

---

## 1. 확인된 주장 (근거 있음)

> 테마별로 묶는다. 각 항목의 이전 대비: 신규(이번 착수) / 이어받음(직전부터 진행) / 완료(이번 마감).

### 테마 A · 대화 경험 고도화

#### E-001 · 대화별 추론 강도 4단계 + 런타임 예산 (이어받음→확장)
- **kind**: git / unit-doc / release-note
- **ref**: RELEASE_NOTES 07-06(reasoning-effort)·07-07(runtime-settings, feature-0018)·07-09(모델별 예산 상한 native 확대 Sonnet 128K·Haiku 64K + 강도별 분리 + 추론↔본문 비율 슬라이더). 낮음/일반/높음/매우높음 대화별 영구, '일반'=무주입(회귀 방지).
- **status**: 확인 — 07-06/07-07 base **PB-0008 PASS**(PR #594/#610). 07-09 확대분은 **배포·RELEASE_NOTES 게재(main) 확인**, 별도 PB-0008 명시 기록은 **확인필요**(→ U-010).
- **note**: '일반'=무주입은 의도된 회귀 방지 — 고정값 주입 시 선택기 미조작 Sonnet 대화가 기본값 강등되기 때문. baseline 엔 강도 선택·런타임 설정 전무 → 신규 축의 성숙.

#### E-002 · 메시지 편집(ChatGPT식) — 오타 수정 + 요청 바꿔 재답변 (신규·헤드라인)
- **kind**: git / unit-doc(REPORT/TASK/DESIGN/REVIEW) / dev-transcript(보조)
- **ref**: feature-0019-message-editing. 대화 내부 브랜치 트리(`parent_message_id`+`active_leaf`, 마이그 0041). 1:1=단순 수정 또는 요청 수정 시 분기 재답변(`<n/m>` 버전 페이징) / 그룹·공유=단순 수정만(@assistant 호출 메시지 편집 잠금·per-message sender IDOR 방지). 비분기 대화는 기존 경로 byte-동치(회귀 0, 15 테스트).
- **status**: 확인(개발 완료·배포·PB-0008) — Phase 1(1:1) 배포 e5f18b61 **PB-0008 라이브 PASS**(편집·재답변·`<n/m>` 페이징). Phase 2(그룹) 배포 3c487014 **PB-0008 라이브 PASS**(단순 수정만·재답변 버튼 미노출). 적대적 보안 리뷰 **Phase1 2 MAJOR + Phase2 1 MAJOR 수정**(동일-초 tie 서수 매핑·재답변 비원자성 보상복원·join 이벤트 role 비대칭). Major·PLAN-APPROVED. PR #766/#772/#774/#779/#781.
- **note**: **그룹 편집 보안 속성(잠금·IDOR·window 정합)은 코드 보안리뷰(REV-0005)로 결함 없음 확인**되었으나, 그 동작 자체의 별도 라이브 PB-0008 PASS 기록은 없음(PB-0008 은 UI=단순수정까지 실측). 단정 금지 → 세부는 U-011. 헤드라인 신규 기능.

#### E-003 · 응답 지연 타임아웃 복구 모달 제거 → 조용한 자동 재연결 (신규/완료)
- **kind**: git / unit-doc / release-note
- **ref**: RELEASE_NOTES 07-10(ask-timeout-nonblocking). 화면 전체 덮던 복구 모달(z-9999) 제거 → 모달·토스트 없는 자동 재연결, 취소/즉시답변 컴포저 인라인 상시.
- **status**: 확인 — 배포 4b6919ec **POST-DEPLOY PB-0008 라이브 PASS**. main RELEASE_NOTES 게재.
- **note**: 장시간 추론에서도 지연은 정상 — 전체 화면 차단은 과잉. 흐름 보존.

#### E-004 · 실시간 진행 표시 (관찰자·그룹 멤버) (신규)
- **kind**: git / unit-doc
- **ref**: feature-0003 realtime-progress(CHG-20260721T1758). 대화를 열어둔 유휴 관찰자/그룹 멤버에게, 재진입 없이 "처리 중" 말풍선·진행이 실시간 등장(배경 run-감지 폴러 ~4s / 숨김탭 15s → 검증된 loadHistory 경로 위임). 백엔드 무변경(frontend-only +133 app.js).
- **status**: 확인(코드/사전배포) — 유닛 23/23 PASS·feature-0003 pytest RC=0·실 Windows Chrome 유휴 탭 실측 스크린샷. PR #862 merged(2026-07-21). **배포후 별도 POST-DEPLOY PB-0008 라이브 PASS 기록은 확인되지 않음**(→ U-012).
- **note**: feature-0009 foreign-run 불변식 존중(내 run 갈아타기 금지). baseline 진행표시는 본인 요청 시점에만 시작 → 관찰 상태 실시간화가 신규.

### 테마 B · 답변 신뢰·정직 (신규 축)

#### E-005 · 답변 자가 적대 검증 (AI 가 자기 답변을 스스로 비판) (신규)
- **kind**: git / unit-doc(FUNCTION/REPORT/DECISIONS/TEST) / dev-transcript(보조)
- **ref**: feature-0021-redteam-review. 답변 확정 직후·저장 직전 단일 choke-point 에서, 초안 맥락과 분리된 별도 리뷰어가 5축(근거 정합/SQL 정확성/권한·정보누출/완전성/정직성)으로 적대 점검. BLOCK 시 제한 횟수 내 수정. 운영자는 관리 콘솔 "감사 > AI 추론"에서 조회(`console.reasoning.read`). 전 경로 fail-open(가용성 게이트 아님). 강도 게이팅(낮음=skip / 일반=1패스+1수정 / 높음=수정→재검증). `REDTEAM_ENABLED=0` 이면 기존 경로 동치. 마이그 0042(additive).
- **status**: 확인(개발 완료·배포) — 신규 유닛 34 PASS(redteam 18·agent_notes 8·admin_reasoning 8)·회귀 0. 배포 PR #819(23b8faba, 07-15). 콘솔 화면은 후속 IA/서브탭 PB-0008 POST-DEPLOY 라이브 기록 존재.
- **note**: **리뷰어의 실판정 품질(라이브 트래픽에서 결함 실제 검출)은 미측정 → U-013**. LLM-as-judge 정확도 golden 평가는 후속. 비용=답변당 리뷰 LLM 호출(저비용 모델·강도 게이팅·on/off·fail-open 으로 완화). "claude-code 식 자기 추론" 사용자 요청의 산물. baseline 엔 답변 2차 점검 전무 → 신규.

#### E-006 · 첨부파일 근거 정합 — 부분증거 과단정 환각 봉인 (신규·연속 완결)
- **kind**: git / unit-doc / policy-doc(LEARNINGS) / friction-ledger
- **ref**: LRN-20260714-0004(부분증거 전수단정 환각)·LRN-20260714-0003(형제표현 감사). 3면 봉인: 구조(소형 결과 절단 없이 ~12,000자·500행 전량 표시), 피드백(절단·차단 안내를 epistemic 하게 — 미열람 행 단정 금지), 계약(시스템 프롬프트 부재/전수 단정은 완전근거 필요·불가 시 '미확인' 명시). 결정론 도구 `check_table_coverage`(첨부 SQL 이 실DB 테이블 조작하는지 대소문자 무시로 코드가 판정 — CamelCase↔소문자 false-missing 봉인). 인라인 초과 노트를 거짓 인프라장애 대신 정직 노트로 교체. 신규 첨부 라벨 대칭.
- **status**: 확인(코드·유닛·배포) — `check_table_coverage` 유닛 12 PASS·회귀 0·§18.8 적대 2렌즈 봉인. 배포 PR #803(3c8e78df, 4서비스 실증)·#800/#809/#813·첨부 버전 PR #771. **단 "라이브 환각·false-missing 재발 감소"는 미측정 → U-013**(친수 이력 상태 전부 `fixed:deployed:unverified-live`, 외부 소스 DB 도달 불가로 end-to-end 라이브 재현 미완).
- **note**: 사용자 명시 불만("답변 내 환각이 극심합니다")이 재현됨 → 프롬프트 단일 레버로는 비결정 LLM 이 계속 미끄러진다는 실측 → 핵심을 **코드-권위 결정론**으로 이관(사용자가 Option C 명시 선택). "봉인했다"와 "라이브로 확인했다"를 분리 표기(정직).

#### E-007 · 대화 별칭 누출 가드 + 시스템변수 과차단 해소 (신규/완료·부수)
- **kind**: git / unit-doc / friction-ledger
- **ref**: conv-alias-leak-guard(PR #807, 3ae49153) — 대화 답변 클라이언트가 로컬 게이트웨이 별칭을 상류로 유출해 "Invalid model name" 400 유발하던 것을 안전 기본 모델로 fail-loud 해소(적대 패널 2차 400 반영). sysvar-guard(PR #792) — 읽기전용 SQL 가드 denylist 가 MySQL 시스템변수(`@@`) 읽기까지 과차단하던 것 허용(형제표현 함께 감사, 보안 회귀 0).
- **status**: 확인(머지·배포) — 별칭 가드 머지 확인·시스템변수 배포(9dce3caa). **라이브 무재발 실증은 확인필요**(→ U-013 계열).
- **note**: 둘 다 대화 감사(FRICTION_LEDGER) 유래 수정. 부수 항목 — 청중 덱에서는 신뢰 테마 보조로만.

### 테마 C · 함께 보기 (협업)

#### E-008 · 공유 가시성 [from,to] window + 보안 봉인 (이어받음/완료)
- **kind**: git / unit-doc / policy-doc(SECURITY §21) / dev-transcript(보조)
- **ref**: RELEASE_NOTES 07-04(share-visibility-window, Critical)·SECURITY §21/§21.1~21.5·feature-0009 CHG-20260704T130000·FUNCTION AC-GC-A20~A27. '여기부터/여기까지'로 `[from,to]` window 만 노출, 가려진 구간을 뷰·LLM recall·fork 3면 물리 배제(loader 단), fail-closed, join stamp never-widen(재공유 widen 403).
- **status**: 확인(기능·보안 개발 완료 — make test 28 신규 PASS + 적대 7-렌즈 패널). **라이브 시각검증은 U-009**(직전 기간 이월).
- **note**: 초기 recall 누출(적대 패널 M1 적발) → recall 까지 태그 확장 봉인(§21.4). "물리 배제"=인젝션으로도 없는 행 못 끌어냄. baseline 엔 공유 자체가 전체 노출 → window 격리가 신규 능력(직전 기간 착수, 본 기간 이어받음).

#### E-009 · 공유 링크 참여 알림 + 답변 리뷰 UX (이어받음·부수)
- **kind**: git / unit-doc
- **ref**: RELEASE_NOTES 07-03(gc-join-notice)·07-04(말풍선 ☰ 통합). 참여 시 '참여 알림' pill+기존 멤버 unread(`__event__` sentinel 로 LLM 히스토리 배제), 말풍선 액션 ☰ 통합(👍/👎만 외부), 공유뷰 mermaid 반응형.
- **status**: 확인(공유뷰 mermaid **PB-0008 실 Windows PASS**) — join-notice 는 적대리뷰 BLOCKING(참여이벤트 LLM 오염) 봉인.
- **note**: 부수 UX. 청중 덱 §함께 보기 보조로만.

### 테마 D · 자율 지식

#### E-010 · 용어사전 자율등록 + ENUM 코드사전 + 채택 인박스 통합 (이어받음→확장)
- **kind**: git / unit-doc / policy-doc(DECISIONS)
- **ref**: RELEASE_NOTES 06-29(용어 자율등록, ADR-20260629T101500)·07-07(ENUM 코드사전 alembic 0039·`kb.enum.curate`·채택 인박스 통합). AI 가 대화에서 용어·코드값 후보 제안(신뢰도 ≥0.85/0.9 자동승급·미만 검토 큐), 용어+ENUM+샘플 검수를 "채택 인박스" 단일 트리아지로 통합.
- **status**: 확인(개발 완료) — 용어 자동등록 13 + ENUM 코어 14 + 웹 9 테스트 PASS·호스트 스위트 1,581 PASS. 용어 역할 드롭다운 버그 **PB-0008 재검증 PASS**. **ENUM·채택 인박스 라이브 = U-009 계열**.
- **note**: 자동 학습은 원래 지식오염 방지로 막아온 것 → 하이브리드 자동승급+전수 감사+가역으로 안전하게 열음. baseline 엔 코드값 사전·채택 인박스 전무 → 이어받아 확장.

#### E-011 · 분석 기반 제품 분류 'AI 제안→사람 승인' (신규)
- **kind**: git / unit-doc / release-note
- **ref**: RELEASE_NOTES 07-08(§59, feature-local ADR-025). 데이터베이스→제품 매핑을 이름 규칙에서 분석 신호(테이블 구성·node_analysis)로 개선. 매핑 테이블이 에이전트 접근 allowlist 를 겸하므로 LLM 산출은 **Pending 적재까지만**(RuleId NULL) → 사람이 "✨ AI 분류 제안"에서 승인/거부. 환각 차단 3중 게이트(스키마 실재·연결 제품 화이트리스트·MIN_CONF 0.6)·데몬 기본 OFF.
- **status**: 확인 — POST-DEPLOY 라이브 실증(dry-run 11→10건 Pending 적재, PR #626). 접근 allowlist 무변경(보안 경계 신설 아님).
- **note**: "AI 가 제안하되 경계는 사람이 최종 승인" — 자율성과 안전 경계의 균형. 신규.

### 테마 E · 관계도 지도 (관리자)

#### E-012 · 평면 목록 → 대화형 노드 그래프 + 렌더러 PixiJS 전면 교체 (이어받음·대폭 확장 / 렌더러 교체=신규)
- **kind**: git / unit-doc(REPORT §77~82·BLUEPRINT) / policy-doc(SECURITY §19) / dev-transcript(보조)
- **ref**: feature-0016. (이어받음) AGE 그래프 DB + 노드 그래프(역할 색 Okabe-Ito·실선/점선 관계·함수/프로시저 ƒ/⚙·AI 능동 분석·크로스-DB). (신규 사건) **렌더 엔진 전면 이관 G6 Canvas → PixiJS v8 WebGL(07-13)** — 대규모 팬 버벅임 근본 해소, 게임엔진 기각(성능 원천=GPU 상주 씬은 WebGL 일반 속성이라 웹 스택으로 획득). 디자인 무붕괴 계약(D1~D6), 렌더러 seam 비상 폴백. 후속: 오브젝트 풀(선택 리빌드 183ms→30ms, 6배)·라벨 BitmapText.
- **status**: 확인(부분) — PixiJS 이관 **라이브 PB-0008 PASS**(실 Windows Chrome, 무중단 배포 후: §78 PR #752→d776f57b·§79 #755·§80 #759). 컨텐츠 클러스터 POST-DEPLOY+PB-0008 PASS(23,465 objects). 그래프 검색(컨텐츠·AI 분석 매칭+상세 리스트) POST-DEPLOY PB-0008 PASS(#842/#848). 미니맵 전체보기·상세 내비 sticky/scroll·hover-fx PB-0008 PASS.
- **note**: **핵심 정직 경고 — PixiJS 라이브 검증 규모는 409객체(건즈) 수준**이며, 정작 이관을 촉발한 **실 규모(수천 테이블·수만 함수·다수 펼침)에서의 라이브 팬 성능은 미확증 → U-016**. §80 커밋 스스로 "사용자 실 규모에선 Text 가 팬 붕괴"라 인정. 성능 수치 측정위치 구분: `60fps/p95 16.8ms`=실 Windows Chrome(845 등가씬/409객체), `11k 스트레스 22~31fps`=headless POC 무최적화 floor, `BitmapText 수천배`=통합 하네스. **ADR 번호 없음** — PixiJS 결정 기록은 BLUEPRINT/REPORT §78(청중 비노출). 렌더러 교체=신규 사건, 나머지=이어받음.

#### E-013 · 대규모 관계도 성능·정리 + AI 능동 분석 '주의' 실질화 (이어받음)
- **kind**: git / unit-doc / release-note
- **ref**: RELEASE_NOTES 07-10(§60~76). 세로 폭주 해소(적응형 폭 balance)·노드-레벨 컬럼 LOD·뷰포트 컬링(화면 밖 미그리기·참조 보존)·배치정렬 위상서명 메모이즈(882노드 7.4×)·미니맵 전체이미지 재사용·상단 툴바 13컨트롤→3존 통합. AI 능동 분석 '주의' 계약 재설계(§69, ADR-034 — 형식적 자기-불평 대신 실질 운영·보안 포인트만) T69.5 POST-DEPLOY(715/715 done·0 failed, PR #744).
- **status**: 확인 — §60~76 대부분 headless 테스트 PASS + 위상서명 메모이즈 POST-DEPLOY 882노드 7.4×(서버측). §69 '주의' 실질화 POST-DEPLOY 완수(사용자 원 리포트 해소, 사용자 릴리즈노트 편입). **화면 렌더 FPS 실 하드웨어 체감은 U-016**.
- **note**: 극단 줌아웃 클러스터 집계 카드(ADR-030/031)는 규모 파악 저해로 §67 폐기 — 정직한 되돌림. 측정위치=서버측/headless.

### 테마 F · AI 관제·콘솔 (운영)

#### E-014 · AI 운영 현황 패널 + 관리 콘솔 정보구조(IA) 개편 + 서브탭 (이어받음→완료)
- **kind**: git / unit-doc / policy-doc(SECURITY §20/§23)
- **ref**: (이어받음) RELEASE_NOTES 07-02(aiops-panel)·07-03(ds-avg-latency·aiops-ttft) — 관리>감사>'AI 운영 현황' 탭(worst-of 상태 배너·KPI·Attention·활동 feed·계측 커버리지), 지연 KPI 를 전체 왕복→단계 간격(step_gap)으로 재정의(alembic 0033). (신규/완료) feature-0021 console-ia(07-16) — 단일 'AI 추론' 탭(관측+설정 혼재) → **감사>AI 추론** / **설정>프롬프트 그룹** 성격 분리 + 감사 3탭→'AI 운영 현황' 단일탭+서브탭[LLM 사용량|운영 현황|추론] + 프롬프트 3항목→단일+서브탭 + 서브탭 sticky.
- **status**: 확인 — 패널 10/10+페이징 15/15+step-gap make test 1,430 PASS, ds-avg-latency **배포+PB-0008 PASS**. console-ia **POST-DEPLOY PB-0008 라이브 PASS**(PR #849)·console-subtabs 배포+PB-0008 PASS(#850). **패널 자체 라이브+지연 KPI 실트래픽 = U-015 / subtab-sticky 라이브 PB-0008 미기록**.
- **note**: 지연 KPI 재정의는 배포후 트래픽 축적 필요. IA 재편은 백엔드 엔드포인트 불변(console.reasoning.read 재배치·guidance 라우트 권한 재사용, 신규 권한 0).

#### E-015 · 권한 체계 카테고리 계층화 + 원자 단위 분리 (신규·완료)
- **kind**: git / unit-doc / policy-doc(SECURITY §22)
- **ref**: feature-0003 perm-category-hier(07-14)+perm-atomic-split(07-15). 카테고리 접근 권한 5종(`console.{account,product,audit,kb,system}.access`) — 각 nav 카테고리 조회 게이트, 하위 권한 종속(progressive disclosure). 사전 4종×CRUD 16 + product·datasource CUD/test = 원자 23종 신설(레거시 묶음 7종 grid 숨김·함의 유지). 그래프 뷰 권한 분리(`metadata.graph.read`·`metadata.graph.analyze`).
- **status**: 확인 — perm-category-hier **POST-DEPLOY PB-0008 PASS**(backfill 마커·계층 depth·admin 13탭, PR #801/#802). perm-atomic-split **POST-DEPLOY PB-0008 PASS**(원자 트리·레거시 묶음 0건, PR #810/#812). 접근 무손실 backfill(멱등 1회).
- **note**: **perm-atomic-split 은 UI 단독 아님** — 엔드포인트 enforcement 를 액션별 원자 단위로 전환(사전 22+제품 12+데이터소스 4 핸들러). 부작용 회귀 1건(작업화면 '연결 테스트' 버튼 미표시)→07-16 ds-test-gate-fix 로 복구(표시 계층만·백엔드 enforcement/보안 불변). Critical 변경이라 부여 조합 회귀 관찰 필요.

#### E-016 · 그래프 조작 도움말 + 우클릭 컨텍스트 메뉴 + 메타데이터 콘솔 재설계 (신규/이어받음·UI 단독)
- **kind**: git / unit-doc / release-note
- **ref**: (신규) graph-entry-help(07-14, 첫 입장 도움말 팝업·중간버튼 커서 표식)·graph-ctxmenu(제품 밴드/스키마 클러스터/컨텐츠 카테고리 3대상 각자 정합 메뉴·hit-test WYSIWYG). (이어받음) metadata-console redesign/polish/ux2(07-07~08, 채택 인박스·샘플 검수를 각 사전 하위 2차 보기로 통합·read-only 상세 패널·5서브뷰 폴리시).
- **status**: 확인 — 각 건 POST-DEPLOY PB-0008 라이브 PASS(win-browser). metadata-console 은 §18.8 3렌즈 적대 패널+PB-0008. **UI 단독 — 백엔드/RBAC/스키마 0**(graph-ctxmenu-category 리터럴 밴드 육안 1건만 DEFERRED).
- **note**: 연속 사용자 피드백 기반 반복 개선. 초심자 발견성·정확한 대상 판독.

### 테마 G · 기반·안정성

#### E-017 · 무중단 배포 커버리지 완성 — 웹+워커+게이트웨이+엣지 (완료)
- **kind**: git / unit-doc(REPORT/TASK/MODIFY)
- **ref**: feature-0020-zd-deploy-all(07-14). 기존 web 무중단(feature-0014)을 워커(insight/ask)·bedrock-gateway·caddy 로 확장. 워커 build-once 이미지 핀(`mysql-ai-agent:<sha>`)·healthy 게이트·last-good 롤백·게이트웨이 배포창만 surge replica(평상시 비용 0)·alembic stale-image 가드·워커 healthcheck 오탐 견고화(10s→30s).
- **status**: 확인 — PR #780(eaba795a) 라이브 배포 exit 0·웹/워커 healthy·엣지 /healthz 200·게이트웨이 무접촉(POST-DEPLOY #782)·4시나리오 dry-run·compose config 통과.
- **note**: **워커 자동 롤백 미실증(첫 배포는 last-good 부재)·POST-DEPLOY attended → U-014**. DB 엔진 HA·호스트 무중단은 단일 호스트 SPOF 로 범위 밖(구조적). insight-worker 크래시 3회 후 자동재시작 정지(폭주 억제)라 헬스 모니터링 병행 필요. baseline 엔 무중단 자체 전무 → 완료.

#### E-018 · 코드 자동 지도화 / LLM 내비게이션 완성 (완료)
- **kind**: git / unit-doc / policy-doc(AGENTS §21.11)
- **ref**: feature-0012 item10(app.py 19,650→3,722줄 -81%·148 라우트→21 도메인 라우터·결정론 AST 이동·route 스냅샷 byte-동치)+item11(인라인 인증 라우트 50개 전수 분류·누수 13개 DI 재작업)+code-nav(ROUTEMAP 자동생성·CODE_NAVIGATION 손유지·순환 폐쇄 정책 §21.11.7+CI 백스톱).
- **status**: 확인 — item10 라이브 a5ac1690·item11 4c203f9c(누적 배포·soak). 매 배치 게이트 GREEN(route 스냅샷 byte-동치·정적분석·pytest). blue-green 게이트가 추출 버그(ModuleNotFoundError·NameError 500) 실제 적발→수정.
- **note**: **인증 경로 DI-rework 브라우저 admin 로그인 최종 QA 는 사용자 환경 게이트 사인오프 대기 → U-014 계열**. 지도는 "링크"가 아니라 "이름+grep"(AI worker 실제 탐색 방식). "재배포 안정성·AI 위임개발 가속"으로 남는 결과. baseline 엔 라우터 모듈화 진행 중 → 완료.

#### E-019 · AI 작업 공간 격리 (신규)
- **kind**: git / unit-doc(REPORT/TASK/REVIEW/DECISIONS)
- **ref**: feature-0022-agent-scratch-workspace(07-21). 전용 DB `agent_scratch`+저권한 role(NOSUPERUSER, CONNECT 이 DB 로만 — 지식베이스/운영 DB 물리 도달 불가), 대화별 스키마(`s_<대화해시>`)+search_path pin+앱 가드 cross-schema 차단, 도구 4종(반입은 기존 SELECT 신뢰경계 execute_sql 재사용 — 유출 표면 증가 0), TTL reaper(기본 24h). 기본 OFF(운영자 bootstrap+enable 전 런타임 불변).
- **status**: 확인(개발 완료·배포·활성화) — 유닛 22 PASS(보안 guard·타입추론·enabled 게이트)·회귀 0. 라이브 배포·활성화(ba60f4b9·healthy)+적대 보안리뷰 반영(가드 allowlist 반전). 라이브 스모크가 실버그(run_sql SET 타임아웃 파라미터화 오류) 적발→수정(PR #861)→재배포·재스모크로 반입→JOIN 정상.
- **note**: **전체 e2e(두 소스 반입→JOIN→TTL DROP·대화 격리 라이브) TASK-0011 미완 → U-017**. 현재 대화 격리는 소프트웨어 guard 강제(PG 레벨 대화별 role 은 TASK-0013 후속). REPORT 본문 "라이브 deferred"는 초기 스냅샷 — TASK/REVIEW(source_of_truth)가 이후 라이브 활성화·재스모크 완료 기록(보고는 후자 기준). 신규.

#### E-020 · insight-worker 안정화 + 용도별 LLM 라우팅 + 헬스 프로브 (이어받음)
- **kind**: git / unit-doc / policy-doc(LEARNINGS)
- **ref**: (이어받음) RELEASE_NOTES 07-03(insight 부하분산·heartbeat·LLM fallback)·07-04(llm-routing-interactive-split — 실시간=claude 24/7 / insight 배치=시각 기반)·07-07(edge 폴백 차단, LRN-20260707-0001). (신규) llm-health-probe(07-15) — 잘못된 "사용량 소진" 배너 고착 해소(thinking 모델에 max_tokens=1 ping 이 항상 400 → 유효 ping+recovery-only gate)·probe-throttle-monotonic-flake(갓 부팅 워커 첫 복구 프로브 spurious throttle 수정).
- **status**: 확인 — 대화 답변 edge 폴백 차단 **LRN Verified**(live probe: chat→cloud·gemma 도달불가). health-probe 유닛 37 PASS·throttle 39 PASS·근본원인 재현 확정. **라이브 배너 자동해소 실증은 미완(TASK unchecked) → U-013 계열**.
- **note**: edge(gemma) 폴백이 07-07 역효과(두 계정 rate-limit 시 대화가 소형 맥락 모델로 조용히 강등·~30K 토큰 절단) → "라우팅 폴백은 능력 동등 or clean-fail" 교훈, edge-free alias+회귀가드 봉인. 정직 회귀 스토리.

---

## 2. 확인 필요 (근거 부족·불일치·단정 위험 — "완료/검증/배포"로 단정 금지)

### U-009 · 공유 window·ENUM 채택 인박스·제품분류 — 라이브 시각검증 (일부 이월)
- **왜 확인필요**: 기능·보안·테스트는 개발 완료이나 일부 PB-0008 = POST-DEPLOY(baked) 또는 미실측(직전 기간 이월 U-003/U-004).
- **가진 것 / 없는 것**: 있음=코드·테스트·적대 패널·POST-DEPLOY 일부. 없음=실 Windows 브라우저 육안(공유 ☰ 범위 배너·채택 인박스 왕복).
- **확인 방법**: 배포 후 PB-0008 실 Windows 시각검증.

### U-010 · 추론 예산 07-09 확대분 별도 PB-0008
- **왜 확인필요**: 07-07 base 는 PB-0008 PASS, 07-09 상한확대(Sonnet 128K·Haiku 64K)+강도별 분리+비율 슬라이더는 배포·RELEASE_NOTES 게재 확인이나 별도 PB-0008 명시 기록 없음.
- **가진 것 / 없는 것**: 있음=배포·게재·07-07 base PASS. 없음=07-09 확대분 실화면 PB-0008.
- **확인 방법**: 배포 후 PB-0008.

### U-011 · 메시지 편집 — 그룹 편집 보안 속성 라이브
- **왜 확인필요**: 그룹 편집 잠금(@assistant)·per-message sender IDOR·window 정합은 코드 보안리뷰(REV-0005)로 결함 없음 확인이나 별도 라이브 PB-0008 PASS 기록 부재(PB-0008 은 UI=단순수정까지 실측). TASK-P2-4·TEST 항목 미체크 잔존.
- **가진 것 / 없는 것**: 있음=코드 보안리뷰·Phase2 UI PB-0008. 없음=잠금·IDOR·window 동작 자체 라이브 육안.
- **확인 방법**: 배포 후 그룹 편집 시나리오 PB-0008.

### U-012 · 실시간 진행 표시 — 배포후 라이브 PB-0008
- **왜 확인필요**: 사전배포 실측(실 Windows 유휴탭 스크린샷)까지 확인, 배포후 별도 POST-DEPLOY PB-0008 라이브 PASS 기록 없음(테스트 빌드 검증 후 라이브 원복).
- **가진 것 / 없는 것**: 있음=유닛 23 PASS·사전배포 실측. 없음=배포본 POST-DEPLOY 육안.
- **확인 방법**: 배포 후 유휴 관찰자 시나리오 PB-0008.

### U-013 · 답변 신뢰 기능의 "효과(재발 감소)" 실측 (Critical — 단정 금지)
- **왜 확인필요**: 자가 적대 검증의 **리뷰어 실판정 품질**, 첨부 근거정합의 **라이브 환각·false-missing 재발 감소**, 별칭 가드·시스템변수·헬스프로브 배너해소의 **라이브 무재발**이 모두 미측정(친수 이력 `unverified-live`, 외부 소스 DB 도달 불가로 end-to-end 미완).
- **가진 것 / 없는 것**: 있음=코드·유닛·적대 패널·배포. 없음=라이브 트래픽에서 결함 실제 검출·환각 감소 수치.
- **확인 방법**: 다음 대화 감사(conversation_audit) corroboration 재측정 + 리뷰어 golden 평가.

### U-014 · 무중단 자동 롤백·인증경로 DI QA·헬스프로브 배너해소 — 라이브 실증
- **왜 확인필요**: 워커 자동 롤백은 첫 배포 last-good 부재로 미실증(POST-DEPLOY attended), 라우터 DI-rework 인증경로 브라우저 admin 로그인 QA 는 사용자 사인오프 대기, LLM 헬스프로브 라이브 배너 자동해소 TASK unchecked.
- **가진 것 / 없는 것**: 있음=배포 exit0·healthy·게이트 GREEN·유닛. 없음=실패 상황 자동롤백 실증·admin 로그인 최종 QA·라이브 배너 해소.
- **확인 방법**: 배포 리허설(자동롤백 유발)·admin 로그인 QA·배포 후 /api/llm/health 관측.

### U-015 · AI 운영 관제 패널 — 라이브 + 지연 KPI 트래픽 축적
- **왜 확인필요**: 패널 배포후 PB-0008 이연, 재정의 지연 KPI(step_gap)는 "배포후 트래픽 축적" 필요. subtab-sticky 라이브 PB-0008 미기록.
- **가진 것 / 없는 것**: 있음=10/10·15/15 테스트·ds-avg-latency PB-0008·console-ia PB-0008. 없음=패널 실화면·재정의 KPI 실트래픽.
- **확인 방법**: 배포 후 PB-0008 + 실트래픽 축적 관측.

### U-016 · 관계도 대규모 라이브 팬 성능(FPS) — 실 하드웨어·실 규모 (Critical 측정한계)
- **왜 확인필요**: PixiJS 이관 라이브 검증은 **409객체 규모만** — 이관을 촉발한 실 규모(수천 테이블·수만 함수·다수 펼침) 라이브 팬은 미확증(§80 커밋 자인). 화면 FPS 는 headless/WSL 실 GPU 미측정.
- **가진 것 / 없는 것**: 있음=409객체 60fps/16.8ms(실 Windows)·서버측 쿼리 60x·headless 11k floor. 없음=실 운영자 하드웨어·실 규모 체감 FPS.
- **확인 방법**: 운영자 실 PC·실 데이터 규모에서 프레임 트레이스.

### U-017 · AI 작업공간 — 전체 e2e·대화 격리 라이브
- **왜 확인필요**: 반입→JOIN 스모크는 확인, 전체 e2e(두 소스 반입→JOIN→TTL 만료 DROP·대화별 격리 라이브) TASK-0011 미완. PG 레벨 대화별 role 은 TASK-0013 후속(현재 소프트 guard).
- **가진 것 / 없는 것**: 있음=유닛 22·라이브 활성화·반입/JOIN 스모크. 없음=TTL DROP·대화 격리 라이브 실증.
- **확인 방법**: 라이브 e2e 시나리오 실행 + 대화별 role 후속.

### U-018 · 사용자 체감 개선폭 (속도·정확도·편의) 정량치 (이월)
- **왜 확인필요**: 수치 미측정 — 기능·수단까지 확인, "사용자 체감 몇 % 향상/정확도 향상폭"은 실사용 관찰 전(직전 기간 U-001/U-002 이월).
- **가진 것 / 없는 것**: 있음=기능 배포·PB-0008(일부). 없음=만족도·과업시간 단축·정확도 향상 수치.
- **확인 방법**: 실사용 로그·설문·A/B, 평가 harness.

### U-019 · 07-11~07-22 사용자 대면 릴리즈노트 main 미랜딩
- **왜 확인필요**: 메시지 편집·실시간 진행·계정 하위탭·애니메이션 설정 등 07-11~22 사용자 대면 릴리즈노트가 doc-sync 브랜치(`ai/claude/doc-sync-20260715-020501`)에만 있고 origin/main 미랜딩. unit 문서·git·배포 기준으로는 확인되나 릴리즈노트 게재는 미완.
- **가진 것 / 없는 것**: 있음=unit 문서·배포·PB-0008. 없음=main 릴리즈노트 게재.
- **확인 방법**: doc-sync 랜딩(문서 정합 작업 후속).

---

## 3. 특별 주의 항목 (단정 절대 금지 — §1/§2 로 분류 완료)

- **실제 배포 여부**: 라이브 배포 근거 종류 명시 = 머지/PR + POST-DEPLOY 기록 + PB-0008(일부). **운영 프로덕션 부하 로그는 원장에 미인용**(단일 호스트·라이브 사용자 1명 조건). 배포됨=E-002/E-003/E-005/E-006/E-011/E-012/E-014/E-015/E-017/E-019. 재배포/자동롤백/최종 QA 잔여=U-014.
- **테스트 결과**: 인용된 PASS 는 make test/컨테이너 스위트·유닛·적대 패널(§18.8)·PB-0008. 미검증 = U-009~U-018.
- **성능 개선 수치**: E-000c(23,465 objects=서버측 파이프라인)·E-013(위상 메모이즈 882노드 7.4×=서버측·이웃조회 60x=서버측)·E-012(60fps/16.8ms=실 Windows **409객체 한정**)·E-000d(부하 104/104·RW 134/0=단일 호스트 부하시험). **화면 FPS 실 규모=U-016(측정불가/미확증)**. 뭉뚱그린 "N배·60fps" 금지 — 항상 측정위치·규모·조건 병기. 특히 PixiJS "60fps"는 409객체 실측이고 실 규모 라이브 아님.
- **장애 재발방지 효과**: edge 폴백 맥락손실 봉인+회귀가드(E-020), '일반'=무주입 회귀가드(E-001), rel-selfheal 3일 정지 근본수정+AST 가드(직전), 첨부 부분증거 3면 봉인(E-006), 별칭 가드(E-007). **"가드 도입"까지 확인 — 재발 0 실증은 U-013(관측 이연)**.
- **화면 변경 전후 자료**: 실측 스크린샷은 unit TEST/evidence(PB-0008 PASS 항목)에 존재. **덱은 실측 화면 미첨부 → 전/후는 인라인 SVG 개념 도식(업무 관점) + "실제 화면 대신 개념 도식" 명시**(민감정보·계정 노출 회피).
- **문서-코드 불일치(conflict)**:
  - **C-1**: feature-0022 REPORT Summary "라이브 deferred"(초기 스냅샷) vs TASK/REVIEW "라이브 활성화·재스모크 완료" → **TASK/REVIEW(source_of_truth) 가 최신**. 덱은 "배포·활성화 완료"로 서술하되 전체 e2e(U-017) 병기.
  - **C-2**: PixiJS 교체는 **번호 ADR 없음** — 결정 기록은 unit BLUEPRINT/REPORT §78(청중 비노출). content-cluster 만 ADR 2건(ADR-20260713T105932/163000).
  - **C-3**: 07-11~22 사용자 릴리즈노트가 main 미랜딩(doc-sync 브랜치 잔류, U-019) — 배포·기능은 확인, 문서 게재만 미완. 청중 덱 무관(릴리즈노트 인용 안 함).
  - **C-4(청중 비노출)**: feature-0018(런타임 설정)·feature-0021(자가검증)·feature-0016 뷰 정본은 코드가 feature-0003/0002 에 거주하는 cross-cutting 라벨 — 오류 아님(추적 라벨 구조).
  - **C-5(청중 비노출)**: perm-atomic-split 은 UI 단독 아님(엔드포인트 enforcement 전환) — 부작용 회귀 1건(ds-test 버튼) 07-16 복구(보안 불변).
