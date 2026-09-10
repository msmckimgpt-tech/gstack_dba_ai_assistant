---
doc_type: TEST_RUN
feature_id: feature-0046-native-client
status: active
---

# TASK-20260910-inapp-update — 출하

## Git·웹 배포

- 제품 commit `223f08ae`, PR [#1670](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1670), 병합 `c684d12a5072401a53517ae92fed8f682893d21e`. PR statusCheckRollup은 빈 배열이므로 원격 CI 결과는 없다. 구현·테스트 코드와 게시한 바이너리의 소스는 병합 main과 동일하다.
- `bin/deploy-web.sh --web-only` exit 0. web-a/web-b 대상 c684d12a ready, 90초 soak PASS, asset_stamp `4c750e490a9b` 일치. `/healthz` 200 및 git_commit c684d12a, MySQL/PG healthy. 실제 서빙 release-notes-data.js와 main bytes 일치.
- compose build가 metadata-file 경합으로 exit 1을 반환했지만 canonical 배포기는 생성된 mysql-ai-web:c684d12a 이미지의 GIT_COMMIT 정합을 확인했다. 이후 두 replica 교체·soak가 성공했다. 이 경고와 최종 배포 exit 0을 함께 기록한다.
- web-only이므로 ask-worker/MCP 컨테이너 교체·실제 제공자 대화 스모크는 미수행이다. 배포 상태만으로 전체 대화 동작을 보장하지 않는다.
- [배포 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/deploy-web.log), [병합 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/finalize-product.log).

## 공개 채널·다운로드

- Environment: Windows HTTP + Caddy HTTPS
- Result: PASS
- 공개 채널은 **1.4.0**. 최초 설치용 Setup과 앱 내부 갱신용 ZIP을 같은 게시 잠금에서 파일→매니페스트 순서로 반입했다. 시험용 1.4.1은 게시하지 않았다.
- Setup: 25,951,514 bytes, SHA-256 `41b5327596abbb7baac50bce028b9162d723d1aa680b1c123ea3ce89d8b1a199`.
- Update ZIP: 31,788,646 bytes, SHA-256 `6e2ab21268d4d6de3bcef7fff885193bf262befb48800c58994a739b8d9c8cee`.
- 서버 호스트에서는 프로젝트 CA와 원래 hostname 검증을 유지한 `curl --connect-to ...:127.0.0.1:443`으로 Caddy 엣지를 거쳐 두 파일을 다운로드해 지문을 대조했다. WSL의 공인 IP 직접 접속은 이 검사 경로가 아니다.
- 별도로 Windows에서 실제 updater 코드를 실행해 동봉 주소 `https://112.185.196.20`의 채널 발견→ZIP 다운로드→CA·크기·해시 검사를 통과했다. 이 과정은 실제 운영 주소로 직접 접속했으며 connect-to/fixture가 아니다. 사용자 설치본에 적용하지는 않았다.
- [채널](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/channel.json), [HTTPS 지문 대조](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/http-release-check.json), [Windows 운영 서버 다운로드](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-live-download.json).

## 1.3.1 최초 전환 추가 실측

- Environment: DQA-client
- Result: PASS
- Scenario: 공개 1.3.1과 같은 실제 동결 앱 payload를 별도 AppId/스킴/경로/홈으로 설치한 뒤, 기존 앱의 확인창을 통해 1.4.0 시험용 Setup을 실행. 페이지·러너는 제어된 fixture다. 최초 시험 설치는 격리용으로 재컴파일한 설치 외피이며 공개 Setup 실행과 구분한다.
- app PID 35760, runner PID 23056 유지, 진행값 1→326, 페이지 로드 1회·draft 유지. 활성 슬롯은 1.4.0-1로 전환됐다. 정상 종료 뒤 기존 루트 실행 경로가 1.4.0과 같은 브라우저 프로필 cookie로 복귀했다.
- 지속 포인터 잠금·동시 설치 mutex 실패 보존, 일시 잠금 재시도·같은 버전 새 슬롯 재설치도 PASS. 기존 클라이언트의 최초 전환 경로가 유지됨을 확인했으며 **이 경로는 Setup을 한 번 실행한다**.
- [전환 결과](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-transition.json), [실행 로그](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/windows-transition.log).
- 최종 ZIP 갱신 시험본과 최초 전환 시험본의 소유 프로세스 0개를 각각 확인한 후 제거 exit 0, 갱신 슬롯 포함 versions 폴더 제거 PASS. [ZIP 시험본 제거](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/cleanup-final.json), [전환 시험본 제거](/root/download/docker/mysql_ai_delegated_dev/artifacts/dqa-inapp-update-20260910/cleanup-transition.json).

## 완료 판정·경계

- 현재 요청의 구현·독립 리뷰·Windows 내부 갱신·구버전 최초 전환·공개 및 다운로드 검증 완료. 1.4.0→시험용 1.4.1의 설치기 없는 갱신 실측은 [구현 Run](20260910-inapp-update.md)을 따른다.
- 사용자 원본 로그인·토큰·진행 중 대화는 건드리지 않았다. 실제 사용자 AI 제공자 대화 검증은 미수행이다. 1.2.x 최초 전환의 재시작은 이전 코드의 동작이며 이번에 그 버전을 다시 실측한 것으로 기록하지 않는다.
- 후속 커밋은 이 출하 증적·상태 문서만 변경한다. 게시한 1.4.0 제품 코드·바이너리는 같다.
