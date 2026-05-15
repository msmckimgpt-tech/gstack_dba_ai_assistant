---
doc_type: SECURITY
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.6.1
domain: [security]
ai_read_priority: 4
---

# Security

## 1. 기본 원칙
- 비밀정보를 문서나 코드에 평문으로 저장하지 않는다.
- 최소 권한 원칙을 따른다.
- 파괴적 변경은 사전 검토와 롤백 방안을 요구한다.
- 로그, 보고서, 산출물에 민감정보가 포함되지 않도록 주의한다.

## 2. 비밀정보 처리
- API 키, 토큰, 비밀번호, 인증서는 문서나 샘플 파일에 직접 커밋하지 않는다.
- `../.env`는 로컬 전용 파일로 사용하고, `.gitignore`로 제외한다.
- `../.env.example`에는 민감값을 넣지 않으며, 원본 루트 `.env`의 의미 체계를 보존한 샘플만 둔다.
- 인증서와 세션 파일은 `../../artifacts`에만 저장한다.

## 3. 승인 필요 변경
다음은 사람이 승인해야 한다.
- 인증/인가 변경
- 데이터 삭제 및 파괴적 마이그레이션
- 외부 공개 범위 변경
- 개인정보 처리 변경
- 비용 상승 위험이 큰 외부 연동 변경

## 4. 기록 규칙
보안 관련 우려사항은 숨기지 말고 `REVIEW.md`와 `REPORT.md`에 명시한다.

## 5. 현재 저장 경계
- 코드 및 문서: `repo/`
- 런타임 로그와 출력: `../../artifacts/shared`
- MySQL 데이터: `../../artifacts/mysql-data`
- 인증서: `../../artifacts/certs`

## 6. 자격증명 관리 패턴
- 자격증명 파일(`.cnf`, `.env`, 인증서 등)은 저장소에 커밋하지 않는다.
- 기능별 `src/config/credentials/` 디렉토리에 실제 자격증명을 두되, `.gitignore`로 제외한다.
- `*.example` 파일만 커밋하여 필요한 키와 형식을 문서화한다.
- 자격증명 파일 권한은 `0600` (소유자만 읽기/쓰기)을 유지한다.
- `.gitignore` 패턴 예시:
  ```
  # 자격증명 제외
  **/config/credentials/*.cnf
  **/config/credentials/*.env
  !**/config/credentials/*.example
  ```
- 자격증명 경로와 필요 권한은 해당 기능의 `FUNCTION.md` §10 Dependencies에 명시한다.

## 7. Anonymous 접근 허용 경로 (allowlist)

본 저장소의 모든 HTTP endpoint 는 기본적으로 로그인 쿠키 검증을 요구한다 (`_require_account` → 401). 다음 경로는 **명시적 예외** 로 anonymous 접근이 허용된다. RBAC refactor 시 실수로 `_require_account` 를 일괄 부착하지 않도록 주의한다.

| 경로 | 메서드 | 인증 | 용도 | 도입 |
|---|---|---|---|---|
| `/share/{token}` | GET | anonymous | 대화 공유 페이지 (`share.html` FileResponse) | TASK-0058 (REQ-20260514-0001) |
| `/api/public/share/{token}` | GET | anonymous | 공유된 대화 read-only 조회 (메시지 + SQL + 결과셋) | TASK-0058 |
| `/api/public/share/{token}/fork` | POST | **로그인 필요** + `conversation.create` | 공유받은 viewer 가 본인 계정으로 fork (`_optional_account` 가 아닌 `_require_account` 사용) | TASK-0058 |

### 7.1 운영 정책

- `/api/public/...` 네임스페이스는 **공유 view 외 다른 anonymous endpoint 추가 금지**. 신규 anonymous endpoint 가 필요하면 본 표를 갱신 + REVIEW.md 등재.
- 공유 페이지는 사내 IP 가정 (운영 LAN 또는 VPN 경유) 으로 활성화돼 있다. 외부 LAN 노출이 발생하면 SQL 원문 + 결과셋이 외부로 그대로 전달된다.
- 공유 페이지의 `share.html` 은 `meta robots noindex,nofollow` 와 fixed footer "사내 공유용 — 외부 IP 로 전달 시 데이터 노출 위험" 안내를 포함한다.

### 7.2 외부 배포 전 보완 (TODO)

외부 LAN / 공개 인터넷 배포가 가시화되면 다음 중 하나 이상의 보완을 본 cycle 전에 추가한다:

1. **IP allowlist**: Caddy / reverse proxy 레벨에서 `/api/public/share/...` 와 `/share/...` 에 대한 사내 CIDR 화이트리스트.
2. **Token 별 비밀번호**: `WebConversationShares` 에 `PasswordHash VARCHAR(255) NULL` 컬럼 + 생성 시 옵션. GET 응답 401 시 password prompt 노출.
3. **시간 기반 만료**: `ExpiresAt DATETIME NULL` 컬럼 + GET 시 `NOW() > ExpiresAt` → 410. 기본은 무기한 + 명시 revoke 그대로 유지.

후속 cycle 결정은 운영 환경 변경 시점에 진행한다 (사용자 직접 결정 필요).
