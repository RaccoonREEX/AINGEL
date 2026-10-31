import { localVoice } from "../components/aingel/browserSpeech";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import PrivateMediaConsent, { imageTestFields } from "../components/PrivateMediaConsent";
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
  const [privateTest, setPrivateTest] = useState(false);
  const [located, setLocated] = useState<Located | null>(null),
    [objectName, setObjectName] = useState("");
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
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
  // A preview of the server's synthetic fixture «shapes»: choosing it sends only the fixture id, never this file.
  const bundled = useRef<File | null>(null);
  const [fixtureObject, setFixtureObject] = useState("red_circle");
  useEffect(() => { setLocated(null); setPrivateTest(false); }, [file, profile.id]);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  const fixture = () => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext("2d")!;
    // Same drawing as the server fixture (assistance.synthetic.shapes_image).
    ctx.fillStyle = "rgb(236,236,232)";
    ctx.fillRect(0, 0, 640, 480);
    ctx.fillStyle = "rgb(30,80,200)";
    ctx.fillRect(90, 170, 141, 141);
    ctx.fillStyle = "rgb(210,40,40)";
    ctx.beginPath();
    ctx.arc(480, 240, 70, 0, Math.PI * 2);
    ctx.fill();
    canvas.toBlob((blob) => {
      if (blob) {
        bundled.current = new File([blob], "synthetic-shapes.png", { type: "image/png" });
        setFile(bundled.current);
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
    // Local voices only: a network voice would send the description to its provider.
    const voice = localVoice(profile.locale);
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
            form.set("locale", profile.locale);
            if (file === bundled.current) form.set("fixture", "shapes");
            else {
              // A real image: only under the person's own grants (camera + photos to Meta).
              form.set("image", file);
              form.set("profile", profile.id);
              for (const [key, value] of Object.entries(imageTestFields(profile, privateTest))) form.set(key, String(value));
            }
            setPrivateTest(false);
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
          {file && file !== bundled.current && <PrivateMediaConsent profile={profile} kind="image" checked={privateTest} onChange={setPrivateTest} disabled={busy} />}
          <button disabled={busy || !file} className="primary">
            {t("analyze")}
          </button>
        </form>
        <hr />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file) return;
            const form = new FormData();
            form.set("locale", profile.locale);
            if (file === bundled.current) form.set("fixture", fixtureObject);
            else {
              form.set("image", file);
              form.set("profile", profile.id);
              for (const [key, value] of Object.entries(imageTestFields(profile, privateTest))) form.set(key, String(value));
              form.set("object_name", objectName);
            }
            setPrivateTest(false);
            void run(async () => {
              setLocated(null);
              setLocated(await api<Located>("locate/", "POST", form));
            });
          }}
        >
          <h2>{t("locate")}</h2>
          <Field label={t("objectPrompt")}>
            {file && file === bundled.current ? (
              // The synthetic test only offers the server's objects: nothing typed is sent.
              <select value={fixtureObject} onChange={(e) => setFixtureObject(e.target.value)}>
                <option value="red_circle">{locale === "es-EC" ? "Círculo rojo" : "Red circle"}</option>
                <option value="blue_square">{locale === "es-EC" ? "Cuadrado azul" : "Blue square"}</option>
              </select>
            ) : (
              <input
                required
                maxLength={80}
                value={objectName}
                onChange={(e) => setObjectName(e.target.value)}
              />
            )}
          </Field>
          <p className="hint">{t("objectPromptHint")}</p>
          <button
            className="primary"
            disabled={busy || !file || (file !== bundled.current && !objectName.trim())}
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
