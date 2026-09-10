---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260909-nondisruptive-update

DQA 1.3.0은 현재 앱과 AI 연결을 유지한 채 새 버전을 설치하고, 사용자가 정상 종료한 다음 실행부터 적용한다. 실행 중인 전체 앱·Python을 덮어쓰던 구조를 매번 새 versions 폴더에 설치하는 구조로 바꿨다. payload 실행 검사와 설치 완료 후에만 원자적으로 실행 대상을 교체한다.

고정 런처를 바로가기·자동시작·스킴이 공유한다. 기존 루트 실행 파일은 rename으로 보존하고 같은 이름에 호환 런처를 배치해 오래된 실행 경로도 유지한다. 새 구조의 이전 슬롯 실행도 활성 슬롯으로 전달한다. 설치 완료 후에는 현재 앱을 다시 열거나 종료하지 않는다. 실패는 현재 앱을 유지하고 알리며, 단순 installer spawn을 성공으로 기록하지 않는다.

기존1.2.x 자체 업데이터의 종료 코드는 소급 변경할 수 없다. 최초 전환도 중단 없이 하려면 새 설치기를 직접 실행한다. 그 뒤1.3.0 이상의 업데이트 메뉴는 작업을 유지한다. 창 닫기는 트레이 숨김이므로 새 버전 적용 시점이 아니다. 미서명 자동 적용 기본 off 유지. 실행 중일 수 있는 옛 슬롯을 삭제하지 않아 설치 횟수에 따라 디스크 사용량이 증가한다.

## 검증

- CLI: native 전체617 passed /1 skipped, focused112 passed. 릴리스노트 렌더34개 통과.
- 독립 리뷰2명: backend/security/QA, UX/design. 최대3회 범위에서 P1/P2 전부 수정 후 번들 PASS. 실제 Windows 수용 판정과 구분한다.
- Windows: 실제 설치한 DQA의 격리 홈/설치 경로, 제어된 페이지·자식 러너로 8개 설치 시나리오 및 실제 노트 렌더·이전 슬롯 실행 전환 통과. 실제 사용자의 앱/토큰/로그인 저장소는 변경하지 않았다.
- [최종 실측 원장](test-runs.d/20260909-nondisruptive-update.md)에 성공·실패·미검증 경계를 함께 기록한다.

## Git 동기화 결과

- worktree: `.worktrees/feature-0046-nondisruptive-update`; branch `ai/codex/feature-0046-nondisruptive-update`.
- 제품 commit `c039297d`, PR [#1663](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1663) 병합 `2c5d6c66`. pre/post verify PASS. GitHub Actions 실행 결과는 별도로 제공되지 않았다.
- 1.3.0 공개:26,138,425 bytes, SHA-256 `72f7281575daf58afdf011f2e4d56ac11dde8317d820be7b6156594a22ab24d3`. 실제 HTTPS/프로젝트CA 다운로드가 검증한빌드와일치. [채널 근거](artifacts/20260909-nondisruptive-update/channel.json).
- 웹 릴리스노트 배포: main제품 `2c5d6c66`, web-a/web-b ready 및90초soak PASS, asset_stamp `aaffca7a36d4` 일치. healthz200·실제서빙노트·KEK주입존재(값비공개) 확인. [배포로그](artifacts/20260909-nondisruptive-update/deploy-web.log).
- 배포 경고: compose의 임시metadata파일경합이 발생했으나 canonical배포기가 이미지/GIT_COMMIT 실물을 대조해 정상빌드를 확인하고계속했다. web-only이므로 대화스모크/워커교체는 수행하지 않았다.
- 검증용Windows 앱은전부종료됐음을조회했고 격리설치제거도exit0. 사용자원본설치/앱은변경하지않았다.
- 후속커밋은출하문서/증적/파일모드만변경하며 배포된제품코드·바이너리는동일하다.
- 정책 SHA-256: `a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2` (worktree 및 main 동일).
- 이전 기록: [report history](report-history/20260909-before-nondisruptive-update.md).

## TASK-20260910-transparent-icon-release

사용자 요청: 전진한 버전을 반영하여 투명 아이콘을 배포까지 완료한다. 이전 SVG 승인과 마상 브랜드 방향을 유지한다.

- main/공개 채널 1.3.0을 통합하여 1.3.1을 배포했다. 슬롯 설치와 실행 중 연결 유지, 텍스트 선택·검색 등 최신 기능을 보존한다.
- 안정 실행기·ICO 경로를 창 재실행 속성/바로가기/프로토콜/제거 표시에 사용하고 기존 실행기의 PE 아이콘도 무중단 교체한다.
- 정책 SHA-256: a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2. 위험도 Minor, 사용자 배포 명시 승인.
- 이전 아이콘 작업/잠금 화면으로 시각 검수 보류한 증적: [20260910-before-icon-release.md](report-history/20260910-before-icon-release.md). 1.1.3 후보는 게시하지 않는다.

## 2026-09-10 — 투명 아이콘 1.3.1 검증

Environment: DQA-client
Result: PASS
Scenario: 실제 Windows동결본/격리설치본의 아이콘·업데이트·실패보존·바로가기·제거. native624/웹30/노트34도PASS. 실제사용자계정/유료AI는검증대상이아니다. [정본](test-runs.d/20260910-transparent-icon-release.md). PR1617 병합 및 채널/웹 배포 결과는 아래 최종 출하 기록을 참조한다.

## 2026-09-10 — 1.3.1 최종 출하

PR1617 병합 main ebf5e365를 웹2replica에 배포하고 ready·90초 soak를 통과했다. Windows 설치기1.3.1을 공개했으며 public/localhost 양쪽 실제 다운로드의 TLS/bytes/SHA가 검증빌드와 일치한다. 기본 주소 실제 DQA 로그인 화면의 투명 심볼과 작업 표시줄을 확인하고 검증용 앱을 정상 종료했다. 사용자 원본 설치/앱은 변경하지 않았다.

배포 검수에서 발견한 Windows public80/443 리스너 누락은 feature-0006에서 수정했다. 사용자 UAC 승인 후 정본 운영 스크립트와 해당 리스너를 복구했으며 다른 포트·방화벽·서비스 재시작은 변경하지 않았다. [최종 원장](test-runs.d/20260910-transparent-icon-release.md). 웹/클라이언트 제품은 ebf5e365이고 이후 커밋은 운영 스크립트·검증·증적 정합이다. GitHub Actions와 유료 AI 대화는 별도 PASS를 주장하지 않는다.
