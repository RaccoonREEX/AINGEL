import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import type { Context, WithProfile } from "../ui";
import type { Key } from "../i18n";
import { activityLabel } from "../i18n";
import type {
  Circle,
  Member,
  Memory,
  Profile,
  Routine,
  CareMessage,
  Scene,
  Located,
} from "../types";
export default function See({ profile, t, locale, busy, run }: WithProfile) {
  const [located, setLocated] = useState<Located | null>(null),
    [objectName, setObjectName] = useState("");
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [result, setResult] = useState<Scene | null>(null),
    [voiceMessage, setVoiceMessage] = useState("");
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => setLocated(null), [file]);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  const fixture = () => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, 640, 480);
    ctx.fillStyle = "blue";
    ctx.fillRect(60, 150, 160, 160);
    ctx.fillStyle = "red";
    ctx.beginPath();
    ctx.arc(460, 230, 80, 0, Math.PI * 2);
    ctx.fill();
    canvas.toBlob((blob) => {
      if (blob) {
        setFile(
          new File([blob], "synthetic-shapes.png", { type: "image/png" }),
        );
        setConfirmed(true);
        setResult(null);
      }
    }, "image/png");
  };
  const speak = () => {
    if (!result) return;
    const synth = window.speechSynthesis;
    if (!synth) {
      setVoiceMessage(t("noVoice"));
      return;
    }
    const voices = synth.getVoices();
    const voice = voices.find((x) =>
      x.lang.toLowerCase().startsWith(profile.locale.slice(0, 2)),
    );
    if (!voice) {
      setVoiceMessage(t("noVoice"));
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(result.text);
    utterance.lang = profile.locale;
    utterance.voice = voice;
    synth.speak(utterance);
  };
  useEffect(() => {
    if (result && profile.preferences.voice_output) speak();
  }, [result, profile.preferences.voice_output]);
  return (
    <>
      <p>{t("seeIntro")}</p>
      <p className="callout">{t("syntheticOnly")}</p>
      <section className="panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            const form = new FormData();
            form.set("image", file);
            form.set("locale", profile.locale);
            form.set("synthetic", String(confirmed));
            void run(async () => {
              setResult(null);
              setResult(await api<Scene>("scene/", "POST", form));
            });
          }}
        >
          <div className="actions">
            <Field label={t("chooseImage")}>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setConfirmed(false);
                  setResult(null);
                }}
              />
            </Field>
            <button type="button" disabled={busy} onClick={fixture}>
              {t("useFixture")}
            </button>
          </div>
          {preview && (
            <div className="vision-stage">
              <img src={preview} alt={t("preview")} />
              {located?.matches.map((m) => (
                <div
                  key={m.id}
                  className="object-overlay"
                  style={{
                    insetInlineStart: `${m.box[0] * 100}%`,
                    top: `${m.box[1] * 100}%`,
                    width: `${(m.box[2] - m.box[0]) * 100}%`,
                    height: `${(m.box[3] - m.box[1]) * 100}%`,
                  }}
                >
                  <img src={m.mask_png} alt="" />
                  <span>{m.id}</span>
                </div>
              ))}
            </div>
          )}
          <label className="check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            {t("syntheticConsent")}
          </label>
          <button disabled={busy || !file || !confirmed} className="primary">
            {t("analyze")}
          </button>
        </form>
        <hr />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            const form = new FormData();
            form.set("image", file);
            form.set("locale", profile.locale);
            form.set("synthetic", String(confirmed));
            form.set("object_name", objectName);
            void run(async () => {
              setLocated(null);
              setLocated(await api<Located>("locate/", "POST", form));
            });
          }}
        >
          <h2>{t("locate")}</h2>
          <Field label={t("objectPrompt")}>
            <input
              required
              maxLength={80}
              value={objectName}
              onChange={(e) => setObjectName(e.target.value)}
            />
          </Field>
          <p className="hint">{t("objectPromptHint")}</p>
          <button
            className="primary"
            disabled={busy || !file || !confirmed || !objectName.trim()}
          >
            {t("locate")}
          </button>
        </form>
        {located && (
          <div aria-live="polite">
            <h3>{t("matches")}</h3>
            <span className="badge">
              {t(located.mode === "meta" ? "meta" : "mock")}
            </span>
            <p className="hint">
              {located.model || "—"} ·{" "}
              {located.latency_ms === null ? "—" : `${located.latency_ms} ms`}
            </p>
            {located.analyzed && !located.matches.length && (
              <p>{t("notFound")}</p>
            )}
            {located.matches.map((m) => (
              <p key={m.id}>
                {m.id} · {t(m.horizontal)}
                {m.confidence !== null &&
                  ` · ${Math.round(m.confidence * 100)}%`}
              </p>
            ))}
            <p className="hint">{t("samHint")}</p>
          </div>
        )}
      </section>
      {result && (
        <section className="panel" aria-live="polite">
          <span className="badge">
            {t(result.mode === "meta" ? "meta" : "mock")}
          </span>
          <h2>{t("result")}</h2>
          <p className="scene-result">{result.text}</p>
          <p className="hint">
            {result.model || "—"}{" "}
            {result.latency_ms !== null &&
              `· ${t("latency")}: ${new Intl.NumberFormat(locale).format(result.latency_ms / 1000)} s`}
          </p>
          <div className="actions">
            <button onClick={speak}>{t("speak")}</button>
            <button onClick={() => window.speechSynthesis?.cancel()}>
              {t("stopSpeaking")}
            </button>
          </div>
          {voiceMessage && <p role="status">{voiceMessage}</p>}
        </section>
      )}
    </>
  );
}
