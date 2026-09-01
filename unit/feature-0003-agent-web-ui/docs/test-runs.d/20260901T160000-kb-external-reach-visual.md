---
run_at: 2026-09-01T15:00:00+09:00
session: ai/claude/kb-external-reach
scope: PB-0008 시각검증 — 전역 상속 4축 노출 + KB grounding 도달 (20260901T160000-kb-external-reach)
verdict: PASS
---

### Run 1 — 미머지 브랜치 라이브 무접촉 기동 (Environment: docker bind-mount, 라이브 web 무변경)
- 라이브 이미지(`mysql-ai-web:786815f2`)를 그대로 쓰고 **브랜치 소스만 bind-mount** 한 별도
  컨테이너 `web-verify-kbreach`(포트 18099, `repo_dbnet`). 공유 이미지를 **다시 빌드하지 않는다** —
  덮어쓰면 라이브가 내 코드로 바뀌고, 그 상태의 관측은 「배포 전 검증」이 아니다.
  - `.../src/static` → `/app/web/static:ro`
  - `.../src/routers` → `/app/web/routers:ro`
  - `.../feature-0002/src/modules` → `/app/modules:ro`
- `Application startup complete` 확인.

### Run 2 — API 계약 실측 (Environment: Windows-browser, 실제 Chrome + 로그인 세션)
- `bin/win-browser.py session-check` → `authenticated=true, username=bootstrap_admin, role=admin`.
- 5개 엔드포인트를 `scope_key=product.dk_qa` 로 호출한 결과:

  | 축 | count | inherited_count | inherited_error |
  |---|---|---|---|
  | 용어사전 | 23 | 7 | — (0057 cycle 필드) |
  | ENUM | 9 | **9** | false |
  | 테이블 설명 | 153 | 0 | false |
  | 컬럼 설명 | 1,046 | 0 | false |
  | 샘플쿼리 | 0 | 0 | false |

- `scope_key=common` 에서는 5축 전부 `inherited_count=0` — **자기 자신을 상속분으로 다시 세지
  않는다**(중복 표시 방지).
- ⚠ **테이블/컬럼/샘플의 0 은 배선 실패가 아니라 데이터 현실이다**. PG 실측:
  `table_descriptions` 는 `product.dk_qa` 153 · `product.gz_qa_g` 1 뿐이고 `common` **0행**,
  `column_descriptions`·`sample_queries` 도 `common` **0행**. 즉 상속할 것이 아직 없다.
  배선 자체는 뮤턴트 M4/M7 이 지키고, ENUM 축이 라이브에서 9건으로 실증한다.

### Run 3 — 콘솔 시각검증 (Environment: Windows-browser, 실제 Chrome 화면)
- 관리 콘솔 → 메타데이터 → 제품 `DK온라인 - QA` → **ENUM 코드사전**:
  `9건` · `.is-inherited` **9행** · 배지 문구 **「전역 상속 · 여기서 편집 불가」** 렌더 확인.
  종전 이 표면은 상속분이 **0건**이었다(배지 렌더가 `sub === "glossary"` 블록 안에 갇혀 있었다).
- 5개 하위탭 순회 — 렌더 오류/빈 경고 없음:
  용어사전 23건(상속 7) · ENUM 9건(상속 9) · 테이블 153건 · 컬럼 1,046건 · 샘플 0건(정상 안내).
- 증적: `evidence/20260901T160000-kb-external-reach-enum-inherited.png`

### Run 4 — 미수행분 (정직)
- **`inherited_error` 경고 배너의 화면 렌더**: 라이브에서 상속분 조회를 실패시킬 안전한 수단이
  없어 화면 관측을 못 했다. 서버 계약(`inherited_error: true` + 목록 200 유지)과 프론트 분기는
  단위 테스트 3건 + 뮤턴트 M7 로 잠갔다.
- **F1(`get_task_context`) 라이브 왕복**: MCP 토큰이 필요한 브리지 경로라 이 컨테이너에서
  단독 관측이 안 된다. 배포 후 실사용 turn 에서 관측한다.
