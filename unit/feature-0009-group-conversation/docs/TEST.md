---
doc_type: TEST
feature_id: feature-0009-group-conversation
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- 무엇을 검증하는지
- 어떤 범위를 제외하는지

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다. `CLI`·`WSL-headless` 는
> 서버 계약(contract) 검증으로만 카운트하며 화면 검증을 대체하지 못한다 (실 사용자 관점 괴리 방지).
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium (feature-0004 browser service, gstack /browse) | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge 를 AI 가 CDP 자동 구동 (`bin/win-browser.py`) | ✓ |
>
> Windows-browser 검증 절차는 **PB-0008** (`playbooks/PB-0008-windows-browser-verification.md`).

## 2. Test Cases
### TEST-0001
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

### TEST-0002
- Purpose:
- Preconditions:
- Steps:
- Expected Result:

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run YYYY-MM-DD-001
- Date:
- Environment: CLI | WSL-headless | Windows-browser   <!-- §1 분류표 참조. 웹/UI 검증은 Windows-browser 필수 -->
- Runner: AI / Human
- Bridge: <!-- Windows-browser 인 경우: relay | mirrored + win-browser.py doctor 결과 -->
- Evidence: <!-- 스크린샷 경로 등 (Windows-browser run 권장) -->
- Result Summary:
- Pass/Fail:
- Notes:

### Run 2026-06-23-gc-avatar-identicon
- Date: 2026-06-23
- Environment: Windows-browser
- Runner: AI
- Bridge: relay @ http://172.28.64.1:9223 (win-browser.py doctor ok=true, Windows Chrome/149.0.7827.116)
- Scenario: `unit/feature-0003-agent-web-ui/tests/win-browser-avatar-identicon.scenario.json`
- Evidence: `artifacts/pb0008-avatar-identicon/01_avatar_strip.png`, `02_conversation_avatars.png`
- Result Summary: 그룹 대화 메시지 프로필 아바타 Identicon 정합 검증. `_msgAvatarEl` 기능 결과 — 무아바타 user=`identicon`(이전 맨 글자), 업로드 계정(id35)=`img:/api/avatars/35`(실제 이미지), assistant(auto)=`text:AI`(배지 유지). 실제 대화 열람 시 메시지 아바타 kinds=`[identicon, AI]`. 스크린샷 01: mckim2/mckim3/review_user01/admin/operator 모두 고유 컬러 Identicon, id35 실제 이미지, 좌하단 bootstrap_admin 프로필 Identicon 과 동일 렌더러로 정합.
- Pass/Fail: **PASS**
- Notes: 헤더/프로필 `applyAvatar()`+`identiconSvg()` 와 동일 시드 해시 → 같은 사용자는 어디서나 같은 아이콘. 실제 아바타 업로드 계정은 이미지 그대로 표시(회귀 없음).

## 4. Untested Areas
- 아직 검증되지 않은 영역
