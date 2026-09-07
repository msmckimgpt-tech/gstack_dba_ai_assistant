---
name: _dqa-conversation_audit
description: "라이브 대화(그룹·1:1)에서 사용자가 겪은 마찰 — 명시적 신호(도구 거부·에러 반복·과도 재질문·brute-force·rate-limit 노출) + 암묵 이탈 신호(침묵 종료·체념·짧은 좌절 토큰·thumbs-down·수동 우회) — 을 직접 탐색·진단하고, 그 근본 원인을 코드가 거주하는 unit feature 에서 수정·검증·출하하는 cross-cutting maintenance persona. 사람이 필요 시 호출하거나 주기 정합으로 예약. 단건(한 대화 한 마찰) / 드레인(여러 대화·같은-뿌리 batch) 모드"
generated_by: codex-environment-install
managed_body_sha256: fce50a54837355d18e464ec64eebd907aff99b41442b61390c23a4688a70c10e
---

Read `.codex/CONTEXT.md` from the current policy root, then follow `.codex/commands/_dqa/conversation_audit.md`. Resolve the policy root from `repo/AGENTS.md` when launched in the wrapper, otherwise from `AGENTS.md`. Use the current user arguments as `$ARGUMENTS`.
