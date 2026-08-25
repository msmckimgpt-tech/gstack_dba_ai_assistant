---
run_at: 2026-08-25T10:55:00+09:00
session: ai/claude/ctxmenu-order-parity
scope: 폴더·대화 우클릭 메뉴 순서 정합 — REQ-20260825T1030-ctxmenu-order-parity
verdict: PASS (Environment: Windows-browser)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

- 브리지: `bin/win-browser.py` relay @ `http://172.26.144.1:9223`, Chrome/151.0.7922.170.
- 대상: **미머지 브랜치를 라이브 무접촉으로** 보기 위해 라이브 web 이미지(`mysql-ai-web:9f4a82e4`)
  + 본 worktree 의 `src/static` bind-mount 컨테이너(`web-verify-ctxmenu`, `https://localhost:18099`,
  로그인 `bootstrap_admin`). 라이브 web-a/web-b·caddy 무접촉.
- 계측: 실제 **우클릭**(`mouse.click(button="right")`)으로 메뉴를 열고 렌더된 항목의 textContent 를
  순서대로 수집 — 코드 문자열이 아니라 화면에 그려진 순서를 본다.

## 실측 — 세 케이스 모두 규칙 준수 (PASS)

| 대상 | 실측 순서 | 첫/끝 고정 |
|---|---|---|
| **하위 폴더**(부모 있음) | `이름 변경 · 하위 폴더 추가 · 최상위로 꺼내기 · 설정` | ✓ |
| **최상위 폴더**(꺼내기 미표시) | `이름 변경 · 하위 폴더 추가 · 설정` | ✓ |
| **대화** | `이름 변경 · 공유 · 이동 · 설정` | ✓ |

조건부 항목(`최상위로 꺼내기`)이 빠져도 남은 항목의 상대 순서와 첫/끝 고정이 유지된다
(AC-…-2). 종전 폴더 메뉴는 `하위 폴더 추가 · 이름 변경 · 설정 · 최상위로 꺼내기` 였다 —
공통 항목 두 개(`이름 변경` 2번째, `설정` 3번째)가 대화와 어긋나 있었다.

캡처: `artifacts/pb0008-ctxmenu/folder-nested.png`(하위 폴더 4항목) ·
`folder-root.png`(최상위 폴더 3항목) · `conversation.png`(대화 4항목).

## 잔류물 (§16.6 (f))

- 검증용 폴더 2개(`메뉴순서 검증(상위)`/`(하위)`)를 만들고 삭제했다 — 상위 `DELETE` 200,
  하위는 상위 삭제에 함께 정리되어 404(정상). 라이브 대화·폴더 무변경.
- 검증 컨테이너 `web-verify-ctxmenu` 는 검증 종료 후 제거한다.

## 미수행 (사유 명시)

- **동작 재검증은 하지 않았다** — 이 cycle 은 항목의 *순서*만 바꾸고 각 항목의 `onSelect`·
  `action` 배선은 건드리지 않았다. 각 항목의 동작은 직전 cycle
  (`REV-20260824T173000-sidebar-rename-focus`)에서 라이브 실측했다.
- **키보드 내비게이션 순서**(Tab/방향키)는 별도 확인하지 않았다 — 메뉴 항목은 DOM 순서를 그대로
  따르므로 시각 순서와 일치한다.
