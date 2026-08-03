# Run — 쿼리 리뷰 시간-방향 계약 라이브 실측 (PB-0008)

- **Date**: 2026-08-03 17:12~17:16 KST
- **Environment**: **Windows-browser** (`bin/win-browser.py`, 실제 Windows Chrome 150.0.7871.128, relay 브리지 `http://172.26.144.1:9223`)
- **대상**: `FR-review-frames-live-db-as-spec`(CHG-20260730T190000) + `FR-operator-global-prompt-shadows-code-seals`(CHG-20260731T030000) 의 **행동 변화 실측**
- **배포본**: main `954adc87` — web-a/web-b/ask-worker/insight-worker 4서비스 GIT_COMMIT=954adc87 healthy
- **판정**: **PARTIAL PASS** — 프레이밍 축은 재현 실패(=수정 성공), **접지 축에서 잔여 결함 1건 발견**

## 1. 재현 설계 (통제된 BEFORE/AFTER)

원 마찰 대화 `20260730074631-a2efa955`(2026-07-30, product 119, claude-haiku)와 **동일 조건**을 실제 브라우저로 재현했다.

| 축 | BEFORE (…a2efa955) | AFTER (…969946a2) |
|---|---|---|
| 제품 | 119 건즈 글로벌 QA | **동일** (GZ_QA_G, `mysql-gz-qa-global` 단일 DS) |
| 모델 | claude-haiku | **동일** |
| 요청문 | `첨부파일의 쿼리 리뷰를 진행해주세요.` | **동일** (20자) |
| 첨부 | 5개 `.sql` | **동일 파일** — MinIO 원본을 회수해 재업로드, **sha256 5/5 일치** (`9451c50ace`·`4fad880bcf`·`60ebf64ab8`·`5964a2af80`·`2ea40630a2`), 전부 `upload_status=uploaded` |

조작은 실제 브라우저에서 수행: `#newConversationBtn` 클릭 → 제품 dropup 에서 `(GZ_QA_G) 건즈 글로벌 QA` 클릭 → `#attachFileInput` 에 파일 5회 주입(DataTransfer, `multiple=false` 라 순차) → `#promptInput` 입력 → **`#sendBtn` 실제 클릭**.

## 2. PASS — 프레이밍 계약이 화면에서 확인됨

증적: `evidence/20260803-review-framing-after-top.png`, `evidence/20260803-review-framing-after-precondition.png`

| 계약 | BEFORE 관측 | AFTER 관측 | 판정 |
|---|---|---|---|
| 시간 방향 명시 | 없음 | 도입부 **"마이그레이션/신규 기능 추가 스크립트… 실제 DB 현황(BEFORE)과 비교하여"** | **PASS** |
| 최상단 배치 | `## 0. 배포 순서 의존성 (가장 중요)` | 파일별 **논리·설계 리뷰**로 시작 | **PASS** |
| 미배포 상태 표현 | "테이블은 **아직 존재하지 않습니다**" / "ServerID 컬럼도 PK도 **전혀 없습니다**" (핵심 지적) | `적용 전제` 표에 **✅ 신규 생성 예정** / **✅ 존재** | **PASS** |
| 전제 절 분리 | 결함과 혼재, 최상단 | **`📊 적용 전제 (배포 전 확인 체크리스트)`** 단일 절, 후반부 | **PASS** |
| 심각도 배지 귀속 | 🔴 Critical 이 "시그니처 변경"·"배포 순서" 에 부착 | 🔴🔴🟡🟡🟢 전부 **적용 후에도 남는 결함**(중복 결제 처리·PK 설계·인덱스·에러코드·주석)에만 부착 | **PASS** |
| 배포 순서 | 최상단 "가장 중요" | 말미 `생각해볼 점 → Q: 배포 순서는?` 정보 제공 | **PASS** |
| 리뷰 본문 축 | 현재 DB 와의 차이 나열 | PK 설계·인덱싱 전략·중복 결제 멱등성·에러 처리·타입/시간대 일치·동시성 | **PASS** |

