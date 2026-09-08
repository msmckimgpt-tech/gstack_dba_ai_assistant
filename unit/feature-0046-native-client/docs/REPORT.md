---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260908-text-interaction — Issue #1626

DQA 창의 pywebview 기본값(text_select=False)이 답변·텍스트 첨부 선택을 막고 있었다. text_select=True로 복구했다. Ctrl+F는 배포 모드에서 AreBrowserAcceleratorKeysEnabled=False이던 것을 UI 스레드에서 True로 설정한다. 디버그·개발자 도구·클립보드 인가·읽기 전용 본문을 바꾸지 않는다.

클라이언트 1.2.3 Windows 설치기 빌드 성공. 서버 코드 변경은 없으므로 웹 재배포는 불필요하다. 기존 사용자 앱은 종료·설치하지 않았으며 배포 후 기존 [업데이트 확인]을 통해 적용한다.

[실측 원장](test-runs.d/20260908-text-interaction.md)·[수정본](artifacts/20260908-text-interaction/fixed.json)·[빌드](artifacts/20260908-text-interaction/build.json).

검증: 창 테스트 50개 통과, native 전체 530 PASS/1 SKIP. 실제 제품 Shell/WebView2 + 합성 문서에서 답변·Markdown·원문 선택/Ctrl+C/V를 검사했다. 이전 설정 대조군은 세 영역 모두 선택 실패로 원인을 재현했다. 상세 최신 결과는 test-runs.d/20260908-text-interaction.md.

**미검증:** native Ctrl+F 검색창·F3/Shift+F3 일치 이동·Escape 닫힘. 이 호스트에서 SendKeys/대상 HWND 입력은 브라우저 단축키로 전달되지 않았고, CDP 입력은 본문 편집에만 도달했다. 설정값 활성화와 재로드 후 유지 확인을 검색 UI PASS로 합산하지 않는다. 전체 수용 기준 판정 PARTIAL. 첨부는 현재 표시되는 텍스트 형식이며 PDF/스프레드시트/OCR 신규 뷰어가 아니다.

위험도 Minor. 사용자 요청 및 AGENTS.md §16.5.1/deploy_scope included 범위. 적용 정책 SHA-256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2.

## Git 동기화 결과

- pre-commit 검증 및 PR 준비 중. 사용자 승인 대기 없음.
- 제품 코드 독립 UX/design 리뷰 PASS; 실측 범위는 PARTIAL.
- 이전 기록: [report history](report-history/20260908-before-text-interaction.md).
