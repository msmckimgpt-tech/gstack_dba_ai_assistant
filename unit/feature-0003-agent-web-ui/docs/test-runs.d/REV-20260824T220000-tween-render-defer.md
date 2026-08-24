---
run_at: 2026-08-24T22:20:00+09:00
session: ai/claude-corp/feature-0003-tween-render-defer
scope: 트윈 중 재렌더 보류 — CHG-20260824T220000-tween-render-defer
verdict: PASS (Environment: Windows-browser)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

- 대상: 라이브 web 이미지 + worktree `src/static` bind-mount(`web-verify-dnd`, `https://localhost:18097`).
  서빙 판정은 `docker exec grep` 으로 컨테이너 안 파일 직접 확인(`sidebarTweenUntil` 3건).
- 계측: 목록 컨테이너에 `MutationObserver(childList)` 로 **렌더 시각**을, rAF 로 대상 행의 computed
  transform(vy)을 함께 기록 — "트윈이 언제 끊겼는가" 를 렌더 이벤트와 대조해야 원인이 드러난다.

## 수정 전/후 대조 (같은 조작: 대화를 폴더로 드래그, 30px 이동)

| | 렌더/트윈 시퀀스 |
|---|---|
| **전**(배포본 `abc1a1a9`) | `t=173 렌더(invert 30px)` → `vy 30 → 21 → 14` → **`t=241 재렌더 → tf 비워짐`(절단)** |
| **후** | `t=73 렌더(invert 30px)` → `vy 30 → 21 → 14 → 9 → 5 → 3 → 2 → 1`(**123ms 완주**) → `t=308 보류분 렌더 1회` |

전(前)에는 트윈이 목표까지 가지 못하고 vy 14 에서 잘렸다. 후(後)에는 vy 1 까지 감속을 마친 뒤,
보류됐던 후속 렌더가 트윈 종료 후 **한 번으로 합쳐** 실행된다.

## 이 Run 이 확정한 것

직전 cycle 의 수정(대화 이동의 즉시-렌더 제거)은 **불충분**했다. 이동 직후에는 읽음 처리·히스토리
로드 등 후속 갱신 렌더가 여럿 따라오고, 그 중 하나만 트윈 창에 겹쳐도 재구성이 진행 중인 transform
을 지운다. 경로를 하나씩 막는 접근은 새 경로가 생길 때마다 다시 뚫린다 — 그래서 **렌더 wrapper
한 지점**에서 보류하도록 바꿨다(병렬 세션이 IME 조합용으로 이미 만들어 둔 보류 경로를 공유).

## 미수행

라이브 서빙본 재확인은 배포 후 POST-DEPLOY 로 수행한다.
