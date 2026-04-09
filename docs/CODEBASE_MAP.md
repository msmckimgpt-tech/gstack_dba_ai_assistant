---
doc_type: CODEBASE_MAP
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Codebase Map

저장소의 파일 구조와 주요 진입점을 AI가 빠르게 참조할 수 있도록 요약한다.
기능 추가/삭제, 파일 구조 변경 시 갱신한다.

## 1. Directory Tree

```
repo/
├── AGENTS.md              # AI 운영 정책 정본
├── CONTRIBUTING.md         # 기여 및 커밋 규칙
├── .aiignore              # AI 컨텍스트 제외 패턴
├── .env.example           # 환경변수 템플릿
├── docs/                  # 프로젝트 수준 문서
│   ├── ARCHITECTURE.md
│   ├── CONVENTIONS.md
│   ├── DECISIONS.md
│   ├── PROJECT.md
│   ├── SECURITY.md
│   ├── STATUS.md
│   ├── LEARNINGS.md
│   └── CODEBASE_MAP.md    # 이 문서
├── playbooks/             # 반복 작업 템플릿
├── shared/                # 공통 모듈
├── tests/                 # 통합 테스트
│   └── integration/
└── unit/                  # 기능 단위
    ├── _template/         # 기능 템플릿
    └── <feature-id>/      # 각 기능
```

## 2. Key Entry Points

| File | Role | Notes |
|------|------|-------|
<!-- 프로젝트 주요 진입점을 아래에 기입한다 -->

## 3. Shared Module Index

| Module | Purpose | Used By |
|--------|---------|---------|
<!-- shared/ 내 모듈과 사용처를 기입한다 -->

## 4. Feature File Index

<!-- 각 기능의 주요 소스 파일을 기입한다 -->

## 5. External Interfaces

| Interface | Type | Used By |
|-----------|------|---------|
<!-- 외부 API, DB, 큐 등 연결점을 기입한다 -->
