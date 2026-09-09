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

## TASK-20260909T120000-client-125-share-entry — DQA Connect 1.2.5 출하

어제 머지한 「공유 링크에서 앱으로 들어가면 **그 대화**가 열린다」는 서버·정적 자산까지
배포됐지만 사용자에게 도달하지 않은 상태였다. 그 절반이 **설치본 코드**인데, 채널 최신
1.2.4 는 그 머지(2026-09-08 20:07 KST)보다 **4시간 34분 앞선** 15:33 KST 게시본이었다.
지금 공유 화면에서 [DQA 앱에서 참여 · fork] 를 누르면 앱은 뜨지만 서비스 루트를 연다 —
파손이 아니라 의도된 degrade 이고, 이 릴리스가 그것을 걷어낸다.

**1.2.5 를 빌드·게시했다.** `DQAConnect-Setup-1.2.5.exe` · 26,051,359 bytes · sha256
`909d246b8a2b19a8e395905377d5bc1c07a0bf02f012aae79b97fd3ed5d905d7`. 라이브 채널이 그 값을
광고하고 `GET /client/…-1.2.5.exe` 로 받은 바이트의 sha256 이 **일치**한다. 이전 1.2.4 는
404 로 도달 불가가 되는데 이는 설계다(광고 중인 파일만 서빙 — 철회가 곧 도달 불가).

**「소스에 있다」와 「나갈 파일에 있다」를 구분해 확인했다.** 대상은 설치기가 담는 앱 폴더의
`dist/DQAConnect/DQAConnect.exe` 다. 그 PYZ 는 모듈별 zlib 압축이라 평문 검색은 0건이고
(그것만 보면 「없다」로 오판한다), 압축 스트림을 복원해 `show.path` 1건 · `safe_app_path`
2건(`client/core` · `client/gui`)을 확인했다 —
[scan_frozen.py](artifacts/20260909-client-125/scan_frozen.py) 로 재현한다.
⚠ **받은 설치기 자체는 뜯어 보지 않았다**: Inno 산출물은 LZMA2 라 같은 스캐너로 0건이다.
앱 폴더 → 설치기의 연결은 빌드 로그의 사실이지 측정이 아니다(적대 리뷰 MED-2).
⚠ 「복원한 스트림 개수」는 경계 추정 휴리스틱에 딸린 값이라 재현마다 다르다(다른 휴리스틱으로
621) — 판정에 쓰는 것은 개수가 아니라 **매치가 든 스트림이 있는가** 다.

**출하 동결본으로 실측했다** — 격리 `%USERPROFILE%` + 목적지만 기록하는 로컬 프로브 서버.
① 꺼진 상태 실행 → `GET /c/DEST-ONE`, ② 상주 중 실행 → `GET /c/DEST-TWO` **같은 포트·같은
nonce**(새 창이 아니라 떠 있던 창이 옮겨졌다는 증거), ③ 질의 밀반입
(`?client_port=1&client_nonce=STOLEN…`) → `GET /` + **앱 자기 좌표**(밀반입 값이 한 글자도
남지 않았다), protocol-relative·`..` 도 각각 루트, ④ 양성 대조 `/c/CONTROL-OK` 는 수용.
④ 가 없으면 ③ 의 「요청 없음」이 「앱이 안 떴다」와 구분되지 않는다.

**변경은 「상수 1줄」이 아니었다.** `test_iss_version_matches_the_canon` 이
`DQAConnect.iss` 의 `#define AppVersion` 폴백이 1.2.4 에 머문 것을 잡았다. 빌드는
`/DAppVersion=` 로 정본을 주입하므로 이번 산출물은 옳았지만, 폴백이 갈리면 손으로 ISCC 를
부른 설치기가 파일명과 프로그램 버전을 서로 다르게 갖는다.

**미검증 (넘겨 읽지 말 것):** ① **설치본** 실행 — 잰 것은 설치기가 담는 그 폴더를 그대로
띄운 격리 동결본이다. ② **OS 스킴 핸들러 발사** — 등록은 읽기로 확인했으나
(`HKCU\Software\Classes\dqa-connect\shell\open\command` = 설치본 + `"%1"`) 그 명령이 지금
가리키는 것은 사용자의 1.2.4 다. ③ **브라우저 공유 화면 버튼**부터의 종단 경로.
서명 없는 설치기라 무음 적용은 기본 꺼짐(사용자 결정 2026-09-07)이므로 사용자가
[업데이트 확인] 에서 수락한 뒤에 ①②③ 을 잰다. **사용자의 실행 중 앱(PID 29732)은
종료·재설치하지 않았다**(PB-0009 실행 3항) — 이 세션이 만든 격리 홈·프로브 서버·로컬
사본만 정리했다.

