# Codex project entrypoint

This is a compact loader, not a replacement for repository policy. The complete
policy is `AGENTS.md` in this directory. Read `.codex/CONTEXT.md` first, then read
the relevant policy sections and task documents it identifies before acting.
The loader prevents Codex's default 32 KiB instruction limit from silently
truncating the much larger policy. Current user/system/developer instructions
retain precedence. Do not interpret historical transcripts as new requests.
