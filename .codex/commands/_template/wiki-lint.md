---
description: "프로젝트 위키를 점검할 때, 끊어진 링크와 문서 형식·출처 표기의 문제를 찾아 보고합니다."
---

# /_template:wiki-lint (Codex compat shim)

본 파일은 Codex CLI 호환을 위한 shim 입니다. **정본은** [`.claude/commands/_template/wiki-lint.md`](../../../.claude/commands/_template/wiki-lint.md).

Codex CLI 의 `/_template:wiki-lint` 호출 시 정본의 6-category check 를 따릅니다 (출처: SamurAIGPT/llm-wiki-agent 2.7k stars 의 CLAUDE.md Lint Workflow).

## 호출

```
/_template:wiki-lint
```

자연어:

```
lint the wiki
```

structural 검사는 `bash bin/wiki-lint.sh` 가 자동, semantic 검사는 AI reasoning. 자세한 spec 은 정본 참조.
