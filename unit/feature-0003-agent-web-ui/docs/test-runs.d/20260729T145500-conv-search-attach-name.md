---
run_at: 2026-07-29T14:55:00+09:00
session: ai/claude/feature-0003-conv-search-attach-name
scope: 대화 검색 첨부 파일명 축 (검색 SQL·매칭 근거 API·검색 모달 칩)
verdict: PASS (라이브 PB-0008 완료 — 2026-07-29 18:00)
---

### Run — 단위/계약 검증 (Environment: container agent image, `make test` harness)

- 신규 `unit/feature-0003-agent-web-ui/tests/test_conv_search_attachment_name.py` **26건 PASS / 0 FAIL**
  (`python -m pytest -q -p no:cacheprovider` — agent 이미지 격리 컨테이너, 라이브 DB 무접촉).
  **실행 기반** — fake 커넥션이 `_list_conversations{,_pg}` 가 실제로 조립한 SQL·params 를 캡처한다
  (초안의 `inspect.getsource` 문자열 검사는 codex 리뷰 P2 지적을 받아 폐기).
  - A1~A4 첨부 축 권한 게이트(PG): `any`=전 대화 / `own`=owner·멤버 스코프(self_id 2회 바인딩) /
    `own` + self_id 부재=축 제외(fail-closed) / 권한 없음=축 제외 + 제목·본문 축은 보존
  - A5 MySQL 폴백 동형(권한 없음→축 없음, own→스코프, any→무제한)
  - A6 `_search_attachment_axis` 판정표 — **`conversation.list.any` 는 축 근거가 아님**을 명시 고정
  - V1~V2 가시성 한정: `deleted_at/superseded_at IS NULL`(PG) · `DeletedAt/SupersededAt IS NULL`(MySQL)
  - G1 검색어 없는 목록 조회는 첨부 테이블 미조회(실제 SQL 로 확인 — 비용 회귀 0)
  - E1~E3 LIKE escape: PG·MySQL·수집 헬퍼 모두 `ESCAPE '!'` + `a%b_c` → `%a!%b!_c%` 리터럴화
  - C1~C6 수집 헬퍼: PG/MySQL 계약·cap 파라미터·가시성·최신 우선 정렬·빈 입력 단락·DB 예외·커서 생성 실패
  - P1~P3 엔드포인트 스코프(실제 `conversations()` 호출 + 응답 JSON 파싱):
    `any`=3건 전부 / **`list.any` + `attachment.read.own` = 본인·멤버 2건만(타 계정 파일명 미노출)** /
    첨부 권한 없음 = 수집 함수 미호출 + `matched_attachments` 빈 dict
  - F1~F4 프론트: append 병합 · **캐시 리셋 지점이 excerpt 와 1:1 대응**(이 assert 가 실패 폴백
    누락을 실제로 적발) · 칩 렌더 · 표시 게이트 · 파일명이 `_searchHighlight`(escapeHtml) 경유 · 카피
- **회귀 — baseline 대조**: 동일 커맨드로 `unit/feature-0002-agent-core/tests` +
  `unit/feature-0003-agent-web-ui/tests` + `unit/feature-0023-conversation-api-access/tests` 전체를
  본 worktree 와 `main`(`repo/`) 양쪽에서 실행하고 `FAILED` 목록을 diff 했다.
  - main baseline: 21 FAILED (attachment 13 · runtime_settings 1 · share_redaction 7)
  - 본 worktree: 21 FAILED — 목록이 baseline 과 **동일**. `comm -13` 결과 **신규 실패 0건**.
  - 잔여 실패는 전부 라이브 DB/네트워크 의존 환경성 baseline 이며 본 변경과 무관하다 — 실패 테스트
    어느 것도 검색 경로를 다루지 않는다.
- `ruff check unit/feature-0003-agent-web-ui/src` PASS (All checks passed).

### Run — 적대 리뷰 (Environment: codex CLI, `/codex review` — §18.8.1 경로 2)

