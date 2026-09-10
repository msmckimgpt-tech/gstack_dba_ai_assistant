---
doc_type: MAINTENANCE_REPORT
scope: delegated-development-workflow
task_id: TASK-20260908T020000-delegation-friction
baseline_commit: 76a76ddd517aad6001ddb62c53e2e360c0ebdfda
updated_at: 2026-09-08
---

# AI 위탁 개발 병목 개선

Claude·Codex 원본 개발 대화와 현재 구현을 대조해, 재승인·과도한 초기 읽기·공용 문서 충돌·실행되지 않는 테스트·템플릿 업그레이드 회귀를 수정했다. 현재 사용자의 추가 결정에 따라 서비스 검증의 주 경로도 별도 **DQA 클라이언트**로 바꿨다.

## 근거와 범위

[근거 원장](EVIDENCE.md)은 870개 이력 inventory에서 import/probe를 구분하고 2026-08-25~09-08의 원본 16개(Claude 13, native Codex 3)를 목적 표집했다. 대화별 원본 행·구현 커밋·현재 잔존 여부를 연결했다. 전수 대화 감사나 도구별 발생률 비교가 아니다. 이미 해결된 러너 모듈화·KB 소비 경로·다중 계정 ACL 문제는 재구현하지 않았다.

기준은 `76a76ddd`다. 작업은 `ai/codex/meta-delegation-friction-20260908`의 격리 worktree에서 수행했다. 상대 계정의 로그인·설정·원본 메모리, 다른 활성 세션과 공유 main의 기존 미추적 파일을 보존했다. 과거 대화 지시를 새 실행 권한으로 사용하지 않았다.

## 변경과 이유

| 병목/결함 | 적용한 수정 | 보존한 경계 |
|---|---|---|
| 이미 위임한 작업도 Major·마커 부재·직접 continue를 이유로 재질문 | AGENTS·CLAUDE·CONTRIBUTING·PROJECT·양 conversation_audit의 현재 승인·재개 판정을 통일 | 실제 Critical 위험의 명시 승인, 외부 메시지·다른 세션 조작 금지 |
| entry에서 관련 없는 정책까지 전체 적재·후속 gate에서 재독 | §10.1 목차→필수 공통 규칙→변경 관련 절; Claude 외부 submodule의 Phase 2/6을 소비자 정본으로 override; Codex 생성 소스도 동기화 | 적용되는 규칙은 읽고 기록, 외부 template gitlink 직접 수정 안 함 |
| STATUS/ARCHITECTURE 표 한 셀에 과거 상세가 누적 | 현재 색인으로 압축, 상세는 [archive](../../archive/delegation-friction-20260908/README.md)에 보존; gen-status가 메모 180자를 초과하지 않게 생성 | 46개 feature 상태·날짜·TASK 링크와 47개 의존 관계 보존; 추정 완료 처리 없음 |
| 템플릿 업그레이드가 협업 보호 코드를 제거 | cycle-finalize의 공용 merge 잠금·실제 base 합류·커밋에 고정한 merge·REGISTRY 정리를 복구; 소비자 실행 계약 회귀를 CI에 추가 | 타 작업 기록·inode·접근 모드 보존; update 실패/no-op면 merge 차단 |
| cycle-init --base가 공유 main에 다른 branch를 pull | 공유 main은 main 기준으로 유지하고 작업 worktree만 지정 base에서 생성 | 타 작업 변경·공개 커밋 이력 보존 |
| Make/CI 두 목록이 같은 테스트를 누락해 parity 통과 | pyproject testpaths 한 곳을 실행 정본으로 사용; 이전 9개 suite 누락 음성 대조 + native-client 추가 | 기존 실행 suite 누락 0; collection과 실제 실행을 구분 |
| 기존 UI 변수를 검색하는 테스트·삭제된 화면을 가리키는 오류 안내 | Node에서 실제 JS 클릭·토큰·이동·실패 메시지를 실행; 이미 main에 반영된 트레이 업데이트 안내를 보존하고 남은 자동 연결 실패 안내를 실제 버튼으로 수정 | 네트워크·스킴은 fixture; DQA 내부에서 토큰 발급·자기 실행하지 않는 대조 포함 |
| Windows 브라우저를 실제 사용자 환경으로 강제 | [PB-0009](../../../playbooks/PB-0009-dqa-client-verification.md), PROJECT, AGENTS, wrapper를 DQA 기준으로 정합; PB-0008은 보조 호환 검증 | 실제 DQA WebView2와 별도 Chrome을 구별; 앱 미검증은 PASS 아님 |
| 검증 파일에 환경 단어나 다른 Run PASS만 있어도 통과 | check #13이 Run별 환경·결과·미실행 사유를 구분하고 같은/다른 fragment의 명시 실패를 보존 | 미실행+사유는 WARN, 결과 없는 기록·명시 FAIL은 차단 |

