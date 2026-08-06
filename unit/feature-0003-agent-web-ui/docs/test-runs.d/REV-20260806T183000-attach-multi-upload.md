---
run_at: 2026-08-06T18:30:00+09:00
session: ai/claude/attach-multi-upload
scope: feature-0003-agent-web-ui — 첨부 다중 업로드 경로 · 중복 스킵 UX · 편집본 버전 체인 통합
verdict: PASS (헤드리스·pytest) / PB-0008 PENDING
---

### REV-20260806T183000-attach-multi-upload 폴더 단위 첨부 · 중복 스킵 알림 · 편집본 체인 통합 (Major §12.3, 2026-08-06)

- 무엇: (1) 파일 선택 대화상자에서 **여러 파일**을 고를 수 있고 전량이 업로드된다 (2) 컴포저 영역에
  드롭해도 첫 파일이 두 번 올라가지 않는다 (3) 이미 올라간 것과 내용이 같은 파일은 오류가 아니라
  "변경 없음" 으로 건너뛰고 **요약 1회**로 알린다 (4) assistant 수정본이 원본과 같은 버전 체인에 남는다.

#### 사전 실측 (라이브 데이터 조회 — 읽기 전용)

사용자가 지목한 대화 `20260806052006-3f48cbb7`(`구 로그 테이블 DROP 유지 결정`)의 활성 첨부와
로컬 `D:\Masang\git\_review\gz\dev-GunzPlus\Schema\*` 22개 파일의 sha256 을 전수 대조:

- **22/22 파일이 내용 동일**(파일명·바이트수·해시 일치) — "동일 파일" 판정은 정확했다. 따라서 판정
  임계를 완화하지 않고 경로·알림·체인만 수정했다(§16.7 G7-a).
- 같은 대화에 `x.sql` / `x_v2.sql` 형태의 **분열 체인 9쌍** 존재 — 편집본이 다른 파일명으로 저장되어
  원본이 head 에서 빠진 결과. 이번 cycle 이 그 기전을 제거한다(소급 병합은 미수행 — REPORT §8).
- 조회 경로: web-a 컨테이너 내 `app._connect_memory()`(MySQL `WebConversationAttachments`) +
  `shared.db._pg_connect_ro()`(PG `agent_runtime.core_conversations` 제목 확정). **쓰기 0**.

#### Run 1 — 프론트 하네스 (Environment: jsdom, 2026-08-06)

`node unit/feature-0003-agent-web-ui/tests/verify_attach_multi_upload.mjs` → **28 passed, 0 failed**

| 축 | 건수 | 내용 |
|---|---|---|
| (A) 정적 계약 | 5 | `multiple` 존재 · change/drop 이 `files[0]` 미사용 · chatPane 위임 가드 · 스킵 토스트가 에러 톤 아님 |
| (B) 실행 | 8 | 3개 선택 → 배치 1회·3개 전달·단건 경로 미사용·value 리셋 / composer 드롭 시 배치 1회·3개 각 1회·**첫 파일 중복 0** / chatPane 부재 폴백 |
| (C) 집계·문구 | 9 | 업로드1·건너뜀2·실패1 집계 · silent 플래그 · 요약 1회 · 문구 3종 · 실패 시 에러 톤 · 전부 건너뜀은 정보 톤 · **단건은 개별 토스트 + 요약 없음** · 0건 처리 표기 |
| (D) 저장명 | 3 | 확장자 보존 · 기존 `_v<n>` 재부여(이중접미 방지) · 확장자 없는 이름 |
| (E) 뮤테이션 역검증 | 3 | `files[0]` 복원 · drop 가드 제거 · `multiple` 제거 → **셋 다 하네스가 FAIL 로 검출** |

#### Run 2 — pytest 전 스위트 (Environment: CLI, 2026-08-06)

격리 컨테이너(`--network none`, 라이브 DNS·DB 도달 불가)에서 feature-0002 / 0003 / 0023 전 스위트
실행 → **exit 0, 실패 0**. 신규·갱신분: `test_attachment_versioning.py` N3(원본명 승계) ·
N4(안전 확장자 불변) · N5(체인 단일성) · N6(다운로드 표시명 분리).

> 실행 메모: 호스트 DNS 단절로 `make test` 의 이미지 빌드 단계가 실패해(`registry-1.docker.io` 해석
> 불가), 기존 `repo-unittest-agent` 이미지에 pytest 를 주입한 사본으로 **동일 격리 env**를 재현해
> 실행했다. `-p no:warnings` 외 러너 옵션은 Makefile 과 동일.

#### Run 3 — 전체 mjs 하네스 회귀 (Environment: jsdom, 2026-08-06)

`tests/verify_*.mjs` **45 스위트 전건 통과**(실패 0). 첨부·컴포저 인접 스위트
(`verify_attach_version_diff` · `verify_new_conv_dedup` · `verify_model_persist` ·
`verify_step_result_scroll_preserve`) 포함.

#### PB-0008 Windows-browser 라이브 실측 — **PENDING(배포 후)**

정적 자산(`index.html`·`app/composer.js`)이 web 이미지에 baked 되므로 미머지 상태에서는 라이브
무접촉으로 검증할 수 없다. 배포 후 실 Windows Chrome via `bin/win-browser.py` relay 로 다음을
실측하고 본 fragment 에 Run 을 append 한다:

1. "+ > 파일 첨부" 에서 **여러 파일 동시 선택**이 가능하고 선택 수만큼 첨부 pill 이 생긴다.
2. 컴포저 입력창 위에 여러 파일 드롭 → 첫 파일이 두 번 올라가지 않는다(중복 토스트 0).
3. 이미 올라간 파일들을 다시 올리면 빨간 에러가 아니라 **요약 1회**
   (`첨부 N개 중 … 변경 없음(건너뜀)`)가 정보 톤으로 뜬다.
4. 단건 업로드는 기존대로 개별 토스트(요약 없음) — 회귀 없음.
5. assistant 수정본이 목록에서 **원본과 같은 항목**으로 보이고 "버전 N개 ▾" 로 이력이 펼쳐지며,
   구버전 다운로드 파일명에 `_v<n>` 이 붙는다.

de-risk (배포 전 확보):
- ESM `node --check` PASS(composer.js) + 위 3 Run.
- 백엔드 변경은 파일명 결정 1곳 + 다운로드 표시명 1곳으로 좁고, 스키마·엔드포인트·RBAC 변경 0.
- 인라인 보안 검토 HIGH/MEDIUM 0건(REVIEW.md REV-20260806T183000 참조).
