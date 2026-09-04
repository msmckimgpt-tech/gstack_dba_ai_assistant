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
| 트레이 | 메뉴 ID 라우팅 · 기본 항목 · 비활성/구분선 무시 · 콜백 예외 격리 · 툴팁 상한 · 생성 실패 시 `start()` 가 거짓 |
| 창 닫기 분기 | 트레이 있음=숨김(연결 유지) / 없음=종료 · 안내 문구가 그 실재와 일치 · 풍선 1회 |
| 스레드 경계 | 트레이 콜백은 큐에만 넣는다(tkinter 직접 조작 금지) |
| 자식 창 | 자식을 띄우는 **모든** 함수가 창 숨김 인자를 실제로 넘긴다(소스 census + 행위) |
| 두 껍데기 상주 정합 | 상주 중 유휴가 종료시키지 않음 · 트레이 없음/죽음이면 종전 계약 복귀 · [종료] 로만 끝남 · 두 껍데기 메뉴 어휘 동일 |
| 패널 문구 | `status.resident` 로 두 문구를 갈라 말함 · 문구가 가리키는 요소 실재 · DOM 렌더 대조군 |

## 2. 실행

```
python3 -m pytest unit/feature-0046-native-client/tests/ -q     # 177건

# 실 Windows 층(ctypes/Win32)은 리눅스에서 돌지 않는다 — 별도 실측:
#   tests/windows/README.md  (verify_console / verify_flicker / verify_tray / verify_gui)
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

### Run 2026-09-04T10:40:00+09:00 — 트레이 상주 + 자식 콘솔 창 제거
- 상세는 fragment: [`test-runs.d/TASK-20260904T100000-tray-and-windowless.md`](./test-runs.d/TASK-20260904T100000-tray-and-windowless.md)
- Environment: `CLI` 177/177 PASS · 뮤테이션 21/21 KILL (NOOP 0)
- Environment: **Windows-native (실 머신)** — 4종 실측 전부 PASS. 대조군까지 둔 관측:
  자식 콘솔 핸들 `2430520 → 0`, 바탕화면 콘솔 창 peak `2 → 1`.
- Verdict: PASS
- 적대 리뷰(codex) P1 4건 수정 후 **재측정본**이다 — 수정 전 수치를 인용하지 않는다.

### Run 2026-09-04T15:20:00+09:00 — 재구성: 웹 셸 주 경로에도 트레이 상주
- 상세: [`test-runs.d/TASK-20260904T150000-tray-parity.md`](./test-runs.d/TASK-20260904T150000-tray-parity.md)
- Environment: `CLI` 256/256 PASS · 뮤테이션 8/8 KILL(NOOP 0, M24 는 문법 파손 판을 폐기하고 행동 판으로 재실행)
- Environment: `CLI` (jsdom) — 패널 상주 문구 **DOM 렌더** 확인 + 대조군 FAIL 실증
- ⛔ **PB-0008 미수행** — 이 패널은 Windows 브리지가 만든 `client_port/nonce` 로만 나타나고
  유효 토큰이 없다. 라이브 반영은 공유 web 컨테이너를 건드려야 해 §13.2.9 가 금지한다.
  다음 cycle 로 이월(사유는 fragment §4).
- Verdict: PASS (미수행 2건 명시)
