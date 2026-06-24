# shared/ 공통 모듈

## 목적
여러 기능에서 실제로 공통으로 쓰는 코드가 생겼을 때만 이 디렉토리에 둔다.
`from shared.<module> import ...` 형식으로 import 하며, 동작 조건은 **shared/ 의 부모
디렉토리가 sys.path 에 있을 것**이다 — 컨테이너는 WORKDIR `/app`(Dockerfile `COPY shared
/app/shared`), `make test`/eval 은 PYTHONPATH 의 `/work`(repo 루트, shared 의 부모).

## 현재 승격된 모듈 (feature-0011-shared-extraction, P5a 진행 중)
- `model_catalog` — LLM 모델 카탈로그(순수 stdlib). agent-core·web 양 feature 가 공유하는
  첫 승격 모듈(P5a Step 1). 이력: `unit/feature-0011-shared-extraction/docs/MODIFY.md`.
- (예정) db.py, config/memory/llm 등 — P5a Step 2~4 에서 점진 승격.

## 거버넌스 규칙
1. shared 코드를 변경하는 AI는 자신의 기능 `MODIFY.md`에 변경을 기록한다.
2. 변경 내용을 `/repo/shared/MODIFY.md`에도 교차 참조로 기록한다.
3. 변경이 다른 기능에 영향을 줄 수 있으면, 영향받는 기능의 `REPORT.md`에 알림을 남긴다.
4. 대규모 shared 변경은 별도 unit으로 승격하는 것을 우선 검토한다.

## 소유권
- shared 코드는 특정 기능에 소유되지 않는다.
- 변경 시 프로젝트 수준 `DECISIONS.md` 또는 기능 `REVIEW.md`에 근거를 남긴다.
