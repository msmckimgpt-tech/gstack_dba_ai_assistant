"""동결본 exe 안에 그 코드가 실렸는지 **문자열 상수로** 확인한다.

⚠ PyInstaller 의 PYZ 는 모듈별 zlib 압축이라 **평문 검색은 0건** 이다 — 그것만 보고
「없다」로 판정하면 배포된 적 없는 코드를 배포했다고 믿게 된다.

⚠ 아래 「복원한 스트림 개수」는 **경계 추정 휴리스틱에 딸린 값** 이라 재현마다 다를 수 있다
   (적대 리뷰 2026-09-09 MED-2: 다른 휴리스틱으로 621). 판정에 쓰는 것은 개수가 아니라
   **매치가 든 스트림이 있는가** 다.

⚠ 대상은 `dist/DQAConnect/DQAConnect.exe` (설치기가 담는 **앱 폴더**) 다.
   `DQAConnect-Setup-*.exe` 는 Inno 의 LZMA2 라 이 스캐너로는 0건이 나온다 — 그 둘을
   같은 문장에 넣지 말 것.

사용: python3 scan_frozen.py <dist/DQAConnect/DQAConnect.exe> [찾을 문자열 …]
"""
import re
import sys
import zlib

def main() -> int:
    path = sys.argv[1]
    probes = [s.encode() for s in (sys.argv[2:] or ["show.path", "safe_app_path"])]
    blob = open(path, "rb").read()
    print(f"{path}: {len(blob):,} bytes")
    for p in probes:
        print(f"  평문 매치 {p.decode()}: {blob.count(p)}")
    hits = {p: 0 for p in probes}
    streams = 0
    for m in re.finditer(b"\x78[\x01\x9c\xda\x5e]", blob):
        try:
            out = zlib.decompressobj().decompress(blob[m.start():m.start() + 400_000])
        except zlib.error:
            continue
        if len(out) < 200:
            continue
        streams += 1
        for p in probes:
            if p in out:
                hits[p] += 1
    print(f"  복원한 zlib 스트림: {streams} (휴리스틱 의존 — 판정은 아래 매치 유무)")
    for p, n in hits.items():
        print(f"  스트림 내 매치 {p.decode()}: {n}")
    return 0 if all(hits.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
