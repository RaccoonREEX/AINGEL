import { useEffect, useRef, useState } from "react";
import type { translator } from "./i18n";
import type { Profile } from "./types";

export default function Hear({
  profile,
  t,
}: {
  profile: Profile;
  t: ReturnType<typeof translator>;
}) {
  const [status, setStatus] = useState<
      "idle" | "connecting" | "recording" | "finishing"
    >("idle"),
    [consent, setConsent] = useState(false),
    [error, setError] = useState("");
  const [turns, setTurns] = useState<
    { id: number; text: string; final: boolean }[]
  >([]);
  const socket = useRef<WebSocket | null>(null),
    context = useRef<AudioContext | null>(null),
    stream = useRef<MediaStream | null>(null),
    node = useRef<AudioWorkletNode | null>(null),
    turn = useRef(0),
    flush = useRef<(() => void) | null>(null);
  const cleanup = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    node.current?.disconnect();
    node.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
  };
  useEffect(
    () => () => {
      cleanup();
      socket.current?.close();
    },
    [],
  );
  const start = async () => {
    setError("");
    setTurns([]);
    turn.current = 0;
    setStatus("connecting");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      });
      context.current = new AudioContext({ sampleRate: 24000 });
      if (context.current.sampleRate !== 24000) throw new Error("audio_rate");
      await context.current.audioWorklet.addModule("/pcm-worklet.js");
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/captions/`,
      );
      socket.current = ws;
      ws.onopen = () =>
        ws.send(
          JSON.stringify({
            type: "start",
            locale: profile.locale,
            synthetic: consent,
          }),
        );
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "ready") {
          const ctx = context.current;
          if (!ctx || !stream.current) return;
          const processor = new AudioWorkletNode(ctx, "aingel-pcm");
          node.current = processor;
          processor.port.onmessage = (e) => {
            if (e.data === "flushed") {
              flush.current?.();
              flush.current = null;
            } else if (
              ws.readyState === WebSocket.OPEN &&
              ws.bufferedAmount < 240000
            ) {
              ws.send(e.data);
            } else {
              setError(t("hearError"));
              cleanup();
              ws.close();
            }
          };
          ctx.createMediaStreamSource(stream.current).connect(processor);
          processor.connect(ctx.destination);
          void ctx.resume();
          setStatus("recording");
        }
        if (message.type === "speechStart") {
          turn.current = message.turnId;
        }
        if (
          message.type === "transcript" ||
          message.type === "speechComplete"
        ) {
          const id = message.turnId ?? turn.current;
          setTurns((old) => {
            const next = old.filter((x) => x.id !== id);
            next.push({
              id,
              text: message.transcript || "",
              final: message.type === "speechComplete" || !!message.final,
            });
            return next.sort((a, b) => a.id - b.id);
          });
        }
        if (message.type === "error") {
          setError(t("hearError"));
          cleanup();
        }
        if (message.type === "closed") {
          cleanup();
          setStatus("idle");
        }
      };
      ws.onerror = () => {
        setError(t("hearError"));
        cleanup();
        setStatus("idle");
      };
      ws.onclose = (e) => {
        cleanup();
        setStatus("idle");
        if (e.code !== 1000) setError(t("hearError"));
      };
    } catch {
      cleanup();
      setStatus("idle");
      setError(t("hearError"));
    }
  };
  const stop = async () => {
    setStatus("finishing");
    stream.current?.getTracks().forEach((track) => track.stop());
    if (node.current)
      await Promise.race([
        new Promise<void>((resolve) => {
          flush.current = resolve;
          node.current?.port.postMessage("flush");
        }),
        new Promise<void>((resolve) => setTimeout(resolve, 500)),
      ]);
    cleanup();
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify({ type: "stop" }));
    else setStatus("idle");
  };
  return (
    <>
      <p>{t("hearIntro")}</p>
      <p className="callout">{t("hearPrivacy")}</p>
      <section className="panel">
        <label className="check">
          <input
            type="checkbox"
            checked={consent}
            disabled={status !== "idle"}
            onChange={(e) => setConsent(e.target.checked)}
          />
          {t("hearConsent")}
        </label>
        <div className="actions">
          <button
            className="primary"
            disabled={!consent || status !== "idle"}
            onClick={() => void start()}
          >
            {t("hearStart")}
          </button>
          <button disabled={status !== "recording"} onClick={() => void stop()}>
            {t("hearStop")}
          </button>
        </div>
        <p role="status" className="hint">
          {t(
            status === "recording"
              ? "micActive"
              : status === "connecting"
                ? "loading"
                : status === "finishing"
                  ? "working"
                  : "micOff",
          )}
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="captions" aria-live="polite" aria-label={t("hear")}>
          {turns.map((x) => (
            <p
              key={x.id}
              className={x.final ? "final-caption" : "partial-caption"}
            >
              {x.text}
            </p>
          ))}
        </div>
        <p className="hint">muse-voice-transcribe-1.0 · {t("hearLimit")}</p>
      </section>
    </>
  );
}
