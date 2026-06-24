---
doc_type: TEST
feature_id: feature-0011-shared-extraction
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract
- 성공 조건: `from shared.model_catalog import ...` 가 두 feature(agent-core·web)와 격리 테스트
  컨테이너·프로덕션 컨테이너(/app)에서 해석되고, `make test` 결과가 본 변경 전후 동일(회귀 0).
- 실패 모드: import 경로 미해결(ModuleNotFoundError), `modules/__init__` eager-import 체인 단절,
  컨테이너 COPY 누락으로 런타임 import 실패.
- 복구: 단일 commit revert → model_catalog 가 modules/ 로 복귀(이미지 재빌드만, 데이터 무변경).

## 2. Automated Tests
- `make test` (격리 agent 이미지, `--no-deps`, PYTHONPATH=두 src + `/work`):
  - 결과: **1077 passed, 2 failed, 2 skipped**.
  - 2 failed = `test_product_delete_block_conv.py` (admin_delete_product 404≠200) —
    **clean main(165906b)에서도 동일 재현된 baseline 실패**, 본 변경(model_catalog/shared) 무관.
  - 회귀 판정: 본 변경 도입 전/후 동일 결과 → **회귀 0**.
  - moved-module 직접 테스트 `test_prompt_gen_max_tokens.py`: 5/5 PASS.

## 3. Manual / Environment Tests
- **프로덕션 레이아웃(/app) import smoke** (빌드 이미지): agent(`python /app/agent_core.py`)·
  web(`uvicorn web.app:app` 실부팅 "Application startup complete")·memory-init·insight-worker·
  ask-worker 전부 import OK. §18.8 패널 실측.
- **Environment: Windows-browser — N/A (사유 명시)**: 본 cycle 의 web 파일 변경(app.py)은 **import
  경로 1줄**(`from modules.model_catalog`→`from shared.model_catalog`)뿐으로 **UI 표면·렌더링·동작
  변화가 0**이다(behavior-identical). PB-0008 Windows-browser 검증(§15.4.1)은 시각/UI 렌더링 회귀
  대상이며 본 변경엔 비해당. import 해석은 패널의 라이브 uvicorn 부팅으로 대체 검증됨.

## 4. Coverage Gaps / Follow-up
- 라이브 배포 후 web-1/agent healthz·smoke 는 배포 단계(cycle-finalize→재배포)에서 확인 예정.
- baseline 실패(test_product_delete_block_conv)는 feature-0003 소관 — 별도 추적 권장.
