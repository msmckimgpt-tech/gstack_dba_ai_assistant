---
doc_type: MODIFY
feature_id: feature-0006-lan-proxy-access
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: LAN/TLS 운영 자산을 기능 단위 구조로 이관
- Files: src/caddy/Caddyfile, src/windows/*
- Notes: 인증서와 Caddy 상태 파일은 `../../../../artifacts`에 저장

## CHG-20260424-0002
- Date: 2026-04-24
- Related Requirement: TASK-0005 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — Windows portproxy + Caddy TLS 로컬 dev 구조의 존재 이유, 인증서 artifacts/ 분리 원칙, 프로덕션 cherry-pick 궤적(Caddyfile 유지, windows/ 제외, 공인 인증서 전환) 명시. 대안은 로컬 dev 맥락 유지(nginx/traefik 제외, 프록시 없는 각 서비스 직접 TLS 제외).
- Files: unit/feature-0006-lan-proxy-access/docs/ANCHOR.md, unit/feature-0006-lan-proxy-access/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. "이 feature를 프로덕션으로" 요청 시 §3의 cherry-pick 기준이 onboarding 진입점. dev-specific 경로 제거 판단이 Conflict Protocol 없이 자연 진행.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.
