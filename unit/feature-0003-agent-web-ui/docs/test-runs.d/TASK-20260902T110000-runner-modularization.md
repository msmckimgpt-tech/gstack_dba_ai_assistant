---
run_at: 2026-09-02T11:35:00+09:00
session: ai/claude/feature-0043-runner-modularization
scope: static/agent 배포 산출물 3종을 git 추적에서 제외 (내용 불변 — 빌드 생성물로 전환)
verdict: PASS
---

# Run — TASK-20260902T110000 (feature-0003 측 변경분)

본 cycle 의 실체는 feature-0043 러너 모듈 분할이다. feature-0003 에서 바뀐 것은
`src/static/agent/` 의 **배포 산출물 3종을 git 추적에서 뺀 것**뿐이다
(`bridge_agent.py` · `bridge_setup.sh` · `bridge_setup.ps1`).

## Environment

- 컨테이너 `repo-unittest-agent:latest`, worktree 마운트(`/work`), Makefile `test` 와 같은 배선
- **Environment: Windows-browser — 미수행(사유)**: 이번 변경으로 **브라우저가 렌더하는 표면이
  하나도 바뀌지 않는다.** 근거 3가지:
  1. **HTML·CSS·JS 변경 0** — staged diff 에 `.html`/`.css`/`.js` 파일이 없다.
  2. 추적 해제한 3파일은 **내용이 그대로**다. 빌드(`scripts/build_bridge_agent.py`)가 같은
     바이트를 만들고, 배포 경로 `/static/agent/*` 의 응답 본문은 종전과 동일하다
     (산출물 diff 는 러너 4,267행 중 57행이며 전부 접근자 전환·블록 이동·PEP8 — 화면 무관).
  3. 이 3파일은 **브라우저가 실행하지 않는 다운로드 대상**이다(파이썬 러너 + 설치 스크립트).
     `<script>`/`<link>` 로 로드되지 않으므로 렌더 트리에 들어가지 않는다.
- 카고컬트 회피를 위해, 화면과 무관하다고 단정하는 대신 **도달성**은 배포 후 실측 항목으로
  남긴다(§POST-DEPLOY) — 「렌더가 안 바뀐다」와 「내려받을 수 있다」는 다른 명제다.

## 회귀

feature-0003 포함 Makefile `test` 전 대상 **6,956건 rc=0**. 상세는 feature-0043 측 fragment
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260902T110000-runner-modularization.md`.

## POST-DEPLOY (배포 후 확인)

- [ ] `GET /static/agent/bridge_agent.py` 200 + 본문이 소스 빌드 산출물과 일치
- [ ] `GET /static/agent/bridge_setup.sh` · `bridge_setup.ps1` 200
- [ ] 연결 화면(모달·단독 페이지)의 1단계 명령 블록이 위 URL 을 그대로 가리키는지 육안 1회
