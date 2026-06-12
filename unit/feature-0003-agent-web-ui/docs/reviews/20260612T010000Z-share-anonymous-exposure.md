# 적대적 보안 리뷰 — 익명 공유뷰 SQL navigator (TASK-0251)

- Date: 2026-06-12
- Reviewer: outside-voice adversarial subagent (general-purpose)
- Target: `app.py`(share redaction/steps 공급) + `share.js`(렌더)
- Verdict: 초기 NOT-SHIP (BLOCKER 1) → 흡수 후 PASS

## 컨텍스트

`/share/{token}` 은 **anonymous(비로그인) 접근 가능** read-only 대화 공유 페이지다. 사용자
보고: 본문 SQL "쿼리 열기"(열고닫기) 토글이 의도와 다르며, 실제로는 "결과셋에 따라 실행된
쿼리 전환"(메인 UI navigator) 구조를 원했다.

본 cycle 은 (1) share.js 의 토글 제거 + meta.steps navigator 렌더, (2) share API 가 steps 를
공급하지 않던 것을 `_load_steps_for_message` 동적 조립으로 보강, (3) 익명 노출이므로 step
sanitize 를 한다.

## 5축 적대 검토 결과

### 1. Redaction 우회 — BLOCKER (흡수됨)
share 가 steps 를 조립해 넣으면 각 step 의 `result_summary.csv_paths`(서버 `/shared/` 경로),
`preview`(결과 전문), step `args`(원본 tool 인자), `error`(원본 오류)가 익명 JSON 페이로드로
노출된다 — DOM 렌더가 아니라 `curl /api/public/share/{token}` 응답에서.

라이브 근거: `agent_runtime.steps.result_summary_json` 614건 중 540건이 `csv_paths`(`/shared/...`)
+ `preview` 보유.

**흡수**: `_share_sanitize_step` 화이트리스트 — `{tool,sql,reason,intent,work,result_summary.preview_table}`
만 통과. `_share_attach_sanitized_steps` 가 조립 직후 sanitize 강제.

라이브 end-to-end 검증(worktree app.py 임시 적용, 대화 20260527044221-bc2639bf):
- `_share_load_messages(..., v=CURRENT)` 응답 JSON 에 `csv_paths` 키 0건, bare `preview` 키 0건.
- step 직렬화에 `/shared/out` 0건 (본문 content 의 `/shared/` 는 step 경유 아님 — 범위 밖).
- assistant id=128 의 8 execute_sql step 이 `{intent,reason,result_summary[preview_table],sql,tool,work}`
  키로만 노출.

### 2. XSS / DOM injection — PASS
`buildPreviewTable`(컬럼/셀), `buildSqlStepPanel`(sql/reason), navigator indicator/context 모두
`textContent` 사용 → 신뢰불가 DB 컬럼명/셀값이 HTML 로 해석 안 됨. 본문은 DOMPurify.sanitize 유지.

### 3. 정책 version gate 정합 — PASS (정합 확인)
steps 재조립은 `role=='assistant' and not was_redacted` 일 때만 → attachment_derived(redact 대상)는
steps 미조립. 현 v2 토큰(redact_active=False)에서도 attachment 메시지 본문은 write 시점 redact
저장 + steps 미조립이라 정합. `_SHARE_REDACTED_META_KEYS` 에 `steps` 추가로 이중 차단.

### 4. null/형변환 안전성 — PASS
`buildPreviewTable`(Array.isArray 가드, null 셀 안전, 빈 columns→null), `extractFirstTableRef(null)`,
`buildSqlNavigator`(clamp) 모두 비정상 입력에 crash 없음. `_share_sanitize_step` 은 비-dict/
누락 result_summary 를 안전 처리(단위테스트 `_handles_malformed`).

### 5. 회귀 — PASS
steps 없는 구형 메시지는 기존 `final_sql`/`result_rows` 폴백 보존.

### MINOR (오탐 기각)
"`formatSqlForDisplay` 가 `` sentinel 누락 → `LIMIT 100` 숫자 오치환" — false positive.
diff 의 비가시 제어문자를 리뷰어가 못 본 것. `cat -A` 로 `^A${i}^A` 마스킹 + `/^A(\d+)^A/g`
복원 정상 + Playwright 라이브에서 `LIMIT 10` 정상 표시 확인.

## 검증 요약
- make test 컨테이너 599 PASS (회귀 0, skip 2) + ruff clean + node --check + CSS brace + py_compile.
- Playwright 실 헤드리스 chromium 2종(mock + 라이브 sanitized) ALL PASS.
- 라이브 sanitize end-to-end: step 경유 csv_paths/preview/args/error/`/shared/out` 노출 0.

## 잔존 (범위 밖)
답변 **본문 텍스트**에 LLM 이 `/shared/` 경로를 직접 언급한 경우는 base 부터의 본문 표시
동작(step 경유 아님)으로, 별도 본문 redaction 정책 이슈. 본 cycle 책임 아님.
