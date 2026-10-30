import { useEffect, useRef, useState } from "react";
import Consents from "../components/Consents";
import type { Consents as ConsentValues } from "../types";
import { api } from "../api";
import Field from "../components/Field";
import AingelOrb, { type OrbState } from "../components/aingel/AingelOrb";
import { Brand, type Who } from "./Auth";
import { useMediaQuery } from "../useMediaQuery";
import type { Context } from "../ui";
import type { Profile } from "../types";

export function AcceptInvite({ t, busy, run, onAccepted }: Context & { onAccepted: (id: string) => Promise<void> }) {
  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      const data = new FormData(e.currentTarget);
      void run(async () => {
        const value = await api<{ profile_id: string }>("invites/accept/", "POST", Object.fromEntries(data));
        await onAccepted(value.profile_id);
      }, "errorInvite");
    }}>
      <p className="hint">{t("inviteHint")}</p>
      <Field label={t("inviteCode")}><input name="code" required minLength={20} maxLength={100} autoComplete="off" /></Field>
      <button className="btn btn-primary" disabled={busy}>{t("acceptInvite")}</button>
    </form>
  );
}

type CondId = "vision" | "hearing" | "autism" | "dementia";
type Conds = Record<CondId, { on: boolean; lvl: number }>;
type Signs = "yes" | "no";
type SignLang = "LSEC" | "ASL" | "Otra";
type Reads = "yes" | "difficulty" | "no";
type Address = "usted" | "tu" | "neutral";

const CONDS: { id: CondId; es: [string, string, string[], string[]]; en: [string, string, string[], string[]] }[] = [
  { id: "vision",
    es: ["Ceguera o baja visión", "Dificultad para ver o ausencia de visión", ["Leve", "Moderada", "Severa", "Total"], ["Baja visión leve", "Baja visión moderada", "Baja visión severa", "Ceguera total"]],
    en: ["Blindness or low vision", "Difficulty seeing or no sight", ["Mild", "Moderate", "Severe", "Total"], ["Mild low vision", "Moderate low vision", "Severe low vision", "Total blindness"]] },
  { id: "hearing",
    es: ["Sordera o hipoacusia", "Pérdida auditiva parcial o total", ["Leve", "Moderada", "Severa", "Profunda"], ["Hipoacusia leve", "Hipoacusia moderada", "Hipoacusia severa", "Sordera profunda"]],
    en: ["Deafness or hearing loss", "Partial or total hearing loss", ["Mild", "Moderate", "Severe", "Profound"], ["Mild hearing loss", "Moderate hearing loss", "Severe hearing loss", "Profound deafness"]] },
  { id: "autism",
    es: ["Autismo (TEA)", "Según el nivel de apoyo que necesita", ["Nivel 1", "Nivel 2", "Nivel 3"], ["Nivel 1 · necesita apoyo", "Nivel 2 · apoyo sustancial", "Nivel 3 · apoyo muy sustancial"]],
    en: ["Autism (ASD)", "By the level of support needed", ["Level 1", "Level 2", "Level 3"], ["Level 1 · requires support", "Level 2 · substantial support", "Level 3 · very substantial support"]] },
  { id: "dementia",
    es: ["Alzheimer o deterioro cognitivo", "Dificultad para recordar u orientarse", ["Inicial", "Moderada", "Avanzada"], ["Etapa inicial", "Etapa moderada", "Etapa avanzada"]],
    en: ["Alzheimer's or cognitive decline", "Difficulty remembering or finding the way", ["Early", "Moderate", "Advanced"], ["Early stage", "Moderate stage", "Advanced stage"]] },
];

/** Keys the server already stores; the rest are listed in the profile notes until supported. */
const SUPPORTED = new Set(["visual_assistance", "voice_output", "large_text", "high_contrast", "hearing_assistance", "sign_language", "simple_instructions", "reduced_motion", "one_step", "memory_assistance", "speech_pace=slow", "easy_read", "default"]);

