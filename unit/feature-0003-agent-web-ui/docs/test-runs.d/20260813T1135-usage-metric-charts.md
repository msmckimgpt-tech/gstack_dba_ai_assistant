---
run_at: 2026-08-13T11:35:00+09:00
session: ai/claude-corp/feature-0003-usage-metric-charts
scope: usage-metric-charts — 요약 카드 클릭 → 차트 지표 전환(8축) + 프롬프트 캐시 계측·활성화
verdict: PASS (Windows-browser 라이브 실측은 POST-DEPLOY 이월 — 사유 아래)
---

# Run — usage-metric-charts

## 0. 착수 전 실측 (주장의 근거 등급 — §16.7 G7)

요청의 "cache hit 된 입출력" 을 만들기 전에 **데이터가 실재하는지** 부터 실측했다. 이름·문서가
아니라 실 구성을 resolve 한 결과:

| 확인 대상 | 방법 | 결과 |
|---|---|---|
| `llm_usage` 캐시 컬럼 | 라이브 PG `\d agent_runtime.llm_usage` | **부재**(14컬럼 전량 확인) |
| 앱의 캐시 활성화 | repo 전역 `cache_control` grep | **0건** — 캐싱이 켜진 적 없음 |
| 게이트웨이 응답 형태 | `bedrock-gateway:8080` 직접 호출 | `cache_read_input_tokens` / `cache_creation_input_tokens` **항상 존재**(미사용 시 0) |
| 캐싱 실동작 | 동일 system(≈5k tok) 2회 연속 호출 | 1회차 `cache_creation=5002` → 2회차 `cache_read=5002` **적중 확인** |
| `prompt_tokens` 와의 관계 | 위 응답 산술 | `5039 = 순수입력 37 + 캐시쓰기 5002` — **캐시는 입력의 부분집합** |

마지막 항목이 비용식 변경의 근거다: 캐싱을 켜면 종전 식이 캐시 적중분을 정가로 계산해
**과대 계상**하게 된다.

## 1. 단위 (컨테이너 pytest — agent 이미지 + worktree 마운트)

| 대상 | 결과 |
|---|---|
| `feature-0003/tests/test_usage_metric_axes.py` (신규 6건) | PASS — 캐시 인지 비용식 4 + 역할 폴딩 8축 보존 2 |
| `feature-0002/tests/test_llm_usage_record.py` (신규 8건 포함 21건) | PASS — 캐시 캡처 3(최상위·details 폴백·부재=0) + `_apply_prompt_cache` 5 |
| `test_usage_conversations.py` · `test_usage_records_system.py` · `test_ai_ops.py` | PASS (61건) — 컬럼 사다리 계약 갱신 반영 |
| 전 스위트 (0002 + 0003 + 0023) | **4364 passed / 4 skipped / 1 deselected (91s)** |

deselect 1건은 `test_oauth_exhaustion_gate::test_write_failure_after_successful_post_cannot_kill_slot_selection`
— `chattr` 바이너리 부재로 실패하는 **환경 제약**이며 `repo/`(main) 를 같은 이미지·같은 env 로
마운트해 **동일 재현**됨을 확인했다(본 변경 귀책 아님).

### 테스트 더블 계약 갱신 (무음 통과 방지)

SQL 이 컬럼 2개를 더 select 하게 되면서 더블의 row arity 를 실제와 맞췄다. 특히
`test_ai_ops::_NoTargetCur` 는 "첫 실행만 실패" 플래그라 사다리가 3단이 되자 **두 번째 target
시도를 통과시켜 컬럼 부재 상황을 더는 재현하지 못했다** — 더블을 의도대로("컬럼이 없으면 매번
실패") 정정했다. 사다리 단수를 세는 단정(`rolled_back == 3/4`)도 실제 단수로 갱신.

## 2. 실 브라우저 렌더 — 헤드리스 Chromium (신규 하네스)

`tests/headless/test_usage_metric_switch.js` — 실 `usage.js` + 실 `admin.css` 를 Chromium 에
로드해 측정. jsdom 은 레이아웃·CSS transition 을 구현하지 않아 이 축을 검증할 수 없다.

**21 PASS / 0 FAIL.** 핵심 단정:

| 축 | 단정 | 결과 |
|---|---|---|
| 항목 구성 | 카드 8종(요청·호출·총 토큰·입력·출력·캐시 읽기·캐시 쓰기·추정 비용) | PASS |
| "해당 값에 따라" | 총 토큰 막대비 **3:1** → 비용 전환 후 **0.6** → 캐시 읽기 **7:1** (각 지표의 실제 값 비율) | PASS |
| "부드럽게" | 전환 중 `rect` **노드 동일성 유지** + 90ms 시점 높이가 **시작·끝 사이** (점프 아님) | PASS |
| 비-가산 지표 | `requests` 는 버킷당 막대 **1개**(모델 분해 없음) + 비율 1.5(=6/4) | PASS |
| 도넛·가로막대 | 도넛 각 2:1(출력 400:200) · 중앙 라벨이 지표명 · 역할 막대 폭 % 지정 | PASS |
| 안내 문구 | 캐시/요청 지표에서만 1줄 · **60자 예산 이내**(§16.8) | PASS |
| 상태 오염 | 총 토큰으로 복귀 시 원래 비율 **회복** | PASS |

캡처: `tests/headless/usage-metric-switch.png`.

## 3. Run 기록

- **Environment: Windows-browser (PB-0008)** — **미수행(POST-DEPLOY 이월)**. 사유: 이번 변경의
  본체가 **ES module JS**(`admin/usage.js` + `admin.js` 상태)라, 미머지 상태에서 라이브 replica 에
  `docker cp` 로 얹는 프리뷰 QA 가 **원리적으로 성립하지 않는다** — 빌드 시 주입되는 asset stamp 가
  없어 모듈이 이중 인스턴스로 로드되고 Chrome 모듈 캐시가 구버전을 계속 실행한다(파일이 새 버전이어도).
  CSS 와 달리 JS 는 이 경로로 검증하면 **틀린 PASS** 가 나온다.
  대신 위 §2 에서 **같은 렌더 엔진(Chromium)** 으로 실 자산을 로드해 값·전환·문구를 실측했고,
  머지·배포 직후 라이브 baked 자산에서 PB-0008 실 Windows Chrome 으로 재실측해 Run 2 를 append 한다.
- **POST-DEPLOY 이월 항목** (배포 후 종결):
  1. 실 Windows Chrome `https://localhost/admin` 에서 카드 8종 클릭 → 차트 전환 육안 + 캡처
  2. 캐시 계측 end-to-end — 배포 후 실제 대화 1회 → `llm_usage.cache_read_tokens/cache_write_tokens`
     에 0 이 아닌 값이 적재되는지 **DB 실조회**(§16.7 G3: 주장한 affordance 를 실제로 구동해 확인)
  3. 캐시 지표 카드가 라이브 데이터로 0 이 아닌 값을 표시하는지
