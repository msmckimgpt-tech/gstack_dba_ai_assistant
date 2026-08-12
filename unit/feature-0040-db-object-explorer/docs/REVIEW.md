---
doc_type: REVIEW
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: append-only
source_of_truth: true
---

# Review

## REV-20260812T030000-ai-claude-corp-feature-0040-db-object-explorer [SUBAGENT:self-review] — CONCERN

- Related TASK: feature-0040-db-object-explorer
- Trigger: schema/스키마 · API/엔드포인트 · UI/화면 keyword matched
- Timestamp: 2026-08-12T03:00:00Z
- Verdict: CONCERN
- Human Approval Needed: no

### 판단 근거

**1. 왜 역할 축인가 (대안 기각 근거는 ANCHOR §2)**
사용자가 "궁극적으로 모든 DB 시스템 대응" 을 명시했다. 벤더 객체축은 DBMS×객체로 도구가
곱해지고, 같은 일을 하는 객체가 이름만 달라 모델이 오판한다. 역할 축은 도구 2개를 고정한다.

**2. `DELEGATED` 상태를 왜 나중에 추가했나**
초판은 3상태(SUPPORTED/UNSUPPORTED/PRIVILEGED)였고, `routine` 이 하위클래스 지원표에
없어 기본값 UNSUPPORTED 로 떨어졌다 → 도구가 **"MySQL 은 프로시저를 지원하지 않습니다"**
라는 명백한 거짓을 냈다. 이 기능이 막으려는 실패를 이 기능이 저지른 셈이라, 상태를 추가하고
**base 클래스가 `OWNED_ELSEWHERE` 를 선점 처리**해 하위클래스가 실수할 수 없게 만들었다.
회귀 잠금(`test_routine_is_delegated_on_every_dialect`)은 신규 방언에도 자동 적용된다.

**3. `routine` 을 `db_objects` 로 이관하지 않은 이유 (ADR-DBOBJ-0001)**
개념적 정결함이 유일한 이득인데, 대가는 라이브 그래프 투영·능동 분석·크로스-DB 참조 파싱을
관통하는 회귀 위험이다. 경계를 taxonomy 에 **명시**(OWNED_ELSEWHERE + DELEGATED)해 두 벌
관리의 함정을 막았다.

**4. msdb 접근을 어떻게 좁혔나**
`msdb` 는 `system_databases()` 소속으로 freeform 하드 차단 대상이다. 구조화 경로만
`_agent_jobs_sql` **한 함수**에서 4개 뷰의 고정 조인으로 읽으며, 외부 입력은
`keyword`/`name`/`allow_dbs`/`schema`(전부 `_safe_ident` 정제)뿐이다. 임의 msdb 조회로
확장될 표면을 남기지 않았고, freeform 차단은 불변이다.

**5. 시노님 대상 마스킹**
`sys.synonyms` 는 `base_object_name` 이 allowlist 밖 DB·linked server 명을 노출한다는
이유로 freeform 화이트리스트에서 **의도적으로 제외**된 뷰다. 구조화 경로가 그 결정을
우회하면 안 되므로, 대상이 허용 범위 밖이면 **존재만 알리고 이름은 가린다**.

**6. 빈 allowlist 를 왜 `IN ('')` 으로 닫았나**
빈 `IN ()` 은 구문 오류이거나 엔진에 따라 필터가 사라져 **전 서버 작업이 노출**된다.
경계가 불명확할 때 넓게 여는 대신 닫는다(fail-closed). 회귀 잠금 있음.

**7. PRIVILEGED 역할의 prune 억제**
권한 부족으로 0행이 온 것을 "전부 삭제됐다" 로 읽으면 그래프 노드가 사라졌다 살아났다
진동한다. prune 을 **역할 단위**로 판정해 PRIVILEGED + 빈 결과면 억제한다.

### CONCERN (완료 판정에 영향)

**C-1. 라이브 시각검증 미수행.** 웹 자산 변경이라 `visual_verification_scope: always`
대상인데 수행하지 않았다. 사유는 (a) 정적 자산 baked → 재배포 선행 필요, (b) `db_objects`
SSOT 가 마이그레이션+insight cadence 이후에 채워져 그 전엔 **빈 상태 확인**에 그친다
(§16.6 「데이터 의존 UI 요소」 미충족). **이 기능은 라이브 시각검증 완료가 아니며**,
POST-DEPLOY 체크리스트를 TEST.md §3 에 명시했다.

**C-2. 비용 증가분을 정량화하지 못했다.** 능동 분석 시드에 역할 객체가 들어가 대상 수가
늘지만, 라이브 스키마별 역할 객체 수를 실측하지 않아 증가분을 수치로 말할 수 없다
(§16.7 G7-b — 표본 없는 정량 주장 금지). 배포 후 `db_objects` 행 수로 확인해야 한다.

**C-3. change-reanalysis 3축 미확장.** 역할 객체 변경이 자동 재분석을 트리거하지 않는다
(주기 introspect 로 SSOT·그래프에는 반영됨). 소비처 없는 `inventory_sink` 키를 채워
"감지된다" 는 인상만 남기는 대신, **넣지 않고 사유를 코드 주석·문서에 남겼다**.

### 검증이 실제로 잡은 결함 3건

1. **DbObject 가 `__terms__` 클러스터로 강등** — `_metaSchemaComboOf` 누락. 칩 색·아이콘은
   맞고 **자리만 틀리는** 형태라 코드 리뷰로는 놓치기 쉬웠다. 헤드리스 단언이 포착.
2. 위 **2번**(routine → UNSUPPORTED 거짓).
3. MSSQL cross-DB 경로 `r[1:]` 오프셋 오류로 본문 매칭 열이 조용히 비던 결함.

### 타 feature 테스트 수정의 정당성

`test_catcluster_panel_scroll.js` 단언 2건은 `_metaGraphRenderClusterDetail` 의 **인자
목록 전체를 pin** 해, 무관한 인자 1개 추가만으로 FAIL 했다. 지키려던 불변식은 "focusFam
관통" 이므로 그것만 남겼다. **뮤테이션 역검증**으로 보호 강도 유지를 실증(내 번들 PASS ·
baseline PASS · focusFam 제거 시 FAIL).
