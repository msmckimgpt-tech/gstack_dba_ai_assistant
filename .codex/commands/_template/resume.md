# /_template:resume (Codex compat shim)

본 파일은 Codex CLI 호환을 위한 shim 입니다. **정본은** [`.claude/commands/_template/resume.md`](../../../.claude/commands/_template/resume.md).

Codex CLI 의 `/_template:resume <대상>` 호출 시 정본의 Phase 1~7 workflow(세션·worktree 추적 → 중단 지점 복원 → 거버넌스 게이트 따라 재개·완수)를 따릅니다. 인자가 비면 `/root/.claude` 최근 세션을 순서대로 제시(read-only).

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

자세한 spec(대상 해소·중단 복원·idempotency·완수 게이트)은 정본 참조. 행동 차이는 0.
