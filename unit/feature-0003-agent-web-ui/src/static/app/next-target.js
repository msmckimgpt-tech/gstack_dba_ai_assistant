/* feature-0041 — 로그인 후 복귀 대상(`?next=`) 안전성 판정.
 *
 * DOM 에 의존하지 않는 순수 함수만 둔다 — 이 판정이 틀리면 **로그인 직후 오픈 리다이렉트**가
 * 되므로(피싱·자격증명 유도), 브라우저 없이 실행해서 검증할 수 있어야 한다.
 *
 * ⚠ 문자열 검사로는 부족하다. codex 리뷰가 잡은 실제 우회:
 *     "/\\evil.com"  →  `startsWith("/")` 통과 · `startsWith("//")` 미통과
 *   그런데 브라우저는 `\` 를 `/` 로 정규화해 **https://evil.com/ 으로 나간다.**
 *   그래서 문자열이 아니라 **URL 해석 결과의 origin** 을 비교한다.
 */

/**
 * @param {string} raw   `?next=` 원문
 * @param {string} origin 현재 오리진(예: "https://host")
 * @returns {string|null} 안전하면 이동할 경로, 아니면 null
 */
export function safeNextTarget(raw, origin) {
  const value = String(raw || "");
  if (!value) return null;
  let url;
  try {
    url = new URL(value, origin);
  } catch (_e) {
    return null;
  }
  if (url.origin !== origin) return null;
  // 스킴 상대(`//host`)·역슬래시 변형은 위 origin 비교에서 걸리지만, javascript: 같은
  // opaque origin 은 "null" 로 비교를 통과할 수 있는 환경이 있어 명시적으로 막는다.
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  return url.pathname + url.search + url.hash;
}
