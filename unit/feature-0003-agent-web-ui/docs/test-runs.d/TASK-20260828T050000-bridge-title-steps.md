---
run_at: 2026-08-28T04:00:00+09:00
session: ai/root/feature-0043-bridge-title-steps
scope: feature-0043 대화 제목 2단 + 실행 단계 사유(브리지 경로) — 서버 라우터·MCP 어댑터·러너
verdict: PARTIAL — 계약·배선 검증 PASS / 화면 시각검증은 브리지 setup 불가로 미수행
---

# Run — 대화 제목 · 실행 단계 사유 (TASK-20260828T050000)

Environment: **Windows-browser 미수행 (브리지 setup 불가)** + 컨테이너 pytest/ruff PASS

## Windows-browser 미수행 사유 (AGENTS.md §15.4.1 · PB-0008 사유 명시 조항)

이 cycle 에서도 `bin/win-browser.py` 브리지가 성립하지 않는다 — 직전 cycle
(`REV-20260827T000500-bridge-poll-ui.md`)과 **같은 원인이 그대로**다.

```
$ python3 bin/win-browser.py doctor
{"ok": false, "win_host": "8.8.8.8", "bridge_mode": null, "endpoint": null,
 "issues": ["동작 중인 CDP 브리지 없음 — Windows Chrome 미기동이거나 WSL→Windows relay 미구성."]}
```

WSL 이 Windows 호스트 IP 를 DNS 서버 주소(`8.8.8.8`)로 오판해 relay 대상이 성립하지 않는다.
doctor 가 제시하는 해소책은 (A) 관리자 PowerShell `netsh portproxy` 또는 (B) `.wslconfig`
mirrored + WSL 재시작이며, 둘 다 이 세션에서 수행할 수 없다(관리자 권한 / 현 세션 종료).

**미수행을 미수행으로 기록한다** — 통과시키지 않는다.

추가로, 이 변경의 화면 효과는 **개인 AI 가 실제로 연결되어 질문을 처리해야** 나타난다
(제목 승급은 `submit_answer` 의 `title`, 단계 사유는 개인 AI 가 보낸 `reason`). 브라우저만으로는
재현할 수 없고 사용자 환경의 러너/MCP 연결이 필요하다.

## 대신 검증한 것

### 1. 컨테이너 전량 테스트 (`make test`)

`COMPOSE_PROJECT_NAME=repo make test` — feature-0002·0003·0014·0020·0023·0041·0043 전량 green,
`ruff` All checks passed. 실패 0.

### 2. 신규 계약 (`test_bridge_title_steps.py`, 42건)

- 제목: 적재 경로가 자동 제목을 붙이는가(연결·미연결 두 분기) · `submit_answer` 의 `title` 이
  전달 경로 끝까지 흘러가는가 · 보호 조건이 **UPDATE 문 안에** 있는가(TOCTOU 차단) ·
  `app` 재수출로 런타임 배선이 끊기지 않는가.
- 단계: 도구 호출 시점 기록 배선 · work/reason 두 축 적재 · 출처(`external-ai`/`derived`) 구분 ·
  narration 이 실행 인자에서 제거되는가 · 채번이 `pg_advisory_xact_lock` + 단일 INSERT 인가 ·
  원장 이관이 중복 방지 fallback 인가.
- 도구 스키마: 어댑터 2종 × 조사 도구 9종의 `reason` 수용·전달, 도구 설명의 사유 요구,
  `submit_answer` 의 `title`.
- 러너: `split_title` 값 검사 7케이스(마커 유무·대소문자·따옴표·중간 등장·`#` 없는 정상 줄·
  제목만 온 응답).

### 3. codex 적대 리뷰 (REV-20260828T050000)

P1 3건 · P2 5건 적발 → P1 전건 + P2 3건 수정, P2 2건 사유 기록. 상세는
`unit/feature-0043-external-llm-bridge/docs/{REVIEW,REPORT}.md`.

## 배포 후 사용자 확인이 필요한 항목 (화면)

1. 웹에서 새 대화에 질문 전송 → **즉시** 사이드바 제목이 질문 앞머리로 바뀐다.
2. 개인 AI 가 답변 제출 → 제목이 맥락 요약으로 승급된다(직접 rename 한 대화는 그대로).
3. 답변의 「실행 단계」에 각 단계마다 **사유(왜) + 작업(무엇)** 이 함께 보이고, 테이블/스키마
   이름이 들어간 구체 문구로 표시된다.
