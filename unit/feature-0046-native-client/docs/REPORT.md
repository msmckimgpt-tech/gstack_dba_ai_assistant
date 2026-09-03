---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## 1. 현재 상태

**2026-09-03 초판.** Windows 클라이언트가 실 머신에서 동작한다 — AI 감지(PATH 밖 포함) · 로그인
상태 JSON 판정 · GUI 구성 · PyInstaller 단일 exe(9.17MB) 빌드 · 실행까지 실측했다.

실측이 결함 1건을 잡았다: `--windowed` 빌드는 `sys.stdout` 이 없어 `print()` 가 미처리 예외
대화상자를 띄우고 **프로세스가 멈춘다**. 로컬 테스트로는 보이지 않는 결함이었다.

## 2. 남은 리스크

- **미서명 배포** — SmartScreen 경고 2클릭(사용자 결정으로 감수). 대상이 「경고를 무서워하는
  사람」이라 이탈이 생길 수 있다. 계측(ITEM-00 퍼널)이 그 크기를 잴 것이다.
- **gemini 미지원** — 로그인 대행 명령 미실측. 화면이 그 사실을 말한다(과장하지 않음).
- **배포 경로 미구현** — 웹에서 exe 를 받는 경로는 ITEM-03/06 과 함께.

## 3. Git 동기화 결과

- 커밋: 본 cycle
- verify-completion: PASS
- Push / PR: 완료
