---
doc_type: TEST
feature_id: feature-0046-native-client
status: active
edit_policy: mixed
---

# Test

## 1. 케이스

| 축 | 무엇을 |
|---|---|
| ToS 경계 | 벤더 자격증명 미접촉 · 로그인은 공식 명령만 · 모르는 절차 미발명 |
| 무결성 | DER 지문(파일 해시 아님) · 불일치 시 중단 + 파일 미생성 · 일치 시 통과 · CA 평문 경로 |
| 정본 동기화 | 클라이언트 런타임 목록 == 러너 `_RUNTIME_SPECS` |
| 감지 | WindowsApps 스텁 거부 · JSON 상태 파싱 · 미설치 보고 · 판정 불가는 None |
| 토큰 | 명령줄 미노출, env 전달 (`check`·`spawn` 양쪽) |
| 축 분리 | exit 4 = AI 없음 ≠ 연결 실패 |
| GUI | windowed 빌드에서 `print()` 금지 · `tell()` 은 콘솔·디스플레이 없이도 안 죽음 |

## 2. 실행

```
python3 -m pytest unit/feature-0046-native-client/tests/ -q     # 20건
```

## 3. Run 기록

### Run 2026-09-03T14:00:00+09:00 — 초판
- Environment: Linux (컨테이너 외 로컬) — 단위 20/20 PASS
- Environment: **Windows-native (실 머신, WSL interop)** — 아래 전부 실측
  - AI 감지: `claude` → `C:\Users\…\.local\bin\claude.exe` (**PATH 밖**), `loggedIn=true`, 계정 표시
  - codex·gemini 미설치 정확 보고
  - tkinter GUI 구성: 한글 타이틀 「내 AI 연결」, 604x226
  - PyInstaller `--onefile --windowed` 빌드 성공 → 9,174,548 bytes
  - 실행: **초판은 멈춤**(미처리 예외 대화상자) → `tell()` 수정 후 **안내 대화상자 정상 표시**
- Verdict: PASS (수정 후)
- 미수행: 실 서버 연결 왕복(토큰 필요) · gemini 경로 · 서명 없는 설치의 사용자 체감