검증: 네이티브 전체 **590 passed / 1 skipped / 0 failed**.
`test_bridge_security.py::test_read_only_actions_stay_quiet` 는 전체 부하에서 간헐 적색,
단독 초록(worktree·main 동일) — 선재 flake.
[실측 원장](test-runs.d/TASK-20260909T120000-client-125-share-entry.md) ·
[빌드](artifacts/20260909-client-125/build.json) ·
[게시](artifacts/20260909-client-125/published.json) ·
[프로브 로그](artifacts/20260909-client-125/probe.log).

**릴리스노트를 함께 냈다** (적대 리뷰 MED-1). 종전 클라이언트 버전은 모두 항목이 있는데
1.2.5 만 없었고, 9월 8일 노트는 이미 「앱을 거칩니다」라고 알린 상태였다 — 그 노트가 같은
자리에 「새 앱 버전을 받으신 뒤에만 성립합니다」라고 적어 둔 그 버전이 이것이다. 그 문장을
닫는 항목을 2026-09-09 블록에 넣고 요약에도 한 줄 더했다. 서버 코드는 그대로지만 **정적 자산이
바뀌므로 웹 재배포가 필요하다** — 앞선 판에서 「웹 재배포 불필요」라고 적었던 것을 정정한다.

**적대 검증 3인이 결함 18건을 잡았고 전부 조치했다** — security CONCERN · backend CONCERN ·
qa BLOCK. 가장 값비싼 것들은 「버전 상수 1줄」이라는 내 전제를 깬 것이었다:

- **게시 도구의 기본 릴리스 디렉토리가 연결된 worktree 에서도 라이브 채널을 가리켰다**
  (`parents[5]` 셈 + `.worktrees/artifacts` 심볼릭 링크). 아무 실험용 worktree 에서
  `--setup` 한 번이면 서명 없는 바이너리가 전 사용자에게 나간다. `docker-compose.yml` 앵커로
  바꾸고, 연결 worktree 면 추측하지 않고 `--dir` 을 요구한다.
- **롤백(`--activate`)이 `publish()` 의 검사를 하나도 걸지 않았다.** `1.1.0-hotfix` 같은 값이면
  채널 전체가 404 가 되고 클라이언트는 그것을 「아직 배포 없음」이라는 정상 상태로 읽는다 —
  급할 때 쓰는 길에서 가장 비싼 실패다.
- **죽은 단정 3건.** 두 건은 항진명제(`or` 뒤 느슨한 절 · 「그렇게 쓰지 말라」는 경고 주석이
  만족시키던 문자열), 한 건은 봉인 부재(`FUNCTION.md` 의 「현재 공개 채널은 1.2.4이다」가
  라이브와 어긋난 채 남았다). 셋 다 고치고 **뮤턴트로 봉인을 확인**했다.
- **§16.6 위반.** 목적지 6칸을 내가 조립한 `--path` 로만 쟀는데, 상류가 실제로 만드는 스킴
  URL 은 `parse_scheme_url` 을 한 번 더 지난다 — 그 분기가 1R-F3 의 토큰 배제 방어이고,
  **가장 최근에 넣은 방어가 실행으로 확인되지 않은 유일한 것**이었다. 정본
  조립기(`dqa_identity.app_open_url`)가 만든 링크를 OS 스킴 핸들러와 같은 argv 한 칸으로
  던져 라이브에서 다시 쟀다(⑤), 상주 중 부적격도 함께(⑥).
- **PB-0009 라벨을 나눴다.** 격리 동결본 실측을 `Environment: DQA-client` 로 적으면 기계는
  「설치본 실측」으로 읽는다. `DQA-client-isolated` 로 분리하고 설치본 종단은 Run 6 `NOT-RUN`.

이연(근거는 [리뷰 artifact](reviews/20260909T142000-client-125-share-entry.md)): 빈
`ca_sha256` 일 때 사설 CA 를 평문 HTTP 로 무검증 설치하는 **선재** 결함, 매니페스트/실물
불일치의 진단 표면이 0 인 것 — 둘 다 이 diff 밖이고 동선을 바꾸므로 별도 cycle 로 남긴다.

검증(조치 후): 네이티브 **595 passed / 1 skipped / 0 failed**(신규 봉인 5건 포함) ·
공유 화면 jsdom **108 passed** · 릴리스노트 jsdom **34 passed**.
⚠ feature-0003 의 pytest 는 worktree 에서 `app` 임포트가 되지 않아 돌리지 못했다 — 이번
변경은 그쪽 정적 자산 1개뿐이고 CI 가 컨테이너에서 돌린다.

위험도 **Minor** (§12.3) — 버전 정본 2곳 + 릴리스노트 데이터 + 게시 도구 방호벽 + 테스트
봉인. 제품 로직·권한·스키마 변경 0. `deploy_scope: included` 범위(§16.5.1).
