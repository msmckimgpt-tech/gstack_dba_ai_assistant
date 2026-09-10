---
description: "프로젝트 위키에 관해 질문하면, 관련 문서를 찾아 근거와 출처를 담은 답변을 제공합니다."
---

# /_template:wiki-query (Codex compat shim)

본 파일은 Codex CLI 호환을 위한 shim 입니다. **정본은** [`.claude/commands/_template/wiki-query.md`](../../../.claude/commands/_template/wiki-query.md).

Codex CLI 의 `/_template:wiki-query <question>` 호출 시 정본의 4-step workflow 를 따릅니다 (출처: SamurAIGPT/llm-wiki-agent 2.7k stars 의 CLAUDE.md Query Workflow).

## 호출

```
/_template:wiki-query LLM wiki 가 RAG 와 어떻게 다른가?
```

자연어:

```
what does the wiki say about <question>
```

자세한 spec 은 정본 참조.
