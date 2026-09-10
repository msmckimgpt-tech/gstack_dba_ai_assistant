---
description: "중단한 작업을 이어갈 때, 이전 대화와 현재 작업 상태를 확인해 남은 작업을 재개합니다."
---

# /_template:resume (Codex compat shim)

본 파일은 Codex CLI 호환을 위한 shim 입니다. **정본은** [`.claude/commands/_template/resume.md`](../../../.claude/commands/_template/resume.md).

Codex CLI 의 `/_template:resume <대상>` 호출 시 정본의 Phase 1~7 workflow(세션·worktree 추적 → 중단 지점 복원 → 거버넌스 게이트 따라 재개·완수)를 따릅니다. 인자가 비면 `/root/.claude`·`/home/claude-corp/.claude` 최근 세션을 순서대로 제시(read-only).

## 호출

```
/_template:resume <feature-id> 작업 이어서 재개
```

인자 없이 (최근 세션 목록 제시):

```
/_template:resume
```

자연어:

```
다른 세션에서 하던 <작업>을 이어서 재개해줘
```

**더 정확히 이어받기** — 제목만으로는 유사 제목이 많을 때 우열이 안 갈립니다. 그 세션의 마지막 답변에서 **중단 지점 한 줄**을 함께 주면 본문 literal 앵커로 정확히 확정됩니다:

```
/_template:resume "<제목>"

"<중단 시점 문장 그대로>"
```

## 세션 추적은 스크립트가 한다

정본 Phase 1·3 의 기계적 단계(Claude home 루트 탐지 · slug 변종 surface · self/tracker 제외 · 제목·중단신호·마지막 TodoWrite 추출 · worktree 매핑 · arg 해소)는 **`resume-probe.py`** 가 결정론적으로 끝냅니다 — 손으로 `python3 -c` heredoc 을 조립하지 마십시오:

```bash
REPO=$(git rev-parse --show-toplevel); [ -f "$REPO/repo/AGENTS.md" ] && REPO="$REPO/repo"
python3 "$REPO/.claude/commands/_template/resume-probe.py" --resolve "<사용자 arg 원문>" --repo "$REPO"
python3 "$REPO/.claude/commands/_template/resume-probe.py" --list -n 12 --repo "$REPO"
```

digest 는 재계산 없이 그대로 신뢰하고, verdict(`single` / `single-probable`=교차검증 후 "추정" 표기 / `ambiguous`=택일 질문 / `none`=권한 배제 후 fail-loud)를 채택합니다. `read_denied` 가 0 이 아니면 권한 실패이지 작업 부재가 아닙니다.

## 정본과 다르지 않은 점

- `AGENTS.md` **전량 Read 금지** — 집행할 앵커 조문(§16.3·§16.5·§13.2.4/.5/.7/.10·§18.3/.4/.8·§12.2/.3·§15.4.1)만 targeted read (정본 Phase 2).
- 채택한 잔여 목록이 빌 때까지 **turn 경계에서 멈추지 않음** (정본 6.3 하드스톱 해당 시에만 중단).
- 이어받은 산출물이 **타 계정 소유**일 때 §13.2.10 권한 어댑터로 복구 (정본 6.0-A).

자세한 spec(대상 해소·중단 복원·idempotency·완수 게이트)은 정본 참조. 행동 차이는 0.
