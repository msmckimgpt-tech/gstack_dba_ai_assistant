"""feature-0043 — 러너 능력 신고의 **리비전 지문**과 **계정별 baseline 원장** 순수 정본.

## 왜 shared 이고, 왜 별 모듈인가

이 파일이 답하는 질문은 둘이다.

1. **「목록이 바뀌었는가」** — 프런트가 새로고침 없이 모델·추론등급 선택기를 갱신하려면
   그 사실을 *값으로* 받아야 한다. 문구를 파싱하거나 목록 전체를 비교하는 방식은
   판정이 두 벌이 되고(서버·프런트), 갈리는 순간 느슨한 쪽이 사용자가 보는 진실이 된다.
   그래서 서버가 **지문 하나**를 내고 프런트는 같은지만 본다.
2. **「이 계정의 이 런타임은 마지막으로 무엇을 쓸 수 있었나」** — 능력 목록의 출처가
   LLM 답변이라 회차마다 흔들린다. 흔들림을 흡수하는 캐시가 사용자 머신에만 있어서,
   머신을 바꾸거나 홈을 비우면 목록이 통째로 달라졌다(사용자 제보 2026-09-02).

`shared/bridge_tasks.py` 에 얹지 않은 이유는 두 가지다 — (a) 그 파일은 task **상태 술어**의
정본이고 능력 원장은 다른 관심사다, (b) 그 파일을 hot_path 로 선언한 활성 세션이 여럿이라
(§13.2.5-A) 새 관심사를 같은 파일에 넣으면 만들 필요 없는 충돌을 만든다.

## 무엇을 두지 않는가

- **DB 접근·JSON 컬럼 읽기/쓰기**: `oauth_store` 가 소유한다. 여기 커넥션이 들어오면
  같은 요청 안에서 두 트랜잭션이 생긴다(`bridge_tasks` 와 같은 규율).
- **신고 본문의 정제(sanitize)**: `routers/ai_tools._sanitize_runtimes` 가 **수신 시점**의
  단일 게이트다. 여기서 다시 정제하면 두 벌이 되고, 한쪽만 느슨해지는 날 그 경로가
  통과 경로가 된다. 이 모듈은 **이미 정제된 목록**을 받는다고 전제한다.
- **출처(provenance) 허용 판정**: 러너 `_REPORTABLE_SOURCES` · 서버
  `_SANITIZE_SOURCE_ALLOW` 두 집합이 정본이고 구조 테스트가 그 둘을 대조한다.

## 화석 방지 계약 (읽는 사람이 반드시 알아야 하는 것)

서버가 모델 목록을 보관한다는 것은 **caps-trust-gate 사고와 같은 «모양»** 이다 —
사용자 제보 4회를 만든 `gpt-5.1-codex` 화석이 정확히 「우리가 들고 있던 목록을 화면에
그린」 형태였다. 다른 점은 **출처와 만료뿐**이므로 그 둘이 이 모듈의 계약이다:

- baseline 은 **그 계정 자신의 러너 신고**에서만 자란다. 우리 소스의 표(`builtin`)가
  들어올 경로는 없다 — 이 모듈은 목록을 **만들지 않고** 받은 것만 병합한다.
- baseline 은 **화면에 직행하지 않는다.** 러너가 라이브 확인을 통과시킨 것만 신고가 되고,
  신고만이 카탈로그가 된다(사용자 결정 2026-09-02 「확인-후-표시」).
- 만료는 **생성일이 아니라 사용일**(`last_used_at`) 기준이다 (사용자 결정 2026-09-02).
  생성일 고정 기준이면 매일 쓰는 런타임도 14일마다 전면 재질의로 떨어져, 안정성을 얻으려고
  만든 원장이 주기적으로 불안정을 재생산한다.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

__all__ = [
    "BASELINE_TTL_DAYS",
    "BASELINE_MAX_VERIFY_STREAK",
    "BASELINE_MAX_RUNTIMES",
    "caps_revision",
    "normalize_baseline",
    "merge_baseline",
    "prune_stale",
    "baseline_for_runner",
    "dumps_baseline",
]

#: baseline 항목이 «쓰이지 않은 채» 살아 있을 수 있는 기간 (사용자 결정 2026-09-02: 14일).
#:
#: 기준 컬럼은 `last_used_at` 이고 그 값은 **살아 있는 러너가 그 런타임을 신고할 때마다**
#: 갱신된다. 하트비트가 30초마다 능력을 매번 싣기 때문에, 실제로 쓰이는 런타임은 연결돼
#: 있는 동안 계속 현재로 유지되고 만료되지 않는다. 따라서 만료되는 모집단은 «14일 넘게
#: 어떤 러너도 신고하지 않은 런타임» — 그 계정이 더 이상 쓰지 않는 CLI 뿐이다.
BASELINE_TTL_DAYS = 14

#: baseline 이 담는 런타임 수 상한. 수신 시점 정제가 이미 신고를 8개로 자르므로
#: (`ai_tools._CAPS_MAX_RUNTIMES`) 같은 값을 쓴다 — 원장이 신고보다 넓어질 이유가 없고,
#: 넓으면 한 계정이 오래 쓰며 모은 런타임이 상한 없이 쌓인다.
BASELINE_MAX_RUNTIMES = 8

#: 저장 문서 전체의 바이트 상한. 컬럼이 TEXT 라 물리 상한은 훨씬 크지만, 이 값은
#: **하트비트 응답에 실려 매 30초 나가는** 페이로드이기도 하다. 상한을 넘으면 오래
#: 쓰지 않은 항목부터 버린다(만료 판정과 같은 축 — `last_used_at` 오름차순).
BASELINE_MAX_BYTES = 16 * 1024

#: `last_used_at` 을 **다시 찍기까지의 최소 간격** (1시간).
#:
#: ## 왜 필요한가 (자체 적발, 2026-09-02)
#:
#: 하트비트는 능력을 **매번** 싣고 계정당 30초마다 온다. 신고를 받을 때마다 timestamp 를
#: 갱신하면 **내용이 하나도 안 바뀌었는데도 직렬화 바이트가 달라져** 저장 게이트의
#: 「값이 그대로면 쓰지 않는다」가 무력화된다 — 계정당 30초마다 `UPDATE WebAccounts` 가
#: 나가고, 연결된 계정 수에 비례해 곱해진다. 초판이 정확히 그 상태였고, 같은 파일의
#: 주석이 갖지 못한 성질을 주장하고 있었다.
#:
#: ## 왜 1시간인가 (경계 양측 — §16.7 G4)
#:
#: 이 값이 하는 일은 「사용 중」을 만료로 오판하지 않는 것뿐이고, 만료 임계는 **14일**이다.
#: 그래서 상한 쪽 경계는 아주 넓다 — 1시간 granularity 로도 하루 한 번 켜는 사용자의
#: 항목이 만료되기까지 14일 여유가 그대로 남는다(오차는 최대 1시간, 임계의 0.3%).
#: 하한 쪽 경계는 쓰기 비용이다 — 30초 → 1시간이면 쓰기가 **120분의 1**로 줄어든다.
#: 더 늘리면 얻는 것이 없고(쓰기는 이미 시간당 1회), 줄이면 그만큼 무의미한 쓰기가 는다.
BASELINE_TOUCH_MIN_SEC = 3600

#: 열린 열거 없이 **연속으로 확인만** 통과할 수 있는 횟수 (기본 5).
#:
#: ## 왜 이 축이 필요한가 (적대 리뷰 2026-09-02 §3)
#:
#: `last_used_at` 은 러너가 붙어 있는 동안 계속 갱신되므로 **TTL 14일에 결코 도달하지
#: 않는다.** 그러면 한 번 원장에 든 잘못된 값이 (a) 새 머신마다 확인 질의의 **앵커**로 다시
#: 제시되고 (b) 순응적인 답으로 `verified` 를 다시 받고 (c) 다시 갱신된다 — 자기강화 루프고,
#: 탈출구가 사용자가 `--refresh-caps` 를 아는 것 하나였다.
#:
#: ## 왜 «벽시계 나이» 가 아니라 «횟수» 인가 (확인 라운드 R3 S1 수용)
#:
#: 초판은 「마지막 열린 열거로부터 14일」로 두었다. 그런데 러너는 로컬 캐시가 있으면 다시
#: 열거하지 않으므로(그게 캐시의 목적이다) 앵커는 **마지막 캐시 소실 시점**에 고정되고
#: 14일 뒤 죽는다. 제보 ②의 표제 시나리오는 «머신 교체» 이고 그 주기는 수개월이라, 3개월
#: 뒤 새 노트북이 붙으면 원장은 이미 서빙 불가여서 **열린 열거 1회(=불안정 목록 1회)를
#: 그대로 겪는다** — 원장이 값을 하는 창이 정작 필요한 시점을 비껄러 간다.
#:
#: 횟수로 세면 그 결합이 끊긴다: 원장은 **몇 달이 지나도** 유효하고, 대신 열린 열거 없이
#: 확인만 N회 통과하면 다음은 강제로 열린 열거가 된다. 자기강화 루프를 끊는 성질은 같고
#: (무한히 재앵커될 수 없다), 유효 창은 사용 빈도에 따라 자연히 결정된다.
#:
#: 값의 근거(경계 양측 — §16.7 G4): 새 머신 첫 연결이 1회를 쓰므로 5면 머신 4대를 새로
#: 붙이는 동안 원장이 유효하다. 그보다 크면 잘못된 값이 더 오래 재사용되고, 1~2면 머신 두
#: 대만 바꿔도 원장이 꺼져 초판과 같은 문제가 된다.
BASELINE_MAX_VERIFY_STREAK = 5

#: 원장 항목의 `build` 지문 최대 길이. 러너 신고값(`agent_build`)은 클라이언트가 주는
#: 문자열이고, 검증 없이 넣으면 그 한 필드가 문서 예산(`BASELINE_MAX_BYTES`)을 통째로
#: 잠식해 **원장을 영구히 비운다**(실측: 40KB `agent_build` → 문서 NULL 고정, 그 뒤로는
#: `before == after` 라 쓰기조차 없어 조용하다 — 적대 리뷰 2026-09-02).
#: 같은 값을 `set_runner_report` 는 hex 6~16자로 좁히므로 여기서도 같은 폭으로 좁힌다.
BASELINE_BUILD_MAX_LEN = 16

#: 런타임당 원장에 담는 모델·등급 수 상한. 수신 시점 정제(`_sanitize_runtimes`)와 같은 값.
#: 원장은 여러 러너의 신고를 **합집합**으로 누적하므로(아래 `merge_baseline`) 상한이 없으면
#: 신고가 흔들릴 때마다 자라기만 한다.
BASELINE_MAX_MODELS = 40
BASELINE_MAX_EFFORTS = 12


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """`Z` 를 명시한 UTC ISO8601. 저장·전송 양쪽이 같은 표기를 쓴다.

    `+00:00` 대신 `Z` 로 쓰는 이유는 이 저장소가 첨부 `CreatedAt` 축에서 이미 그 규약을
    세웠기 때문이다(`_iso_utc_z`) — 표기가 두 가지면 파서가 두 벌이 된다.
    """
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(raw: object) -> datetime | None:
    """저장된 timestamp 를 tz-aware datetime 으로. 못 읽으면 `None`.

    ⚠ `None` 을 «지금» 으로 폴백하지 않는다. 폴백하면 값이 깨진 항목이 **영원히 만료되지
    않는다** — 화석 방지의 유일한 시간축이 그 폴백 하나로 무력화된다. 못 읽는 값은
    「모른다」이고, 만료 판정에서 「모른다」는 만료 대상이다(아래 `prune_stale`).
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        got = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if got.tzinfo is None:
        # naive 는 UTC 로 읽는다 — 이 모듈이 쓰는 값은 전부 `_iso` 산출물이라 naive 가
        # 나올 자리는 손으로 넣은 값뿐이고, 그때 로컬시각으로 읽으면 만료가 9시간 밀린다.
        return got.replace(tzinfo=timezone.utc)
    return got


