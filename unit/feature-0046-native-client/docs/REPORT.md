---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260908-codex-connect-fix — 수정본 검증·출하 진행

실제 DQA1.2.1 연결창에서 Codex root/claude-corp 선택 후 failed receipt를 재현했다. 모델 카탈로그 성공 시 영속 상세가 비어 있는 정상 계약을 lifecycle의 detail[name]이 KeyError로 처리하고, 예외 로깅 인자도 누락되어 원인이 가려졌다.

빈 상세 처리, 실제 alive:true 검증, 선택별 독립 세대, 위치 변경 후 재시도, OS/WSL 권한 실패 판정, CI 계정 제외, 사용 불가 위치 UI를 수정했다. 사용자 계정의 권한은 변경하지 않았다. root/claude-corp의 홈 기준 CLI 무도구 진단 요청은 둘 다 성공하여 Permission denied를 현 환경의 모든 실행에서 재현된 것으로 단정하지 않는다.

코드 검증과 실제 설치·요청/응답 증거는 test-runs.d/20260908-codex-connect-fix.md에 구분해 기록한다. 1.2.4 실제 설치/질문 검증은 배포 후 이어서 수행하며, 이전 cycle의 완료 주장은 현재 수정본 검증을 대신하지 않는다.

## TASK-20260908-update-install-proof — 실제 설치 완료 (DQA 1.2.1)

## TASK-20260908-text-interaction — Issue #1626

DQA 창의 pywebview 기본값(text_select=False)이 답변·텍스트 첨부 선택을 막고 있었다. text_select=True로 복구했다. Ctrl+F는 배포 모드에서 AreBrowserAcceleratorKeysEnabled=False이던 것을 UI 스레드에서 True로 설정한다. 디버그·개발자 도구·클립보드 인가·읽기 전용 본문을 바꾸지 않는다.

클라이언트 **1.2.3 공개 완료**. 최신 릴리스 API·설치기 실제 다운로드 모두 HTTP 200, 26,048,286 bytes, SHA-256 `85b69a01da88019031c7cead689d6c7c4359d750b58f7ed32a22958424c5d672`로 Windows 빌드와 일치한다. [공개 검증](artifacts/20260908-text-interaction/published.json). 서버 코드 변경은 없으므로 웹 재배포는 불필요하다. 기존 사용자 앱은 종료·설치하지 않았으며 배포 후 기존 [업데이트 확인]을 통해 적용한다.

[실측 원장](test-runs.d/20260908-text-interaction.md)·[수정본](artifacts/20260908-text-interaction/fixed.json)·[빌드](artifacts/20260908-text-interaction/build.json).

검증: 창 테스트 50개 통과, native 전체 530 PASS/1 SKIP. 실제 제품 Shell/WebView2 + 합성 문서에서 답변·Markdown·원문 선택/Ctrl+C/V를 검사했다. 이전 설정 대조군은 세 영역 모두 선택 실패로 원인을 재현했다. 상세 최신 결과는 test-runs.d/20260908-text-interaction.md.

**미검증:** native Ctrl+F 검색창·F3/Shift+F3 일치 이동·Escape 닫힘. 이 호스트에서 SendKeys/대상 HWND 입력은 브라우저 단축키로 전달되지 않았고, CDP 입력은 본문 편집에만 도달했다. 설정값 활성화와 재로드 후 유지 확인을 검색 UI PASS로 합산하지 않는다. 전체 수용 기준 판정 PARTIAL. 첨부는 현재 표시되는 텍스트 형식이며 PDF/스프레드시트/OCR 신규 뷰어가 아니다.

위험도 Minor. 사용자 요청 및 AGENTS.md §16.5.1/deploy_scope included 범위. 적용 정책 SHA-256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2.

## Git 동기화 결과

- 제품 commit c5842b94, PR #1628 병합 513f0d5e. pre/post verify-completion PASS, native 검색 UI 미검증 경고 보존.
- 업데이트 채널 공개·다운로드 검증 완료. 사용자 승인 대기 없음. 검색 UI 실측 부채는 Issue #1626으로 유지한다.
- 제품 코드 독립 UX/design 리뷰 PASS; 실측 범위는 PARTIAL.
- 이전 기록: [report history](report-history/20260908-before-text-interaction.md).
