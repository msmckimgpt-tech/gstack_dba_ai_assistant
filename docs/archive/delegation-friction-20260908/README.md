---
doc_type: ARCHIVE_INDEX
scope: project
status: archived
lifecycle: archived
source_of_truth: false
---

# 개발 위탁 병목 정리 전 문서 스냅샷 (2026-09-08)

이 디렉토리는 STATUS/ARCHITECTURE에서 누적된 완료 서사와 과거 관측을 보존한다.
**현재 상태·제약·승인·작업 착수의 정본이 아니다.** 기본 진입 읽기에서 제외하며,
과거 판단을 조사할 때 해당 부분만 찾는다. 현행은 [STATUS](../../STATUS.md),
[ARCHITECTURE](../../ARCHITECTURE.md), 각 unit의 FUNCTION/TASK/REPORT다.

| 원본 | 정리 전 bytes | 최장 행 bytes | SHA-256 |
|---|---:|---:|---|
| [STATUS-before.md](./STATUS-before.md) | 143422 | 41597 | `db80c4d4ad54dc505643b9e3fcd1c1dc07a387b1bb80f543fae565421938a200` |
| [ARCHITECTURE-before.md](./ARCHITECTURE-before.md) | 170247 | 11378 | `dc59178a33c10cce046b0a6a2a1a06ae085442903becd951119b054af65fb450` |

보존 기준 commit: `76a76ddd517aad6001ddb62c53e2e360c0ebdfda`. 위 SHA-256은 **archive 변환 전 원본**이다.
스냅샷 본문은 내용 전체를 보존하고, frontmatter를 archived/비정본으로 표시한 뒤
안내문을 추가했다. Markdown 상대 링크에는 `../../`를 앞에 더해 이동 전과 같은
파일로 해석되게 했다. 본문 backtick의 경로는 원본 문서 기준 표기이며 실행 명령이 아니다.
아카이브가 현재 문서를 가리키는 링크는 탐색 편의용이지 과거 동작의 증거가 아니다.
바이트 단위 원문이 필요하면 저장소 루트에서 immutable Git 객체를 읽는다:

```bash
git show 76a76ddd517aad6001ddb62c53e2e360c0ebdfda:docs/STATUS.md
git show 76a76ddd517aad6001ddb62c53e2e360c0ebdfda:docs/ARCHITECTURE.md
```

상태 정리에서 기능 ID·상태·최종 갱신 날짜와 TASK 링크는 바꾸지 않는다.
표의 숫자는 상태를 재판정하지 않고 실제 행을 집계한다. ARCHITECTURE의 의존 대상과
의존 유형도 유지하며 상세 작업/검증 회차는 이 스냅샷과 unit 문서에서 조회한다.

검증 결과는 [verification.json](./verification.json)에 기록했다. 46개 기능의 ID·상태·날짜·
TASK 링크, 47개 의존 관계의 ID·대상·유형은 최초 정리 전후 동일했다. 이후 main 합류에서
0002·0003·0043·0046의 갱신 날짜를 2026-09-08로 반영했으며 기능 상태는 유지했다.
현재 STATUS의 ID·상태·날짜·TASK 링크는 합류한 main과 일치한다. 기존 Markdown 대상도
모두 유지했으며 원본 상세 스냅샷은 보존 규칙에 따른 변환과 정확히 일치한다.

| 현행 인덱스 | 정리 전 bytes | 정리 후 bytes | 최장 행 bytes (전 → 후) |
|---|---:|---:|---:|
| STATUS | 143422 | 22493 | 41597 → 507 |
| ARCHITECTURE | 170247 | 33575 | 11378 → 487 |

STATUS 집계는 총수 45를 실제 46행으로 정정했으며 상태별 값(in-progress 33,
review 10, done 2, planned 1)은 보존했다. 과거 worktree·미검증 항목은 스냅샷과
현행 미해소 기록으로 구별하고, 완료를 재판정하지 않았다.

최신 main 합류 기준은 `ec913f94360cd706b4769e7e9c98e5d69b27d5c4`다. feature-0046의 1.1.2 릴리스 요약은
main STATUS와 TASK/REPORT의 완료 기록을 대조해 TASK frontmatter에 반영했다.
상태 표는 병합한 TASK 정본으로 재생성하며, 기존 여섯 TASK/REPORT의 main 본문과
이 작업의 별도 추적 블록을 모두 보존했다. 상세 대조는 verification.json의 main_integration을 따른다.
