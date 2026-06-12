---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, security, datasource, ssrf]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0030
linked_canonical: ../../docs/DECISIONS.md#ADR-0030
status_adr: accepted
created: 2026-06-11
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0030 — datasource SSRF 사설망 경계 env 토글

> **이 노트는 사람용 mirror 다.** 결정 본문 정본은 [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0030]] 안에 있다. drift 시 정본 우선.

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0030]] |
| 상태 | accepted (TASK-0228, 2026-06-11) — **Major §12.3 보안 수준 저하, 사용자 명시 승인** |
| 결정일 | 2026-06-11 |

## 1. 한 문장 요약

사내 운영이 대부분 사설망 IP 로 DB 를 구성하는 현실에서, datasource 생성의 사설/링크로컬 SSRF 차단을 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED` env 토글 뒤로 분기한다 (코드 기본값 `=1` 활성, secure-by-default).

## 2. 결정의 핵심

- **방어 코드 보존**: `_ssrf_check_host` + allowlist 로직은 삭제하지 않는다. 코드 기본값 `=1` (미설정/미상값 = 차단 유지). 운영 `.env.secret` 에서만 `=0` 으로 비활성화 (`0`/`false`/`no`/`off`).
- **현재 운영 상태**: `.env.secret` 에 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` → 사내 사설망 datasource 생성 허용.
- **불변식 (토글 무관 항상 유지)**: ① 클라우드 메타데이터 IP (`169.254.169.254`, `100.100.100.200`, IPv6-mapped) **하드차단** ② DNS rebinding pin (검증된 IP 로 고정 연결) ③ 빈 host / 해석 실패 거부. 토글이 끄는 것은 사설/링크로컬/reserved/multicast 차단뿐.
- **UI 정합**: `GET /api/admin/datasources` 응답에 `ssrf_private_guard_enabled` 추가, admin 콘솔 안내 문구가 토글 OFF 시 "사설망 IP 허용(메타데이터는 여전히 차단)" 으로 분기.

## 3. 복원 절차 (사설 경계 재활성화)

1. `repo/.env.secret` 의 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` → `=1` (또는 줄 제거 = 기본 활성).
2. (선택) 정당한 사내 host 를 `AGENT_DATASOURCE_HOST_ALLOWLIST` 에 콤마구분 host/CIDR 로 등재.
3. `sudo docker compose up -d --build web` 재기동. **코드 변경 불필요** — 토글·allowlist 메커니즘 상주.

## 4. 영향 받는 영역

- `app._ssrf_check_host` + `AGENT_DATASOURCE_HOST_ALLOWLIST`, admin datasource CRUD API
- 관련 feature: [[../Features/feature-0003-agent-web-ui]] · [[../Features/feature-0002-agent-core]]
- 관련 concept: [[../concepts/datasource-registry]]
- accepted-risk: 토글 OFF 동안 `console.manage` admin 이 임의 사설 IP 등록 가능 → 내부망 SSRF 표면 증가 (신뢰 사내망 전제).

## 5. 관련 노트

- [[../../docs/DECISIONS|정본]]
- [[../concepts/datasource-registry]] — 자격증명 암호화 저장 (연결 자격은 envelope 암호화)
- [[../concepts/multi-datasource]]
- [[../../docs/SECURITY|docs/SECURITY.md]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- TASK-0205/0214 의 SSRF/DNS rebinding 방어 위에 운영 토글 추가

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/security` · `#domain/datasource` · `#domain/ssrf`
