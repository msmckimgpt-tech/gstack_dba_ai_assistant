---
doc_type: ANCHOR
feature_id: feature-0011-shared-extraction
created_at: 2026-06-24T11:46:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0011-shared-extraction — 공통 모듈 shared/ 추출 (점진 리팩터)

## §1. 외부 관점 요약
처음 코드를 여는 사람은 "왜 `modules/` 안에 잘 있던 공통 코드를 repo 루트 `shared/` 로
빼내지? 두 feature(0002 agent-core·0003 web)가 이미 PYTHONPATH 로 서로의 `modules/` 를
import 하고 있는데 굳이?" 라고 의문을 가질 수 있다. 이유: 현재 `modules/db.py` 하나가
**app.py 84곳 + feature-0002 11개 파일 + scripts** 에서 import 되는 repo 최다결합 모듈이라,
두 feature 가 사실상 feature-0002 의 `modules/` 에 암묵적으로 종속돼 있다(소유권 불명확).
공통 코드를 명시적 `shared/` 네임스페이스로 모으면 (a) "누가 무엇을 공유하는가" 가 import
경로로 드러나고, (b) Dockerfile/`make test` 가 `shared` 를 단일 지점으로 배선해 feature 별
이미지 분리(P5b/Dockerfile split)의 토대가 된다. 두 번째 의문 — "왜 한 번에 다 안 옮기고
한 모듈씩?": `db.py` 를 첫 추출로 삼으면 ~100+ 재배선 + Dockerfile + PYTHONPATH + 라이브
web 컨테이너를 한 turn 에 건드리는 최고위험이라, **저결합 모듈부터 test-gated 로 플러밍을
증명**하는 안전 sequencing 을 택했다(big-bang 금지).

## §2. 대안 분기
- **Alt-A: db.py 를 첫 추출로 한 번에 전부 이동.** 페르소나: 리팩터를 단숨에 끝내려는 팀.
  안 고른 이유: db.py 는 app.py 84 + 0002 11파일 + scripts 결합으로, 추출이 Dockerfile COPY
  레이아웃·`make test` PYTHONPATH·라이브 web-1 이미지를 동시에 건드린다. 검증 없이 긴 작업
  끝에 강행하면 가동 중 제품 회귀 위험이 크다. → 저결합 모듈로 플러밍을 먼저 증명.
- **Alt-B: shared/ 없이 두 feature 가 계속 서로의 modules/ 를 PYTHONPATH 로 참조.** 페르소나:
  현상 유지·변경 최소화 팀. 안 고른 이유: 공통 코드가 feature-0002 소유로 묶여 0002 변경이
  0003 에 암묵 전파되고, feature 별 이미지 분리가 불가능하다(0003 이미지가 0002 src 전체를
  COPY 해야 함). 소유권·빌드 분리 목표와 상충.
- **Alt-C: shared/ 를 별도 PyPI 패키지/서브모듈로.** 페르소나: 멀티레포 성숙 조직.
  안 고른 이유: 단일 repo·단일 배포 스택에 패키징/버전 관리 오버헤드가 과대. repo 루트
  `shared/` 디렉토리 + PYTHONPATH 배선으로 충분.

## §3. 가정된 사용 시나리오
6개월 후 다른 작업자가 P5a Step 2(db.py shim 추출)를 맡는다. 그는 본 ANCHOR/FUNCTION 과
첫 추출(model_catalog) 의 MODIFY 이력만 읽고 다음을 재발명 없이 파악할 수 있어야 한다:
(1) `shared/` 는 `__init__.py` 를 가진 Python 패키지이고 import 는 `from shared.<mod> import ...`
형식이며, (2) 동작 조건은 **shared/ 의 부모 디렉토리가 sys.path 에 있을 것** — 컨테이너는
WORKDIR `/app`(COPY shared → /app/shared), `make test`/eval 은 PYTHONPATH 에 `/work`(=repo
루트, shared 의 부모) — 이고, (3) 새 모듈을 옮길 때 반드시 `from modules.<x>` 절대형뿐 아니라
`modules/` 내부의 `from .<x>` **상대 import 사이트까지** 전수 재배선해야 한다(model_catalog
추출 때 `modules/llm.py` 의 상대 import 를 처음 놓쳐 `modules/__init__` eager-import 체인이
무너진 교훈). 각 추출은 `make test` green(회귀 0) 게이트를 통과해야 한다.

### 동반 메모 — 라이브 reconciliation GDPR legal-erasure gap (#4, 결정-독립)
feature-0002 `attachment_reconciliation.py` 는 **미배선(unwired) GDPR legal-erasure 설계**
(TASK-0094 D6 4-state + legal pseudonym, Phase 10 의존)다. 라이브 web(feature-0003)판
reconciliation 에는 이 legal-erasure 경로가 **가동되지 않는다**. 본 추출은 이 코드를
보존하며 dedup-merge 하지 않는다. wiring 은 별도 compliance 결정 사항이다(본 cycle 범위 밖).

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. release/milestone 시 사람이 append.)
