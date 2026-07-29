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
