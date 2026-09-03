---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
---

# Task

## 1. 현재 상태

첫 cycle 완료 — 코어·GUI·빌드 스크립트·테스트 20건. **실 Windows 에서 감지·GUI 구성·exe 빌드·
실행까지 실측 확인.** 후속: 자동시작·자동 업데이트·벤더 설치기 실행.

## 2. Cycle — TASK-20260903T140000 Windows 네이티브 클라이언트 초판 (ROADMAP ITEM-08)

- [x] `src/client/core.py` — 감지·로그인 대행·무결성 대조·러너 기동 (GUI 무의존)
- [x] `src/client/gui.py` — tkinter 껍데기 + `tell()` 안내
- [x] `src/scripts/build_client.py` — PyInstaller onefile/windowed, 비-Windows 차단
- [x] `tests/test_client_core.py` 20건 — ToS 경계·무결성·정본 동기화·토큰 취급·축 분리
- [x] **실 Windows 실측**: claude 를 PATH 밖 `.local\bin` 에서 감지 · JSON 로그인 판정 ·
      tkinter 한글 타이틀 구성 · PyInstaller exe 빌드(9.17MB) · 실행
- [x] **실측이 결함 1건 적발**: windowed 빌드에서 `print()` → 미처리 예외 대화상자로 **멈춤**.
      `tell()` 로 교체 후 재빌드·재실행으로 해소 확인
- [ ] 자동시작 등록 (후속)
- [ ] 자동 업데이트 (후속)
- [ ] 벤더 설치기 동의 실행 (후속 — 현재는 설치 안내 링크)
- [ ] gemini 로그인 대행 (SPIKE-02 미실측 — 실측 후 지원/강등 결정)
- [ ] 웹 `/ai/connect` 에서 클라이언트 배포 (ITEM-03/06 과 함께)

## 3. Completion Checklist

- [x] REQ 의 AC 구현
- [x] 자동 테스트 통과 (20건)
- [x] FUNCTION/MODIFY/REVIEW/REPORT/TEST 갱신
- [x] BLOCKED 없음
- [ ] 라이브 배포 검증 — 웹 배포 표면 변경 0이라 이번 cycle 대상 아님
