---
run_at: 2026-09-01T14:40:00+09:00
session: ai/claude/selfreview-envelope-and-light-models
scope: "자가 검증 봉투 미해제 결함 수정 + 콘솔 작업 경량 모델 — 실 러너 end-to-end"
verdict: PASS
---

# Run — TASK-20260901T143000-selfreview-envelope

- **Environment**: container (`make test` 전량) + **실 러너 end-to-end**(bind-mount 격리
  인스턴스 `https://localhost:18095`, 실 claude CLI)

## 1. 결함은 라이브 실측에서만 드러났다

직전 cycle 배포 후 실제로 연결해 질문을 보냈다. 러너는 검증을 수행했고:

```
[bridge] t_4gYpIHeJg6DICuxL: 자가 검증 완료 (9416ms) — 제출에 동봉
[bridge] t_4gYpIHeJg6DICuxL: 제출 완료 (대화 반영=True)
```

**그런데 원장은 비어 있었다** — `redteam_reviews WHERE source='external'` 0 rows. 서버 로그에
경고도 없었다(파싱 실패가 `debug` 레벨이었다).

### 원인 — 봉투를 벗기지 않았다

러너가 보내는 것은 판정이 아니라 **봉투**다:

```json
{"raw": "{\"verdict\":\"pass\",\"findings\":[]}", "latency_ms": 9416, "model": "fable", ...}
```

서버는 이것을 `parse_review_text` 에 그대로 넣었는데, 그 함수는 **dict 를 받으면 이미 파싱된
판정으로 보고 그대로 돌려준다.** 그래서 `sanitize` 는 `verdict` 도 `findings` 도 없는 dict 를
보고 `None` 을 냈다 — **모든 자가 검증이 조용히 버려졌다.**

실 CLI 응답을 재현해 확증했다:

| 경로 | 결과 |
|---|---|
| `sanitize(parse_review_text(봉투))` ← 서버가 하던 것 | **None** |
| `sanitize(parse_review_text(봉투["raw"]))` | `{"verdict":"pass", …}` |

### 왜 단위 테스트가 못 잡았나 (이 cycle 의 진짜 교훈)

양쪽을 **각각** 검사했다 — 서버 테스트는 `sanitize(parse_review_text("<원문>"))` 을 **직접**
불렀고, 러너 테스트는 러너가 `{"raw": …}` 를 만드는지만 봤다. **이음매**(러너가 만든 그 값을
서버가 실제로 소비하는가)를 아무도 보지 않았다. 27건이 green 인 채로 기능이 0% 동작했다.

## 2. 수정 + 역검증

- `shared/self_review.from_runner_payload()` — 봉투 규약을 **계약 모듈 한 곳**에 둔다.
  관측 메타(지연·모델·등급)는 **봉투 것이 이긴다**(판정 본문의 같은 키는 AI 가 스스로 적은
  값이라 신뢰 등급이 다르다).
- 버린 사실을 `info` 로 남긴다 — 이 결함이 오래 숨은 이유가 정확히 **침묵**이었다.
- 이음매 테스트 6건 신설. 러너 봉투 모양은 **러너 소스에서 읽어** 재현한다(손으로 적으면
  러너가 봉투를 바꾸는 날 이 테스트만 낡아 같은 형태로 다시 깨진다).

**역검증**: 수정 전(`origin/main`) 사본으로 되돌려 실행 → **8건 FAIL**. 내가 만든 뮤턴트가
아니라 **출하된 코드**에서 죽는 것을 확인했다.

## 3. 실 러너 end-to-end (수정 후)

같은 경로를 처음부터 다시 탔다 — 토큰 발급(제품 API) → 러너 기동 → 웹에서 질문 전송.

```
[bridge] t_nlHATWUULdxtfE77: 자가 검증 완료 (13681ms) — 제출에 동봉
[bridge] t_nlHATWUULdxtfE77: 제출 완료 (대화 반영=True)
```

원장:

```
id=397 source=external task_id=t_nlHATWUULdxtfE77 verdict=revise
block_count=1 warn_count=0 model=fable reasoning_level=high latency_ms=13681 findings_n=1
```

**검증이 실제 결함을 잡았다** — 이 실행에서 답변 생성이 `exit 1` 로 실패해 자동 대체
안내문이 나갔는데, 검증자가 그것을 정확히 지목했다:

> `[BLOCK/completeness]` 초안이 사용자의 질문(대한민국의 수도)에 전혀 답하지 않고 오류
> 안내문만 담고 있다 · 근거: 본문은 'AI 가 오류로 끝났습니다(exit 1)' 뿐이며 '서울'이
> 어디에도 없다

설계 의도(검증하되 자동 수정하지 않는다)대로 답변은 그대로 전달됐고, **판정만** 화면에 남았다.

### 콘솔 화면

| 자리 | 값 |
|---|---|
| 운영 현황 KPI | `자가 검증 / 1건 / 결함 지적 1 · BLOCK 1 · WARN 0` |
| 축별 지적 표 | `완전성  BLOCK 1  WARN 0` |
| 브리지 작업 행 | `… 제출됨 · bootstrap_admin · 자가 검증 = BLOCK 1 · 답변 140 B` |

## 4. 콘솔 작업 경량 모델 (사용자 결정 2026-09-01)

> "관리 콘솔에서 이용될 모델은 모두 경량 모델로 구성해주세요. claude는 haiku, codex는 luna
>  모델과 같은 경량 모델로 작동해야 합니다."

**러너가 신고한 목록에서만** 고른다 — 없는 이름을 지어 보내면 러너가 그것을 CLI 인자로 넘겨
실행이 실패한다(P0-T 가 겪은 형태). 대조 실패면 빈 값이고 러너 기본값이 쓰인다.

실 러너 신고(`fable · opus · sonnet · haiku`)에서 선택 = `('claude','haiku')`.

실제 콘솔 작업(메타데이터 자동완성)을 제품 API 로 적재해 실측:

```
[bridge] j_ktxasPLY1drcu4eg: 내 AI(claude)에게 전달, 모델 haiku      ← 콘솔 작업
[bridge] t_nlHATWUULdxtfE77: 내 AI(claude)에게 전달, 모델 fable, 추론 high   ← 대화 (불변)
```

**대화 축은 건드리지 않았다** — 그건 사용자가 화면에서 직접 고른 값이다.

## 5. 미검증으로 남긴 것

- **codex 런타임의 `luna` 선택은 단위로만 확인**했다(이 머신의 codex 쿼터가 소진돼 실 기동
  불가). 선택 로직은 실 신고 형태(`gpt-5.6-luna` 접두 포함)로 테스트했다.
- 추론 등급은 낮추지 않았다 — 등급 어휘가 러너마다 달라(P0-Z3) 서버가 추측하면 「고른 적
  없는 값이 반영됐다」가 된다. 모델만 낮춘다.
