---
run_at: 2026-09-08T20:37:00+09:00
session: /_template:entry attach-folder-tree (POST-DEPLOY)
scope: feature-0003 폴더 첨부 라이브 배포 후 실측
verdict: PASS
---

# TASK-20260908T203700-attach-folder-tree-postdeploy — 라이브 배포 후 실측

PR #1638 머지(`4e3d70b0`) → `make deploy-web` 배포 후, **라이브 인스턴스**에서 확인한 결과.
`deploy_scope: included`(FIRST_REQUEST.md) 에 따른 자동 배포.

## 배포

- `DEPLOY_EXIT=0` · scope=all · 무중단 one-at-a-time 롤링(web-a → web-b → MCP → 워커).
- **alembic `0058_glossary_term_tier` → `0059_attachment_relative_path` 실제 적용**
  (배포 로그 `-- Running upgrade …`). migrate-lint head 단일성 PASS.
- 서비스 GIT_COMMIT 실측 `4e3d70b0` 일치: `web-a` · `web-b` · `ask-worker` · `insight-worker`.
- 엣지 `https://localhost/healthz` = 200.

## 라이브 스키마 (실측)

| 대상 | 결과 |
|---|---|
| PG `agent_runtime.core_attachments.relative_path` | `character varying(1024)` 실재 |
| MySQL `WebConversationAttachments.RelativePath` | `varchar(1024)` 실재 |

## 라이브 기능 (실측 — Environment: Windows-browser, 실 Chrome + 배포본)

대화 `20260908113723-f2eafb94` 에 폴더 3파일 업로드:

| 확인 | 결과 |
|---|---|
| 업로드 3건 | 전건 200 · 전송 경로 == 저장·반환 경로 |
| **PG read backend 경로** | 목록이 `relative_path` 를 그대로 반환 — dual-write 미러가 경로를 실었다(라이브는 `ATTACHMENTS_READ_BACKEND=postgres`) |
| **동명 파일 비충돌** | `postdeploy/src/config.json` 과 `postdeploy/test/config.json` 이 **둘 다 v1** — 경로 없이는 후자가 전자를 supersede 했을 지점 |
| 목록 폴더 칩 | 3/3 렌더 (`📁 postdeploy` · `📁 postdeploy/src` · `📁 postdeploy/test`) |
| 행 레이아웃 | 3행 모두 55px 균일 |
| 폴더 첨부 진입점 | `#attachDirInput` 실재 · `+` 메뉴에 "폴더 첨부" |

- 캡처: `docs/evidence/attach-folder-tree-postdeploy.png` — 라이브 화면에서 `config.json` 두 개가
  각각 `📁 postdeploy/src` · `📁 postdeploy/te…` 로 구분되어 보인다.

## 미수행 (그대로 남김)

- 실제 폴더 **드래그&드롭 제스처**: 브라우저 자동화로 OS 파일 드롭을 합성할 수 없다.
  코드 경로는 테스트로 고정했고, 결과는 실사용으로 확인한다.
- 실 LLM 답변에서의 구조 인지: 이 계정에 개인 AI 브리지가 연결돼 있지 않다("내 AI가 실행 중이
  아닙니다"). 프롬프트에 실리는 문자열 자체는 배포 전 격리 검증에서 직접 실측했다.
