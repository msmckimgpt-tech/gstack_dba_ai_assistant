---
run_at: 2026-07-29T21:30:00+09:00
session: ai/root/metadata-product-scope
scope: [metadata, knowledge-base, product-scope, admin-console, injection, migration]
verdict: PRE-COMMIT PASS (make test 전 스위트 · codex 적대 리뷰 10라운드 P1 0 · 이관 dry-run 검증) · POST-DEPLOY 라이브 이관 + PB-0008 예정
---

### Run (2026-07-29) — metadata-product-scope (지식베이스 메타데이터 스코프 축 datasource → 제품) — **Environment: container(make test)** · **Environment: Windows-browser (PB-0008) = 배포 후 수행**

cycle: `ai/root/metadata-product-scope` · 정본 = TASK `20260729T2130-metadata-product-scope` ·
FUNCTION `REQ-20260729T213000-metadata-product-scope` · REVIEW `REV-20260729T213000-metadata-product-scope` · MODIFY `CHG-20260729T213000-metadata-product-scope`.

- **전 스위트**: `make test`(agent 이미지 격리 컨테이너, `--no-deps` + 라이브 DB 차단 env) **PASS**,
  ruff clean. route-parity 골든은 신규 `GET /api/admin/metadata/scopes` 1건만 증분(222→223).

- **신규/변경 테스트**
  - `test_kb_glossary_enum.py` — 제품 축 전환: 기본 scope 가 활성 **제품**에서 도출 ·
    **같은 제품이면 활성 DS 가 무엇이든 동일 scope**(1제품↔N DS 회귀 가드) · `product.<key>` 정규화
    멱등·sanitize 통과 · 제품/데이터소스 컨텍스트 상호 무간섭 · 제품 미지정 → common 만 ·
    **expand/contract**(플래그 on 이면 레거시 ds 꼬리 포함, off 면 소멸) · 명시 scope 호출엔 꼬리 없음 ·
    "제품 없음" vs "해소 실패" 신호 구별.
  - `test_metadata_phase2.py` — 허용 축이 제품(datasource 라벨은 400) · **공유 datasource 라도
    제품별 scope 분리** · 골격 후보가 제품 접근DB 로 한정 · **allowlist 밖 schema 404 + introspection
    미도달** · 카탈로그 미가용 fail-closed(503, 라이브 연결 미도달) · **호출자 datasource override
    무시** · 레거시 접근DB 행(DatasourceKey 빈값) primary 해소 · 레거시 단일 바인딩 카탈로그 폴백 ·
    **MSSQL DB allowlist 대소문자 무관 + 원본 케이스 연결** · 미등록 제품 404 / scope 미지정 400 /
    공용 404 · 접근DB 미선언 제품의 introspection 폴백.
  - `test_enum_self_heal.py` — sweep 대상이 제품 스코프 · `_self_heal_scope_keys` 단독 검증(단일 DS
    제품만 · 레거시 단일 바인딩 폴백 · common/미매칭 제외).

- **이관 스크립트 dry-run(라이브 데이터 대조)** — `--assess` 판정 5,405건:
  `single` 2,004 · `schema` 3,126 · `ambiguous` 257 · `common` 18(불변).
  `--migrate --purge-ambiguous` 계획 = update 5,130 · delete 257. `--verify-contract` 잔여 5,387건
  (이관 전이므로 정상 — contract 보류 판정).

- **codex 적대 리뷰 10라운드** — P1 12건 + P2 3건 흡수 후 최종 P1 0건(REVIEW entry 표 참조).

- **PB-0008 미수행 사유**: 라이브 반영 전에는 새 스코프 선택기(제품 목록)가 서빙되지 않아 육안 검증이
  무의미하다. 배포 → 라이브 이관 → contract 후 수행하고 본 fragment 에 append 한다.

### POST-DEPLOY (2026-07-29) — 라이브 이관 + contract + PB-0008 — **PASS**

배포본 `5060c9f3`(PR #1072 머지 → `make deploy-web` scope=all, soak 통과 · web-a/web-b
`mysql-ai-web:5060c9f3` · ask/insight-worker `mysql-ai-agent:5060c9f3` · edge
`/healthz git_commit=5060c9f3`).

