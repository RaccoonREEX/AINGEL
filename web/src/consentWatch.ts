import { useCallback, useEffect, useMemo, useRef } from "react";
import { api } from "./api";
import type { ConsentState } from "./types";

/**
 * The person's consent for captures, one of three separate layers:
 * - the browser's permission (getUserMedia) says whether this page may reach the hardware;
 * - the person's consent (care.consent: camera_local, microphone_local, meta_*) says whether they allow it at all;
 * - the backend checks its authorization on every request and refuses or discards (403 / 400 / 409).
 * A camera or microphone opens only with the person's current grant, read fresh just before. While something is open
 * or pending, the state is re-read every 15 s and whenever this browser records a decision: a revocation stops the
 * captures it covers, aborts pending requests and drops late answers. A new grant is needed to start again.
 */
export type Capture = "camera" | "microphone";
export type ConsentChange = { epoch: boolean; camera: boolean; microphone: boolean; unverified?: boolean };

const PURPOSE: Record<Capture, string> = { camera: "camera_local", microphone: "microphone_local" };
export const CONSENT_CHANGED = "aingel:consent-changed";
const POLL_MS = 15000;

export function purposeStatus(state: ConsentState | null, purpose: string) {
  return state?.purposes.find((p) => p.id === purpose)?.status ?? "pending";
}

export function mayStart(state: ConsentState | null, capture: Capture) {
  return purposeStatus(state, PURPOSE[capture]) === "granted";
}

/** What a new state means for what is running: the epoch moves on every decline or revocation. */
export function consentChange(previous: ConsentState | null, current: ConsentState): ConsentChange {
  return {
    epoch: !!previous && previous.epoch !== current.epoch,
    camera: mayStart(previous, "camera") && !mayStart(current, "camera"),
    microphone: mayStart(previous, "microphone") && !mayStart(current, "microphone"),
  };
}

/** Backend answers that mean the capture or request is no longer authorized. */
export function stopsCapture(code: string) {
  return code === "consent_changed" || code === "privacy_review_required" || code === "camera_consent_revoked";
}

/** Tells the open screens of this browser that a decision was just recorded for [profileId]. */
export function announceConsentChange(profileId: string) {
  window.dispatchEvent(new CustomEvent(CONSENT_CHANGED, { detail: { profileId } }));
}

/** The watch itself, without React: [load] reads the current state, [onChange] stops what a change covers. */
export function createConsentWatcher(load: () => Promise<ConsentState>, onChange: (change: ConsentChange) => void) {
  let state: ConsentState | null = null;
  let failures = 0;
  const refresh = async () => {
    const next = await load();
    const change = consentChange(state, next);
    state = next;
    failures = 0;
    if (change.epoch || change.camera || change.microphone) onChange(change);
    return next;
  };
  return {
    refresh,
    /** A fresh check right before opening a capture; false when it cannot be verified. */
    allowed: async (capture: Capture) => {
      try { return mayStart(await refresh(), capture); } catch { return false; }
    },
    /** One periodic check while something is open: two in a row that cannot be made stop everything. */
    tick: async () => {
      try { await refresh(); } catch {
        if (++failures >= 2) onChange({ epoch: true, camera: true, microphone: true, unverified: true });
      }
    },
  };
}

export function useConsentWatch(profileId: string, active: boolean, onChange: (change: ConsentChange) => void) {
  const handler = useRef(onChange);
  handler.current = onChange;
  const watcher = useMemo(
    () => createConsentWatcher(() => api<ConsentState>(`profiles/${profileId}/consent/`), (change) => handler.current(change)),
    [profileId],
  );

  useEffect(() => {
    const changed = (e: Event) => { if ((e as CustomEvent).detail?.profileId === profileId) void watcher.refresh().catch(() => {}); };
    window.addEventListener(CONSENT_CHANGED, changed);
    return () => window.removeEventListener(CONSENT_CHANGED, changed);
  }, [profileId, watcher]);

  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => void watcher.tick(), POLL_MS);
    return () => window.clearInterval(id);
  }, [active, watcher]);

  const allowed = useCallback((capture: Capture) => watcher.allowed(capture), [watcher]);
  return { allowed, refresh: watcher.refresh };
}
