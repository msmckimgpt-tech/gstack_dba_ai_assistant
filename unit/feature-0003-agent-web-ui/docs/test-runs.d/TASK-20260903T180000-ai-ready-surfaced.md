---
run_at: 2026-09-03T12:40:00+09:00
session: ai/claude-corp/feature-0043-ai-ready-surfaced-to-ui
scope: 연결 칩 「답할 수 없음」 상태 신설 (TASK-20260903T180000)
verdict: PARTIAL
---

# Run — TASK-20260903T180000 (연결 칩 새 상태)

## Environment

- 변경 자산: `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js`
  (`_paintConn` 에 「답할 수 없음」 상태 추가 + 모달 성공 판정에 축 반영)
- 서버측: fast-path 스키마 2컬럼 · 저장·읽기·`connect_status` 노출

## 1. 배포 전 검증 (수행)

| 축 | 결과 |
|---|---|
| ESM 구문 | `node --check` PASS |
| 상태 사다리 순서 | 「답할 수 없음」이 「업데이트 필요」보다 **먼저**(단정으로 잠금) |
| 엄격 비교 | `aiReady === false` 만 — `undefined`/`null` 은 종전 상태 유지 |
| 죽은 가드 | 조건절 정확 일치 + 갈래의 문구 대입 단정(뮤테이션 I7 로 실증) |
| 모달 성공 판정 | `b.ai_ready !== false` 반영(단정으로 잠금) |
| 서버 회귀 | feature-0003 + feature-0043 컨테이너 **FAILED 0** |
| 뮤테이션 | **8종 전건 KILL** |

## 2. **Environment: Windows-browser — 배포 전 수행 불가(사유)**

이 cycle 의 새 상태는 **배포 후에만 화면에 나타난다**. 이유는 관측 가능하다:

- 새 상태의 입력은 `connect_status` 의 `ai_ready` 이고, 그 값의 출처는 **이번 cycle 이
  추가하는 서버 컬럼**(`WebOAuthTokens.RunnerAiReady`)이다.
- 배포 전 라이브 서버에는 그 컬럼이 없어 읽기가 `None`(모른다)을 돌려준다 → 화면은 설계대로
  **종전 상태**(대기 중/업데이트 필요)를 그린다. 즉 배포 전 브라우저에서는 이 분기를
  **원리적으로 재현할 수 없다.**
- 러너 쪽 신고는 이미 라이브에 있다(빌드 `21be250d67c8` = `ai_ready` 신고 포함, 실측
  하트비트 수신 중). 따라서 배포 직후 그 계정의 협상 실패가 반영되는 순간 새 상태가 뜬다.

**따라서 실 Windows 브라우저 Run 은 POST-DEPLOY 로 수행한다** — 그때 확인할 것:

1. 칩이 **「답할 수 없음」** 으로 바뀌는가 (현 라이브 계정은 `claude` OAuth 만료 상태라
   협상이 실패하므로 이 조건이 실제로 성립한다)
2. `title` 에 **사유**가 실리는가
3. 연결 모달이 그 상태를 **완료로 읽지 않는가**
4. 구 러너/미신고 계정에서 **종전 상태가 유지**되는가(tri-state 무회귀)

⚠ 이 항목을 「완료」로 적지 않는다(`verdict: PARTIAL`). 사용자 지적의 요지가 **화면이 거짓을
말한다**는 것이므로, 화면을 실제로 보지 않은 상태를 통과로 기록하면 같은 부류의 잘못을
검증 기록에서 반복하는 셈이다.
