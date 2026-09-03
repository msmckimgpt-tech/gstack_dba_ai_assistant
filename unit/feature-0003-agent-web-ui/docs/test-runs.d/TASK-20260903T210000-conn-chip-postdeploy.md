# TASK-20260903T210000 — 연결 칩 3상태 POST-DEPLOY 실측 (배포 b3a4fff1)

- verdict: PASS
- 대상: TASK-20260903T200000(3상태) + TASK-20260903T210000(CSS 범위) 두 cycle 의 합
- 배포: `0d641ea8`(3상태) → `b3a4fff1`(CSS 수정). `no upstreams available` **0건**(Caddy 실측)

## 1. **Environment: Windows-browser** — 3조건 대조 실측

같은 계정·같은 토큰에서 **가짜 AI 의 응답성만** 바꿨다. DB 를 손으로 고치지 않았다 —
토큰은 제품 함수 `issue_token_pair` 로 발급하고, 상태는 러너가 신고한 것만 읽었다.

| 조건 | 러너 사건 | 서버 원장 | API `ai_ready` | 칩 |
|---|---|---|---|---|
| **A. 확인 중** (매달리는 AI, 상한 900초) | (진행 중) | `RunnerAiReady=NULL` | `null` | **「확인 중」** `state=checking` `rgb(71,85,105)` `::before "◌ "` |
| **B. 정상** (즉답 AI — 대조군) | `caps.liveness_ok` | `=1` | `true` | **「대기 중」** `state=on` `rgb(21,128,61)` `::before "● "` |
| **C. 불가** (매달리는 AI, 상한 15초) | `caps.liveness_fail` | `=0` + 사유 | `false` | **「답할 수 없음」** `state=off` `rgb(180,83,9)` `::before "○ "` + `title` 에 사유 |

세 조건 모두 `listening: true` 다 — **러너는 살아 있다.** 종전 코드는 이 셋을 전부
「대기 중」(정상)으로 그렸다. 그것이 사용자가 지적한 거짓이다.

조건 C 의 사유 원문(화면 `title` 에 그대로):

```
이 컴퓨터의 custom 가 응답하지 않습니다 — TimeoutExpired: Command '['/tmp/…']' timed out after 15.0 seconds
```

## 2. 칩 색 — 라이트 모드 실 렌더

CSS 수정(`@media` 미닫힘) 전/후 대조. 측정은 실 Windows Chrome + `getComputedStyle`:

| 상태 | 수정 전 | 수정 후 |
|---|---|---|
| `checking` | `rgb(0,0,0)` · 배경 투명 · `::before none` | `rgb(71,85,105)` · `rgba(71,85,105,.08)` · `"◌ "` |
| `idle` | (동일하게 무스타일) | `rgb(146,64,14)` |
| `stale` | (동일하게 무스타일) | `rgb(29,78,216)` |
| `on` | `rgb(21,128,61)` (정상) | `rgb(21,128,61)` |

`idle`·`stale` 은 **이 세션 전부터 깨져 있던 선재 결함**이다 — 「확인 중」을 넣다가 드러났다.
네 상태가 모두 서로 다르고 정상(`on`)과 구별된다: `allDistinctFromOn: true`.

파싱된 스타일시트 재확인: `checking` 셀렉터 **7건**(수정 전 **0건**). 8개 시트 중 7개 스캔,
1개는 교차출처(bunny.net 폰트)로 접근 불가 — 우리 규칙과 무관.

## 3. 서버 배포 실물 확인

```
$ docker exec repo-web-b-1 python3 -c 'inspect.signature(oauth_store.set_runner_ai_health)'
(cur, raw_token, ai_ready, reason, *, reported: 'bool | None' = None) -> 'bool'
```

`reported=` 가 배포본에 실물로 있다(「키 없음」과 「`null` 신고」를 가르는 축).
러너 번들도 확인: `note_ai_probing`·`ai_blocked`·`confirm_ai_or_report`·`verify_ai_liveness`
전부 서빙 중이고, `body["ai_ready"] = None if _ai_ok is None else bool(_ai_ok)` 도 그대로.

라이브 스키마: `RunnerAiReady tinyint(1) NULL` · `RunnerAiUnreadyReason varchar(300) NULL`
— 이번 두 cycle 은 마이그레이션 불필요.

## 4. 사용자 실 계정(10) 라이브 상태 — 합성이 아닌 실제

사용자 러너가 14:23~14:24 에 **자기갱신**(`run.selfupdate` → `e4651e04c152`)해 새 빌드로
돌고 있고, 그 관측이 서버 원장에 도달했다:

```
token 228  RunnerAiReady=0
  reason="이 컴퓨터의 claude 가 응답하지 않습니다 — TimeoutExpired: …claude.exe -p…"
  RunnerBuild=e4651e04c152   LastHeartbeat=16:37:14 KST
account_ai_health(10) → False
```

⇒ 사용자 화면은 **「답할 수 없음」 + 사유**다. 종전이라면 「대기 중」이었다.

⚠ 토큰 회전 축 확인: 계정 10 의 최신 행은 `253`(NULL, 하트비트 없음 = refresh 행)이지만
`account_ai_health` 는 `_LIVE_TOKEN_PREDICATE` 로 실제 하트비트 토큰(228)을 읽는다 —
회전이 판정을 NULL 로 리셋하지 않는다. 이것을 의심해 직접 확인했다(추정 아님).

## 5. 정리

- 테스트 러너 프로세스 **0**
- 테스트 토큰 248·249·250·251 **폐기 완료**(전부 `RevokedAt` 설정 확인)
- 가짜 AI 하네스 `/tmp/fakeai2` 제거
- **사용자 계정 10 은 읽기만 했다** — 어떤 행도 쓰지 않았다

## 6. 남긴 미검증 (정직 표기)

- 질문을 **이미 보낸 뒤** 확인이 실패로 떨어지는 창(기본 상한 30초)에서 그 질문은
  즉시-정직-응답 경로를 타지 못하고 정상 경로로 처리된다. 종단 보장은 P0-AK 소관이며
  이 두 cycle 이 좁히지 않았다.
- 다크 모드 렌더는 측정하지 않았다(브라우저가 라이트 모드). 다크 규칙은 정적 검사로만
  확인했다.
- 사용자 머신의 `claude` 재인증 자체는 사용자 조치다. 이 작업이 고친 것은 **그 상태가
  화면에 정직하게 나타나는가** 이며, 사용자가 말한 대로 인증 상태는 현상일 뿐이다.
