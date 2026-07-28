---
run_at: 2026-07-28T11:52:00+09:00
session: ai/claude/conv-quality-token-e2e-doc
scope: feature-0023-conversation-api-access (대화 품질 조정 — Bearer 토큰 경로 라이브 e2e)
verdict: PASS
---

# Run — 토큰 경로 라이브 e2e (배포 fe6d3700)

- Date: 2026-07-28
- Environment: `CLI` (라이브 서비스 HTTP 왕복 — 실 배포본 `mysql-ai-web:fe6d3700`, web-a/web-b healthy)
- Runner: AI (claude)
- 계정: **`bootstrap_admin`** (사용자 지시 — 전용 저권한 서비스 계정 부재)
- 토큰: `bin/api-token-issue.sh --expires-days 1` 단수명 발급 → **검증 후 즉시 revoke**(아래 실증)

## 계정 선택의 의미 — 의도치 않은 강한 검증

발급 스크립트가 privileged 계정 경고를 냈다:

> ⚠ 계정 'bootstrap_admin' 의 역할이 'Admin'(관리 권한)입니다. API 토큰은 **전용 저권한 서비스
> 계정**에 발급하길 권장합니다. (런타임 denylist 가 관리 엔드포인트를 차단하나, 최소권한 원칙상
> 저권한 계정 사용이 안전합니다.)

즉 이 e2e 는 **"관리자 권한을 가진 계정에 발급된 토큰"** 이라는 최악 조건에서 수행됐고, 그 결과
관리 엔드포인트가 전부 403 이었다 — scope allowlist ∩ 계정권한 위의 **절대 denylist**가 계정 권한을
무력화함을 라이브로 실증한 것이다(REV-20260722-0002 HIGH-1 수정의 end-to-end 확증).
**운영 권장은 여전히 전용 저권한 서비스 계정이다** — 본 검증은 일회성이며 토큰은 폐기됐다.

## 결과

| # | 검증 | 기대 | 실측 |
|---|---|---|---|
| 1 | 토큰 발급 scope | 신규 기본값 `folder.` 포함 | `conversation.,product.access.,folder.` ✅ |
| 2 | `GET /api/ai/capabilities` (Bearer) | 200 · `auth=api_token` | 200 · `api_token` ✅ |
| 3 | 모델 목록 | 계정 권한 필터 반영 | `[opus-5, sonnet-4, haiku-4]` ✅ |
| 4 | 제품 목록 | 접근 가능분 + 기본값 | 16건 · `default=109` ✅ |
| 5 | 폴더·첨부 축 | `folder.` scope 로 열림 | 둘 다 `available=true` ✅ |
| 6 | **관리 엔드포인트 3종** | **403** (절대 denylist) | `/api/admin/openapi.json` `/accounts` `/ai-ops` **전부 403** ✅ |
| 7 | 무토큰 | 401 | 401 ✅ |
| 8 | 폴더 생성 + 지침 | 200 | 200 (`folder_id=18`) ✅ |
| 9 | 대화 생성 → 폴더 배정 | 200 | 200 ✅ |
| 10 | 제품 고정 `PATCH …/product` | 200 · pinned 반영 | `product_id=7 pinned 마이크로볼츠-로컬` ✅ |
| 11 | 첨부 업로드 (multipart) | 200 · ingested | `id=586 kind=csv size=30 status=ingested` ✅ |
| 12 | `ask` (sonnet-4 + high) | 200 · error 없음 | 200 · 5.5s · `2+3은 5입니다.` ✅ |
| 13 | `capabilities?conversation_id=` | 4축 전부 반영 | model=`claude-sonnet-4` · reasoning=`high` · product=7 pinned · 폴더 지침 노출 ✅ |
| 14 | 타 계정 대화 id | 설정 미노출(oracle 차단) | `접근할 수 없는 대화입니다.` (존재/부재 구분 없음) ✅ |
| 15 | 토큰 revoke 후 재사용 | 401 | 401 ✅ (`--list` 에 `revoked` 확인) |

**11번(첨부 multipart)** 은 MCP `upload_attachment` 가 타는 것과 동일한 서버 경로다 — stdlib multipart
조립의 서버측 수용을 확인했다(MCP 프로세스 자체 기동은 `mcp` SDK 미설치로 여전히 미검증).

## 정리
- e2e 대화·폴더 삭제(200), 첨부는 대화 삭제에 동반.
- 토큰 **revoke 완료** — `#11 … | revoked`, 동일 토큰 재사용 401 실증.
- 토큰 원문은 파일·로그에 남기지 않고 `shred` 로 제거(발급 stdout 은 마스킹 출력).

## 잔여 미검증
- **MCP 서버 프로세스 왕복** — `mcp` SDK 가 agent 이미지에 없어 tool 등록·stdio 왕복은 미수행.
  서버가 호출하는 HTTP 계약(위 8~13)은 전부 실증됐으므로 잔여 위험은 SDK 배선 레이어에 한정.
- 전용 저권한 서비스 계정 기반 운영 검증(계정 신설은 운영 결정).