function presets(c: Conds, signs: Signs, signLang: SignLang, reads: Reads, es: boolean) {
  const out: { t: string; k: string }[] = [];
  const L = (a: string, b: string) => (es ? a : b);
  if (c.vision.on) {
    out.push({ t: L("Ver en el inicio: describir lo que tiene delante", "See on the home screen: describe what is in front"), k: "visual_assistance" });
    if (c.vision.lvl >= 2) { out.push({ t: L("Respuestas siempre en voz alta", "Answers always read aloud"), k: "voice_output" }); out.push({ t: L("Uso principal por voz, botones grandes", "Voice first, large buttons"), k: "voice_first" }); }
    else { out.push({ t: L("Texto más grande", "Larger text"), k: "large_text" }); out.push({ t: L("Mayor contraste", "Higher contrast"), k: "high_contrast" }); }
  }
  if (c.hearing.on) {
    out.push({ t: L("Escuchar en el inicio: subtítulos en tiempo real", "Hear on the home screen: live captions"), k: "hearing_assistance" });
    if (c.hearing.lvl >= 2) out.push({ t: L("Respuestas en texto, sin depender del audio", "Text answers that don't rely on audio"), k: "text_first" });
    out.push({ t: L("Avisos con vibración", "Vibration alerts"), k: "haptic_alerts" });
  }
  if (signs === "yes") {
    out.push({ t: L(`Videos de lengua de señas (${signLang})`, `Sign language videos (${signLang})`), k: "sign_language" });
    if (reads === "no") out.push({ t: L("Pictogramas y videos en lugar de texto", "Pictograms and videos instead of text"), k: "no_reading" });
    if (reads === "difficulty") out.push({ t: L("Frases cortas con apoyo visual", "Short sentences with visual support"), k: "easy_read" });
  }
  if (c.autism.on) {
    out.push({ t: L("Instrucciones cortas y literales", "Short, literal instructions"), k: "simple_instructions" });
    out.push({ t: L("Reducir movimiento", "Reduce motion"), k: "reduced_motion" });
    if (c.autism.lvl >= 1) out.push({ t: L("Un elemento a la vez en las listas", "One item at a time in lists"), k: "one_step" });
    if (c.autism.lvl >= 2) out.push({ t: L("Anticipar siempre lo que viene después", "Always preview what comes next"), k: "routine_preview" });
  }
  if (c.dementia.on) {
    out.push({ t: L("Hoy y Recordar destacados en el inicio", "Today and Remember on the home screen"), k: "memory_assistance" });
    out.push({ t: L("Lectura pausada", "Slow reading pace"), k: "speech_pace=slow" });
    if (c.dementia.lvl >= 1) out.push({ t: L("El círculo de cuidado puede configurar rutinas", "The care circle can set up routines"), k: "can_configure" });
    if (c.dementia.lvl >= 2) out.push({ t: L("Inicio simplificado: AINGEL, Hoy y Necesito apoyo", "Simplified home: AINGEL, Today and I need support"), k: "simplified_home" });
  }
  if (!out.length) out.push({ t: L("Configuración estándar", "Standard setup"), k: "default" });
  return out;
}

