---
run_at: 2026-09-08T12:45:00+09:00
session: /_template:entry attach-folder-tree
scope: feature-0003 (첨부 업로드·목록·프론트) + feature-0002 (LLM 컨텍스트·read_attachment) + shared
verdict: PASS (자동) / PENDING (앱 시각검증 — 배포 후)
---

# TASK-20260908T124500-attach-folder-tree — 폴더 첨부 · 디렉토리 트리 보존

## 자동 테스트

- Environment: pytest (컨테이너 `make test` 정본 + 로컬 대조)
- **컨테이너 `make test` (정본 하네스): exit 0** — pytest rc 를 그대로 반환하는 경로
  (`Makefile:test` 의 `rc=$?` → `exit $rc`)이므로 exit 0 = 전건 통과. `ruff` 도 `All checks passed!`.
  실행: worktree 마운트(`-v <worktree>:/work`), 전용 compose 프로젝트 `repo-unittest`, 라이브 DB 차단 env.
- 신규 **52건** 전건 PASS:
  - `unit/feature-0002-agent-core/tests/test_attach_folder_tree.py` (35)
    — 경로 정규화 12 · 트리 렌더 3 · 프롬프트 주입 6 · 부트스트랩 배선 3 ·
      패널 적발분 회귀 8 · `read_attachment` 경로 해소 4(리뷰가 **뮤테이션 생존**으로
      입증한 미커버 구간 — 프롬프트가 모델에게 약속한 계약에 테스트가 0이었다)
  - `unit/feature-0003-agent-web-ui/tests/test_attach_folder_upload.py` (17)
    — 체인 스코프 3 · API 직렬화 2 · 업로드 배선 4 · PG 미러 계약 1 ·
      backend 적발분 회귀 7(backfill 4번째 면 · read degrade · 승계 2곳 · 계보 스코프 ·
      일괄 다운로드 폴더 보존 · 개수 캡 live-head · 프론트 병합 3곳)
- 회귀: 컨테이너 정본에서 실패 0. 별도로 **로컬 pytest 대조**도 수행 — main 19건 = worktree 19건으로
  **차집합 0**(로컬 실패는 환경 한계: `web` 패키지 경로 부재·MSSQL 라이브 접속 시도로, 컨테이너에서는
  나지 않고 main 에서도 동일하게 난다). 두 축 모두 회귀 0.
- 기존 테스트 1건(`test_attachment_versioning.py::test_m1_materialize_branches_from_user_chain`)이
  INSERT 바인딩 **위치 하드코딩**(`ins[10]`) 때문에 컬럼 추가로 깨졌고, 위치가 아니라
  **내용으로 MetaJson 을 찾도록**(`_meta_json_param`) 고쳐 같은 취약성을 제거했다.

## 검증 대상 계약 (요청 → 무엇을 확인했나)

| 요청 항목 | 확인한 것 |
|---|---|
| 폴더 전달 | 폴더 input(`webkitdirectory`) + 드롭 재귀 순회(`webkitGetAsEntry`) 두 경로가 코드에 배선됨 |
| 디렉토리 트리 보존 | `relative_path` 가 정규화되어 저장·직렬화·PG 미러 3면·fork·assistant 편집본까지 승계 |
| assistant 인지 | 파일 라인 `path="..."` + `DIRECTORY STRUCTURE` 트리 블록이 실제 중첩 구조로 렌더 (테스트가 트리 문자열 전체를 고정) |
| (파생) 동명 파일 | 다른 폴더의 같은 이름이 서로를 supersede 하지 않음 — 체인 SQL·params 를 포획해 검증 |
| (파생) 경로 안전성 | traversal·절대경로·드라이브 접두·제어문자·깊이 초과 차단 |
| (파생) 무회귀 | 폴더 첨부 없으면 트리 블록 미렌더 · 마이그레이션 전 짧은 row 에서 IndexError 없이 폴백 |

## 시각검증 — 실제 Windows 브라우저 (PB-0008 · §16.6)

- **Environment: Windows-browser** — 실 Windows Chrome 152.0.7977.75, CDP relay(`bin/win-browser.py`).
- 대상: **격리 컨테이너** `https://172.26.154.233:18099` — 라이브 web 이미지(`mysql-ai-web:92cfa2c2`)에
  본 branch 의 `src`·`shared` 를 마운트, 라이브 MySQL/MinIO 공유, `ATTACHMENTS_READ_BACKEND=mysql`
  + `DUAL_WRITE=0` 으로 PG 스키마 무접촉. 라이브 web-a/b 는 건드리지 않았다.
