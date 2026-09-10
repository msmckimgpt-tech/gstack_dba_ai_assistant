---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# TASK-20260910-inapp-update

## 회귀·리뷰

- Environment: CLI
- Result: PASS
- 최신 main ebf5e365(1.3.1 아이콘·설치기 수정) 통합 후 native 전체 650 passed / 1 skipped. jsdom 경로 미지정으로 빠진 DOM 검사를 `DQA_JSDOM=/tmp/node_modules/jsdom/lib/api.js`로 재실행해 PASS: 총 651개 검증. 경고 1건은 중복 ZIP 멤버를 거절하는 테스트의 의도적 입력이다.
- 릴리스노트 DOM 34 PASS, 변경 Python 파일 ruff PASS, ROUTEMAP 재생성·codenav PASS.
- 집중 검증은 ZIP 경로 이탈·Windows 예약명·링크·확장 크기·검증 실행 실패·포인터 실패·동시 적용·다운그레이드 거절·HTTP 리디렉션 거절, 게시 경쟁·파일 변조·롤백/prune·채널 철회를 포함한다.
- 독립 backend/security/QA 3회, UX/design 2회 리뷰 후 P1/P2 0. 실제 Windows 실행과 리뷰 판정을 구분한다. 정본은 REVIEW의 두 inapp-update artifact다.
- [native 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/native.log), [DOM 보완](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/dom.log), [노트](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/notes.log).

## Windows 앱 내부 갱신

- Environment: DQA-client
- Result: PASS
- Scenario: 별도 AppId·스킴·설치 경로·홈의 실제 1.4.0 동결 설치본 → 시험용 1.4.1 ZIP, 실제 WebView2 및 제어된 HTTPS 페이지·러너. 1.4.1은 검증 전용으로 공개하지 않는다.
- 최종 run4에서 app PID 22772, runner PID 21216을 유지했고 진행값 1→367, 페이지 로드 1회, 작성 중 draft 보존을 확인했다. 새 슬롯은 1.4.1-1. 업데이트 HTTP 요청은 모두 ZIP이며 설치기 다운로드가 없었다.
- 실제 확인창 수락→패키지 준비 완료 후 앱은 계속 실행됐다. 트레이 정상 종료 뒤 기존 루트 EXE로 실행하면 1.4.1과 같은 프로필의 fixture cookie로 복귀했다.
- 설치기와 같은 Global mutex 경합, 다운로드 SHA 불일치, active-slot 공유 잠금 각각 실패 표시·기존 포인터/앱/러너 보존. 잠긴 포인터 때문에 만들어진 미공개 슬롯은 정리됐다.
- 실제 릴리스노트 renderer/data를 설치본 WebView2에서 실행해 1.4.0 내부 갱신·다음 실행 안내, 구버전 최초 전환 예외와 1.2.x 재시작 주의 문구를 확인했다.
- 최종 검증용 앱/러너가 모두 종료됐음을 조회한 뒤 제거기를 실행했다. exit 0, 앱 내부 갱신으로 생긴 versions 폴더까지 제거됨을 확인했다. [제거 결과](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/cleanup-final.json).
- 검사 이력: run1 갱신 PASS. run2는 시험 페이지의 UTF-8 선언 누락으로 한글 노트 확인 FAIL. 시험 페이지에 UTF-8 meta/HTTP charset을 명시한 run3 PASS. 이후 main 아이콘 변경 통합·전체 재빌드 후 최종 run4 PASS. 제품 문제를 숨기기 위한 assertion 완화는 하지 않았다.
- [최종 결과](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-final.json), [실행 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-final.log). 재현 진입점: `tests/windows/verify_inapp_update.py`, Windows README.

## 빌드·공개 경계

- 실제 Windows Python 3.14 / PyInstaller / Inno Setup 빌드 exit 0. 게시 후보 Setup 25,951,514 bytes / SHA-256 `41b5327596abbb7baac50bce028b9162d723d1aa680b1c123ea3ce89d8b1a199`; Update ZIP 31,788,646 bytes / SHA-256 `6e2ab21268d4d6de3bcef7fff885193bf262befb48800c58994a739b8d9c8cee`.
- [빌드 지문](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/build-files.json), [빌드 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-build.log).
- 이 기록 시점에는 공개 채널 1.3.1이다. 병합·웹 배포·1.4.0 채널 게시·실제 다운로드 지문 확인은 후속 출하 Run에 기록한다.

## 검증 한계

- 실제 설치된 DQA·WebView2를 사용했지만 페이지/러너는 fixture다. 사용자 원본 앱·로그인·토큰이나 실제 AI 제공자 대화를 검증한 결과로 확대하지 않는다.
- 1.3.x 이하에는 ZIP 갱신 코드가 없으므로 1.4.0 최초 전환은 기존 앱 내 설치기가 한 번 필요하다. 1.2.x의 재시작 동작도 소급 변경할 수 없다.
- 활성 포인터 변경 후 크래시가 나더라도 다음 실행은 새 버전을 선택한다. 실행 중일 수 있는 이전 슬롯을 자동 제거하지 않아 디스크 사용량이 증가할 수 있다. 명시적 앱 제거 시 versions 전체 정리를 검증한다.