/** 2c (web) and 2e-2h (phone): person, conditions with level, communication, activation. */
export default function Onboarding(props: Context & { onCreated: (id: string) => Promise<void>; who: Who; ownName: string; username?: string; onLogout: () => void }) {
  const { busy, run, onCreated } = props;
  const es = props.locale === "es-EC";
  const L = (a: string, b: string) => (es ? a : b);
  const [step, setStep] = useState(1);
  const [name, setName] = useState(props.who === "me" ? props.ownName : "");
  const [preferred, setPreferred] = useState(props.who === "me" ? props.ownName.split(" ")[0] || "" : "");
  const [relationship, setRelationship] = useState("");
  const [profileLocale, setProfileLocale] = useState(props.locale);
  const [timezone, setTimezone] = useState("America/Guayaquil");
  const [conds, setConds] = useState<Conds>({ vision: { on: false, lvl: 1 }, hearing: { on: false, lvl: 0 }, autism: { on: false, lvl: 0 }, dementia: { on: false, lvl: 0 } });
  const [signs, setSigns] = useState<Signs>("no");
  const [signLang, setSignLang] = useState<SignLang>("LSEC");
  const [reads, setReads] = useState<Reads>("yes");
  const [address, setAddress] = useState<Address>("usted");
  const [stepError, setStepError] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [act, setAct] = useState<OrbState>("idle");
  const [showInvite, setShowInvite] = useState(false);
  // Authorizations are given here, once; the apps do not ask again per action.
  const [consents, setConsents] = useState<ConsentValues>({ camera: false, microphone: false, meta_data: false });
  const timers = useRef<number[]>([]);
  const savedId = useRef<string | null>(null);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const reduced = conds.autism.on;
  const mobile = useMediaQuery("(max-width: 760px)");
  const shown = preferred.trim() || name.trim().split(" ")[0] || L("la persona", "them");
  const nOn = CONDS.filter((c) => conds[c.id].on).length;
  const list = presets(conds, signs, signLang, reads, es);
  const timezoneOk = () => { try { new Intl.DateTimeFormat("en-US", { timeZone: timezone.trim() }); return true; } catch { return false; } };
  const goto = (n: number) => {
    if (n > 1 && !name.trim()) { setStep(1); setStepError(L("Escribe el nombre de la persona.", "Enter the person's name.")); return; }
    if (n > 1 && !timezoneOk()) { setStep(1); setStepError(L("Ingresa una zona horaria válida, por ejemplo America/Guayaquil.", "Enter a valid time zone, such as America/Guayaquil.")); return; }
    setStepError("");
    setStep(Math.max(1, Math.min(4, n)));
  };
  const activate = () => run(async () => {
    const keys = new Set(list.map((x) => x.k));
    const preferences: Record<string, boolean> = {
      visual_assistance: keys.has("visual_assistance"), hearing_assistance: keys.has("hearing_assistance"),
      memory_assistance: keys.has("memory_assistance") || nOn === 0, large_text: keys.has("large_text"),
      high_contrast: keys.has("high_contrast"), voice_output: keys.has("voice_output"),
      reduced_motion: keys.has("reduced_motion"), simple_instructions: keys.has("simple_instructions"),
    };
    if (nOn === 0) { preferences.visual_assistance = true; preferences.hearing_assistance = true; }
    const condLines = CONDS.filter((c) => conds[c.id].on).map((c) => `${(es ? c.es : c.en)[0]}: ${(es ? c.es : c.en)[3][conds[c.id].lvl]}`);
    const pending = list.filter((x) => !SUPPORTED.has(x.k)).map((x) => `${x.t} (${x.k})`);
    const notes = [
      condLines.length ? `${L("Apoyos indicados", "Support needs")}: ${condLines.join("; ")}.` : "",
      props.who === "other" && relationship.trim() ? `${L("Relación de quien configura", "Relationship of the person setting up")}: ${relationship.trim()}.` : "",
      signs === "yes" ? `${L("Lectura", "Reading")}: ${reads === "yes" ? L("lee bien", "reads well") : reads === "difficulty" ? L("con dificultad", "with difficulty") : L("no sabe leer", "does not read")}.` : "",
      pending.length ? `${L("Configuración predefinida pendiente de soporte", "Preset items not yet supported")}: ${pending.join("; ")}.` : "",
      L("Esta información no es un diagnóstico.", "This information is not a diagnosis."),
    ].filter(Boolean).join("\n");
    // A retry after a failed communication save must not create a second profile.
    const id = savedId.current ?? (savedId.current = (await api<Profile>("profiles/", "POST", { display_name: name.trim(), locale: profileLocale, timezone: timezone.trim(), support_notes: notes, preferences, consents: { camera: !!consents.camera, microphone: !!consents.microphone, meta_data: !!consents.meta_data } })).id);
    const communication = await api<Record<string, unknown>>(`profiles/${id}/communication/`);
    await api(`profiles/${id}/communication/`, "PATCH", {
      ...communication,
      preferred_name: preferred.trim().slice(0, 100),
      addressing: address === "usted" ? "formal" : address === "tu" ? "informal" : "preferred_name",
      pace: conds.dementia.on ? "slow" : "standard",
      interaction: conds.autism.on && conds.autism.lvl >= 1 ? "one_step" : "standard",
      sentence_length: reads !== "yes" && signs === "yes" ? "short" : communication.sentence_length,
      sign_language: signs === "yes" ? (signLang === "LSEC" ? "lsec" : signLang === "ASL" ? "asl" : "other") : "none",
    });
    setCreated(id);
    timers.current.push(window.setTimeout(() => setAct("happy"), 2300), window.setTimeout(() => setAct("idle"), 5400));
  });
  const opt = <T extends string>(items: [T, string][], cur: T, set: (v: T) => void, cls = "") => items.map(([v, l]) => (
    <button type="button" key={v} className={`seg ${cls}${cur === v ? " is-on" : ""}`} aria-pressed={cur === v} onClick={() => set(v)}>{l}</button>
  ));
  const greet = address === "usted" ? L(`Hola, ${shown}. Estoy aquí para ayudarle.`, `Hello, ${shown}. I'm here to help you.`)
    : address === "tu" ? L(`Hola, ${shown}. Estoy aquí para ayudarte.`, `Hi, ${shown}. I'm here to help you.`)
    : L(`Hola, ${shown}. Estoy aquí para ayudar.`, `Hello, ${shown}. I'm here to help.`);
  const steps = [L("Persona", "Person"), L("Condiciones", "Conditions"), L("Comunicación", "Communication"), L("Activar", "Activate")];
  const done = !!created;
  return (
    <div className="setup" data-step={step}>
      <header className="setup-top">
        <Brand size={30} />
        <nav className="setup-steps" aria-label={L("Pasos de configuración", "Setup steps")}>
          {steps.map((l, i) => (
            <button type="button" key={l} disabled={done} onClick={() => goto(i + 1)} className={`${i + 1 <= step ? "is-reached" : ""}${i + 1 === step ? " is-current" : ""}`} aria-current={i + 1 === step ? "step" : undefined}>
              <span>{i + 1}</span>{l}
            </button>
          ))}
        </nav>
        <span className="setup-count">{L(`Paso ${step} de 4`, `Step ${step} of 4`)}</span>
      </header>
      <div className="setup-mobile-progress">
        <div><span>{L(`Paso ${step} de 4`, `Step ${step} of 4`)}</span>{step === 2 && <b>{L(`${nOn} seleccionadas`, `${nOn} selected`)}</b>}</div>
        <span className="progress"><span style={{ width: `${step * 25}%` }} /></span>
      </div>
      <div className="setup-body">
        <main id="main" className="setup-main">
          {step === 1 && (
            <div className="setup-section setup-narrow">
              <div className="setup-head">
                <span className="overline">{props.who === "me" ? L("TUS DATOS", "YOUR DETAILS") : L("PERSONA A LA QUE CUIDAS", "PERSON YOU CARE FOR")}</span>
                <h2>{L("¿Para quién es este AINGEL?", "Who is this AINGEL for?")}</h2>
                <p>{L("Estos datos ayudan a AINGEL a dirigirse a la persona por su nombre y en su idioma.", "These details help AINGEL address the person by name and in their language.")}</p>
              </div>
              <div className="setup-grid">
                <label className="input-field"><span>{L("Nombre de la persona", "Person's name")}</span><input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required /></label>
                <label className="input-field"><span>{L("Nombre preferido", "Preferred name")}</span><input value={preferred} onChange={(e) => setPreferred(e.target.value)} maxLength={100} /></label>
                {props.who === "other" && <label className="input-field"><span>{L("Relación con la persona", "Relationship to the person")}</span><input value={relationship} onChange={(e) => setRelationship(e.target.value)} maxLength={60} placeholder={L("Hija, hijo, cuidador…", "Daughter, son, carer…")} /></label>}
                <label className="input-field"><span>{L("Idioma preferido de AINGEL", "AINGEL's preferred language")}</span><select value={profileLocale} onChange={(e) => setProfileLocale(e.target.value as typeof profileLocale)}><option value="es-EC">Español (Ecuador)</option><option value="en-US">English (US)</option></select></label>
                <label className="input-field"><span>{L("Zona horaria", "Time zone")}</span><input value={timezone} onChange={(e) => setTimezone(e.target.value)} maxLength={80} list="aingel-zones" /></label>
                <datalist id="aingel-zones"><option value="America/Guayaquil" /><option value="America/Bogota" /><option value="America/Lima" /><option value="America/Mexico_City" /><option value="America/New_York" /><option value="Europe/Madrid" /></datalist>
              </div>
              {stepError && <p className="form-error" role="alert">{stepError}</p>}
              <button type="button" className="auth-link" onClick={() => setShowInvite(!showInvite)}>{L("¿Recibiste un código de invitación? Únete a un AINGEL existente", "Got an invite code? Join an existing AINGEL")}</button>
              {showInvite && <div className="invite-box"><AcceptInvite {...props} onAccepted={onCreated} /></div>}
            </div>
          )}
          {step === 2 && (
            <div className="setup-section">
              <div className="setup-head-row">
                <div className="setup-head">
                  <h2>{L(`¿Qué apoyos necesita ${shown}?`, `What support does ${shown} need?`)}</h2>
                  <p>{L("Selecciona todas las que apliquen y su nivel. Puedes elegir varias.", "Select all that apply and their level. You can choose several.")}</p>
                </div>
                <span className="pill-count">{nOn === 0 ? L("Ninguna seleccionada", "None selected") : nOn === 1 ? L("1 condición seleccionada", "1 condition selected") : L(`${nOn} condiciones · AINGEL combinará los apoyos`, `${nOn} conditions · AINGEL will combine support`)}</span>
              </div>
              <div className="cond-grid">
                {CONDS.map((c) => {
                  const s = conds[c.id], [title, desc, levels, full] = es ? c.es : c.en;
                  return (
                    <div key={c.id} className={`cond-card${s.on ? " is-on" : ""}`}>
                      <button type="button" className="cond-toggle" aria-pressed={s.on} onClick={() => setConds({ ...conds, [c.id]: { ...s, on: !s.on } })}>
                        <span className="checkbox" aria-hidden="true">{s.on && <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>}</span>
                        <span className="cond-text"><b>{title}</b><small>{desc}</small></span>
                      </button>
                      {s.on && (
                        <div className="cond-level">
                          <span className="overline">{L("NIVEL", "LEVEL")}</span>
                          <div className="seg-row" role="group" aria-label={`${title} · ${L("nivel", "level")}`}>
                            {levels.map((l, i) => <button type="button" key={l} className={`seg seg-sm${s.lvl === i ? " is-on" : ""}`} aria-pressed={s.lvl === i} onClick={() => setConds({ ...conds, [c.id]: { on: true, lvl: i } })}>{l}</button>)}
                          </div>
                          <span className="cond-caption">{full[s.lvl]}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="setup-foot-note">{L("Otras necesidades se pueden escribir después en Personalizar. Esta información no es un diagnóstico.", "Other needs can be added later in Personalize. This information is not a diagnosis.")}</p>
            </div>
          )}
          {step === 3 && (
            <div className="setup-section setup-narrow setup-comm">
              <div className="setup-head"><h2>{L(`¿Cómo se comunica ${shown}?`, `How does ${shown} communicate?`)}</h2><p>{L("AINGEL ajusta cómo muestra y lee las respuestas.", "AINGEL adapts how it shows and reads answers.")}</p></div>
              <div className="q"><span className="q-label">{L("¿Usa lengua de señas?", "Do they use sign language?")}</span><div className="seg-row seg-row--yn">{opt<Signs>([["yes", L("Sí", "Yes")], ["no", "No"]], signs, setSigns, "seg-wide")}</div></div>
              {signs === "yes" && (
                <div className="q-nested">
                  <div className="q"><span className="q-label">{L("¿Qué lengua de señas?", "Which sign language?")}</span><div className="seg-row seg-row--stack">{opt<SignLang>([["LSEC", "LSEC (Ecuador)"], ["ASL", "ASL"], ["Otra", L("Otra", "Other")]], signLang, setSignLang)}</div></div>
                  <div className="q"><span className="q-label">{L("¿Sabe leer?", "Can they read?")}</span><div className="seg-row seg-row--stack">{opt<Reads>([["yes", L("Sí, lee bien", "Yes, reads well")], ["difficulty", L("Con dificultad", "With difficulty")], ["no", L("No sabe leer", "Does not read")]], reads, setReads)}</div><span className="q-hint">{L("Si no lee, AINGEL usará videos de señas y pictogramas en lugar de texto.", "If they don't read, AINGEL will use sign videos and pictograms instead of text.")}</span></div>
                </div>
              )}
              <div className="q"><span className="q-label">{L("¿Cómo prefiere que le hablen?", "How do they prefer to be addressed?")}</span><div className="seg-row seg-row--three">{opt<Address>([["usted", L("Usted", "Formal")], ["tu", L("Tú", "Informal")], ["neutral", "Neutral"]], address, setAddress, "seg-wide")}</div></div>
            </div>
          )}
          {step === 4 && (
            <div className="setup-activate">
              <AingelOrb size={mobile ? 270 : 340} state={act} configured={done} reducedMotion={reduced} />
              <h2 role="status" aria-live="polite">{done ? L("Tu AINGEL está listo", "Your AINGEL is ready") : L("Todo listo para activar", "Ready to activate")}</h2>
              <p>{done ? greet : L(`AINGEL aplicará la configuración predefinida para ${shown}. Podrás cambiarla en Personalizar.`, `AINGEL will apply the preset for ${shown}. You can change it in Personalize.`)}</p>
              {!done && <Consents value={consents} onChange={setConsents} es={es} disabled={busy} />}
              {props.busy && <p className="hint" role="status">{props.t("working")}</p>}
              <div className="setup-activate-actions">
                {done
                  ? <button type="button" className="btn btn-primary btn-lg btn-pill btn-wide" onClick={() => void run(() => onCreated(created!))}>{L("Inicio", "Home")}</button>
                  : <button type="button" className="btn btn-primary btn-lg btn-pill btn-shadow" disabled={busy} onClick={() => void activate()}>{L("Activar AINGEL", "Activate AINGEL")}</button>}
              </div>
            </div>
          )}
          {step !== 4 && (
            <div className="setup-nav">
              <button type="button" className="btn btn-outline btn-pill" style={{ opacity: step === 1 ? 0.4 : 1 }} disabled={step === 1} onClick={() => goto(step - 1)}>{L("Atrás", "Back")}</button>
              <button type="button" className="btn btn-primary btn-pill" onClick={() => goto(step + 1)}>{step === 3 ? L("Revisar y activar", "Review and activate") : L("Continuar", "Continue")}</button>
            </div>
          )}
        </main>
        <aside className="setup-side">
          {step !== 4 && (
            <div className="setup-side-orb">
              <AingelOrb size={180} configured={false} reducedMotion={reduced} />
              <span>{L("Sin configurar", "Not set up")}</span>
            </div>
          )}
          <div className="setup-side-head"><span className="overline">{L("CONFIGURACIÓN PREDEFINIDA", "PRESET CONFIGURATION")}</span><b>{nOn >= 2 ? L(`Combinada para ${nOn} condiciones`, `Combined for ${nOn} conditions`) : nOn === 1 ? L("Para 1 condición", "For 1 condition") : L("Sin condiciones seleccionadas", "No conditions selected")}</b></div>
          <ul className="preset-list">
            {list.map((p) => (
              <li key={p.k}><span className="preset-dot" /><div><span>{p.t}</span><code>{p.k}{!SUPPORTED.has(p.k) && ` · ${L("próximamente", "coming soon")}`}</code></div></li>
            ))}
          </ul>
          <span className="setup-side-foot">{L("Todo se puede cambiar después en Personalizar.", "Everything can be changed later in Personalize.")}</span>
          <button type="button" className="auth-link setup-logout" onClick={props.onLogout}>{props.t("logout")}{props.username ? ` · ${props.username}` : ""}</button>
        </aside>
      </div>
    </div>
  );
}
