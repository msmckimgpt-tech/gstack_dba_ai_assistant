---
run_at: 2026-08-28T08:00:00+09:00
session: ai/root/feature-0043-deferred-question
scope: feature-0043 미연결 질문 보관·이어받기 (deferred → 최근 1건 승격)
verdict: PARTIAL — 계약·배선·라이브 진단 PASS / 화면 시각검증은 브리지 setup 불가로 미수행
---

# Run — 미연결 질문 보관·이어받기 (TASK-20260828T080000)

Environment: **Windows-browser 미수행 (브리지 setup 불가)** + 라이브 DB 실측 + 컨테이너 pytest/ruff PASS

## 이 cycle 의 출발점 — 라이브 실측으로 원인을 확정했다

사용자 제보("인증을 포함한 요청 즉시 제목은 바뀌었지만 LLM 동작 자체가 막힘")를 라이브
`agent_memory` DB 로 대조했다(admin, account_id=10):

```sql
-- WebOAuthTokens (access) + WebAuthSessions
token 18 | session 708 | RevokedAt 2026-08-27 19:07:58 | session IsRevoked=1
token 21 | session 710 | RevokedAt NULL                | session CreatedAt 19:08:05
-- WebAiTasks: 19:08 대 질문 행 없음(= 적재되지 않음)
-- 같은 질문이 15:25:11 에는 적재 → 15:31:17 답변 제출 완료
```

| 시각 | 사건 |
|---|---|
| 15:16:16 | 로그인(세션 708) → 이 세션으로 AI 연결(토큰 18) |
| 15:25 | 같은 질문 정상 처리(적재 → 점유 → 제출) |
| **19:07:58** | **로그아웃 → 세션 708 폐기 + AI 연결 토큰 18 동시 폐기**(P0-R 의 의도된 동작) |
| 19:08:05 | 재로그인(세션 710) |
| **19:08:0x** | **질문 전송 → 그 시점 연결 없음** → 미적재 + "다시 질문해 주세요" |
| 19:09:04 | AI 재인증(토큰 21) |

**판정은 정확했다.** 결함은 그 다음 — 재입력 요구였다. 그리고 같은 스크린샷이 **제목 자동
설정(직전 cycle)이 작동함**을 함께 증명한다(적재되지 않은 질문인데 제목은 붙었다).

## Windows-browser 미수행 사유 (AGENTS.md §15.4.1 · PB-0008)

```
$ python3 bin/win-browser.py doctor
{"ok": false, "win_host": "8.8.8.8", "bridge_mode": null, "endpoint": null, ...}
```

WSL 이 Windows 호스트 IP 를 DNS 주소로 오판해 relay 대상이 성립하지 않는다. 해소책(관리자
PowerShell `netsh portproxy` / `.wslconfig` mirrored + WSL 재시작)은 이 세션 범위 밖이다.
직전 cycle 과 동일한 상태이며, **미수행을 미수행으로 기록한다.**

추가로 이 변경의 효과는 **연결이 끊긴 창에서 질문 → 재연결** 이라는 시퀀스가 필요해, 브라우저
단독으로는 재현할 수 없다(사용자 환경의 러너/MCP 연결이 함께 있어야 한다).

## 대신 검증한 것

### 1. 컨테이너 전량 테스트

`COMPOSE_PROJECT_NAME=repo make test` — feature-0002·0003·0014·0020·0023·0041·0043 전량 green,
`ruff` All checks passed. 실패 0.

### 2. 신규 계약 (`test_deferred_question.py`, 22건)

- 상태 정본: `deferred`/`expired` 존재·길이(VARCHAR(16))·취소 대상 포함·24시간 상한
- 승격 규칙: 최근 1건 선택 · 나머지 만료 · **승격과 만료가 한 문장**(동시 연결 중복 방지) ·
  실패가 도구 호출을 깨지 않음
- 적재 경로: 미연결도 적재 · 폴링 안 함 · 안내 문구가 재입력을 요구하지 않음 · 만료 안내 존재
- 배선: `list_open_requests`·`wait_for_request` 승격 · 루프 밖 1회 · 말풍선 정정이 웹 정본
  재사용 · 대기열 술어에 `deferred` 미노출
- codex 조치: 보상 삭제가 보류 포함 · 만료 정정 재시도 · 미연결 응답이 프런트 도달 ·
  `expired` terminal(서버·프런트)

### 3. codex 적대 리뷰 (REV-20260828T080000)

P1 5건 · P2 3건 적발 → P1 3 + P2 2 수정, 3건 한계 기록. 상세는
`unit/feature-0043-external-llm-bridge/docs/{REVIEW,FUNCTION}.md`.

## 배포 후 사용자 확인이 필요한 항목

1. AI 연결을 끊은(또는 로그아웃/재로그인) 상태에서 질문 → 말풍선이 "연결하면 이 질문부터
   처리합니다" 로 뜨는지(“다시 질문해 주세요” 가 아님).
2. 그 상태에서 AI 를 연결 → **다시 입력하지 않아도** 그 질문의 답변이 같은 말풍선에 나타나는지.
3. 연결 없이 여러 번 물었을 경우 — **마지막 질문 1건**만 답변되고, 나머지 말풍선은 "처리되지
   않았습니다" 로 바뀌는지.
