# /_template:wiki-ingest (Codex compat shim)

본 파일은 Codex CLI 호환을 위한 shim 입니다. **정본은** [`.claude/commands/_template/wiki-ingest.md`](../../../.claude/commands/_template/wiki-ingest.md).

Codex CLI 의 `/_template:wiki-ingest <raw-path>` 호출 시 정본의 10-step workflow 를 동일하게 따릅니다 (출처: SamurAIGPT/llm-wiki-agent 2.7k stars 의 CLAUDE.md Ingest Workflow).

## 호출

```
/_template:wiki-ingest wiki/raw/articles/my-article.md
```

자연어 trigger (Codex / Gemini / OpenCode 의 multi-agent 호환):

```
ingest wiki/raw/articles/my-article.md
```

자세한 spec 은 정본 참조. Codex 와 Claude Code 의 *행동 차이는 0* — 둘 다 정본의 10 단계를 그대로 실행합니다.
