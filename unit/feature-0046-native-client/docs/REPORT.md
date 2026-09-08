---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260908-codex-connect-fix — DQA1.2.4 설치·실제 응답 확인

실제 DQA1.2.1 연결창의 Codex 실패 원인은 정상적인 모델 카탈로그 응답을 빈 상세 캐시로 처리하는 계약과 연결 완료 처리 사이의 불일치였다. KeyError와 예외 로깅 인자 누락을 고치고, 실제 응답·서버 수락·현재 선택이 일치할 때만 연결 완료로 인정한다. 선택별 독립 세대와 재시도로 다른 AI 조회·위치 변경의 오래된 결과도 차단한다.

제품 PR #1631(8f1116cf) 전체 서버 배포와1.2.4 공개를 완료했다. **실제 Windows DQA의 트레이 [업데이트 확인]에서1.2.3→1.2.4 설치를 수락**했다. 수락 후11.153초에 새 앱이 시작되고14.186초에 설치기 두 프로세스가 모두 exit0으로 끝났다. 설치 파일/실행 파일 SHA-256, pending 해소,5초 안정 실행을 대조했다.

**실제 DQA 새 대화에서 Codex(root, GPT-6-Astra/높음)가 `42 DQA_CODEX_42`로 답했다.** 런타임 처리·자가 검토·제출32318ms, delivered=true. Windows UI Automation으로 입력·클릭하고 실제 WebView2 답변 텍스트를 확인했다. 별도 브라우저나 수동 러너를 사용자 절차로 실행하지 않았다.

권한 오류 위치는 안전한 permission_denied 상태로 자동 연결·로그인 대행에서 제외하고 목록에는 사유를 남긴다. **이번 현장에서는 Codex root와 claude-corp 모두 가용성 응답·실제 UI 연결이 성공**하여 사용자가 겪은 Permission denied를 재현했다고 보고하지 않는다. 계정명 차단·OS 권한 수정은 하지 않았다. Claude의 claude-corp 응답 실패 위치가 비활성 목록에 남는 것은 실제 확인했다. gh-runner는 탐색·기존 캐시·UI 후보에서 제거했으며 OS/CI 계정은 유지한다.

[검증 원장](test-runs.d/20260908-codex-connect-fix.md)에 코드·실제 설치·대화·제한을 구분하고, 해당 원장의 artifacts 링크에 인증정보 없는 증거를 보존한다. 실제 화면에서 발견한 안내의 Markdown 강조 기호 노출도 공통 연결 UI에서 수정했다. PR #1633(7ca6f2a4) 웹 배포 후 실제 설치 앱을 정상 종료·재실행해 강조 기호 제거와 root 자동 복원을 확인했다. 최종 설치판은1.2.4다.

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
