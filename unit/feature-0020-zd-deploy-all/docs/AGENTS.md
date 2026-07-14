---
doc_type: FEATURE_AGENT_POLICY
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: human-guided
source_of_truth: false
---

# Feature AI Notes

- 이 기능의 우선 문서는 루트 `../../../AGENTS.md` 이다.
- **코드 거주 (cross-cut)**: 본 feature 의 구현은 `bin/deploy-web.sh`(feature-0014 스파인 확장)·
  `docker-compose.yml`·`Makefile`·`bin/alembic-migrate.sh` 에 거주한다 — `../src` 는 비어 있음
  (feature-0015/0017 과 동일 패턴).
- 배포 스크립트 수정 시 `--dry-run` 4 scope(기본/--web-only/--workers-only/--rollback) 전 경로
  통과를 최소 게이트로 한다. compose 수정 시 `config -q` ±`--profile deploy-surge` 둘 다 검증.
- 마이그레이션 게이트(CONVENTIONS §12)·MySQL online-DDL(§13)은 본 feature 가 소비하는 선행
  게이트 — 여기서 변경하지 않는다.
