# GEMINI.md

이 저장소의 공식 에이전트 운영 규칙은 `/repo/AGENTS.md` 를 따릅니다.

이 문서는 별도 정책 문서가 아니며, **Gemini CLI 호환을 위한 참조 파일** 입니다 (출처: https://github.com/SamurAIGPT/llm-wiki-agent — 2.7k stars, `CLAUDE.md` + `AGENTS.md` + `GEMINI.md` 3-schema 패턴).

## Gemini CLI 사용자

- 정책 정본: `/repo/AGENTS.md`
- Wiki 운용 정본: `/repo/docs/WIKI.md`
- Wiki vault: `/repo/wiki/`

Gemini CLI 는 slash command 대신 자연어 trigger 를 사용합니다 (출처: SamurAIGPT/llm-wiki-agent 의 multi-agent 호환 설명). 본 프로젝트의 wiki 명령은 다음 자연어로 호출:

| 자연어 trigger | 대응 slash command (Claude Code) | 작업 |
|---|---|---|
| "ingest this paper: wiki/raw/..." 또는 "raw/<file> 을 ingest" | `/wiki-ingest <path>` | source 를 wiki/sources/, entities/, concepts/ 에 합성 |
| "what does the wiki say about X" 또는 "wiki query: X" | `/wiki-query <question>` | Index 읽고 답변 합성 |
| "lint the wiki" 또는 "wiki 의 health 점검" | `/wiki-lint` | structural/semantic 검사 |

자세한 workflow 는:
- [`.claude/commands/_template/wiki-ingest.md`](.claude/commands/_template/wiki-ingest.md)
- [`.claude/commands/_template/wiki-query.md`](.claude/commands/_template/wiki-query.md)
- [`.claude/commands/_template/wiki-lint.md`](.claude/commands/_template/wiki-lint.md)
- [`docs/WIKI.md`](docs/WIKI.md) §6 — Workflow

## 다른 LLM agent compat 정보

- Claude Code: `/repo/CLAUDE.md` (thin redirect) + `/repo/.claude/commands/_template/*` (slash commands)
- Codex / OpenCode: `/repo/AGENTS.md` (정본) + `/repo/.codex/commands/_template/*` (slash commands compat shim, v3.6.1+)
- Cursor: `/repo/.cursorrules` (있다면 thin redirect to AGENTS.md)
- GitHub Copilot: `/repo/.github/copilot-instructions.md` (있다면 thin redirect)
- Gemini CLI: 이 파일

매핑 파일은 정책을 *직접 정의하지 않고* AGENTS.md 를 가리키는 참조 역할만 합니다.
