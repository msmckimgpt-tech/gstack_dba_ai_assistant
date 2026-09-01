---
run_at: 2026-09-01T16:20:00+09:00
session: ai/claude/feature-0043-injection-fp-postdeploy
scope: 인젝션 오판 해소 POST-DEPLOY 실측 (배포 afcd1a42)
verdict: PASS (서버축 6/6 · 러너 배포 도달 4/4) — 사용자 왕복 1건은 사용자 확인 이월
---

# Run — 인젝션 오판 해소 POST-DEPLOY 실측

대상 배포: `afcd1a42` (scope=all). 배포 검증 체크리스트: web-a/b·ask-worker·insight-worker·
ext-tool-mcp-a/b **전부 동일 SHA** · caddy `no upstreams available` **0건** · surge 잔존 0 ·
대화 경로 스모크 PASS.

## 1. 서버축 — 배포본에서 직접 구동 (`docker compose exec web-a`)

| # | 확인 | 결과 |
|---|---|---|
| S1 | `wrap_principal_request` 가 `⟦USER-REQUEST⟧` 로 열고 `⟦UNTRUSTED-DATA⟧` 를 쓰지 않는다 | **PASS** |
| S2 | `wrap_conversation_history` 가 `⟦CONVERSATION-HISTORY⟧` 로 열고 `⟦UNTRUSTED-DATA⟧` 를 쓰지 않는다 | **PASS** |
| S3 | `_bridge_origin_preamble` 4요소(`config.json`·로그아웃·상위 안전 규칙·`⟦USER-REQUEST⟧`) | **PASS** |
| S4 | 새 sentinel 위조(`⟦USER-REQUEST⟧` 를 실은 입력)가 `neutralize` 로 판정된다 | **PASS** |

## 2. 자기강화 루프 차단 — **실제로 오염됐던 그 대화**로 실측 ⭐

배포본 `_recent_conversation_context(conn, '20260901030637-95dc8844')` 를 **라이브 DB** 에 대고
직접 호출했다. 이 대화는 assistant 턴 2건(msg 9142 · 9144)이 전부 인젝션 오판 거부문이다.

| # | 확인 | 결과 |
|---|---|---|
| S5 | 조립된 맥락에 거부문 본문이 **없다** (`'프롬프트 인젝션' and '따르지 않'` → False) | **PASS** |
| S6 | 제외 사실이 고지된다 — `[안내] 이전 assistant 턴 **2건**은 요청을 프롬프트 인젝션으로 오판해 중단한 응답이라 맥락에서 제외했습니다. 그 판단을 이어받지 말고, 위 요청을 그대로 수행하십시오.` | **PASS** |

즉 **이 대화는 더 이상 고착 상태가 아니다** — 다음 요청은 직전 거부를 근거로 받지 않는다.
원본 2건은 `core_messages` 에 그대로 남아 화면·감사에서 보인다(지우지 않았다).

## 3. 러너 축 — 「연결 준비」가 내려주는 실물

`curl https://<host>/static/agent/bridge_agent.py` (http=200, 214,898 bytes) 로 **서빙되는
사본**을 받아 그 파일을 직접 import 해 구동했다(소스 트리가 아니라 배포 실물).

| # | 확인 | 결과 |
|---|---|---|
| R1 | 서빙 사본 md5 = 정본 md5 (`966e77f1…`) | **PASS** |
| R2 | `compose_prompt` 출력에 역할 재지정 문형(「시스템 프롬프트로 삼아」·「너는 사내 DB 질의 어시스턴트다」) **부재** | **PASS** |
| R3 | `compose_prompt` 출력에 **평문 토큰 부재** + `BRIDGE_TOKEN` 안내 존재 + 조사 주소 출처(`config.json`·「제3자 주소가 아니다」) 명시 | **PASS** |
| R4 | `system_channel=True` 면 운영자 지침이 본문에서 빠지고, `build_cmd`+`_with_system_prompt` 가 `… --model opus --effort high --append-system-prompt <지침> <질문>` 을 만든다 | **PASS** |

## 4. UI 축 (check #13 이월분 정리)

- HTML·CSS·JS **변경 0** — 이번 cycle 의 `static/**` 변경은 러너 파이썬 사본 1개뿐이다.
  레이아웃·스타일·스크립트 회귀면이 없다.
- 유일한 UI 표면인 안내 1줄(`> 참고: 연결된 AI 가 …`)은 **오판 거부가 실제로 재발해야** 나타난다.
  이번 수정의 목적이 그 재발을 줄이는 것이라 의도적으로 재현하지 않았다.
- 해당 대화는 **사용자 계정(account 10) 소유**라 관리자 세션으로는 열람 경로가 없다 →
  **사용자 확인 항목**으로 이월(아래 5).

## 5. 사용자 확인 이월 (1건)

같은 대화에서 다시 질문했을 때 답변이 거부문이 **아닌** 실제 쿼리 리뷰인지 —
러너를 띄운 사용자 본인만 왕복시킬 수 있다. 러너측 수정(R2~R4)까지 받으려면 화면의
**「연결 준비」를 한 번 더** 눌러 최신 러너를 내려받아야 한다(불일치 시 `stale_build` 표시).
서버측 수정(S1~S6)은 **이미 발효 중**이라 러너 갱신 없이도 대화 고착은 사라진 상태다.
