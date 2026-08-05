// esm-classic-inject.mjs — admin.js/app.js 의 ES module 전환(ITEM-P5b Cycle 7~10 · ITEM-09) 후속.
// jsdom classic <script> 주입 하네스(verify_perm_self_scope · verify_db_rule_pending ·
// verify_ds_accordion_collapse)가 `SyntaxError: Cannot use import statement outside a module`
// 로 파손된 것을 공용 변환기로 해소한다.
//
// 변환은 top-level import/export "배선"만 제거하고 함수 본문은 무수정:
//   1) 다중행 포함 import 문 제거 (라인 끝 주석 허용)
//   2) 재export 라인(`export { a, b };`) 제거 (라인 끝 주석 허용)
//   3) 선언 앞 `export ` 키워드만 제거 (export [async] function/const/let/var/class)
//
// 한계(의도된 fail-loud): 제거된 import 심볼(다른 모듈의 함수)을 top-level 에서 즉시 실행하는
// 코드가 생기면 ReferenceError 로 표면화된다 — 무음 통과가 아니므로, 그 시점에 해당 하네스가
// 심볼 stub 을 realm 에 선주입하는 방식으로 대응한다.
export function stripEsmForClassicInject(src) {
  return src
    .replace(/^import\s+"[^"]+";.*$/gm, "")  // bare(side-effect) import 선행 제거 — from-규칙의 다음 문장 월경(over-consumption) 차단
    .replace(/^import\s[^;]*?from\s+"[^"]+";.*$/gm, "")
    .replace(/^export\s*\{[^}]*\};.*$/gm, "")
    .replace(/^export\s+(?=(async\s+)?(function|const|let|var|class))/gm, "");
}
