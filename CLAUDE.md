# Claude Code Notes

- 이 저장소의 공식 에이전트 운영 규칙은 `./AGENTS.md`를 따릅니다.
- 이 문서는 별도 정책 문서가 아니며, `AGENTS.md`와 `docs/*`를 참조하여 따릅니다.
- 본 저장소는 gstack 스킬(`~/.claude/skills/gstack/`) 과 공존하며, 스킬 호출 시에도 `AGENTS.md` / `CONTRIBUTING.md` / `docs/*` / `unit/feature-NNNN/docs/*` 의 governance 가 우선 적용됩니다.
- gstack 의 `/ship`, `/review`, `/qa`, `/investigate` 등 스킬을 사용할 때는 `CONTRIBUTING.md §5` 커밋 규칙과 `AGENTS.md §2.2` 스테이징 규칙을 따릅니다.
- 기능 진행 이력과 작업 기록은 gstack 의 `TODOS.md` / `CHANGELOG.md` 가 아닌 기존 `docs/STATUS.md` + `unit/feature-NNNN/docs/TASK.md` + `unit/feature-NNNN/docs/REPORT.md` 에 기록합니다. `TODOS.md` 는 feature 단위로 귀속되지 않은 repo-level 보류 아이템만 추적합니다.

## Skill routing

gstack 스킬이 본 저장소 맥락과 충돌하지 않는 경우에 한해, 사용자의 요청이 다음 패턴과 맞으면 Skill 툴을 통해 해당 스킬을 호출한다. 판단이 모호한 경우 기존 governance (`AGENTS.md`) 를 먼저 따르고, 스킬 호출 여부를 사용자에게 확인한다.

- 제품 아이디어 / "이거 만들 가치가 있나" / 브레인스토밍 → `/office-hours`
- 전략 · scope · "더 크게 생각해 보자" · 방향 리뷰 → `/plan-ceo-review`
- 아키텍처 · "이 설계 말 되나" · 엔지니어링 리뷰 → `/plan-eng-review`
- 설계 리뷰(구현 전) → `/plan-design-review`
- 라이브 사이트 시각 감사 → `/design-review`
- 개발자 경험 리뷰(계획 단계) → `/plan-devex-review`
- 개발자 경험 실측 감사 → `/devex-review`
- 전체 리뷰 파이프라인 → `/autoplan`
- 버그 · 에러 · "왜 안 돼" · 근본 원인 분석 → `/investigate`
- 사이트/기능 QA · "이거 작동하나" → `/qa` (리포트만: `/qa-only`)
- PR / diff 사전 리뷰 → `/review`
- 코드 리뷰 · 2차 의견 → `/codex`
- ship/merge/PR 생성 → `/ship`
- merge + deploy + 검증 → `/land-and-deploy`
- 배포 구성 세팅 → `/setup-deploy`
- 배포 후 모니터링 → `/canary`
- 릴리스 후 문서 갱신 → `/document-release`
- 주간 retro → `/retro`
- 보안 감사 · OWASP · 위협 모델 → `/cso`
- 진행 상태 저장 / 복원 → `/context-save` / `/context-restore`
- 편집 범위 제한 → `/freeze` / `/unfreeze` / `/guard` / `/careful`
- PDF 문서 출력 → `/make-pdf`
- 실제 브라우저 QA → `/connect-chrome` + `/browse`
- 인증 쿠키 임포트 → `/setup-browser-cookies`
- 성능 회귀 감지 → `/benchmark`
- 모델 벤치마크 → `/benchmark-models`
- 코드 품질 대시보드 → `/health`
- gstack 학습 히스토리 → `/learn`
- 질문 민감도 튜닝 → `/plan-tune`
- gstack 버전 업그레이드 → `/gstack-upgrade`

본 저장소는 feature 중심 구조이므로, 스킬이 `/ship` 이나 `/review` 로 PR 을 다룰 때는 `CONTRIBUTING.md` 의 브랜치/커밋 규칙(`<type>(<scope>): 요약 (#<issue>)` + `TASK-NNNN` 접미)을 우선 적용한다.
