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
| 업데이트 버전 판정 | 수치 비교(`1.10.0 > 1.9.0`) · 같으면 갱신 안 함 · 모양 아닌 값은 거짓 |
| 업데이트 출처 | 고정 경로 + TOFU 고정 서버 + 사내 CA · 매니페스트의 URL 미사용 · `remembered_base` 미사용 · 평문 거부 |
| 업데이트 무결성 | 크기·sha256·PE 서명·상한 4축 · 파일명 traversal 거절 · 파일명↔버전 불일치 거절 |
| 릴리스 채널 | 실물 없음/크기·지문 불일치는 **광고 안 함** · 롤백(`--activate`) · 정리가 배포 중인 것을 안 지움 |
| 업데이트 확인창 | `update_apply` 는 `DANGEROUS` · 문구가 버전과 「연결이 끊긴다」를 말함 · 자동 적용 기본 꺼짐 |

## 2. 실행

```
python3 -m pytest unit/feature-0046-native-client/tests/ -q     # 506건

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

### Run 2026-09-07T15:30:00+09:00 — 클라이언트 업데이트 채널
- 상세: [`test-runs.d/20260907T150000-client-update-channel.md`](./test-runs.d/20260907T150000-client-update-channel.md)
- Environment: `CLI` — feature 스위트 **506/506 PASS** (신규 124건 — 적대 2라운드 반영 후 수치)
- Environment: `CLI` — **결함 주입 15/15 FAIL**(§16.7 G11-b — 되돌리면 전부 FAIL 한다)
- Environment: `CLI` + **실 TLS 서버** — 반입 → 서빙 → 수신 → 무결성 거절 **종단 8단계 PASS**
  (사내 CA 서명 https, 받은 바이트가 올린 바이트와 byte-동일)
- 선재 실패 1건(`test_share_redaction_invariant`)은 `main` 에서도 동일 FAIL — 회귀 아님
- ⛔ **미실측**: 설치기 실제 실행(`/SILENT /RELAUNCH`) — Windows 빌드 머신 필요
- `Environment: Windows-browser` 없음 — **웹 자산 변경 0건**이라 check #13 대상 아님
- Verdict: PASS (미실측 1건 명시)

### Run 2026-09-07T18:00:00+09:00 — 라이브 배포 실측 (업데이트 채널)
- 상세: [`test-runs.d/20260907T180000-live-deploy-verify.md`](./test-runs.d/20260907T180000-live-deploy-verify.md)
- Environment: `라이브 배포본` — `main` **697ffa84** 전 서비스 롤아웃 + soak 90s + 대화 스모크 PASS
- Environment: `라이브 배포본 (web-a 컨테이너 내부 8000 — 엣지 미경유)` — 채널 **10 PASS + 1 미경유**:
  마운트 실물 · 없으면 404 · 퍼블리시 후 바이트 동일성 · 공고 안 된 이름 404 ·
  같은 디렉토리의 다른 파일 404 · 제거 후 원복. **미경유 1칸** = 경로 탈출(`{filename}` 단일
  세그먼트라 라우트가 매칭조차 안 됨 — 내 가드를 타지 않았고 되돌려 FAIL 시킬 수도 없다)
- 방법과 그 대가: 정본(`1.1.0`)보다 **낮은 1.0.0** 합성 파일 → `updater.py` 경로는 안 집는다
  (`is_newer` 거짓). ⚠ 그러나 `download_url()` 은 **버전을 비교하지 않아** 사람용
  「연결 프로그램 받기」 버튼은 그 밖이었고, **라이브에 38초 창이 실재했다**(08:58:06→08:58:43.9).
  실피해 0(그 창의 외부 클라이언트 매니페스트 요청 0건) — 다음부터는 격리 인스턴스에서 잰다
- ⚠ 배포 중 관측 2건(둘 다 이 cycle 코드와 무관): 1차 ABORT = caddy **exec 채널** 파손(서빙은 200) ·
  배포 창 안 13초 엣지 정지 = **행위 종류 특정(기존 컨테이너 stop/start) · 행위자 미특정**
- ⛔ **미실측**: 엣지 경유 릴리스 200/다운로드 · web-b 채널 · 연결 화면 버튼 전환(체크리스트 [4]
  PB-0008 — **미이행**) · 설치기 실제 실행 · 실 설치기 종단 · §18.8 3라운드
- `Environment: Windows-browser` 없음 — 웹 자산 변경 0건. ⚠ 이것은 **check #13** 의 면제 논거이며
  배포 후 체크리스트 **[4] 의 면제가 아니다**(둘을 접었던 것을 정정)
- Verdict: PASS (미실측 6건 + 미경유 1칸 명시)


### Run 2026-09-08 — DQA 브랜드 아이콘

정본: [브랜드 아이콘 검증](test-runs.d/20260908T020049-brand-icon.md). Windows 재현 진입점은 `tests/windows/verify_brand_icon.py`이며, 사용자의 AI 질의·연결을 수행하지 않는다.


## 2026-09-08 — AI별 자동 연결

[통합 실행 기록](test-runs.d/20260908T123400-connect-discovery.md): Python·DOM·Windows-browser·실제 DQA/WebView2.