# ── 1. 리비전 지문 ────────────────────────────────────────────────────────────

def caps_revision(runtimes: object) -> str:
    """신고 목록의 **내용 지문** 12자. 목록이 같으면 같고 다르면 다르다.

    프런트는 이 값만 비교해 「카탈로그를 다시 받아야 하는가」를 정한다. 목록 전체를
    내려보내 비교하게 하면 상태 조회가 카탈로그 조회를 겸하게 되고, 그러면 두 응답이
    같은 사실을 두 벌로 말한다(둘이 갈리는 날 화면은 어느 쪽을 믿을지 정해야 한다).

    ## 정규화가 계약이다

    지문은 **의미가 같은 목록에 같은 값**을 내야 한다. 그렇지 않으면 러너가 순서만 바꿔
    신고한 회차마다 프런트가 카탈로그를 다시 받는다(무의미한 왕복). 그래서:

    - 런타임은 이름 오름차순, 각 런타임의 모델·등급은 `value` 오름차순으로 정렬한다.
    - 화면에 영향을 주는 필드만 넣는다 — `runtime`·`label`·모델/등급의 `value`·`label`.
      `source` 는 **넣지 않는다**: 같은 목록이 캐시에서 왔는지 실조회에서 왔는지는 화면에
      아무 차이를 만들지 않고, 넣으면 러너 재기동마다 지문이 흔들려 헛 왕복이 생긴다.

    `None`(신고 없음)과 `[]`(신고했고 고를 것 없음)은 **다른 값**이어야 한다 — 그 구분이
    화면에서 「러너 없음」과 「고를 것 없음」을 가르는 축이고, 지문에서 뭉개면 그 전이를
    프런트가 관측하지 못한다.
    """
    if runtimes is None:
        return ""
    if not isinstance(runtimes, list):
        return ""
    shaped: list[dict] = []
    for item in runtimes:
        if not isinstance(item, dict):
            continue
        name = str(item.get("runtime") or "")
        if not name:
            continue
        shaped.append({
            "r": name,
            "l": str(item.get("label") or ""),
            "m": sorted(
                ((str(o.get("value") or ""), str(o.get("label") or ""))
                 for o in (item.get("models") or []) if isinstance(o, dict)),
            ),
            "e": sorted(
                ((str(o.get("value") or ""), str(o.get("label") or ""))
                 for o in (item.get("efforts") or []) if isinstance(o, dict)),
            ),
        })
    shaped.sort(key=lambda d: d["r"])
    blob = json.dumps(shaped, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


# ── 2. baseline 원장 ─────────────────────────────────────────────────────────

def normalize_baseline(raw: object) -> dict:
    """저장 문서를 `{runtime: entry}` 로. 모양이 어긋난 항목은 **그것만** 버린다.

    전체를 거절하면 한 런타임의 사소한 손상이 그 계정의 원장을 통째로 지운다 —
    `_sanitize_runtimes` 가 신고에 대해 세운 것과 같은 규율이다.

    ⚠ 여기서 값의 **문자집합·개수 상한을 다시 강제하지 않는다.** 이 문서에 들어오는 값은
    전부 `_sanitize_runtimes` 를 통과한 신고에서 왔고, 정제를 두 곳에 두면 두 정의가
    갈릴 준비를 마친다. 여기서 보는 것은 **구조**(dict 인가·이름이 있는가·모델이 있는가)뿐이다.
    """
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for name, entry in raw.items():
        key = str(name or "").strip()
        if not key or not isinstance(entry, dict):
            continue
        models = [o for o in (entry.get("models") or []) if isinstance(o, dict) and o.get("value")]
        if not models:
            # 고를 모델이 없는 항목은 러너에게 확인시킬 것이 없다 — 원장에 남길 이유도 없다.
            continue
        efforts = [o for o in (entry.get("efforts") or []) if isinstance(o, dict) and o.get("value")]
        out[key] = {
            "label": str(entry.get("label") or key),
            "models": models[:BASELINE_MAX_MODELS],
            "efforts": efforts[:BASELINE_MAX_EFFORTS],
            # 만료 판정 축. 부재는 「모른다」로 남긴다 — 여기서 «지금» 을 채우면
            # 손상된 항목이 영원히 만료되지 않는다(위 `_parse_iso` 주석과 같은 이유).
            "last_used_at": str(entry.get("last_used_at") or ""),
            # **앵커 축** — 마지막 «열린 열거»(`source == "probe"`) 시각. 조사용이며 제시
            # 판정에는 쓰지 않는다(그 판정은 아래 `verify_streak` 이 한다 — R3 S1).
            "probed_at": str(entry.get("probed_at") or ""),
            # **제시 판정 축** — 열린 열거 없이 확인만 연속 통과한 횟수.
            # `baseline_for_runner` 가 이 값으로 「확인 대상으로 제시해도 되는가」를 가른다.
            # 열린 열거가 오면 0으로 되돌아간다. 부재·비정수는 「모른다」 = 상한으로 취급해
            # 제시하지 않는다(만료 축에서 부재를 만료로 다루는 것과 같은 방향).
            "verify_streak": (int(entry["verify_streak"])
                              if isinstance(entry.get("verify_streak"), int)
                              and entry["verify_streak"] >= 0
                              else BASELINE_MAX_VERIFY_STREAK),
            # 클라이언트가 주는 값이라 **길이를 좁힌다** — 좁히지 않으면 이 한 필드가
            # 문서 예산을 잠식해 원장을 비운다(위 `BASELINE_BUILD_MAX_LEN` 주석).
            "build": str(entry.get("build") or "")[:BASELINE_BUILD_MAX_LEN],
        }
    return out


def _content_key(entry: object) -> str:
    """만료 timestamp 를 **제외한** 내용 지문. 「내용이 바뀌었는가」 판정에만 쓴다.

    `label`·`models`·`efforts` 만 본다 — `build` 는 러너 파일 지문이라 사용자가 러너를
    갱신하면 바뀌지만 **고를 수 있는 것은 그대로**이고, 그 변화로 쓰기를 유발할 이유가 없다
    (그 사실은 이미 `RunnerBuild` 컬럼이 별도로 들고 있다).
    """
    if not isinstance(entry, dict):
        return ""
    return json.dumps({
        "l": str(entry.get("label") or ""),
        "m": sorted((str(o.get("value") or ""), str(o.get("label") or ""))
                    for o in (entry.get("models") or []) if isinstance(o, dict)),
        "e": sorted((str(o.get("value") or ""), str(o.get("label") or ""))
                    for o in (entry.get("efforts") or []) if isinstance(o, dict)),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _union_options(prev: object, fresh: object, cap: int) -> list:
    """`value` 기준 합집합. **새 신고를 앞에** 두고 라벨도 새 것을 채택한다.

    순서가 계약이다 — 상한(`cap`)에 걸려 잘리는 것은 «오래된 후보» 여야 한다. 반대로 두면
    지금 쓸 수 있는 모델이 옛 후보에 밀려 확인 대상에서 빠진다.

    라벨을 새 것으로 갱신하는 이유: 사람이 읽는 이름은 그 AI 가 방금 말한 쪽이 맞다.
    """
    out: list = []
    seen: set = set()
    for src in (fresh if isinstance(fresh, list) else [],
                prev if isinstance(prev, list) else []):
        for o in src:
            if not isinstance(o, dict):
                continue
            value = str(o.get("value") or "")
            if not value or value in seen:
                continue
            seen.add(value)
            out.append({"value": value, "label": str(o.get("label") or value)})
            if len(out) >= max(1, int(cap)):
                return out
    return out


def merge_baseline(baseline: object, reported: object, *,
                   now: datetime | None = None, build: str = "",
                   sources: dict | None = None,
                   touch_min_sec: int = BASELINE_TOUCH_MIN_SEC) -> dict:
    """신고를 원장에 **병합**한다. 신고에 없는 런타임은 **건드리지 않는다**.

    ## 왜 «신고에 없으면 지우지 않는가»

    한 계정이 여러 머신에서 러너를 띄울 수 있다(그것은 명시적으로 허용된 구조다 —
    하트비트 판정이 `AccountId` 로 묶여 있다). 노트북에서 codex 만 신고하는 러너가
    데스크톱에서 확인해 둔 claude 항목을 지우면, 원장은 **마지막에 말한 머신의 사진**이
    되어 여러 머신 사용자에게 오히려 불안정을 만든다. 원장은 사진이 아니라 **누적**이고,
    누적이 무한히 자라지 않게 하는 것은 삭제가 아니라 **만료**(`prune_stale`)다.

    ## `last_used_at` 은 신고될 때마다 갱신되되, **시간당 1회로 throttle** 된다

    이것이 「사용일 기준 만료」의 구현이다 (사용자 결정 2026-09-02). 하트비트가 능력을
    매번 싣기 때문에, 실제로 쓰이는 런타임은 연결돼 있는 동안 계속 갱신된다.

    ⚠ **throttle 이 없으면 저장 게이트가 무력화된다.** 신고를 받을 때마다 timestamp 를
    새로 찍으면 내용이 하나도 안 바뀌었는데도 직렬화 바이트가 달라져, 호출측의
    「값이 그대로면 쓰지 않는다」가 항상 거짓이 된다 — 계정당 30초마다 UPDATE 다.
    그래서 **내용이 같고 직전 기록이 `touch_min_sec` 안이면 항목을 손대지 않는다**
    (근거·경계는 `BASELINE_TOUCH_MIN_SEC` 주석).

    `reported` 가 `None`(신고할 처지가 아님)이면 원장을 **그대로** 돌려준다 — `[]`(신고했고
    고를 것 없음)과 다른 사실이며, 후자도 «지우라» 는 뜻이 아니다(그 러너가 지금 고를 것이
    없다는 사실이지, 이 계정이 그 런타임을 잃었다는 사실이 아니다).
    """
    current = normalize_baseline(baseline)
    if reported is None or not isinstance(reported, list):
        return current
    ref = now or _utcnow()
    stamp = _iso(ref)
    for item in reported:
        if not isinstance(item, dict):
            continue
        name = str(item.get("runtime") or "").strip()
        if not name:
            continue
        models = [o for o in (item.get("models") or []) if isinstance(o, dict) and o.get("value")]
        if not models:
            continue
        efforts = [o for o in (item.get("efforts") or [])
                   if isinstance(o, dict) and o.get("value")]
        prev = current.get(name)
        # ── 합집합 누적 (적대 리뷰 2026-09-02, medium) ────────────────────────────
        #
        # 한 계정에 두 머신이 붙으면 **같은 런타임 이름으로 서로 다른 목록**을 신고한다 —
        # 목록이 흔들린다는 것이 이 feature 의 전제 자체다. 마지막 신고로 덮어쓰면
        # ① 매 하트비트마다 내용이 바뀌어 throttle 이 무력화되고(계정당 30초 UPDATE ×2)
        # ② `baseline_for_runner` 가 30초마다 다른 목록을 내어 **확인 질의의 입력이
        # 진동한다** — 안정화를 만들려는 기능이 정확히 반대로 동작한다.
        #
        # 그래서 «누적» 을 항목 축(위 docstring)에서 **값 축까지** 확장한다: 두 머신의
        # 목록이 합집합으로 수렴하면 내용이 더 이상 바뀌지 않고 쓰기도 멎는다.
        #
        # 대가는 정직하게: 실제로 사라진 모델이 TTL(또는 앵커 만료)까지 후보로 남는다.
        # 그 대가가 감당 가능한 이유는 **확인-후-표시** 다 — 후보는 화면에 직행하지 않고
        # 그 AI 가 「못 쓴다」고 답하면 신고에서 빠진다. 즉 잘못된 후보의 비용은 확인
        # 프롬프트 한 줄이고, 진동의 비용은 기능 자체의 무력화다.
        models = _union_options((prev or {}).get("models"), models, BASELINE_MAX_MODELS)
        efforts = _union_options((prev or {}).get("efforts"), efforts, BASELINE_MAX_EFFORTS)
        # 앵커 축 — 열린 열거만이 앵커를 새로 세운다. 확인(`verified`)은 앵커를 **밀지
        # 않는다**: 앵커를 함께 밀면 「앵커된 답이 앵커를 갱신」하는 자기강화 루프가 되고,
        # 그것이 정확히 이 축을 도입한 이유다.
        #
        # ⚠ 앵커도 `last_used_at` 과 **같은 throttle 을 탄다.** 러너는 한 실행 동안 같은
        #   출처를 매 하트비트에 다시 싣기 때문에, throttle 없이 매번 새로 찍으면 내용이
        #   같아도 문서가 30초마다 바뀌어 저장 게이트가 다시 무력화된다(이 축을 추가하면서
        #   실제로 그렇게 깨졌고, 회귀 테스트 2건이 그것을 잡았다).
        # 출처는 **out-of-band 한 채널로만** 온다 — 저장 스키마(`_sanitize_runtimes`
        # 4키 계약)에는 출처가 없으므로 항목 안을 볼 이유가 없다.
        #
        # ⚠ 초판은 `or item.get("source")` 폴백을 뒀다(「직접 호출·테스트 편의」). 그것이
        #   **운영에서는 죽은 경로이면서 테스트에서만 살아** 판별력을 가렸다 — `sources={}`
        #   (= 배선이 끊긴 상태)를 넣어도 항목에 실린 `source` 가 앵커를 세워, 확인 경로가
        #   꺼진 사실을 단정이 관측하지 못했다. 채널을 하나로 두면 그 단정이 실제로 판별한다.
        src = str((sources or {}).get(name) or "")
        prev_probed_raw = str((prev or {}).get("probed_at") or "")
        # 연속 확인 횟수 — 열린 열거는 **0으로 되돌리고**, 확인은 **1 올린다**. 그 밖의
        # 출처(`cache`)는 건드리지 않는다: 캐시 신고는 그 머신이 이미 확인해 둔 사실의
        # 반복이지 새 확인이 아니다(그것까지 세면 한 머신이 계속 붙어 있기만 해도 원장이
        # 꺼진다 — R3 S1 이 지적한 「벽시계」 문제의 횟수판 재현).
        prev_streak = (prev or {}).get("verify_streak")
        prev_streak = prev_streak if isinstance(prev_streak, int) and prev_streak >= 0 else 0
        if src == "probe":
            streak = 0
        elif src == "verified":
            streak = prev_streak + 1
        else:
            streak = prev_streak
        if src == "probe":
            _prev_probed = _parse_iso(prev_probed_raw)
            _fresh_enough = (_prev_probed is not None
                             and (ref - _prev_probed).total_seconds()
                             < max(0, int(touch_min_sec)))
            probed_at = prev_probed_raw if _fresh_enough else stamp
        else:
            probed_at = prev_probed_raw
        fresh = {
            "label": str(item.get("label") or name),
            "models": models,
            "efforts": efforts,
            "last_used_at": stamp,
            # ⚠ `confirmed_at` 은 **두지 않는다** (확인 라운드 2026-09-02 §2). 초판에 있었고
            #   값이 항상 `last_used_at` 과 동일했으며 **읽는 코드가 하나도 없었다** — 같은
            #   라운드가 `system.py` 에서 제거하라고 지적한 「소비처 0 필드」와 같은 클래스다.
            #   30초마다 나가는 페이로드와 `BASELINE_MAX_BYTES` 예산만 잠식했다.
            #   「언제 라이브로 확인됐나」가 필요해지면 그때 소비처와 함께 넣는다.
            "probed_at": probed_at,
            "verify_streak": streak,
            "build": str(build or (prev or {}).get("build") or "")[:BASELINE_BUILD_MAX_LEN],
        }
        if prev is not None and _content_key(prev) == _content_key(fresh) \
                and str(prev.get("probed_at") or "") == probed_at \
                and prev_streak == streak:
            prev_used = _parse_iso(prev.get("last_used_at"))
            if prev_used is not None and (ref - prev_used).total_seconds() < max(0, int(touch_min_sec)):
                # 내용 동일 + 앵커 동일 + 직전 기록이 충분히 최근 → **손대지 않는다**(쓰기 0).
                continue
        current[name] = fresh
    return prune_stale(current, now=now)


def prune_stale(baseline: object, *, now: datetime | None = None,
                ttl_days: int = BASELINE_TTL_DAYS) -> dict:
    """`last_used_at` 이 TTL 을 넘긴 항목과 **읽을 수 없는 항목**을 뺀다.

    「모른다」(`last_used_at` 부재·파싱 불가)를 **만료로 다룬다.** 반대로 두면 값이 깨진
    항목이 영원히 남고, 그것이 정확히 화석이다 — 시간축 하나가 화석 방지의 전부이므로
    그 축을 읽지 못하는 항목은 원장에 있을 자격이 없다. 잃는 것은 «다음 연결에서 다시
    확인받는 것» 뿐이다.

    상한(`BASELINE_MAX_RUNTIMES`·`BASELINE_MAX_BYTES`)을 넘으면 **오래 쓰지 않은 순서로**
    버린다 — 만료와 같은 축이라 사용자가 예측할 수 있다(무작위·삽입순은 예측 불가).
    """
    entries = normalize_baseline(baseline)
    ref = (now or _utcnow())
    cutoff = ref - timedelta(days=max(1, int(ttl_days)))
    alive: list[tuple[datetime, str, dict]] = []
    for name, entry in entries.items():
        used = _parse_iso(entry.get("last_used_at"))
        if used is None or used < cutoff:
            continue
        alive.append((used, name, entry))
    # 최신 사용 순 — 상한 초과 시 뒤(오래된 것)부터 잘린다.
    alive.sort(key=lambda t: (t[0], t[1]), reverse=True)
    out: dict = {}
    for _used, name, entry in alive[:BASELINE_MAX_RUNTIMES]:
        out[name] = entry
    # 바이트 상한 — 넘으면 가장 오래 쓰지 않은 것부터 뺀다.
    while out and len(dumps_baseline(out).encode("utf-8")) > BASELINE_MAX_BYTES:
        oldest = min(out, key=lambda n: (_parse_iso(out[n].get("last_used_at"))
                                         or datetime.min.replace(tzinfo=timezone.utc), n))
        out.pop(oldest, None)
    return out


def baseline_for_runner(baseline: object, *, now: datetime | None = None) -> list[dict]:
    """러너에게 내려보낼 모양. **만료된 항목은 실리지 않는다.**

    러너는 이것을 «확인 질의의 입력» 으로만 쓴다 — 그대로 신고하지 않는다(사용자 결정
    「확인-후-표시」). 그래서 여기 `source` 를 넣지 않는다: 출처는 러너가 **자기 확인
    결과로** 정하는 값이고, 서버가 미리 정해 주면 그 값이 확인 없이 통과하는 경로가 된다.

    반환은 신고와 같은 모양(`runtime`/`label`/`models`/`efforts`)이다 — 러너가 두 형태를
    변환하지 않아도 되게. `last_used_at` 같은 원장 메타는 러너에게 쓸 곳이 없으므로 뺀다
    (러너가 만료를 판정하지 않는다 — 그건 서버 몫이다).

    ## 확인만 반복된 항목은 **제시하지 않는다** (적대 리뷰 §3 · 확인 라운드 R3 S1)

    `last_used_at` 은 러너가 붙어 있는 동안 갱신되므로 TTL 에 도달하지 않는다. 그래서
    만료만으로는 「한 번 잘못 든 값이 확인 질의의 앵커로 영원히 되풀이되는」 자기강화
    루프를 끊지 못한다. 열린 열거 없이 확인만 `BASELINE_MAX_VERIFY_STREAK` 회 통과한
    항목은 여기서 빠지고, 받지 못한 러너는 종전 경로대로 열린 질의를 한다 — 그 답이 앵커
    없이 원장을 교정하고 streak 을 0으로 되돌린다.

    ⚠ **벽시계가 아니라 횟수다.** 「마지막 열린 열거로부터 N일」로 두면 러너가 캐시를 쓰는
    동안 앵커가 전진하지 않으므로 원장의 유효 창이 «마지막 캐시 소실 시점 + N일» 에 고정되고,
    제보의 표제 시나리오(머신 교체, 주기 수개월)는 대부분 그 창 밖으로 떨어진다 — 원장이
    정작 필요한 시점에 꺼져 있게 된다.

    `verify_streak` **부재·비정수는 상한으로** 취급해 제시하지 않는다(만료 축에서
    `last_used_at` 부재를 만료로 다루는 것과 같은 방향 — 모르는 것을 근거로 제시하지 않는다).
    """
    entries = prune_stale(baseline, now=now)
    out: list[dict] = []
    for name in sorted(entries):
        entry = entries[name]
        if int(entry.get("verify_streak") or 0) >= BASELINE_MAX_VERIFY_STREAK:
            continue
        out.append({
            "runtime": name,
            "label": entry.get("label") or name,
            "models": list(entry.get("models") or []),
            "efforts": list(entry.get("efforts") or []),
        })
    return out


def dumps_baseline(baseline: object) -> str:
    """저장용 직렬화. 키 정렬로 **같은 내용 → 같은 바이트** 를 보장한다.

    결정적이어야 하는 이유: 내용이 같은데 바이트가 다르면 컬럼 쓰기가 매 하트비트마다
    일어난다(30초 × 계정 수). 쓰기 증폭은 이 feature 가 `CapabilitiesAt` throttle 로 이미
    한 번 다룬 문제다.
    """
    return json.dumps(normalize_baseline(baseline), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))
