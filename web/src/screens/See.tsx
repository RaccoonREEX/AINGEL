import { localVoice } from "../components/aingel/browserSpeech";
import { useEffect, useRef, useState } from "react";
import { APIError, api } from "../api";
import Field from "../components/Field";
import PrivateMediaConsent, { imageTestFields } from "../components/PrivateMediaConsent";
import {
  endsSession, FIXTURES, followUpForm, LEVEL_NAMES, LEVELS, REGION_NAMES, REGIONS, speechParts, visionForm,
  type DetailLevel, type Region, type VisionResult,
} from "../components/aingel/vision";
import type { WithProfile } from "../ui";
import type { Located } from "../types";

type Turn = { asked: string; result: VisionResult };

export default function See({ profile, t, locale, busy, run }: WithProfile) {
  const es = locale === "es-EC";
  const L = (spanish: string, english: string) => (es ? spanish : english);
  const [privateTest, setPrivateTest] = useState(false);
  const [located, setLocated] = useState<Located | null>(null),
    [objectName, setObjectName] = useState("");
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
    [voiceMessage, setVoiceMessage] = useState("");
  // A server fixture: choosing it sends only its id. «shapes» is also drawn here as a preview.
  const [fixture, setFixture] = useState<string | null>(null),
    [fixturePick, setFixturePick] = useState("drawing_dog");
  const [question, setQuestion] = useState(""),
    [level, setLevel] = useState<DetailLevel | "">("");
  // Answers about the current picture; follow-ups use the server's session until it ends.
  const [turns, setTurns] = useState<Turn[]>([]),
    [session, setSession] = useState<{ token: string; until: number } | null>(null),
    [followUp, setFollowUp] = useState(""),
    [region, setRegion] = useState<Region | "">("");
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const [fixtureObject, setFixtureObject] = useState("red_circle");
  useEffect(() => { setLocated(null); setPrivateTest(false); }, [file, fixture, profile.id]);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  const closeSession = () => {
    // Done with the picture: the server deletes it now instead of at the end of its session.
    if (session) void api(`vision/sessions/${session.token}/`, "DELETE").catch(() => undefined);
    setSession(null); setTurns([]); setFollowUp(""); setRegion("");
  };
  const choosePicture = (next: File | null, nextFixture: string | null) => {
    closeSession();
    setFile(next); setFixture(nextFixture);
  };
  const drawShapes = () => {
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
      if (blob) choosePicture(new File([blob], "synthetic-shapes.png", { type: "image/png" }), "shapes");
    }, "image/png");
  };
  const useFixture = () => (fixturePick === "shapes" ? drawShapes() : choosePicture(null, fixturePick));
  const latest = turns.at(-1)?.result ?? null;
  const speak = (result: VisionResult | null = latest) => {
    if (!result) return;
    const synth = window.speechSynthesis;
    // Local voices only: a network voice would send the description to its provider.
    const voice = synth ? localVoice(profile.locale) : null;
    if (!synth || !voice) {
      setVoiceMessage(t("noVoice"));
      return;
    }
    synth.cancel();
    // Long descriptions in parts: some browsers stop a single long utterance midway.
    for (const part of speechParts(result.text)) {
      const utterance = new SpeechSynthesisUtterance(part);
      utterance.lang = profile.locale;
      utterance.voice = voice;
      synth.speak(utterance);
    }
  };
  useEffect(() => {
    if (latest && profile.preferences.voice_output) speak(latest);
  }, [latest, profile.preferences.voice_output]);
  const answered = (asked: string, result: VisionResult) => {
    setTurns((all) => [...all, { asked, result }]);
    if (result.session && result.session_seconds) setSession({ token: result.session, until: Date.now() + result.session_seconds * 1000 - 5000 });
  };
  const failed = (error: unknown) => {
    const code = error instanceof APIError ? String((error.detail as { error?: unknown } | null)?.error ?? "") : "";
    if (endsSession(code)) setSession(null);
    throw error;
  };
  const sessionLive = session !== null && Date.now() < session.until;
  const levelName = (value: DetailLevel) => LEVEL_NAMES[value][es ? 0 : 1];
  return (
    <>
      <p>{t("seeIntro")}</p>
      <p className="callout">{t("syntheticOnly")}</p>
      <section className="panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file && !fixture) return;
            const asked = question.trim() || L("Describir la imagen", "Describe the image");
            const form = fixture
              ? visionForm(profile.locale, { fixture }, level)
              // A real image: only under the person's own grants (camera + photos to Meta).
              : visionForm(profile.locale, { image: file!, profile: profile.id, testFields: imageTestFields(profile, privateTest), question }, level);
            setPrivateTest(false);
            void run(async () => {
              closeSession();
              answered(asked, await api<VisionResult>("vision/", "POST", form).catch(failed));
            });
          }}
        >
          <div className="actions">
            <Field label={t("chooseImage")}>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => choosePicture(e.target.files?.[0] || null, null)}
              />
            </Field>
            <Field label={L("Imagen sintética del servidor", "Server synthetic image")}>
              <select value={fixturePick} onChange={(e) => setFixturePick(e.target.value)}>
                {Object.entries(FIXTURES).map(([id, names]) => <option key={id} value={id}>{names[es ? 0 : 1]}</option>)}
              </select>
            </Field>
            <button type="button" disabled={busy} onClick={useFixture}>
              {t("useFixture")}
            </button>
          </div>
          {fixture && fixture !== "shapes" && <p className="hint">{L("Imagen elegida", "Chosen image")}: {FIXTURES[fixture][es ? 0 : 1]}. {L("La dibuja el servidor; no se muestra aquí.", "The server draws it; it is not shown here.")}</p>}
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
          <div className="actions">
            <Field label={L("Nivel de detalle", "Level of detail")}>
              <select value={level} onChange={(e) => setLevel(e.target.value as DetailLevel | "")}>
                <option value="">{L("Según la pregunta", "From the question")}</option>
                {LEVELS.map((value) => <option key={value} value={value}>{levelName(value)}</option>)}
              </select>
            </Field>
            {file && !fixture && (
              <Field label={L("Tu pregunta (opcional)", "Your question (optional)")}>
                <input maxLength={600} value={question} onChange={(e) => setQuestion(e.target.value)}
                  placeholder={L("Por ejemplo: descríbeme este dibujo a detalle", "For example: describe this drawing in depth")} />
              </Field>
            )}
          </div>
          {fixture && <p className="hint">{L("Con una imagen sintética no se envía texto escrito: elige el nivel o una zona.", "With a synthetic image no typed text is sent: choose the level or an area.")}</p>}
          {file && !fixture && <PrivateMediaConsent profile={profile} kind="image" checked={privateTest} onChange={setPrivateTest} disabled={busy} />}
          <p className="hint">{L(
            "«A fondo» analiza la imagen por zonas en varios pasos y puede tardar hasta un minuto. Para tus preguntas de seguimiento, el servidor guarda la imagen cifrada hasta 15 minutos y luego la borra.",
            "«In depth» analyses the image by areas in several steps and can take up to a minute. For your follow-up questions the server keeps the image encrypted for up to 15 minutes, then deletes it.",
          )}</p>
          <button disabled={busy || (!file && !fixture)} className="primary">
            {t("analyze")}
          </button>
        </form>
        <hr />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!file && fixture !== "shapes") return;
            const form = new FormData();
            form.set("locale", profile.locale);
            if (fixture === "shapes") form.set("fixture", fixtureObject);
            else {
              form.set("image", file!);
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
            {fixture === "shapes" ? (
              // The synthetic test only offers the server's objects: nothing typed is sent.
              <select value={fixtureObject} onChange={(e) => setFixtureObject(e.target.value)}>
                <option value="red_circle">{L("Círculo rojo", "Red circle")}</option>
                <option value="blue_square">{L("Cuadrado azul", "Blue square")}</option>
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
            disabled={busy || (fixture !== "shapes" && (!file || !!fixture || !objectName.trim()))}
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
      {turns.length > 0 && (
        <section className="panel" aria-live="polite">
          <h2>{t("result")}</h2>
          {turns.map(({ asked, result }, index) => (
            <article key={index} className="vision-turn">
              <p className="hint"><strong>{asked}</strong></p>
              <span className="badge">{t(result.mode === "meta" ? "meta" : "mock")}</span>
              {(result.paragraphs?.length ? result.paragraphs : [result.text]).map((paragraph, i) => <p key={i} className="scene-result">{paragraph}</p>)}
              <p className="hint">
                {result.model || "—"} · {levelName(result.level)}
                {result.steps > 1 && ` · ${result.steps} ${L("pasos", "steps")}`}
                {result.latency_ms !== null && ` · ${t("latency")}: ${new Intl.NumberFormat(locale).format(result.latency_ms / 1000)} s`}
              </p>
            </article>
          ))}
          <div className="actions">
            <button onClick={() => speak()}>{t("speak")}</button>
            <button onClick={() => window.speechSynthesis?.cancel()}>
              {t("stopSpeaking")}
            </button>
          </div>
          {voiceMessage && <p role="status">{voiceMessage}</p>}
          {sessionLive ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const ask = fixture ? { region, level } : { question: followUp, region, level };
                const asked = followUp.trim() || [region && REGION_NAMES[region][es ? 0 : 1], level && levelName(level)].filter(Boolean).join(" · ") || L("Otra vez", "Again");
                void run(async () => {
                  answered(asked, await api<VisionResult>("vision/", "POST", followUpForm(profile.locale, session!.token, ask)).catch(failed));
                  setFollowUp("");
                });
              }}
            >
              <h3>{L("Seguir preguntando sobre esta imagen", "Keep asking about this image")}</h3>
              <div className="actions">
                {!fixture && (
                  <Field label={L("Pregunta", "Question")}>
                    <input maxLength={600} value={followUp} onChange={(e) => setFollowUp(e.target.value)}
                      placeholder={L("¿Y sus ojos? ¿Qué hay en el fondo?", "And the eyes? What is in the background?")} />
                  </Field>
                )}
                <Field label={L("Zona", "Area")}>
                  <select value={region} onChange={(e) => setRegion(e.target.value as Region | "")}>
                    <option value="">{L("Toda la imagen", "Whole image")}</option>
                    {REGIONS.map((value) => <option key={value} value={value}>{REGION_NAMES[value][es ? 0 : 1]}</option>)}
                  </select>
                </Field>
              </div>
              <div className="actions">
                <button className="primary" disabled={busy || (!followUp.trim() && !region && !level)}>{L("Preguntar", "Ask")}</button>
                <button type="button" disabled={busy} onClick={closeSession}>{L("Terminar con esta imagen", "Done with this image")}</button>
              </div>
            </form>
          ) : (
            <p className="hint">{L("Para seguir preguntando, describe la imagen otra vez.", "To keep asking, describe the image again.")}</p>
          )}
        </section>
      )}
    </>
  );
}
