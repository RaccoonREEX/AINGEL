import { useCallback, useEffect, useRef, useState } from "react";

export type CameraFailure = "denied" | "unavailable";

/**
 * Camera for explicit, one-off captures. Opens only on start(), never records, and releases the
 * device on stop() and on unmount. capture() returns the full frame as JPEG, kept in memory.
 */
export function useCamera() {
  const video = useRef<HTMLVideoElement | null>(null);
  const stream = useRef<MediaStream | null>(null);
  // Bumped by stop() / unmount and by every start(): a stream that arrives for an older generation is released.
  const generation = useRef(0);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<"" | CameraFailure>("");

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setActive(false);
  }, []);
  const stop = useCallback(() => { generation.current++; release(); }, [release]);

  /** Resolves true when the camera is on, the failure reason (the `error` state lags a render behind), or null
   * when stop() / unmount / a newer start() superseded this call (not a failure: nothing to report). */
  const start = useCallback(async (facing: "environment" | "user" = "environment"): Promise<true | CameraFailure | null> => {
    const gen = ++generation.current;
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) { setError("unavailable"); return "unavailable"; }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, width: { ideal: 1280 } }, audio: false });
      // stop(), unmount or a newer start() happened while the permission prompt was open.
      if (gen !== generation.current) { media.getTracks().forEach((t) => t.stop()); return null; }
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = media;
      if (video.current) { video.current.srcObject = media; await video.current.play().catch(() => {}); }
      if (gen !== generation.current) return null; // stop() already released it
      setActive(true);
      return true;
    } catch (e) {
      if (gen !== generation.current) return null;
      const reason: CameraFailure = e instanceof DOMException && (e.name === "NotAllowedError" || e.name === "SecurityError") ? "denied" : "unavailable";
      setError(reason);
      release();
      return reason;
    }
  }, [release]);

  /** Attach the <video> element; re-binds the live stream if the element changes. */
  const bind = useCallback((element: HTMLVideoElement | null) => {
    video.current = element;
    if (element && stream.current && element.srcObject !== stream.current) {
      element.srcObject = stream.current;
      void element.play().catch(() => {});
    }
  }, []);

  const capture = useCallback(async (): Promise<Blob | null> => {
    const v = video.current;
    if (!v || !v.videoWidth) return null;
    const scale = Math.min(1, 1600 / Math.max(v.videoWidth, v.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(v.videoWidth * scale); canvas.height = Math.round(v.videoHeight * scale);
    canvas.getContext("2d")!.drawImage(v, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.88));
  }, []);

  useEffect(() => stop, [stop]);
  return { bind, start, stop, capture, active, error };
}
