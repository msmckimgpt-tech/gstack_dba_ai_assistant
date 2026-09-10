---
run_at: 2026-09-10T08:02:17+00:00
session: codex-model-switch-20260910
scope: [model-selection, runtime-health, recovery, client]
verdict: pass-pending-client
---

# TASK-20260910-model-switch 검증

- 설치 원인: DQA task t_BRc3Lrh4CHbbCs2G는 codex/gpt-6-astra/medium으로 dispatch됐고 전역 ai.unhealthy_fastfail이 Claude session limit을 재사용했다. 사용자 원문/토큰은 기록하지 않는다.
- RED: 독립 backend stub에서 Claude 실패 뒤 Codex spawn 0회/Claude 사유 재사용; Codex 미가용 시 이전 Claude 호출 1회. 실제 AI/API 호출 없음.
- GREEN: 신규15 PASS(모델/런타임별 실패, 병렬 결과, 위치 세대, 정확한 복구 argv, custom, 미선택 대체 금지, package import). 영향받는 집중124 PASS.
- 전체 첫 실행8 FAIL: 빌드 도중 소스 변경1, mock 인터페이스5, 종전 대체 실행 계약2. 원인을 수정하고 해당124개 전부 재검증했다.
- 최종 전체 결과: **1812 passed / 1 skipped / 0 failures / 0 errors**, 158.153초. artifacts/model-switch-20260910/pytest.xml 및 pytest.log. 앞선 QA의 별도 혼합 실행에서 발생한 client selection 대기 실패는 최종 전체 실행에서 재현되지 않았다.
- backend/qa 최종 코드 PASS. ruff/diff-check 및 verify-completion pre-commit PASS.

Environment: DQA-client
Result: NOT-RUN
Build: 설치 DQA PID12344/WebView2 PID32392, runner 수정 배포 전
Scenario: 모델을 변경한 뒤 해당 AI 실제 응답 도달
Reason: 배포 전. 앱 입력란 비어 있음/전송 버튼 활성 확인, 해당 앱의 CDP는 비활성이고 UIAutomation은 접근 가능.
Alternative: 설치 로그와 실제 런너 코드 대조 및 로컬 argv/복구 행위 회귀.
Next: 배포 후 설치 runner SHA 대조와 합성 확인 질문의 실제 DQA 흐름.
