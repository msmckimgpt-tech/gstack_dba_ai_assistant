---
doc_type: TEST
feature_id: feature-0010-google-drive-integration
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test — Google Drive 연동 토대

## 1. 본 cycle 검증(토대 — 구조/기동 위주, 라이브 연동 없음)
- [x] `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` → PASS.
- [x] `python3 -m py_compile unit/feature-0010-google-drive-integration/src/gdrive_mcp_seam.py` → PASS.
- [x] `bash -n bin/gdrive-mcp.sh` → PASS.
- [x] docker-compose YAML 파싱 + `gdrive-mcp` profile=[gdrive] 확인 → PASS.
- [x] `.env.oauth` gitignore 보호 + `.env.example`/`.env.oauth.example` placeholder-only 확인.

## 2. 활성화 cycle 로 이월하는 시나리오 테스트(본 cycle 미수행)
- [ ] `WEB_GDRIVE_ENABLED=0`(기본): `/api/integrations/google-drive/connect` → 404, 외부 Google 호출 0건.
- [ ] `WEB_GDRIVE_ENABLED=1` + credential: connect→Google 동의→callback→`WebGoogleDriveTokens` 행 생성(암호문 only).
- [ ] AAD 검증: 계정 A 암호문을 계정 B AAD 로 복호 시도 → 실패(InvalidTag).
- [ ] 교차 연동: 계정 A 가 개시한 state 를 계정 B 세션으로 callback → `?gdrive_error=account`.
- [ ] disconnect → 행 삭제 + `/status` connected=false.
- [ ] KEK 미설정 환경 → store 실패(fail-closed), 라우트 외 무영향.
- [ ] seam(A): `inject_for_call` 가 연결 계정 토큰을 복호해 `Authorization: Bearer` 합성, 미연결 시 GDriveTokenUnavailable.

## 3. 비고
- 엄격 시나리오 자동화는 활성화 cycle 에서 `tests/` 로 승격(현 단계는 구조/기동 검증 — ARCHITECTURE §8 정책).

### Environment: Windows-browser — N/A (UI 표면 없음)
- 본 cycle 의 app.py 변경은 **백엔드 JSON API 라우트(status/connect/callback/disconnect)** 와 멱등 DDL 뿐,
  렌더링되는 HTML/template/정적 자산(static/) 변경이 **0건**이다(설정 UI 는 Out of Scope). 또한 모든
  연동 경로가 **기본 비활성(flag OFF → 404)** 이라 화면에 표출되는 사용자 surface 가 없다.
- 따라서 PB-0008 실제 Windows 브라우저 검증은 **해당 없음**(검증할 화면 부재). CHECK#13 WARN 사유 명시.
  활성화 cycle 에서 설정 UI(연결 버튼/상태)가 추가되면 그때 PB-0008 Windows-browser Run 동반.
