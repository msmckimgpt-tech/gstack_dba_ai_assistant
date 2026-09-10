---
run_at: 2026-09-10T08:02:17+00:00
session: codex-model-switch-20260910
scope: [model-selection, runtime-health, recovery, client]
verdict: pass
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

## 출하 및 병행 릴리스 대조

- PR #1678: 구현15360fd8 → main1c620a97. `make deploy-web-only` exit0, web-a/web-b ready 및90초 post-cutover soak PASS, asset stamp190c2c9785e1. 워커/서비스 대화 스모크는 web-only 배포에서 미수행.
- 설치 runner 자동 갱신: 기존371cac83d087e308588d420ca52f156c8cc484c30c1697f267cf9c83b609c42d → 수정4f61b1275e8f2194b18d1ee2c97678cb7f5beb6a7dabe3770bbac80f12377d53. PID22376의 heartbeat 복귀 확인.
- 병행 릴리스 #1679/main931a543e를 fast-forward 통합. 모델 격리·번들 회귀36 PASS, 서버/설치 runner SHA256531984cab769f98f2e141e927f1993a44004b37cf1338efa8c1926942a917a9c 일치. 변경된 discovery 통합 검증은 `artifacts/model-switch-20260910/pytest-integrated.log`.
- 실제 DQA PID12344에서 UIAutomation으로 Opus (최신) → GPT-6-Astra 표시 전환 확인. 합성 입력 뒤 전송 전에 병행 앱 업데이트로 PID34472/1.5.0으로 바뀌어 최초 전송은 미실행. 기존 업무 질문을 재전송하지 않았으며 이 세션은 앱을 재설치·종료하지 않았다.

## 최종 설치 DQA 확인

Environment: DQA-client
Result: PASS
Build: DQA1.5.0 PID34472/WebView2 PID33984, web931a543e, runner531984cab769f98f2e141e927f1993a44004b37cf1338efa8c1926942a917a9c
Scenario: 모델을 변경한 뒤 해당 AI 실제 응답 도달
Evidence: 2026-09-10 17:20:22+09:00 UIAutomation으로 새 대화에서 모델 Opus (최신) → GPT-6-Astra의 실제 표시를 검증한 뒤 합성 요청 전송. 17:20:25.371 task t_BAAHNxS3izL9i7bw dispatch=codex/gpt-6-astra/medium, 17:20:25.377 ai.cmdline.stdin runtime=codex, 17:20:48.798 task.submit.ok delivered=true/dur_ms=23427. 실제 앱 assistant 본문 SWITCH_OK_910 일치·입력란 비어 있음·전송 버튼 활성 확인. Claude 재호출/ai.unhealthy_fastfail 없음.
Artifacts: artifacts/model-switch-20260910/installed-model-switch.json, installed-request-events.json, installed-response.json. 로그는 해당 요청 시간대의 이벤트·모델·길이·지문만 추출하며 토큰/시스템 프롬프트 원문을 담지 않는다.
Boundary: 실제 앱 모델 전환→선택한 AI 실행→응답 표시는 PASS. Claude의 사용량 제한 직후라는 조건은 로컬 회귀로 검증했고, 설치 앱에서 실패를 새로 유발하는 Claude 요청은 보내지 않았다. 원 업무 대화 재실행/DB/파일 조회 없음. 중간에 다른 작업의 입력이 관측된 시도는 덮어쓰기 없이 중단한 뒤 입력란이 비었을 때 새 합성 대화에서 완주했다.
