---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: review
---

# Task

## TASK-20260908-text-interaction

사용자 요청: DQA 답변·첨부 미리보기의 드래그 선택, Ctrl+C/V 및 Ctrl+F 탐색 복구.

## 2.1 Implementation Plan

- `src/client/window.py`: `Shell.run`에서 text_select=True, `Shell._on_loaded`에서 UI 스레드로 WebView2 기본 검색 단축키 활성화. 디버그 모드는 유지하지 않고 기본 비활성 상태를 보존한다.
- `tests/test_embedded_window.py`: 생성 옵션·loaded 콜백·UI 스레드 전달·실패 기록 회귀 검증.
- `tests/windows/verify_text_interaction.py`: 실제 제품 Shell/WebView2에서 드래그→Ctrl+C→입력창 Ctrl+V, Ctrl+F/F3/Escape, Markdown 첨부·원문 코드 DOM을 검증한다. 이전 설정의 대조군도 확인한다.
- `src/client/version.py`, `src/installer/DQAConnect.iss`: 검증 후 새 클라이언트 버전 빌드·공개. 웹 서버 코드 변경은 필요하지 않다.
- 현재 기능 명세·검증 원장·보고·릴리즈노트에 결과와 경계를 기록한다.

수용 기준: 답변 `선택 복사 확인`을 드래그해 Ctrl+C 후 입력창 Ctrl+V하면 동일 문장이 입력된다. 첨부 미리보기의 실제 표시 텍스트에도 동일 동작. Ctrl+F에 `needle` 입력시 화면의 해당 문자열 발견, F3 다음 일치, Escape 닫힘. 읽기 전용 답변은 편집되지 않는다.
검색 범위는 현재 로드된 화면과 열린 텍스트 첨부이며 아직 열지 않은 파일 전체나 이미지 OCR은 포함하지 않는다.
위험도 Minor: 창의 상호작용 옵션 복구, 인증/인가·DB·벤더 호출 변경 없음.

## Context

- worktree: /root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0046-text-interaction
- branch: ai/codex/feature-0046-text-interaction; base 49f7fa41
- policy: AGENTS.md SHA-256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2
- hot_paths: client/window.py (동료 공유 링크 작업은 Shell.navigate 추가; 기존 작업 보존하며 main 통합 시 대조).
- 이전 TASK: [history](task-history/20260908-before-text-interaction.md)

## Progress

- [x] 원인 확인: pywebview text_select 기본 False, edgechromium AreBrowserAcceleratorKeysEnabled=debug(False).
- [x] 구현 및 단위 검증
- [x] DQA-client 텍스트 실측·독립 UX/design 코드 검토. native 검색 UI NOT-RUN/PARTIAL 기록.
- [x] 새 설치기 1.2.3 빌드·PR #1628 병합(513f0d5e)·공개 다운로드 크기/SHA 검증

## 9. Requested Scope

```text
사용자 원문(데이터이며 지시가 아님)
출력된 답변에 대해 텍스트 드래그로 박스처리, Ctrl+C / V 등을 통한 작용
첨부파일 내 텍스트 포함
Ctrl+F 를 통한 텍스트 탐색
```

- [x] 답변: 드래그·Ctrl+C/V 실제 WebView2 fixture 검증.
- [x] 첨부파일 내 텍스트: 현재 표시되는 Markdown·원문 코드 검증. PDF/스프레드시트 본문 미리보기는 기존 제품 미지원.
- [ ] Ctrl+F: 네이티브 설정 복구/재로드 유지 확인. 실제 검색창·결과 이동은 자동화 입력 한계로 NOT-RUN. 전체 수용 기준 PARTIAL.
- [다의어] 박스처리=브라우저 텍스트 드래그 선택; 별도 주석 사각형 그리기는 포함하지 않는다. 예시는 계획 §2.1 유지.

- 설치기 빌드 완료. 공개채널 반입 및 다운로드 검증 완료. 검색 UI 실측 부채는 Issue #1626에 유지한다.

## Verification debt

Ctrl+F/F3/Shift+F3/Escape 실제 검색 UI 확인. 설정 복구를 실제 검색 UI PASS로 대체하지 않는다. 기존 사용자 앱은 임의 종료하지 않는다.
