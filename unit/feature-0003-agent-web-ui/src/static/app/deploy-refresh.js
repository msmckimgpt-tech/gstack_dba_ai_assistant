import { startUiRefresh } from "../ui-refresh.js?v=dev";
import { captureAttachmentDiffState, restoreAttachmentDiffState } from "./attach-diff.js?v=dev";

const RESUME_KEY = "dqa.uiRefresh.resume.v1";
let stopWatching = null;
let composing = false;
let dragging = false;
let pointerHeld = false;
let lastInteraction = 0;

export function readAppRefreshResume(user, storage = window.sessionStorage) {
  try {
    const raw = storage.getItem(RESUME_KEY);
    if (!raw || raw.length > 100000) return null;
    const value = JSON.parse(raw);
    if (value.account !== String(user?.id || "") || !value.account
        || Date.now() - value.at > 300000 || value.at > Date.now()
        || typeof value.conversationId !== "string") {
      storage.removeItem(RESUME_KEY);
      return null;
    }
    return value;
  } catch (_) { return null; }
}

const visible = element => !element.hidden && !element.closest(".hidden") && element.getClientRects().length > 0;

export function appRefreshSafe(state, doc = document) {
  if (!state.user || composing || dragging || pointerHeld || Date.now() - lastInteraction < 1200
      || state.uiMutations > 0 || state.dqaDrag || state.pendingFolderUndo
      || state.sidebarRenameDraft || state.folderRenamingId || state.conversationRenamingId
      || state.myAskInFlight?.size || state.askAbortControllers?.size
      || state.busyConversations?.size || state.pendingConversationEntries?.size
      || state.pendingBubble || state.shareRange || state.searchModal?.open
      || state.composerAttachments?.uploadingCount || state.composerAttachments?.lazyConvCreating
      || Object.values(state.composerAttachments?.byConv || {}).some(bucket =>
        bucket.items?.some(item => item.status !== "ready" || item.source !== "session"))) return false;
  if (doc.querySelectorAll('[data-ui-refresh-restorable]').length > 1) return false;
  for (const element of doc.querySelectorAll('[role="dialog"], .share-mgr-backdrop, #profileDrawer')) {
    if (visible(element) && !element._dqaUiSnapshot) return false;
  }
  for (const element of doc.querySelectorAll('textarea:not([readonly]), input, [contenteditable="true"]')) {
    if (!visible(element) || element.disabled || element.closest('[data-ui-refresh-restorable]')) continue;
    if (element.isContentEditable || element.files?.length) return false;
    if (!['checkbox', 'radio', 'button', 'submit', 'hidden', 'range'].includes(element.type)
        && String(element.value || "").length) return false;
  }
  return true;
}

function messagePosition(log) {
  const rect = log.getBoundingClientRect();
  const row = Array.from(log.querySelectorAll('[data-message-id]'))
    .find(element => element.getBoundingClientRect().bottom > rect.top);
  return { id: row?.dataset.messageId || "", offset: row ? row.getBoundingClientRect().top - rect.top : 0,
    bottom: log.scrollHeight - log.scrollTop - log.clientHeight < 80 };
}

export async function restoreAppRefresh(resume, { state, messageLog, renderComposer, releaseScrollPin, notify }) {
  if (!resume || resume.account !== String(state.user?.id || "")
      || resume.conversationId !== state.activeConversationId) return;
  try {
    // Only non-secret selection metadata crosses navigation; user text and files never do.
    if (typeof resume.model === "string" && resume.model.length < 200) {
      state.selectedModel = resume.model;
      state._modelPickedAt = Date.now();
      state._modelPickedForConvId = state.activeConversationId;
    }
    renderComposer();
    if (!resume.scroll?.bottom && resume.scroll?.id) {
      releaseScrollPin?.();
      const row = Array.from(messageLog.querySelectorAll('[data-message-id]'))
        .find(element => element.dataset.messageId === resume.scroll.id);
      if (row) messageLog.scrollTop += row.getBoundingClientRect().top
        - messageLog.getBoundingClientRect().top - Number(resume.scroll.offset || 0);
    }
    if (resume.diff) await restoreAttachmentDiffState(resume.diff);
    window.sessionStorage.removeItem(RESUME_KEY);
    notify?.("업데이트가 적용되었습니다.");
  } catch (_) { /* A failed restore leaves the current authenticated page available. */ }
}

export function installAppRefresh({ state, messageLog, notify, stamp }) {
  if (stopWatching) stopWatching();
  const interaction = () => { lastInteraction = Date.now(); };
  const beginPointer = () => { pointerHeld = true; interaction(); };
  const endPointer = () => { pointerHeld = false; interaction(); };
  const beginComposition = () => { composing = true; interaction(); };
  const endComposition = () => { composing = false; interaction(); };
  const beginDrag = () => { dragging = true; };
  const endDrag = () => { dragging = false; interaction(); };
  const listeners = [['input', interaction], ['pointerdown', beginPointer], ['pointerup', endPointer],
    ['pointercancel', endPointer], ['keydown', interaction],
    ['compositionstart', beginComposition], ['compositionend', endComposition],
    ['dragstart', beginDrag], ['dragend', endDrag], ['drop', endDrag]];
  for (const [event, handler] of listeners) document.addEventListener(event, handler, true);
  window.addEventListener("blur", endPointer);
  let stop;
  try {
    stop = startUiRefresh({ stamp, notify,
      canApply: () => appRefreshSafe(state),
      prepare: () => {
        const resume = { account: String(state.user?.id || ""), at: Date.now(),
          conversationId: String(state.activeConversationId || ""),
          model: typeof state.selectedModel === "string" ? state.selectedModel : null,
          attachmentSelections: Object.fromEntries(Object.entries(state.composerAttachments?.byConv || {})
            .map(([cid, bucket]) => [cid, (bucket.items || []).map(item => [Number(item.id), item.selected !== false])])),
          scroll: messagePosition(messageLog), diff: captureAttachmentDiffState() };
        const raw = JSON.stringify(resume);
        if (raw.length > 100000) return false;
        window.sessionStorage.setItem(RESUME_KEY, raw);
        return true;
      },
    });
  } catch (_) { /* Storage may be disabled; never reload without recovery metadata. */ }
  stopWatching = () => {
    stop?.();
    for (const [event, handler] of listeners) document.removeEventListener(event, handler, true);
    window.removeEventListener("blur", endPointer);
  };
}
