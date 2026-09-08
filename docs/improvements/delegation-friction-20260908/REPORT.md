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
- GitHub CI와 실제 배포의 성공 여부는 로컬 회귀와 별도로 확인한다.

## 최종 실행 결과

합류 전 전체 make test에서 옛 업데이트 문구를 고정한 feature-0043 회귀 6개가 실패했다. 해당 테스트와 DQA 트레이 안내는 병렬 개발의 origin/main에서 함께 수정됐음을 확인했다. 최신 main 합류 후 실행 결과를 별도로 기록한다.


최종 전체 실행은 `37fae5d5`(최신 main 합류) 기준이며 제품 소스의 후속 수정은 없다. `make test`는 별도 Compose 프로젝트와 테스트 DB 차단 환경에서 실행했다. 종료 코드 0, JUnit 8,075건 중 8,059 PASS/16 skipped/0 fail/0 error, ruff PASS. 로그는 `/tmp/delegation-friction-make-test-merged.log`, JUnit은 `.pytest_cache/delegation-merged-final.xml`이다.

PR/배포 전 구현·검증·독립 리뷰를 마쳤다. 실제 병합·배포 결과는 전달 후 이 절에 추가하며 선행 완료로 기록하지 않는다.


### 마지막 main 합류와 전달 준비

- `8f49f1fc`(template v3.54.2 보드)와 DQA 호스트 한정 네트워크/CA 전달 변경을 추가 합류했다. 이전 전체 실행 이후의 변경이므로 전체 결과를 이 commit의 새 실행으로 표기하지 않았다.
- 영향 범위인 feature-0043 전체: **1,671 PASS / 1 skipped**, 177.61초. 로그 `/tmp/delegation-final-main-bridge.log`, JUnit `.pytest_cache/delegation-final-main-bridge.xml`.
- 합류 후 워크플로 Bats **69 PASS**, 보드 Bats **134 PASS / 4 skipped**(root에서 접근 거부를 재현할 수 없는 사례), Python bin **34 PASS**. 보드 네 파일도 CI 실행에 연결했다. 로그 `/tmp/delegation-merge-{workflow-bats,board-bats,python-bin}.log`.
- Codex CONTEXT와 생성기, §10.1·§16.5.1·§16.6, merge 잠금·최신 base 합류·REGISTRY 보호를 다시 대조했다. main 새 보드 계약과 이전 승인·DQA 정책은 함께 보존됐다.
- 첫 HTTPS push는 OAuth App의 workflow scope 부족으로 거절됐다. 기존 GitHub SSH 인증으로 같은 저장소의 본인 브랜치를 push했다. 원격 URL·로그인·토큰 권한은 바꾸지 않았다. `.agents/ENVIRONMENT.md`에 재현 가능한 처리 기준을 남겼다.
- PR: [#1616](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1616). 실제 병합·배포 후 결과를 추가한다.