동반 확인 — `search_routines` **본문 매칭 위치** 컬럼(REQ-20260731-routine-match-snippet)이 라이브에서 정상 동작:
호출부 4건은 실제 `CALL 'Log_AccountUpdateCash'(…)` 문맥 조각을 표시, 이름으로만 매칭된 1건은 **`(본문 외 매칭)`** + 사유 주석(이름·주석 매칭 또는 LIKE 와일드카드). §18.8 codex P2 로 교정한 "(이름 매칭)" 오단정이 실제로 나타나지 않는다.

## 3. FAIL — 잔여 결함: 미검증 부재 단정 (신규 발견)

`적용 전제` 표 2행:

> `ConcurrentUsers5Rocks_gunz 테이블` | ✅ 신규 생성 예정 | **현재 미존재**, CREATE IF NOT EXISTS 정상

**ground truth 대조 결과 이 주장은 거짓이다.** 같은 datasource(`mysql-gz-qa-global`)에 직접 조회:

```
information_schema.TABLES → ('gunzlog','concurrentusers5rocks_gunz', 1478400)   -- 실존, 약 148만 행
information_schema.COLUMNS 'ServerID' → 0                                        -- ServerID 컬럼 없음
```

- **도구로 확인한 적이 없다** — 이 run 의 도구 호출은 `search_routines`·`describe_table(CharacterCurrency)`·`search_tables(steampaymenthistory)` 3건뿐이고, 이 테이블을 조회한 호출은 **0건**이다. `BOTH SIDES BEFORE COMPARING`·부재 단정 금지 규칙 위반.
- **실질 손해**: BEFORE 답변은 이 테이블이 148만 행으로 실존하며 PK 가 없음을 확인하고 "PK 추가가 기존 데이터 중복으로 실패할 수 있다 → 중복 0건 검증" 까지 갔다. AFTER 답변은 미존재로 **가정**해 그 검증을 통째로 건너뛴다 — 대용량 테이블에 3중 복합 PK 를 추가하는 **실제 마이그레이션 리스크를 놓쳤다**.
- **방향이 뒤집혔다**: 원 마찰이 "현재 DB 기준 과잉 불평" 이었다면, 이 잔여는 **"적용 후를 가정한 과소 검증"** 이다. 시간-방향 계약이 명시한 라이브 대조 목적 **(a) 적용 가능성**이 지켜지지 않았다.

**red-team 자가검증은 이 건을 잡지 못했다** — `verdict=revise`·`block_count=1`·`unresolved=1` 로 BLOCK 은 냈으나 지적 내용은 (i) 첨부 excerpt 에 PK 정의 근거 부재(grounding BLOCK) (ii) `Log_AccountUpdateCash` 정의 미확인(WARN) 두 건이고, `현재 미존재` 오단정은 포함되지 않았다. 또한 **`revision_applied=false` / `revision_rounds=0`** — 수정 라운드가 돌지 않아 답변이 `⚠️ 내부 자가 검증 미해소` 배너와 함께 그대로 전달됐다(화면 확인). 사용자에게 미해소를 숨기지 않은 것은 정직하나, BLOCK 이 수정으로 이어지지 않은 점은 별도 추적 대상(feature-0021).

## 4. 결론

- **시간-방향 계약(A+B+C)은 실사용 화면에서 작동한다** — 사용자가 보고한 "현재 DB 기준으로 불평하듯" 프레임은 동일 입력에서 **재현되지 않았다**.
- **다만 같은 답변에 미검증 부재 단정 1건이 남아 `verified` 로 닫지 않는다.** 원장 `FR-review-frames-live-db-as-spec` 은 프레이밍 축만 실측 통과로 기록하고, 접지 축 잔여를 신규 항목으로 분리한다.
- 잔여 데이터: 재현 대화 `20260803081201-969946a2`(product 119, 5195자 답변, 도구 4회).
