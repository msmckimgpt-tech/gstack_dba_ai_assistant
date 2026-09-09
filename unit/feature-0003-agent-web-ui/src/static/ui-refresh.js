// A completed deployment is applied once, at a safe point chosen by the page.
const ATTEMPT_KEY = "dqa.uiRefresh.attempt.v1";

export function createUiRefresh({ stamp, fetchRelease, canApply, prepare, apply,
  storage, notify = () => {}, now = Date.now, isActive = () => true }) {
  let baseline = null;
  let generation = 0;
  let inFlight = false;
  let applied = false;
  let notified = "";

  return async function check() {
    if (inFlight || applied || !isActive() || !/^[a-f0-9]{12}$/.test(stamp)) return;
    inFlight = true;
    try {
      const release = await fetchRelease();
      if (!isActive() || release?.status !== "complete"
          || !/^[a-f0-9]{12}$/.test(release.asset_stamp || "")
          || !/^[a-f0-9]{7,40}$/.test(release.release || "")
          || !Number.isSafeInteger(release.generation) || release.generation <= 0
          || release.generation < generation) return;
      generation = release.generation;
      const target = `${release.release}:${release.asset_stamp}`;
      if (release.asset_stamp === stamp && (baseline === null || baseline === release.release)) {
        baseline = release.release;
        storage.removeItem(ATTEMPT_KEY);
        return;
      }
      if (!canApply()) {
        if (notified !== target) {
          notified = target;
          notify("업데이트가 준비되었습니다. 현재 작업이 끝나면 자동 적용됩니다.");
        }
        return;
      }
      let previous = {};
      try { previous = JSON.parse(storage.getItem(ATTEMPT_KEY) || "{}"); } catch (_) {}
      const recent = previous?.target === target && now() - previous.at < 300000;
      if (recent && previous.count >= 2) {
        if (notified !== `failed:${target}`) {
          notified = `failed:${target}`;
          notify("업데이트 적용을 기다리고 있습니다. 연결이 안정되면 다시 시도합니다.");
        }
        return;
      }
      // Both callbacks are synchronous: input cannot change between the final gate and navigation.
      if (!isActive() || prepare(release) === false || !isActive() || !canApply()) return;
      storage.setItem(ATTEMPT_KEY, JSON.stringify({ target, at: now(), count: recent ? previous.count + 1 : 1 }));
      applied = true;
      try { apply(release); } catch (error) { applied = false; throw error; }
    } catch (_) {
      // Network/storage failures leave the current page and work intact.
    } finally {
      inFlight = false;
    }
  };
}

export function startUiRefresh(options) {
  let stopped = false;
  const controller = createUiRefresh({
    storage: window.sessionStorage,
    apply: () => window.location.reload(),
    fetchRelease: async () => {
      const abort = new AbortController();
      const timer = window.setTimeout(() => abort.abort(), 5000);
      try {
        const response = await fetch("/api/ui-release", {
          cache: "no-store", credentials: "same-origin", signal: abort.signal,
        });
        if (!response.ok) return null;
        return await response.json();
      } finally { window.clearTimeout(timer); }
    },
    ...options,
    isActive: () => !stopped,
  });
  let timer;
  const tick = async () => {
    await controller();
    if (!stopped) timer = window.setTimeout(tick, 3000);
  };
  const wake = () => { if (!document.hidden) controller(); };
  document.addEventListener("visibilitychange", wake);
  window.addEventListener("online", wake);
  tick();
  return () => {
    stopped = true;
    window.clearTimeout(timer);
    document.removeEventListener("visibilitychange", wake);
    window.removeEventListener("online", wake);
  };
}
