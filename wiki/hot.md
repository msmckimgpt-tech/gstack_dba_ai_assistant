---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-23
---

# Hot Cache

## Last Updated
2026-06-23

## Key Recent Facts
- feature-0010 신설(토대): 계정별 Google Drive 연동 인증 구조 + MCP 구성. `WebGoogleDriveTokens`(cred_crypto AAD=gdrive:{account_id}) + connect/callback/status/disconnect(flag OFF→404) + gdrive-mcp seam A. 연동 미수행/비활성/외부호출 0.

## Recent Changes
- app.py(feature-0003) 인라인 인증 코드 + bin/gdrive-mcp.sh + docker-compose gdrive-mcp(profile gdrive) + src/gdrive_mcp_seam.py + .env.oauth/.env + SECURITY §16 + ARCHITECTURE 기능맵(0010).

## Active Threads
- feature-0010 활성화 cycle 이월: 라이브 토큰교환·refresh 회전·Google revoke·설정 UI·mcp_client seam 배선.
- insight-worker(TASK-0305) GRANT 적용 · NL2SQL few-shot A/B.
