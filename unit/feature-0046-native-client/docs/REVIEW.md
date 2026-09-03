---
doc_type: REVIEW
feature_id: feature-xxxx-template
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-YYYYMMDD-0001
- Related Change:
- Reason:
- Alternatives Considered:
- Risks:
- Open Questions:
- Human Approval Needed:

## REV-20260903T140000-ai-claude-native-client-initial [SKIPPED:live-measured-new-component] — ACCEPTED
- Related TASK: TASK-20260903T140000 (ROADMAP ITEM-08)
- Timestamp: 2026-09-03T14:00:00+09:00
- **[SKIPPED] 사유**: 세션 상위지시로 AgentTool(subagent panel) 금지 → §18.8.2-1 제약 없는 채널로 검증했다. 이 컴포넌트의 고유 위험은 **「실제 Windows 에서 되는가」** 이고 그것은 정적 리뷰가 아니라 **실 머신 실행**으로만 답해진다 — 그래서 검증 예산을 그쪽에 썼다.
- **실 Windows 실측 (WSL interop `/mnt/c` + powershell.exe)**:
  - AI 감지 — `claude` 를 `C:\Users\…\.local\bin\claude.exe` 에서 찾았다. **PATH 밖 표준 위치**이고, 이것이 정확히 `shutil.which` 만으로는 못 찾던 실측 사례(REQ-20260901-win-ai-detect)다. 로컬 리눅스 테스트로는 이 경로가 검증되지 않는다.
  - 로그인 상태 — `claude auth status` JSON 파싱으로 `loggedIn=true` + 계정 표시. codex·gemini 미설치를 정확히 보고.
  - GUI — tkinter 위젯 구성 성공, 한글 타이틀 정상.
  - 빌드 — PyInstaller `--onefile --windowed` → 9,174,548 bytes 단일 exe.
- **⚠ 실측이 결함 1건을 적발했다 (로컬에서는 보이지 않는 종류)**: `--windowed` 빌드는 `sys.stdout` 이 `None` 이라 `print()` 가 예외를 내고, 창 없는 앱의 미처리 예외는 **사용자 입력을 기다리는 대화상자**가 되어 프로세스가 멈춘다. 실제로 5분 타임아웃까지 걸려 강제 종료했다. → `tell()`(messagebox)로 교체하고 **재빌드·재실행으로 해소 확인**. 회귀 잠금 2건 추가(`gui.main` 에 `print` 금지 · `tell` 은 콘솔·디스플레이 없이도 안 죽음).
- **스택을 SPIKE-02 권고에서 바꿨다** — SPIKE 는 Tauri 를 **추정**으로 권고했으나 실측이 전제를 뒤집었다: Rust 없음 / Windows 파이썬 3.14 실재 / tkinter 8.6 동작 / 러너 서드파티 0. 러너가 이미 파이썬이므로 tkinter 면 **sidecar 가 불요**하다. 추정을 실측이 이긴 사례이며, SPIKE 가 그것을 「추정」으로 표기해 둔 것이 이 전환을 가능하게 했다.
- **경계 검사를 「안 한다」로 걸었다** — `test_client_never_touches_vendor_credentials` 가 `.credentials.json`·`auth.json`·`keychain`·`*_token` 등을 금지어로 검사한다. 2026년에 Google 이 이 선을 넘은 도구의 **유료 구독자 계정을 정지**했으므로, 이 테스트가 지키는 것은 코드 품질이 아니라 **사용자 계정**이다.
- **커버리지 과장 금지** — gemini 는 SPIKE-02 에서 로그인 명령을 실측하지 못했다. 지어내지 않고 「이 프로그램에서 대신 실행할 수 없습니다」로 강등하며, 테스트가 그 문구를 잠근다(P0-I 계약).
- 단위 20/20 PASS. **미수행**: 실 서버 연결 왕복(유효 토큰 필요) · gemini 경로 · 서명 없는 설치의 사용자 체감.
- Human Approval Needed: 아니오 — 사용자가 2026-09-03 에 Windows 우선·미서명 진행을 명시 결정했다.