- 세션: `session-login`(bootstrap_admin) — 제품 로그인 폼 경로 그대로.

### 실측 결과

| 확인 항목 | 결과 |
|---|---|
| 폴더 선택 input 실재 | `#attachDirInput` 존재 · `webkitdirectory=true` · `multiple=true` |
| "폴더 첨부" 메뉴 항목 | `#composerActionsAttachDirItem` 존재 · 라벨 "폴더 첨부" |
| 기존 파일 input 분리 유지 | `#attachFileInput.webkitdirectory === false` |
| **스키마 fast-path ALTER** | 컨테이너 기동만으로 라이브 MySQL 에 `RelativePath varchar(1024) YES` 실제 생성 |
| 폴더 업로드 end-to-end | 4파일 전건 200 · 저장·반환 경로가 전송 경로와 일치 |
| **동명 파일 비충돌 (핵심)** | `my-project/src/config.json`(id 1294, **v1**) 과 `my-project/test/config.json`(id 1295, **v1**) 이 **둘 다 v1 로 공존** — 파일명 스코프였다면 후자가 v2 가 되며 전자를 supersede했다 |
| traversal 방어 | `../../../etc/passwd/evil.txt` → `etc/passwd/evil.txt` (상위 이동 제거) |
| **프롬프트 인젝션 방어** | 파일명이 ```` ``` ```` 인 첨부를 실제로 업로드 → 프롬프트에서 `` ` ` ` `` 로 중화, 구획이 `⟦UNTRUSTED-DATA⟧` sentinel 이라 뒤따르는 `FILE VERSION LINEAGES` 블록이 온전 |
| 목록 정렬 | 폴더별로 묶여 정렬 (`my-project/README.md` → `src/…` → `test/…`) |
| **목록 폴더 칩** | 6행 전부 렌더 · 전체 잘림 0건 · `src/utils` 처럼 구분되는 뒷부분 표시 |
| 행 레이아웃 | 6행 모두 **55px 균일** (초판은 긴 칩이 버튼을 다음 줄로 밀어 행 높이가 갈렸다 — 캡처로 적발 후 교정) |
| MySQL ROW_FORMAT | `Dynamic` 실측 — `VARCHAR(1024)` 추가가 InnoDB 8126B in-row 한계에 걸리지 않는다(긴 VARCHAR 은 off-page). ALTER 가 실제로 성공한 것이 그 확인 |

### 라운드 2 재실측 (backend 렌즈 반영 후)

| 확인 항목 | 결과 |
|---|---|
| **계보 스코프 경로화** | `config.json` 2건이 공존하는 상태에서 `/api/attachments/{id}/versions` 가 `lineages` **1건**만 반환(`my-project/src/config.json`) — 다른 폴더 파일을 「경쟁 계보」로 세우지 않는다 |
| **깊이 초과 supersede 방지** | 40단 깊이의 `…/en/messages.json`(id 1299) 과 `…/ko/messages.json`(id 1300) 이 **둘 다 v1**, 경로도 구분됨. 초판(상한 초과 → 경로 폐기)이었다면 후자가 파일명으로 전자를 찾아 **v2 로 편입하며 supersede** 했다 — 사용자가 2개를 올렸는데 1개만 남는 무음 손실 |
| 앞이 잘렸음의 관측성 | 보존된 꼬리 앞에 `…/` 가 붙어 절단 사실이 표시된다(무음 절단 금지) |

- 시각 캡처: `docs/evidence/attach-folder-tree-list.png` — 첨부 패널에 `config.json` 두 개가
  각각 `📁 my-project/src` · `📁 my-project/test` 로 **구분되어** 보인다(P1 해소의 시각 증거).
- **미수행**: 실제 폴더 드래그&드롭 제스처(브라우저 자동화로 OS 파일 드롭을 합성할 수 없음) ·
  실 LLM 답변에서의 구조 인지(개인 AI 브리지 미연결 — 프롬프트 주입 문자열은 위에서 직접 실측).
  두 축 모두 배포 후 실사용으로 확인한다.