- `codex exec -s read-only` 로 staged diff 전체를 적대 검토(포커스: SQL 인젝션·인가 경계·성능·
  fail-soft·XSS·프론트 상태 정합·테스트 tautology). **P1 1건 + P2 4건** 지적.
- P1(첨부 권한 우회) 포함 4건 **in-cycle 수정 완료**, P2 성능 1건은 라이브 `EXPLAIN ANALYZE` 필요로
  POST-DEPLOY 이월. 상세·근거는 REVIEW `[CODEX:conv-search-attach-name]`.
- **재검증(2차)**: 수정본을 같은 형식으로 재검토 → P1·escape·fail-soft·캐시 리셋 **"해결됨" 확인**,
  신규 P2 3건(PG/MySQL 스코프 판정 불일치 · 프론트 응답 경합 · PG runaway 상한 부재) 전건 수정.
- 최종: 신규 테스트 **30건 PASS**(P4~P6·F5 추가) · 전체 회귀 **신규 실패 0**(baseline 부분집합) ·
  `ruff check` PASS.

### Run — 라이브 작업화면 PB-0008 (Environment: Windows-browser) — **완료 (2026-07-29 18:00)**

배포 `495da758`(축) → `db04ce0a`(검색 500 hotfix) 후, 실 Windows Chrome 150(win-browser relay)로 실측.
접속은 WSL2 localhost 포워딩(`https://localhost/`) — Windows Chrome 이 WSL `/etc/hosts` 를 보지 않고,
WSL IP 직접 접속은 앱 `WEB_ALLOWED_HOSTS` 미등록으로 400 이라 호스트 파일 무수정 경로를 택했다.

1. **PASS** — 검색 입력 placeholder 가 `제목 · 본문 · 첨부 파일명 (2자 이상)` 로 라이브 렌더.
2. **PASS** — `attach-scope-probe` 검색 → 2건. 제목이 `새 대화`(제목·본문에 검색어 없음)인 대화가
   첨부 파일명으로 매칭되고, 그 행에 📎 `attach-scope-probe.sql` 칩이 `<mark class="search-snippet-hl">`
   강조와 함께 표시(칩 innerHTML 실측). 본인 대화라 opt-in chip 없이 노출.
3. **PASS** — 본문 매칭 행(`파일의 특정 줄에서 probe token 추출`)은 칩 없이 기존 렌더 유지 —
   근거 표시가 실제 매칭 축을 정확히 반영한다.
4. **PASS** — 구버전/삭제분에만 존재하는 파일명(`GunZ_Init_Query.sql`)으로 검색 → matched 0 ·
   matched_attachments 0. 목록 비가시 첨부가 검색 근거로만 드러나지 않음(AC-2) 라이브 확인.
5. **PASS** — 페이지 정상 렌더, 콘솔 에러 없음. 스크린샷
   `artifacts/shared/win-browser-shots-conv-search-attach/search-attach-chip.png`.

**hotfix 전후 대조**: `db04ce0a` 배포 전 동일 조작은 **500**(`NameError: _COLLATION_AUDIT_DONE`,
2026-07-11 ITEM-10 p7 선행 결함) → 배포 후 200. 라이브 본문 검색이 7월 11일 이후 처음 복구됐다.

### Run — 첨부 EXISTS 성능 실측 (Environment: live PG, EXPLAIN ANALYZE) — codex P2 이월분 해소

규모: `core_attachments` 634행 / `core_conversations` 271행.
- 전체 검색 쿼리 **Execution Time 65.1ms**(planning 2.5ms) — `statement_timeout` 3s 대비 여유.
- 첨부 EXISTS = `Seq Scan on core_attachments` **actual 0.301..0.304ms · loops=1**, 전체의 **0.5% 미만**.
  지배 비용은 기존 메시지 본문 ILIKE 축.
- 판정: `ILIKE '%q%'` 인덱스 미사용은 사실이나 현 규모에서 첨부 축 기여는 무시할 수준. 첨부가
  10만 행대가 되면 §8.7 FULLTEXT/trigram trigger 와 함께 재평가(트리거 = rate limit 빈발 또는
  statement_timeout 히트).
