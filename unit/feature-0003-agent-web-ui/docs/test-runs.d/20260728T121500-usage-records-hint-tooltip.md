---
run_at: 2026-07-28T12:15:00+09:00
session: ai/claude/feature-0003-usage-records-hint
scope: [usage-records, tooltip, row-density, pb0008]
verdict: PASS (POST-DEPLOY 배포본 0f956416 에서 4개 확정 항목 전부 통과)
---

### Run (2026-07-28) — '사용 기록' 행 2번째 줄 제거 → hover 툴팁 — **Environment: Windows-browser (PB-0008)**

브리지 정상(Chrome/150, `eval 1+1 → 2` 게이트 PASS)이며 라이브 접속·모달 개방까지 수행했으나,
**본 변경의 렌더는 pre-deploy 관측에 실패**했다. 사유는 제품 결함이 아니라 스테이징 한계다:

- 미머지 JS 를 `docker cp` 로 반영해도 Chrome 이 **동일 URL 의 컴파일된 ES 모듈**을 재사용해
  (HTTP 캐시 `fetch(..., {cache:'reload'})` 강제 갱신 + 페이지 재탐색에도) 구 렌더가 유지됐다.
  실측: 새 코드가 만드는 title(`… 화면으로 이동`)은 보이지 않고, 제거 대상인
  `.usage-rec-sub` 507개가 그대로 관측 → 구 모듈 실행 확정.
- 배포는 `inject_asset_stamp.py` 가 **새 stamp = 새 모듈 URL** 을 만들어 이 문제가 없다.
  직전 cycle(usage-records-postverify)에서 동일 상황이 POST-DEPLOY 즉시 정상 관측된 선례가 있다.

**pre-deploy 확인 범위(정적)**: `node --check`(ESM) PASS · `.usage-rec-sub|-goto|-note` 참조
grep **0**(JS·CSS 양쪽) · web 테스트 스위트 PASS.

**POST-DEPLOY 확정 항목**: ① 시스템 행이 한 줄(32px)로 렌더되고 `.usage-rec-sub` 0개
② 링크 hover 툴팁에 `<경로> 화면으로 이동` + 모호 시 `(데이터소스 여럿 — 화면까지 이동)`
③ 툴팁 이중 escape(`&gt;`) 해소 ④ 이동 동작·대화 행 회귀 없음.


---

### POST-DEPLOY 확정 (2026-07-28, 배포본 `0f956416`) — **PASS**

`bin/deploy-web.sh` 무중단 롤아웃(web-a/web-b + 워커 `0f956416`, soak 통과) 후 실 Windows Chrome
(`https://localhost/admin`, Chrome/150) 재검증. 예고대로 새 asset stamp = 새 모듈 URL 이라
pre-deploy 를 막던 모듈 캐시 이슈가 재현되지 않았다.

| 확정 항목 | 실측 | 판정 |
|---|---|---|
| ① 두 번째 줄 제거 | `.usage-rec-sub/-goto/-note` 노드 **0개** · 행 높이 **25/25 단일 줄**(32px) | PASS |
| ② 툴팁 통합 | `관계도 화면으로 이동` · `메타데이터 > 용어사전 화면으로 이동` · `메타데이터 > ENUM 코드사전 화면으로 이동` · `메타데이터 > 테이블 설명 화면으로 이동` | PASS |
| ③ 이중 escape 해소 | `&gt;` 포함 툴팁 **0건**(종전 전량) — `>` 정상 렌더 | PASS |
| ④ 정직 표기 보존 | `(데이터소스 여럿 — 화면까지 이동)` 툴팁 **107건**(제거 전 행 표기 건수와 동일) | PASS |
| ⑤ 회귀 | 시스템 200행 · 대화 86행 유지, 행 클릭 → `콘텐츠 그룹 라벨 · mssql-qa-idc` → 관계도 탭 + 스코프 `mssql-qa-idc` + 모달 자동 닫힘 | PASS |

증적: `docs/evidence/pb0008-usage-records-tooltip-20260728.png`