**① 라이브 이관 (사용자 승인 — §12.3 Critical)**
`scripts/kb_scope_rescope.py --migrate --purge-ambiguous --backup /shared/kb-scope-backup-20260729.jsonl --apply`
→ **update 5,130 · merged(중복) 0 · delete 257**, 백업 5,387행 보관.
판정 내역: single 2,004 · schema 3,126 · ambiguous 257 · common 18(불변).

**② contract** — `--verify-contract` **잔여 레거시 0건** 확인 후 `.env` 에
`AGENT_KB_LEGACY_DS_SCOPE_READ=0` + 4개 서비스 재기동. 전 컨테이너 `LEGACY=0` ·
`GIT_COMMIT=5060c9f3` · SHA 핀 이미지 실측(중간에 수동 `--force-recreate` 로 로컬 빌드
태그가 섞였으나 `deploy-web.sh --force-gateway` 정본 경로로 복원 후 재확인).

**③ PB-0008 실 Windows 브라우저 (Chrome/150.0.7871.115, relay @ 172.26.144.1:9223)**
- **스코프 선택기 = 제품**: 라벨 `제품`, `aria-label="메타데이터 스코프(제품)"`,
  옵션 **17건**(공용 + 활성 제품 16). `GET /api/admin/metadata/scopes` 200.
- **1제품↔N데이터소스 해소 실증**: `킹스레이드 - 도쿄 Live` 선택 → 용어 **85건** 렌더.
  이 85건이 이관 전 7개 DS 중 `mysql-kr-an1-auth` 한 곳에만 갇혀 나머지 6개 DS 질의에서
  미주입이던 바로 그 자산이다. 증거: `artifacts/pb0008/pb0008-meta-krlive.png`.
- **1데이터소스↔N제품 경계 실증**(핵심): `mssql-qa-idc` 를 공유하는 3제품이 각자
  **자기 접근DB만** 노출 — CC_QA 17 · DK_QA 35 · FH_QA 8 (`source=product-databases`,
  라이브 introspection 0회). 교차 시도(`scope_key=product.cc_qa` + `schema=FHGame1`,
  같은 datasource 의 FH_QA 소유 DB) → **404 `해당 제품의 접근 DB 가 아닙니다.`**,
  자기 DB(`cc_data_main`) → 200 / 255 테이블. 종전 datasource 축은 서버 전체 DB 를
  나열했으므로 이는 UX 정합인 동시에 **경계 강화**다.
- **이관 귀속 정확도**: 공유 DS 에 뒤섞여 있던 설명이 제품별로 분리됨 —
  DK_QA 테이블 153 / 컬럼 1,046 · WEB_QA 컬럼 1,926 · WEB_G_QA 컬럼 879
  (콘솔 API 응답과 PG 집계 일치).
- **부트스트랩 UI**: 안내문 "현재 선택한 제품(**콜오브카오스 - QA**)의 접근 DB 에서…",
  단위 라벨 `데이터베이스 *`, 후보 **17개 데이터베이스**(= CC_QA 접근DB).
  증거: `artifacts/pb0008/pb0008-meta-bootstrap-ccqa.png`.
- **안내 문구 갱신 확인**: 우측 empty-state 가 "…를 **제품별**로 관리합니다. 등록 내용은
  **그 제품의** 질문/스키마 매칭 시 … (제품이 여러 DB에 걸쳐 있어도 동일하게 적용).
  **공용** 스코프는 모든 제품에 적용됩니다."

**미실증(정직)**: 실제 대화 1건을 돌려 프롬프트에 주입된 사전을 육안 대조하는 end-to-end
주입 검증은 수행하지 않았다 — 주입 경로는 단위 테스트(제품 축 캐스케이드·DS 무관 동일 scope)와
콘솔의 제품별 렌더로 확인했고, 라이브 대화 생성은 사용자 데이터에 흔적을 남긴다.

- **Pass/Fail: PASS**(POST-DEPLOY). CHECK#13 충족.
