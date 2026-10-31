import { useEffect, useMemo, useRef, useState } from "react";
import type { translator } from "./i18n";
import type { Profile } from "./types";
import { useCommunication } from "./Communication";
import SignClips from "./SignClips";
import AingelOrb from "./components/aingel/AingelOrb";
import { analyserLevel } from "./components/aingel/useAudioLevel";
import PrivateMediaConsent, { audioTestFields } from "./components/PrivateMediaConsent";

export default function Hear({
  profile,
  t,
}: {
  profile: Profile;
  t: ReturnType<typeof translator>;
}) {
  const { value: communication } = useCommunication(profile.id);
  const [privateTest, setPrivateTest] = useState(false);
  const es = profile.locale.toLowerCase().startsWith("es");
  useEffect(() => { setPrivateTest(false); }, [profile.id]);
  const [status, setStatus] = useState<
      "idle" | "connecting" | "recording" | "finishing"
    >("idle"),
    [error, setError] = useState("");
  const [turns, setTurns] = useState<
    { id: number; text: string; final: boolean }[]
  >([]);
  const analyser = useRef<AnalyserNode | null>(null);
  const micLevel = useMemo(() => analyserLevel(() => analyser.current), []);
  const socket = useRef<WebSocket | null>(null),
    context = useRef<AudioContext | null>(null),
    stream = useRef<MediaStream | null>(null),
    node = useRef<AudioWorkletNode | null>(null),
    turn = useRef(0),
    flush = useRef<(() => void) | null>(null),
    generation = useRef(0);
  const cleanup = () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    analyser.current?.disconnect();
    analyser.current = null;
    node.current?.disconnect();
    node.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
  };
  useEffect(
    () => () => {
      generation.current++;
      cleanup();
      socket.current?.close();
    },
    [],
  );
  const start = async () => {
    const testFields = audioTestFields(profile, privateTest);
    setPrivateTest(false);
    const current = ++generation.current;
    setError("");
    setTurns([]);
    turn.current = 0;
    setStatus("connecting");
    try {
      const newStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      });
      if (current !== generation.current) {
        newStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = newStream;
      context.current = new AudioContext({ sampleRate: 24000 });
      if (context.current.sampleRate !== 24000) throw new Error("audio_rate");
      await context.current.audioWorklet.addModule("/pcm-worklet.js");
      if (current !== generation.current) {
        cleanup();
        return;
      }
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/captions/`,
      );
      socket.current = ws;
      ws.onopen = () => {
        if (current !== generation.current) {
          ws.close();
          return;
        }
        ws.send(
          JSON.stringify({
            type: "start",
            locale: profile.locale,
            // Authorization given at sign-up (microphone + Meta); the server checks it.
            profile: profile.id,
            ...testFields,
          }),
        );
      };
      ws.onmessage = (event) => {
        if (current !== generation.current) return;
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          setError(t("hearError"));
          cleanup();
          ws.close();
          return;
        }
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
          const source = ctx.createMediaStreamSource(stream.current);
          const meter = ctx.createAnalyser();
          meter.fftSize = 1024;
          meter.smoothingTimeConstant = 0.65;
          analyser.current = meter;
          source.connect(meter);
          source.connect(processor);
          processor.connect(ctx.destination);
          void ctx.resume();
          setStatus("recording");
        }
        if (message.type === "speechStart") {
          turn.current = message.turnId;
          setTurns((old) =>
            old.some((x) => x.id === message.turnId)
              ? old
              : [...old, { id: message.turnId, text: "", final: false }],
          );
        }
        if (
          message.type === "transcript" ||
          message.type === "speechComplete"
        ) {
          const id = message.turnId ?? turn.current;
          setTurns((old) => {
            const previous = old.find((x) => x.id === id);
            if (previous?.final) return old;
            const next = old.filter((x) => x.id !== id);
            next.push({
              id,
              text: message.transcript || previous?.text || "",
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
        if (current !== generation.current) return;
        setError(t("hearError"));
        cleanup();
        setStatus("idle");
      };
      ws.onclose = (e) => {
        if (current !== generation.current) return;
        cleanup();
        setStatus("idle");
        if (e.code !== 1000) setError(t("hearError"));
      };
    } catch {
      if (current !== generation.current) return;
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
        <h2>{t("signPreference")}</h2>
        {communication && (
          <p>
            {t(
              communication.sign_language === "lsec"
                ? "signLsec"
                : communication.sign_language === "asl"
                  ? "signAsl"
                  : communication.sign_language === "other"
                    ? "signOther"
                    : "signNone",
            )}
          </p>
        )}
        <p>{t("signNotAvailable")}</p>
        <SignClips
          profile={profile}
          communication={communication}
          turns={turns}
          t={t}
        />
      </section>
      <section className="panel">
        <PrivateMediaConsent profile={profile} kind="audio" checked={privateTest} disabled={status !== "idle"} onChange={setPrivateTest} />
        {/* There is no synthetic captions test: live microphone audio could be anyone's (assistance.synthetic). */}
        <p className="hint">{es ? "Los subtítulos en vivo envían el audio del micrófono a Meta solo con la autorización «Enviar voz a Meta» de la persona." : "Live captions send microphone audio to Meta only with the person's «Send voice to Meta» authorization."}</p>
        <div className="hear-orb"><AingelOrb state={status === "recording" ? "listening" : status === "connecting" || status === "finishing" ? "thinking" : error ? "retrying" : "idle"} audioLevel={micLevel} reducedMotion={profile.preferences.reduced_motion} size={200} /></div>
        <div className="actions">
          <button
            className="primary"
            disabled={status !== "idle"}
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