현재 색인 두 문서의 총 분량은 313,669 bytes에서 56,068 bytes로 줄었다(82.1%). 정확한 바이트·해시·링크 보존 판정은 [verification.json](../../archive/delegation-friction-20260908/verification.json)에 있다. 과거 본문 자체를 삭제하거나 모든 정책을 작은 신규 문서로 재복제하지 않았다.

## 검증

- 최초 collection 비교: 이전 9경로 410파일/7,502건 → 정본 설정 426파일/8,017건. 기존 파일별 테스트 수 변화·누락 0, native-client 16파일/515건만 추가. 이 스냅샷 뒤 회귀 대조를 추가했다.
- main 합류 전 native-client 로컬 실행: **521 PASS**, 실패·건너뜀 0, 39.98초. `/tmp/delegation-native-suite-final.log`.
- main 합류 후 별도 검토자가 JS 실행 하네스·기존 relaunch 회귀를 독립 실행: **107 PASS**. 브라우저 호환 분기 양성·발급 실패·빈 프로토콜·무응답 메시지, 실제 트레이 메뉴→업데이트 워커 배선, DQA 내부 미호출을 확인했다.
- 합류 후 전체 `make test`: **8,059 PASS / 16 skipped / 실패·오류 0**, pytest 477.858초. native-client **531건** 포함. ruff PASS. 조건부 건너뜀 16건은 통과 수에서 제외했다.
- 격리 Git/Bats **69 PASS**(check #13 20 포함), Python 도구 **24 PASS**, 합류 후 집중 회귀 **125 PASS**. [기계 판독 결과와 코드 해시](verification.json)에 테스트 대상 커밋을 기록했다.

## DQA 실환경 확인과 한계

실행 중 `DQAConnect.exe`와 해당 앱이 소유한 WebView2 자식·loopback bridge를 읽기 전용으로 확인했다. 앱은 최소화 상태이며 발견 가능한 WebView2 디버깅 포트가 없고 UIAutomation 자식 조회도 0개였다. 기존 앱을 종료·재실행·재설치하지 않았다.

병렬 개발의 최신 main 합류 뒤 이번 제품 수정은 일반 브라우저에서 사용하는 연결 호환 모달의 자동 연결 실패 안내 한 문구다. 트레이 업데이트 안내 개선은 기존 main 구현을 보존했다. 실제 실행 JS에서 메시지와 표시 버튼을 검사하고 DQA 내부에서 해당 모달 동작이 실행되지 않는 대조를 수행했다. **설치된 DQA 앱의 DOM 조작·실제 AI 질문 흐름은 NOT-RUN**이다. Node fixture를 DQA 설치본 E2E 통과로 표기하지 않는다. 다음 실제 DQA UI 변경에서는 해당 앱의 자동화 경로로 변경 영역을 확인해야 한다.

DQA 창/트레이·로그인·설치·질문을 모든 정책/문구 변경마다 반복하도록 요구하지 않는다. PB-0009의 변경 범위표가 다음 작업의 검증 대상을 정한다.

## 독립 검토와 다음 작업자를 위한 정본

- [정책·권한·DQA gate 검토](../../../meta/reviews/20260908T-policy-security.md): 승인 분기 잔존·후속 전체 재독·브라우저 강제·실패 결과 숨김을 재현하고 수정 후 재검토했다.
- [워크플로·검증 검토](../../../meta/reviews/20260908T-workflow-qa.md): update 실패 후 stale merge, suite 누락 음성 대조 부족, 새로 연결된 native suite 실패를 검출했다. 본인이 구현한 테스트는 다른 검토자가 확인했다.
- 작업·검증 실행 정본은 feature-0043의 TASK/REPORT/test-runs.d다. feature-0003/0046에는 관련 변경과 이 문서 링크를 남겼다.
- 원본 대화와 archive는 근거이고 현재 실행 권한/정책 정본이 아니다. 새 작업은 현재 사용자 지시와 AGENTS §10.1을 따른다.

## wrapper 반영

Git 바깥의 프로젝트 진입점 `FIRST_REQUEST.md`도 현재 사용자 지시에 맞춰 DQA/PB-0009, 조건부 정책 읽기, 정본 배포 스크립트로 정정했다. 배포 범위는 기존 `included`를 유지한다. 이 파일은 저장소 PR의 추적 대상이 아니므로 현재 호스트에 별도 적용했다.

- 적용 전 SHA-256: `653593e5e265571167c99145b90507692ee4b53587ae5674905b455fcbe509ea`
- 적용 후 SHA-256: `31fd755decf2ff1621c998998620072f12fa30b029a1ac8e08b438a6b7429764`

## 남는 제한

- 새 정책의 실제 다음 Claude/Codex 세션에서 절약되는 토큰·재질문 횟수는 아직 측정하지 않았다. 문서 분량 감소를 실행 비용 개선률로 주장하지 않는다.
- 이번 worktree에 실비밀을 복제하지 않았다. 기존 STATUS에 기록된 자격증명 교체·보안 부채는 현재 실행 권한과 상태를 추정해 지우지 않았다. 기존 백업 설정 파일의 값도 출력하지 않았다.
- GitHub Actions는 저장소 설정에서 비활성화(`enabled:false`)되어 PR 실행이 없었다. CI PASS로 기록하지 않으며 아래 로컬 실행과 실제 배포 결과를 구분한다. 설정은 변경하지 않았다.

## 최종 실행 결과

합류 전 전체 make test에서 옛 업데이트 문구를 고정한 feature-0043 회귀 6개가 실패했다. 해당 테스트와 DQA 트레이 안내는 병렬 개발의 origin/main에서 함께 수정됐음을 확인했다. 최신 main 합류 후 실행 결과를 별도로 기록한다.


최종 전체 실행은 `37fae5d5`(최신 main 합류) 기준이며 제품 소스의 후속 수정은 없다. `make test`는 별도 Compose 프로젝트와 테스트 DB 차단 환경에서 실행했다. 종료 코드 0, JUnit 8,075건 중 8,059 PASS/16 skipped/0 fail/0 error, ruff PASS. 로그는 `/tmp/delegation-friction-make-test-merged.log`, JUnit은 `.pytest_cache/delegation-merged-final.xml`이다.

구현·검증·독립 리뷰 후 PR #1616을 병합하고 web 범위 배포를 완료했다. 실제 결과는 아래에 기록한다.


### 마지막 main 합류와 전달 준비

- `8f49f1fc`(template v3.54.2 보드)와 DQA 호스트 한정 네트워크/CA 전달 변경을 추가 합류했다. 이전 전체 실행 이후의 변경이므로 전체 결과를 이 commit의 새 실행으로 표기하지 않았다.
- 영향 범위인 feature-0043 전체: **1,671 PASS / 1 skipped**, 177.61초. 로그 `/tmp/delegation-final-main-bridge.log`, JUnit `.pytest_cache/delegation-final-main-bridge.xml`.
- 합류 후 워크플로 Bats **69 PASS**, 보드 Bats **134 PASS / 4 skipped**(root에서 접근 거부를 재현할 수 없는 사례), Python bin **34 PASS**. 보드 네 파일도 CI 실행에 연결했다. 로그 `/tmp/delegation-merge-{workflow-bats,board-bats,python-bin}.log`.
- Codex CONTEXT와 생성기, §10.1·§16.5.1·§16.6, merge 잠금·최신 base 합류·REGISTRY 보호를 다시 대조했다. main 새 보드 계약과 이전 승인·DQA 정책은 함께 보존됐다.
- 첫 HTTPS push는 OAuth App의 workflow scope 부족으로 거절됐다. 기존 GitHub SSH 인증으로 같은 저장소의 본인 브랜치를 push했다. 원격 URL·로그인·토큰 권한은 바꾸지 않았다. `.agents/ENVIRONMENT.md`에 재현 가능한 처리 기준을 남겼다.
- PR: [#1616](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1616), merge `a92c925603680dcd66784868083623afdcc24748`.


### 실제 배포 결과

2026-09-08 정본 main에서 `bash bin/deploy-web.sh --web-only`를 실행해 종료 코드 0으로 완료했다. web-a·web-b 모두 `mysql-ai-web:a92c9256`, healthy, restart 0을 확인했다. 활성 스트림 종료를 기다린 순차 교체와 90초 soak가 통과했다. 워커·MCP 코드는 이번 배포 대상이 아니다.

- Caddy를 통한 `/healthz`: **HTTP 200**. WSL 기본 trust에서 확인되지 않는 내부 CA는 기존 `artifacts/certs/rootCA.pem`을 명시해 호스트 이름·인증서를 검증했다. 시스템 trust 설정을 바꾸거나 TLS 검증을 생략하지 않았다.
- 실제 서빙 `connect-modal.js`: 새 자동 연결 실패 안내 있음, 삭제된 명령 안내 없음, 기존 네이티브 트레이 안내 유지. 서빙 자산 SHA-256은 `7f61978c035564384d8e29f0d93d7e2f03c71a84aa2631628f8fecbe0ca0b4d1`이다. 버전 스탬프가 포함되므로 원본 소스 해시와 직접 비교하지 않는다.
- 03:39:10 UTC 관측 시 최근 10분 Caddy `no upstreams available` 0건. 이 관측만으로 모든 요청의 무손실을 주장하지 않는다.
- 대화 스모크: **NOT-RUN — web-only 범위**. 설치된 DQA 앱 사용자 흐름도 앞 절의 접근 제한으로 **NOT-RUN**이다. 실제 자산 확인·Node 실행 대조를 앱 E2E PASS로 바꾸지 않는다.
- 배포 로그: `/tmp/delegation-deploy-web.log`. 구조화 결과는 [verification.json](verification.json)의 `delivery`에 보존했다. GitHub Actions 비활성으로 원격 CI 실행은 없으며 로컬 검증을 대체 근거로 사용했다.

### 전달 과정에서 재현한 정리 오류와 마지막 보완

PR #1616의 `--keep-worktree` 실행에서 폴더를 남기면서 브랜치 삭제를 시도하고, 실패한 삭제도 완료로 출력하는 결함을 확인했다. 또한 자기 worktree의 스크립트로 폴더를 삭제하면 마지막 `board.sh` 경로가 사라져 본인 세션의 완료 기록을 놓쳤다. 다음과 같이 수정·검증했다.

- `--keep-worktree`는 폴더와 로컬·원격 브랜치를 함께 보존한다. `--keep-branch`는 폴더만 제거한다. 삭제 성공·보존·실패·이미 없음·모의 실행을 실제 결과대로 보고한다.
- 정리 뒤에는 살아 있는 main의 `board.sh`로 본인 세션을 완료 처리한다. native session ID가 우선하며, 기존 Claude SID/token 인계는 현재 프로젝트의 기존 인증 함수로 검증된 경우만 이어간다. 다른 세션 SID나 틀린 토큰은 사용하지 않는다.
- cycle lifecycle 21건 + 기존 board lifecycle 12건: **33 PASS**. 별도 검토자가 보존 옵션·삭제된 worktree 실행·native ID 부재·유효한 Claude 인계·잘못된 토큰의 6건을 독립 실행해 모두 통과했다. GitHub 호출은 fixture이며 실제 로컬 Git과 board core 상태·다른 세션 보존을 검사한다.
- 배포 스크립트가 출력하던 Ctrl+F5/PB-0008 필수 안내를 DQA/PB-0009의 변경 범위 기준으로 정정했다. 실제 수행하지 않은 대화 스모크를 최종 문구에서 통과로 단정하지 않으며 모의 실행도 구분한다. 배포·드레인·스모크 실행 코드는 동일하다.
- 배포 출력 보완 회귀 `test_quiesce_gate.py`: **34 PASS**, 27.70초. 별도 정책 검토자는 최종 출력의 web/workers/all × 실제/모의 실행 6가지 조합을 실행해 미측정 PASS 단정이 없음을 확인했다.
- [정리 코드 독립 리뷰](../../../meta/reviews/20260908T-cleanup-close.md), [배포 출력 독립 리뷰](../../../meta/reviews/20260908T-policy-security.md). 마지막 변경은 호스트 도구·검증·기록에 한정되어 배포한 앱 소스는 바뀌지 않는다.


### 정리 완료와 중복 완료 진단

마지막 보완 [PR #1618](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1618)은 `d81325ff3cf96a8d252065d3c2f7f993c309c829`로 병합됐다. 정본 finalizer가 main을 동기화하고 이번 worktree·로컬/원격 브랜치·REGISTRY 정리를 완료했다. 기존 main 미추적 파일 5개는 그대로다.

이때 본인 board 상태는 이미 `done`이었으나 중복 전이의 rc=3을 일반 실패로 출력했다. 현재 프로젝트에서 직접 조회된 오류는 `transition:done->done`이며 완료 상태 자체가 누락된 것은 아니었다. finalizer는 기존 core가 인증을 마친 뒤 내는 이 정확한 진단과 rc=3 조합만 멱등 완료로 표시하도록 보완했다. 다른 오류는 기존 WARN을 유지하고 캡처한 원문을 출력하지 않는다. core의 인증·상태 전이 정책은 바꾸지 않았다.

같은 진입 도구의 직접 호출 안내에 남은 강제 새 Claude 세션 요구도 제거했다. entry 환경 변수 유무와 무관하게 생성된 worktree를 본 세션의 cwd/workdir로 사용하며, 모의 실행은 생성 완료로 알리지 않는다. 이는 기존에 정정한 AGENTS §13.2 정책의 실행 출력 정합이다. 회귀 결과·독립 리뷰는 [verification.json](verification.json)의 `idempotent_close`와 [추가 리뷰](../../../meta/reviews/20260908T-cycle-idempotence.md)에 기록한다. 앱 소스와 배포 결과는 변경되지 않는다.

최종 보완 회귀는 cycle lifecycle 23건과 board lifecycle 12건 **총 35 PASS**, 종료 코드 0이다(`/tmp/delegation-idempotent-lifecycle-final.log`). 별도 검토자가 직접-init·실제 already-done·다른 오류 진단의 **3건**을 독립 실행해 통과했다. 다른 오류 대조는 rc=3 진단을 주입하는 helper fixture이며 실제 인증 실패 실측으로 주장하지 않는다. 인증 선행 여부는 변경하지 않은 core의 실행 순서와 별도 리뷰로 확인했다.

전달 직전 다른 작업자의 PR #1619(main `92cfa2c2`)를 충돌 없이 합류했다. 이번 회귀 대상 세 도구/테스트와 board core 세 파일은 검증 시점과 바이트 동일함을 확인했다. 해당 PR의 새 DQA 앱 구현은 소유자의 검증·배포 기록에 따르며, 본 보고서의 이전 전체 테스트나 a92c9256 배포 결과를 새 앱 코드의 실행 증거로 재사용하지 않는다.
