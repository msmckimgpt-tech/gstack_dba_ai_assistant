---
run_at: 2026-07-29T14:50:00+09:00
session: ai/claude/feature-0003-attach-full-scope
scope: 대화 전체 첨부 자율 참조 + read_attachment 도구 + scopeAll 토글 제거 (pre-commit)
verdict: PASS (컨테이너 스위트 · 정적 계약) / PB-0008 시각검증은 배포 후 이월
---

### Run (2026-07-29 14:50) — attach-full-scope pre-commit — **Environment: container(agent image) — Windows-browser 미수행(사유 명시, 아래 §4)**

#### 1. 신설·수정 테스트

| 파일 | 건수 | 결과 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/tests/test_attach_full_scope.py` | 12 | PASS |
| `unit/feature-0002-agent-core/tests/test_read_attachment_tool.py` | 15 | PASS |
| `unit/feature-0002-agent-core/tests/test_redteam_attachment_manifest.py` | 10 | PASS |
| `unit/feature-0002-agent-core/tests/test_self_review_messages.py` (계약 갱신 + 1건 추가) | 13 | PASS |

실행: `COMPOSE_PROJECT_NAME=repo docker compose run --rm --no-deps agent … pytest -q -p no:warnings …`
→ `.................................................. [100%]` (50 passed)

커버 대상: 대화 스코프 해소(MySQL 폴백 + **PG read 경로** 양쪽) · 그룹 발신자 가드(CSO F1) ·
그룹 해소 실패 fail-closed · client_ids 가 스코프를 넓히지 못함 · 상한 · `read_attachment` 의
권한 경계(스코프 밖 id/파일명 거부) · 줄 범위 슬라이스와 이어읽기 신호 · 인라인 본문 재사용 ·
이미지/이진 거부 · 저장소 실패 시 원인 미단정 · 도구 조건부 노출 · datasource-free 실행 ·
red-team 매니페스트 분리와 **대규모(200건) 예산 상한** · bounded 발신자 누출 게이트.

#### 2. 전체 스위트 — baseline 대조 (qa 리뷰 F10 지적 반영)

`COMPOSE_PROJECT_NAME=repo make test` 결과 **실패 13건**. 같은 명령을 **main worktree
(`repo/`, 본 변경 미적용)** 에서 실행해 대조한 결과 **동일 집합**이 실패한다:

- `test_attachment_idor.py` 4건 · `test_attach_inline_honesty.py` 4건 ·
  `test_attachment_user_version_context.py` 5건 — 컨테이너 환경의 첨부 읽기 백엔드가 PG 라
  fake-cursor(MySQL) 분기가 실행되지 않는 환경성 실패(코드 변경과 무관, 기존 알려진 baseline).
  병렬 cycle `test-live-db-isolation` 이 격리 범위 밖(PG 미격리)으로 명시한 구간과 같은 축이다
  (FUNCTION.md "범위 밖(현행 한계, 명시)" 항목).

**변동 기록**: rebase 전(origin/main 11 commit behind) 측정에서는 실패가 15건이었고,
`test_runtime_settings.py::test_missing_snapshot_is_fail_open` ·
`test_runtime_settings_api.py::test_get_returns_registry` 2건이 포함돼 있었다. rebase 로
병렬 cycle `test-live-db-isolation`(`TEST_ISOLATION_ENV` + conftest `_no_live_memory_conn`)을
흡수하면서 그 2건이 해소돼 13건이 됐다.

→ **본 변경으로 인한 신규 실패 0건** (rebase 전후 모두).

#### 3. 정적 검증

- `node --check unit/feature-0003-agent-web-ui/src/static/app.js` → PASS
- `python3 -m ast` 파싱: 변경된 py 6종 PASS
- `bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` → §5 참조

#### 4. PB-0008 Windows-browser 시각검증 — **이번 cycle 미수행 (사유 명시)**

`visual_verification_scope: always` 대상(웹 자산 `index.html`·`app.js`·`styles.css` 변경)이나,
**사용자 결정(2026-07-29)** 에 따라 검증 시점을 "병합 후 배포본"으로 잡았다. 근거: 본 변경의
시각 대상(체크박스 제거·참조 범위 안내 1줄·첨부 pill × 실삭제 흐름)은 **서버 스코프 해소와 함께
동작할 때만 의미가 있고**, 병합 전 라이브 web 컨테이너를 이 브랜치 코드로 교체하면 같은 핫스팟을
편집 중인 병렬 세션 7개와 사내 서비스에 영향을 준다.

- 배포 직후 수행할 항목(POST-DEPLOY Run 으로 별도 fragment 기록):
  1. 첨부 사이드패널에 "이 대화의 모든 첨부 사용" 체크박스가 **없음** + 안내 1줄 노출
  2. 첨부가 걸린 대화에서 **다음 턴**에 그 파일을 근거로 답변(이전 턴 첨부 참조 실증)
  3. 인라인 상한 밖 파일 질의 시 `read_attachment` 도구 호출이 실행 단계에 표시
  4. 첨부 pill × → 확인 → 실제 삭제 후 assistant 가 더 이상 참조하지 않음
  5. 서빙 자산에 `attachSidePanelNote` baked · `composerAttachmentsScopeAll` 부재 2중 확인
