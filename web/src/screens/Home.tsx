import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, APIError } from "../api";
import AingelOrb, { type OrbState } from "../components/aingel/AingelOrb";
import { useSpeechInput, type SpeechOutcome } from "../components/aingel/useSpeechInput";
import BrowserSpeechConsent, { BrowserSpeechRevoke, micPrivacyLine } from "../components/BrowserSpeechConsent";
import { stopsCapture, useConsentWatch } from "../consentWatch";
import { useSpeechSynthesisLevel } from "../components/aingel/useOutputAudioLevel";
import { useCamera } from "../components/aingel/useCamera";
import { HandIcon } from "../components/aingel/HandIcon";
import PrivateMediaConsent, { imageTestFields } from "../components/PrivateMediaConsent";
import SyntheticConversationConsent, { type SyntheticQuestion } from "../components/SyntheticConversationConsent";
import { useCommunication } from "../Communication";
import { useMediaQuery } from "../useMediaQuery";
import { greetingKey, initials, longDate, summarizeToday } from "../today";
import type { WithProfile } from "../ui";
import type { CareMessage, Located, Memory, Routine, Scene } from "../types";

type Card = { time?: string; title: string; meta: string };
type Source = { title: string; url: string; source: string; downloaded_at: string };
/** Where an answer came from. Shown with every answer; "model" turns are the only ones sent to Meta. */
type Origin = "local" | "model" | "mock" | "vision" | "notice";
type Answer = {
  text: ReactNode;
  spoken: string;
  cards?: Card[];
  memory?: { lead: string; value: string; meta: string; note: string };
  source: string;
  link?: Source | null;
  web?: { url: string; title: string }[];
  excerpt?: string | null;
  origin: Origin;
  offerLocal?: boolean;
  /** An app feature Meta asked to use instead of (or as well as) answering in text. */
  action?: Action | null;
};
type Exchange = { id: number; question: string; answer: Answer | null };
type Action = { name: string; arguments?: Record<string, unknown> | null };
type ConversationReply = {
  mode: "meta" | "mock"; model: string | null; text: string; source: Source | null; excerpt: string | null;
  provenance: { model: string | null; retrieval: "medlineplus" | "web" | null; personalized?: boolean };
  citations?: { url: string; title: string }[];
  action?: Action | null;
};
/** Features of this web app that Meta may trigger (backend assistance.companion actions). */
const ACTIONS = ["describe_surroundings", "find_object", "open_sign_translator"];

const MicIcon = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0" /><path d="M12 17.5V21" /></svg>
);
const Check = ({ size = 12 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
);
/** 3a eyes button: two pills, navy off / gold on a navy disc. */
function EyesButton({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" className={`round-btn${on ? " is-on" : ""}`} aria-pressed={on} aria-label={label} title={label} onClick={onClick}>
      <span className="eyes-glyph"><i /><i /></span>
    </button>
  );
}
const MAX_MODEL_PAIRS = 5;
/** The server rejects conversations whose turns add up to more (conversation_request_invalid). */
const MAX_TURN_CHARS = 8000;

/** 1b / 1c on the web and 1f / 1g / 1h on phones, wired to the real routines, messages and memories. */
export default function Home({ profile, t, locale, run, busy, date, speech: accountSpeech, onOpenToday, onOpenSigns, initialQuestion }: WithProfile & { onOpenToday: () => void; onOpenSigns: () => void; initialQuestion?: string }) {
  const es = locale === "es-EC";
  const L = (a: string, b: string) => (es ? a : b);
  const mobile = useMediaQuery("(max-width: 760px)");
  const { value: communication } = useCommunication(profile.id);
  const speech = useSpeechInput(profile.locale, accountSpeech);
  const [askSpeech, setAskSpeech] = useState(false);
  const tts = useSpeechSynthesisLevel(profile.locale, communication?.pace === "slow" ? 0.8 : 1);
  const camera = useCamera();
  // Requests that depend on the person's authorizations: a revocation aborts them (consentWatch.ts).
  const inflight = useRef(new Set<AbortController>());
  const request = <T,>(path: string, method: string, data: unknown) => {
    const control = new AbortController();
    inflight.current.add(control);
    return api<T>(path, method, data, control.signal).finally(() => inflight.current.delete(control));
  };
  const [phase, setPhase] = useState<OrbState>("idle");
  const [thread, setThread] = useState<Exchange[]>([]);
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState("");
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [messages, setMessages] = useState<CareMessage[]>([]);
  const [tick, setTick] = useState(0);
  // Per-visit switch for reading answers aloud; the camera / Meta authorizations come from sign-up.
  const [autoRead, setAutoRead] = useState(true);
  const [seeking, setSeeking] = useState("");
  const [vision, setVision] = useState(false);
  const [privateTest, setPrivateTest] = useState(false);
  const [syntheticConversation, setSyntheticConversation] = useState(false);
  const timers = useRef<number[]>([]);
  // Bumped when the person clears, stops or leaves: answers still in flight for an older turn are dropped.
  const turn = useRef(0);
  const composer = useRef<HTMLInputElement>(null);
  const threadEnd = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  const phaseRef = useRef(phase); phaseRef.current = phase;
  useEffect(() => {
    setPrivateTest(false); setSyntheticConversation(false); setThread([]); setDraft("");
    turn.current++;
  }, [profile.id]);
  const reduced = !!profile.preferences.reduced_motion;
  const name = communication?.preferred_name || profile.display_name.split(" ")[0];
  const base = `profiles/${profile.id}/`;

  const load = useCallback(async () => {
    const [r, m] = await Promise.all([
      api<Routine[]>(base + "routines/").catch(() => [] as Routine[]),
      api<CareMessage[]>(base + "messages/").catch(() => [] as CareMessage[]),
    ]);
    setRoutines(r); setMessages(m);
  }, [base]);
  useEffect(() => { void load(); const id = window.setInterval(() => setTick((x) => x + 1), 30000); return () => clearInterval(id); }, [load]);
  const today = useMemo(() => summarizeToday(routines, profile.timezone), [routines, profile.timezone, tick]);
  const lastMessage = useMemo(() => [...messages].sort((a, b) => b.created_at.localeCompare(a.created_at))[0], [messages]);

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = []; };
  const later = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
  const settle = (state: OrbState, ms: number) => { setPhase(state); later(ms, () => setPhase("idle")); };
  useEffect(() => () => { turn.current++; clearTimers(); }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("focus-mode", phase === "listening");
    return () => document.documentElement.classList.remove("focus-mode");
  }, [phase]);
  useEffect(() => { threadEnd.current?.scrollIntoView({ block: "end", behavior: reduced ? "auto" : "smooth" }); }, [thread, reduced]);

  const hhmm = (at: string) => at.slice(0, 5);
  const time = (iso: string) => new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: profile.timezone }).format(new Date(iso));
  const localSource = L("Respuesta local de AINGEL", "Local AINGEL answer");

  /** Local, evidence-based answers. Nothing is invented when there is no data; none of this goes to Meta. */
  const local = async (question: string): Promise<Answer | null> => {
    // Only the app's own intents are answered here; anything else («¿Dónde queda el hospital?», «¿Qué debo hacer
    // si me duele el pecho?») falls through to general().
    const q = " " + question.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[¿?¡!.,;:"«»“”]/g, " ").replace(/\s+/g, " ").trim() + " ";
    if (/ (donde (deje|puse|guarde|vi|quedo|quedaron) |donde (esta|estan) (mi|mis) |where (did i (leave|put|see)|(is|are) my) )/.test(q)) {
      const entity = question.replace(/[¿?¡!.]/g, " ")
        .replace(/^\s*(d[oó]nde)\s+(dej[eé]|vi|est[aá]n?|puse|qued[oó]|quedaron|guard[eé])\s+((mis|mi|el|la|los|las|un|una)\s+)?/i, "")
        .replace(/^\s*where\s+(did\s+i\s+(leave|put|see)|is|are|were)\s+((my|the|a)\s+)?/i, "")
        .replace(/\s*(este objeto|this object)\s*/i, "").trim();
      if (!entity) return { text: L("¿Qué objeto quieres encontrar? Por ejemplo: «¿Dónde dejé mis llaves?».", "Which object are you looking for? For example: “Where did I leave my keys?”"), spoken: L("¿Qué objeto quieres encontrar?", "Which object are you looking for?"), source: L("Recuerdos confirmados", "Confirmed memories"), origin: "local" };
      if (!profile.permissions.memories) return { text: t("noAccess"), spoken: t("noAccess"), source: L("Permisos del perfil", "Profile permissions"), origin: "local" };
      setPhase("searching");
      const result = await api<{ evidence?: Memory }>(base + "ask/", "POST", { tool: "search_memory", entity });
      const ev = result.evidence;
      if (!ev) {
        const text = L(`No tengo una observación guardada sobre «${entity}». No voy a adivinar dónde está.`, `I have no saved observation about “${entity}”. I won't guess where it is.`);
        return { text, spoken: text, source: L("Recuerdos confirmados · sin coincidencias", "Confirmed memories · no match"), origin: "local" };
      }
      const value = `${ev.entity.charAt(0).toUpperCase() + ev.entity.slice(1)}, ${ev.location}.`;
      return {
        text: null, spoken: `${L("La última observación registrada indica", "The last recorded observation says")}: ${value}`,
        memory: { lead: L("La última observación registrada indica", "The last recorded observation says"), value, meta: `${date(ev.observed_at)} · ${L("registrado por", "recorded by")} ${ev.author}`, note: L("Es una observación guardada; no garantiza la ubicación actual.", "This is a saved observation; it doesn't guarantee the current location.") },
        source: L("Recuerdos confirmados", "Confirmed memories"), origin: "local",
      };
    }
    if (/ (que tengo (que hacer )?(para )?hoy|que (hay|me toca) (para )?hoy|mi agenda|mis rutinas|mis pendientes|what do i (have|need to do)( to do)? today|what('s| is) on my (agenda|schedule)|my (agenda|routines|schedule)) /.test(q)) {
      const items = await api<Routine[]>(base + "routines/");
      setRoutines(items);
      const s = summarizeToday(items, profile.timezone);
      if (!s.list.length) { const text = L("Hoy no tienes rutinas programadas.", "You have no routines scheduled today."); return { text, spoken: text, source: L("Tus rutinas guardadas · respuesta estructurada local", "Your saved routines · local structured answer"), origin: "local" }; }
      const after = s.next ? s.list.find((x) => !x.confirmed_today && x.at > s.next!.at) : null;
      const lead = L(`Hoy tienes ${s.list.length} rutinas y ya completaste ${s.done}.`, `You have ${s.list.length} routines today and have completed ${s.done}.`);
      const nextText = s.next ? L(`${s.next.title.charAt(0).toLowerCase() + s.next.title.slice(1)} a las ${hhmm(s.next.at)}`, `${s.next.title} at ${hhmm(s.next.at)}`) : "";
      const afterText = after ? L(` Después tienes ${after.title} a las ${hhmm(after.at)}.`, ` After that: ${after.title} at ${hhmm(after.at)}.`) : "";
      return {
        text: s.next ? <>{lead} {L("La próxima es ", "Next is ")}<b>{nextText}</b>.{afterText}</> : <>{lead} {L("No te quedan rutinas pendientes.", "Nothing left to do.")}</>,
        spoken: s.next ? `${lead} ${L("La próxima es", "Next is")} ${nextText}.${afterText}` : `${lead} ${L("No te quedan rutinas pendientes.", "Nothing left to do.")}`,
        cards: [s.next, after].filter((x): x is Routine => !!x).map((x) => ({ time: hhmm(x.at), title: x.title, meta: x.instructions || t(x.category as never) })),
        source: L("Tus rutinas guardadas · respuesta estructurada local", "Your saved routines · local structured answer"), origin: "local",
      };
    }
    if (/ (que me (han|ha) dicho|que me dijeron|mis mensajes|(ultimo|ultimos|nuevo|nuevos) mensajes?|tengo mensajes|what have i been told|what have people told me|my (latest |last |new )?messages?|(any|new) messages) /.test(q)) {
      const items = (await api<CareMessage[]>(base + "messages/")).sort((a, b) => b.created_at.localeCompare(a.created_at));
      setMessages(items);
      if (!items.length) { const text = t("noMessages"); return { text, spoken: text, source: L("Mensajes de tu círculo", "Messages from your circle"), origin: "local" }; }
      const m = items[0];
      const text = L(`Tu último mensaje es de ${m.author}: «${m.body}»`, `Your latest message is from ${m.author}: “${m.body}”`);
      return {
        text, spoken: text,
        cards: items.slice(0, 2).map((x) => ({ time: time(x.created_at), title: x.body, meta: x.author })),
        source: L("Mensajes de tu círculo · con autor y fecha", "Messages from your circle · with author and date"), origin: "local",
      };
    }
    // Only a bare plea for support; «ayúdame a entender…» is a general question.
    if (/^ (necesito (apoyo|ayuda)( por favor)?|ayudame( por favor)?|ayuda|help( me)?( please)?|i need (support|help)) $/.test(q)) {
      const text = t(communication?.distress === "contact_caregiver" ? "supportCaregiverResponse" : "supportQuietResponse");
      return { text: <>{text} <span className="muted">{t("supportNoCall")}</span></>, spoken: text, source: L("Respuesta local de apoyo", "Local support response"), origin: "local" };
    }
    return null;
  };

  /** General questions go to Muse Spark under the sign-up authorization, with MedlinePlus and, if needed, web search. */
  const general = async (question: string, history: Exchange[]): Promise<Answer> => {
    if (syntheticConversation) {
      // The synthetic demo only sends the server's example questions (askFixture), never what was typed or said.
      const text = L("En la prueba sintética elige una de las preguntas de ejemplo: lo que escribes o dices no se envía a Meta.", "In the synthetic test pick one of the example questions: what you type or say is not sent to Meta.");
      return { text, spoken: text, source: localSource, origin: "notice" };
    }
    let pairs = history.filter((x) => x.answer?.origin === "model" && x.question).slice(-MAX_MODEL_PAIRS);
    const build = () => [
      ...pairs.flatMap((x) => [{ role: "user", text: x.question.slice(0, 1000) }, { role: "assistant", text: x.answer!.spoken.slice(0, 1000) }]),
      { role: "user", text: question.slice(0, 1000) },
    ];
    let turns = build();
    // Oldest pairs go first until the whole conversation fits the server's cap.
    while (pairs.length && turns.reduce((n, x) => n + x.text.length, 0) > MAX_TURN_CHARS) { pairs = pairs.slice(1); turns = build(); }
    try {
      const reply = await request<ConversationReply>(base + "conversation/", "POST", {
        turns, actions: ACTIONS,
      });
      const retrieval = reply.provenance.retrieval === "medlineplus";
      if (reply.mode === "mock") {
        return {
          text: reply.text, spoken: reply.excerpt ? `${reply.text} ${reply.excerpt}` : reply.text, excerpt: reply.excerpt, link: reply.source,
          source: retrieval ? L("Modo de prueba · texto de MedlinePlus, sin modelo", "Test mode · MedlinePlus text, no model") : L("Modo de prueba · sin modelo", "Test mode · no model"),
          origin: "mock", action: reply.action ?? null,
        };
      }
      return {
        text: reply.text, spoken: reply.text, link: reply.source, web: reply.citations ?? [], origin: "model", action: reply.action ?? null,
        source: retrieval
          ? L("Generado por Meta Muse Spark con un resumen de MedlinePlus", "Generated by Meta Muse Spark from a MedlinePlus summary")
          : reply.citations?.length ? L("Generado por Meta Muse Spark con búsqueda web", "Generated by Meta Muse Spark with web search")
          : L("Generado por Meta Muse Spark · sin fuente consultada", "Generated by Meta Muse Spark · no source consulted"),
      };
    } catch (e) {
      const detail = e instanceof APIError ? JSON.stringify(e.detail) : "";
      const text = e instanceof APIError && e.status === 429
        ? L("Hiciste muchas preguntas seguidas. Espera un minuto, por favor.", "That was many questions in a row. Please wait a minute.")
        : detail.includes("privacy_review")
          ? t("errorPrivacy")
          : L("Ahora no puedo conectar con el modelo de Meta. Sí puedo ayudarte con tus rutinas de hoy, tus mensajes y tus recuerdos.", "I can't reach Meta's model right now. I can still help with today's routines, your messages and your memories.");
      return { text, spoken: text, source: localSource, origin: "notice", offerLocal: true };
    }
  };

  const respond = (id: number, answer: Answer | null) => {
    setThread((all) => all.map((x) => (x.id === id ? { ...x, answer } : x)));
    if (!answer) { settle("confused", 3200); return; }
    if (autoRead && tts.speak(answer.spoken, () => { if (phaseRef.current === "speaking") setPhase("idle"); })) setPhase("speaking");
    else setPhase("idle");
  };

  const ask = async (question: string, viaVoice: boolean) => {
    clearTimers(); tts.stop();
    const text = question.trim();
    if (!text) return;
    const id = nextId.current++;
    const history = thread;
    setThread((all) => [...all, { id, question: text, answer: null }]);
    setNotice("");
    setPhase("thinking");
    const started = performance.now();
    const gen = turn.current;
    let answer: Answer | null;
    try { answer = (await local(text)) ?? (await general(text, history)); }
    catch (e) {
      if (gen !== turn.current) return;
      setNotice(e instanceof APIError && e.status === 403 ? t("noAccess") : t("errorGeneric"));
      setThread((all) => all.filter((x) => x.id !== id));
      settle("retrying", 2200);
      return;
    }
    // Cleared, stopped or left while waiting: a timer scheduled now could no longer be cancelled.
    if (gen !== turn.current) return;
    if (answer.action && (await act(answer.action, id, gen))) return;
    if (gen !== turn.current) return;
    const final = answer.spoken.trim() || answer.memory ? answer : null;
    later(Math.max(0, 600 - (performance.now() - started)), () => respond(id, final));
  };

  /** Synthetic demo: the server's own question, answered with a fictitious profile; nothing typed is sent. */
  const askFixture = async (fixture: SyntheticQuestion) => {
    clearTimers(); tts.stop();
    const id = nextId.current++;
    setThread((all) => [...all, { id, question: es ? fixture["es-EC"] : fixture["en-US"], answer: null }]);
    setNotice("");
    setPhase("thinking");
    const gen = turn.current;
    let answer: Answer;
    try {
      const reply = await request<ConversationReply>(base + "conversation/", "POST", { fixture: fixture.id, locale });
      answer = {
        text: reply.text, spoken: reply.text, link: reply.source, origin: reply.mode === "mock" ? "mock" : "model",
        source: reply.mode === "mock" ? L("Modo de prueba · sin modelo", "Test mode · no model") : L("Prueba sintética · Meta Muse Spark con un perfil ficticio", "Synthetic test · Meta Muse Spark with a fictitious profile"),
      };
    } catch {
      answer = { text: t("errorGeneric"), spoken: t("errorGeneric"), source: localSource, origin: "notice" };
    }
    if (gen === turn.current) respond(id, answer);
  };

  /** Runs the app feature Meta chose for this turn. true when it took the turn over (no text bubble is shown). */
  const act = async (action: Action, id: number, gen: number) => {
    const raw = action.arguments?.object_name;
    const objectName = typeof raw === "string" ? raw.trim().slice(0, 80) : "";
    if (action.name === "open_sign_translator") { camera.stop(); setVision(false); onOpenSigns(); return true; }
    if (action.name !== "describe_surroundings" && !(action.name === "find_object" && objectName)) return false;
    // Like the eyes button: open the camera first when it is not on yet.
    const ready = (vision && camera.active) || (await openEyes());
    if (gen !== turn.current) return true;
    if (!ready) { setThread((all) => all.filter((x) => x.id !== id)); setPhase("idle"); return true; }
    if (objectName) setSeeking(objectName);
    await look(action.name === "find_object" ? objectName : undefined, id);
    return true;
  };

  const onHeard = (outcome: SpeechOutcome) => {
    if (outcome.kind === "heard") { void ask(outcome.text, true); return; }
    if (outcome.kind === "unavailable") {
      setPhase("idle");
      setNotice(L("No pude reconocer la voz en este navegador. Escribe tu pregunta.", "I couldn't recognise speech in this browser. Type your question."));
      later(50, () => composer.current?.focus());
      return;
    }
    settle("confused", 3200);
  };

  const onMic = async () => {
    if (phase === "listening") { speech.finish(); return; }
    if (phase !== "idle" && phase !== "confused" && phase !== "happy") {
      // Stop: the answer still on its way is dropped, with its unanswered question.
      turn.current++; clearTimers(); tts.stop(); speech.cancel(); setThread((all) => all.filter((x) => x.answer)); setPhase("idle"); return;
    }
    clearTimers(); tts.stop(); setNotice("");
    // The person's consent, read fresh; the browser's own permission is asked afterwards by getUserMedia.
    if (!(await consent.allowed("microphone"))) { setNotice(micNeedsConsent); settle("retrying", 1800); return; }
    const started = await speech.start(onHeard);
    if (started === "consent") { setAskSpeech(true); return; }
    if (started) setPhase("listening");
    else if (started === false) { setNotice(L("No se pudo acceder al micrófono. Revisa el permiso del navegador.", "Couldn't access the microphone. Check the browser permission.")); settle("retrying", 1800); }
  };

  /** Opens the camera like the eyes button; false (with a notice if it failed) when it isn't on. */
  const openEyes = async () => {
    if (!(await consent.allowed("camera"))) { setNotice(cameraNeedsConsent); return false; }
    setVision(true);
    const opened = await camera.start("environment");
    if (opened === true) return true;
    if (opened) { // null: stopped or superseded meanwhile, nothing to report
      setVision(false);
      setNotice(opened === "denied" || !navigator.mediaDevices ? L("No se pudo abrir la cámara. Revisa el permiso del navegador.", "Couldn't open the camera. Check the browser permission.") : L("No hay una cámara disponible.", "No camera is available."));
    }
    return false;
  };
  const toggleVision = async () => {
    if (vision) { camera.stop(); setVision(false); setPrivateTest(false); return; }
    await openEyes();
  };

  const cameraNeedsConsent = L("La persona no ha autorizado el uso de la cámara en este perfil. Puede hacerlo en Autorizaciones.", "The person has not authorized using the camera for this profile. They can do it in Authorizations.");
  const micNeedsConsent = L("La persona no ha autorizado el uso del micrófono en este perfil. Puede hacerlo en Autorizaciones.", "The person has not authorized using the microphone for this profile. They can do it in Authorizations.");
  const revokedText = L("Se retiró una autorización: AINGEL detuvo lo que dependía de ella y descartó las respuestas pendientes.", "An authorization was withdrawn: AINGEL stopped what depended on it and discarded pending answers.");
  // A revocation (here, in another tab or on another device) stops the captures it covers, aborts pending requests
  // and drops their late answers; starting again needs a new grant (allowed() above).
  const consent = useConsentWatch(profile.id, vision || camera.active || phase === "listening" || phase === "thinking" || phase === "searching", (change) => {
    if (change.epoch) {
      inflight.current.forEach((control) => control.abort());
      inflight.current.clear();
      turn.current++; clearTimers();
      setThread((all) => all.filter((x) => x.answer));
    }
    if (change.camera || change.unverified) { camera.stop(); setVision(false); }
    if (change.microphone || change.unverified) speech.cancel();
    tts.stop(); setPhase("idle"); setNotice(revokedText);
  });

  /** One-off capture of the full frame, under the sign-up authorization (camera + Meta); nothing is stored.
   * `existing` answers a turn already in the thread (an action chosen by Meta), whose camera was just opened. */
  const look = async (objectName?: string, existing?: number) => {
    if (!existing && !camera.active) return;
    const gen = turn.current;
    const id = existing ?? nextId.current++;
    const question = objectName ? L(`Busca: ${objectName}`, `Find: ${objectName}`) : L("Describe lo que ves", "Describe what you see");
    if (!existing) setThread((all) => [...all, { id, question, answer: null }]);
    setPhase(objectName ? "searching" : "thinking");
    const testFields = imageTestFields(profile, privateTest);
    setPrivateTest(false);
    const image = await camera.capture();
    if (gen !== turn.current) return;
    if (!image) { setThread((all) => all.filter((x) => x.id !== id)); setNotice(t("errorGeneric")); settle("retrying", 1800); return; }
    const form = new FormData();
    form.append("image", image, "frame.jpg");
    form.append("locale", profile.locale);
    form.append("profile", profile.id);
    for (const [key, value] of Object.entries(testFields)) form.append(key, String(value));
    if (objectName) form.append("object_name", objectName);
    const caution = L("No uses esta respuesta como guía segura para moverte.", "Don't rely on this answer to move around safely.");
    try {
      let answer: Answer;
      if (objectName) {
        const result = await request<Located>("locate/", "POST", form);
        const sides = result.matches.map((m) => ({ left: L("a la izquierda", "on the left"), right: L("a la derecha", "on the right"), center: L("al centro", "in the centre") })[m.horizontal]);
        const text = result.mode === "mock"
          ? L("Modo de prueba: no se analizó la imagen.", "Test mode: the image was not analysed.")
          : sides.length ? L(`Veo ${sides.length} posible(s) ${objectName}: ${sides.join(", ")}.`, `I see ${sides.length} possible ${objectName}: ${sides.join(", ")}.`) : L(`No encontré ${objectName} en esta imagen.`, `I didn't find ${objectName} in this image.`);
        answer = { text: <>{text} <span className="muted">{caution}</span></>, spoken: text, origin: "vision",
          source: result.mode === "mock" ? L("Modo de prueba · imagen no enviada", "Test mode · image not sent") : L(`Meta ${result.model ?? "SAM"} · imagen no guardada`, `Meta ${result.model ?? "SAM"} · image not stored`) };
      } else {
        const result = await request<Scene>("scene/", "POST", form);
        answer = { text: <>{result.text} <span className="muted">{caution}</span></>, spoken: result.text, origin: "vision",
          source: result.mode === "mock" ? L("Modo de prueba · imagen no enviada", "Test mode · image not sent") : L("Meta Muse Spark · imagen no guardada", "Meta Muse Spark · image not stored") };
      }
      if (gen === turn.current) respond(id, answer);
    } catch (e) {
      if (gen !== turn.current) return;
      const code = e instanceof APIError ? String((e.detail as { error?: unknown } | null)?.error ?? "") : "";
      if (stopsCapture(code)) { camera.stop(); setVision(false); }
      const detail = e instanceof APIError ? JSON.stringify(e.detail) : "";
      const text = code === "camera_consent_revoked" || code === "consent_changed" ? revokedText : detail.includes("privacy_review")
        ? L("La prueba no está autorizada. Comprueba los permisos en Personalizar y confirma la prueba privada antes de cada imagen.", "The test is not authorized. Check permissions in Personalize and confirm the private test before each image.")
        : L("No pude analizar la imagen ahora. Inténtalo de nuevo.", "I couldn't analyse the image right now. Please try again.");
      respond(id, { text, spoken: text, source: localSource, origin: "notice" });
    }
  };

  useEffect(() => { if (initialQuestion) void ask(initialQuestion, false); }, []);
  useEffect(() => () => camera.stop(), []);

  const confirmNext = (item: Routine) => run(async () => {
    await api(`${base}routines/${item.id}/confirm/`, "POST");
    await load();
    clearTimers(); settle("happy", 3000);
  });

  const clearConversation = () => { turn.current++; clearTimers(); tts.stop(); speech.cancel(); setThread([]); setNotice(""); setPhase("idle"); };

  const status: Record<OrbState, string> = {
    idle: vision ? L("AINGEL está mirando", "AINGEL is looking") : L("Estoy aquí para ayudar.", "I'm here to help."),
    listening: L("AINGEL está escuchando", "AINGEL is listening"),
    thinking: L("AINGEL está pensando", "AINGEL is thinking"),
    searching: L("AINGEL está buscando", "AINGEL is searching"),
    speaking: L("AINGEL está respondiendo", "AINGEL is answering"),
    retrying: L("AINGEL lo intenta de nuevo", "AINGEL is trying again"),
    happy: L("¡Listo!", "Done!"),
    confused: L("No entendí bien. ¿Puedes repetirlo?", "I didn't quite get that. Can you say it again?"),
  };
  const hint: Record<OrbState, string> = {
    idle: vision ? L("Apunta hacia lo que quieres que vea", "Point at what you want me to see") : L("Toca para hablar", "Tap to talk"), listening: L("Toca para terminar", "Tap to finish"),
    thinking: L("Un momento…", "One moment…"), searching: L("Un momento…", "One moment…"),
    speaking: L("Toca para detener", "Tap to stop"), retrying: L("Un momento…", "One moment…"),
    happy: L("Toca para hablar", "Tap to talk"), confused: L("Toca para hablar", "Tap to talk"),
  };
  const busyPhase = phase !== "idle" && phase !== "happy" && phase !== "confused";
  const syntheticControl = (
    <SyntheticConversationConsent es={es} checked={syntheticConversation} disabled={busyPhase} onChange={(next) => {
      clearConversation(); setDraft(""); setSyntheticConversation(next);
    }} onPick={(q) => void askFixture(q)} />
  );
  const speechConsent = askSpeech
    ? <BrowserSpeechConsent es={es} onAccept={() => void speech.accept(true).then((ok) => { setAskSpeech(false); if (ok) void onMic(); else openComposer(); })} onDecline={() => { setAskSpeech(false); openComposer(); }} />
    : speech.accepted && speech.place === "browser_service" && phase !== "listening" ? <BrowserSpeechRevoke es={es} onRevoke={() => void speech.accept(false)} /> : null;
  const level = phase === "listening" ? speech.level : phase === "speaking" ? tts.level : undefined;
  const micButton = (size: "lg" | "sm") => (
    <button type="button" className={`mic-btn mic-btn--${size}`} onClick={() => void onMic()} aria-label={hint[phase]}>
      {busyPhase ? <span className="mic-stop" /> : <MicIcon size={size === "lg" ? 28 : 22} />}
    </button>
  );
  const suggestions = [L("¿Qué tengo que hacer hoy?", "What do I need to do today?"), L("¿Dónde vi este objeto?", "Where did I see this object?"), L("¿Qué me han dicho?", "What have I been told?")];
  const greeting = { morning: L("Buenos días", "Good morning"), afternoon: L("Buenas tardes", "Good afternoon"), evening: L("Buenas noches", "Good evening") }[greetingKey(profile.timezone)];
  const dateText = longDate(locale, profile.timezone);
  const next = today.next;
  const nextIn = today.minutesUntil;
  const nextLabel = nextIn === null ? "" : nextIn > 0 ? (nextIn < 60 ? L(`en ${nextIn} min`, `in ${nextIn} min`) : L(`en ${Math.floor(nextIn / 60)} h ${nextIn % 60} min`, `in ${Math.floor(nextIn / 60)} h ${nextIn % 60} min`)) : nextIn === 0 ? L("ahora", "now") : L("pendiente", "overdue");
  const askOther = (q: string) => {
    if (q === suggestions[1]) { setDraft(L("¿Dónde dejé mis ", "Where did I leave my ")); openComposer(); return; }
    void ask(q, false);
  };
  const [composerOpen, setComposerOpen] = useState(false);
  const openComposer = () => { setComposerOpen(true); later(50, () => composer.current?.focus()); };
  const inConversation = (thread.length > 0 || composerOpen) && phase !== "listening";
  const listeningMobile = mobile && phase === "listening";
  const eyesLabel = vision ? L("Dejar de mirar", "Stop looking") : L("Dejar que AINGEL vea", "Let AINGEL see");
  const handLabel = L("Traducir lengua de señas", "Sign language translation");

  const orb = (size: number) => (
    <div className={`orb-window${vision ? " is-vision" : ""}`} style={{ width: size, height: size }}>
      <video ref={camera.bind} className="orb-camera" muted playsInline aria-hidden="true" />
      <AingelOrb size={size} state={phase} audioLevel={level} reducedMotion={reduced} vision={vision && camera.active} background={vision ? "#ffffff" : undefined} />
    </div>
  );
  const topButtons = (
    <div className="top-actions">
      <button type="button" className="round-btn" aria-label={handLabel} title={handLabel} onClick={() => { camera.stop(); setVision(false); onOpenSigns(); }}><HandIcon size={22} color="#092E66" /></button>
      <EyesButton on={vision} label={eyesLabel} onClick={() => void toggleVision()} />
    </div>
  );
  const visionPanel = vision && camera.active && (
    <div className="vision-panel">
      <PrivateMediaConsent profile={profile} kind="image" checked={privateTest} onChange={setPrivateTest} disabled={busyPhase} />
      <div className="vision-actions">
        <button type="button" className="btn btn-primary btn-sm btn-pill" disabled={busyPhase} onClick={() => void look()}>{L("Describir lo que ves", "Describe what you see")}</button>
        <form className="seek-form" onSubmit={(e) => { e.preventDefault(); const o = seeking.trim(); if (o) void look(o); }}>
          <input value={seeking} onChange={(e) => setSeeking(e.target.value)} maxLength={80} placeholder={L("Objeto a buscar", "Object to find")} aria-label={L("Objeto a buscar", "Object to find")} />
          <button className="btn btn-outline btn-sm btn-pill" disabled={busyPhase || !seeking.trim()}>{L("Buscar", "Find")}</button>
        </form>
      </div>
      <span className="mic-privacy">{L("Cámara activa · la imagen no se guarda", "Camera on · the image is not stored")}</span>
    </div>
  );

  const answerView = (x: Exchange) => x.answer && (
    <div className="answer" aria-live="polite">
      {x.answer.memory ? (
        <div className="memory-card">
          <span className="memory-lead">{x.answer.memory.lead}</span>
          <span className="memory-value">{x.answer.memory.value}</span>
          <span className="memory-meta">{x.answer.memory.meta}</span>
          <span className="memory-rule" />
          <span className="memory-note">{x.answer.memory.note}</span>
        </div>
      ) : <p className="answer-text">{x.answer.text}</p>}
      {x.answer.excerpt && <blockquote className="answer-excerpt">{x.answer.excerpt}…</blockquote>}
      {!!x.answer.cards?.length && (
        <div className="answer-cards">
          {x.answer.cards.map((c, i) => (
            <div className="answer-card" key={i}>{c.time && <span className="answer-card-time">{c.time}</span>}<div><b>{c.title}</b><small>{c.meta}</small></div></div>
          ))}
        </div>
      )}
      {x.answer.offerLocal && (
        <div className="suggestions suggestions--inline">
          {[suggestions[0], suggestions[2]].map((s) => <button type="button" key={s} className="pill" disabled={busyPhase} onClick={() => void ask(s, false)}>{s}</button>)}
        </div>
      )}
      <div className="answer-foot">
        <span className="source"><span className={`chip chip--${x.answer.origin}`}>{x.answer.origin === "model" ? "Meta" : x.answer.origin === "vision" ? L("Imagen", "Image") : L("Fuente", "Source")}</span>
          {x.answer.source}
          {x.answer.link && <> · <a href={x.answer.link.url} target="_blank" rel="noopener noreferrer">{x.answer.link.title}</a> ({x.answer.link.source})</>}
          {x.answer.web?.map((w) => <span key={w.url}> · <a href={w.url} target="_blank" rel="noopener noreferrer">{w.title}</a></span>)}
        </span>
        <div className="answer-actions">
          <button type="button" className="btn btn-outline btn-sm btn-pill" onClick={() => { if (tts.speak(x.answer!.spoken, () => setPhase("idle"))) setPhase("speaking"); }}>{L("Repetir", "Repeat")}</button>
          <button type="button" className="btn btn-primary btn-sm btn-pill" onClick={() => { tts.stop(); setPhase("idle"); }}>{L("Detener lectura", "Stop reading")}</button>
        </div>
      </div>
    </div>
  );

  const conversation = inConversation && (
    <div className="convo">
      <div className="convo-head">
        <div className="convo-tools">
          <button type="button" className="text-btn" onClick={() => { clearConversation(); setComposerOpen(false); }}>‹ {L("Inicio", "Home")}</button>
          {topButtons}
        </div>
        {orb(mobile ? 170 : 200)}
        <span role="status" aria-live="polite" className="convo-status">
          {(phase === "speaking" || phase === "thinking" || phase === "searching") && <span className={`dot dot--${phase === "speaking" ? "gold" : "blue"}`} />}
          {status[phase]}
        </span>
        {visionPanel}
      </div>
      <div className="convo-body">
        {thread.map((x) => (
          <div className="turn" key={x.id}>
            {x.question && <div className="bubble">{x.question}</div>}
            {answerView(x)}
          </div>
        ))}
        {speechConsent}
        {notice && <p className="home-notice" role="alert">{notice}</p>}
        <div ref={threadEnd} />
      </div>
      <div className="convo-controls">
        {syntheticControl}
        <label className="switch-line"><input type="checkbox" checked={autoRead} onChange={(e) => { setAutoRead(e.target.checked); if (!e.target.checked) tts.stop(); }} />{L("Leer respuestas en voz alta", "Read answers aloud")}</label>
        {!!thread.length && <button type="button" className="text-btn" onClick={clearConversation}>{L("Borrar conversación", "Clear conversation")}</button>}
        {!tts.supported && <span className="muted">{L("Este navegador no tiene voz para leer.", "This browser has no voice to read aloud.")}</span>}
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); const q = draft; setDraft(""); void ask(q, false); }}>
        <label className="sr-only" htmlFor="composer-input">{L("Pregunta", "Question")}</label>
        <input id="composer-input" ref={composer} value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={1000} placeholder={L("Escribe o pulsa para hablar…", "Type or tap to talk…")} autoComplete="off" />
        {draft.trim()
          ? <button className="mic-btn mic-btn--sm" aria-label={L("Enviar", "Send")}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg></button>
          : micButton("sm")}
      </form>
    </div>
  );

  return (
    <div className={`home${inConversation ? " home--convo" : ""}${listeningMobile ? " home--focus" : ""}`}>
      <section className="home-center">
        {!inConversation ? (
          <>
            <div className="home-top">
              <span className="home-date">{dateText}</span>
              <div className="home-top-right">
                <span className="status-badge"><span className="dot dot--gold" />{profile.ready ? L("Círculo configurado", "Circle set up") : L("Círculo en borrador", "Circle in draft")}</span>
                {topButtons}
              </div>
            </div>
            <div className="home-top-mobile">
              <div><span className="home-hello">{L("Hola", "Hi")}, {name}</span><span className="home-date">{dateText}</span></div>
              {topButtons}
              <span className="avatar avatar--44">{initials(profile.display_name)}</span>
            </div>
            {listeningMobile && <span className="listen-pill" role="status"><span className="dot dot--blue" />{status.listening}</span>}
            <h1 className="home-greeting">{greeting}, {name}</h1>
            <div className="home-orb">{orb(mobile ? (listeningMobile ? 290 : 250) : 340)}</div>
            {listeningMobile
              ? <p className="listen-transcript">{speech.transcript || L("Te escucho", "I'm listening")}<span>…</span></p>
              : <p role="status" aria-live="polite" className="home-status">{status[phase]}</p>}
            {!mobile && phase === "listening" && <p className="listen-transcript-web" aria-live="polite">{speech.transcript}</p>}
            {visionPanel}
            <div className="home-mic">
              {micButton("lg")}
              <span className="home-hint">{hint[phase]}</span>
              {phase === "listening" && <span className="mic-privacy">{micPrivacyLine(es, speech.place)}</span>}
              {phase === "idle" && <button type="button" className="text-btn" onClick={openComposer}>{L("Prefiero escribir", "I'd rather type")}</button>}
            </div>
            {syntheticControl}
            {speechConsent}
            {notice && <p className="home-notice" role="alert">{notice}</p>}
            <div className="suggestions">
              {suggestions.map((s) => <button type="button" key={s} className="pill" disabled={busyPhase} onClick={() => askOther(s)}>{s}</button>)}
            </div>
            {next && (
              <button type="button" className="next-mobile" onClick={onOpenToday}>
                <span><small>{L("SIGUIENTE", "NEXT")} · {hhmm(next.at)}</small><b>{next.title}</b></span>
                <span className="ring ring--gold" />
              </button>
            )}
          </>
        ) : conversation}
      </section>
      <aside className="today-panel" aria-label={t("dashboard")}>
        <div className="today-head"><h2>{t("dashboard")}</h2><span>{today.list.length ? L(`${today.done} de ${today.list.length} completadas`, `${today.done} of ${today.list.length} done`) : ""}</span></div>
        {next ? (
          <div className="next-card">
            <div className="next-card-top"><span>{L("SIGUIENTE", "NEXT")}</span><small>{nextLabel}</small></div>
            <div className="next-card-main"><b>{hhmm(next.at)}</b><span>{next.title}</span></div>
            {profile.permissions.configure && <button type="button" disabled={busy} onClick={() => void confirmNext(next)}>{L("Confirmar realización", "Confirm it's done")}</button>}
          </div>
        ) : (
          <div className="next-card next-card--empty"><span>{today.list.length ? L("Todo listo por hoy.", "All done for today.") : L("No hay rutinas para hoy.", "No routines today.")}</span></div>
        )}
        <div className="today-list">
          {today.list.filter((x) => x.id !== next?.id).slice(-5).map((r) => (
            <button type="button" className="today-row" key={r.id} onClick={onOpenToday}>
              <span className="today-time">{hhmm(r.at)}</span>
              <span className={`today-title${r.confirmed_today ? " is-done" : ""}`}>{r.title}</span>
              <span className={`ring${r.confirmed_today ? " ring--done" : ""}`}>{r.confirmed_today && <Check />}</span>
            </button>
          ))}
        </div>
        <div className="last-message">
          <span className="overline">{L("ÚLTIMO MENSAJE", "LATEST MESSAGE")}</span>
          {lastMessage ? (
            <>
              <p>{lastMessage.body}</p>
              <span>{lastMessage.author} · {time(lastMessage.created_at)}</span>
            </>
          ) : <p className="muted">{t("noMessages")}</p>}
        </div>
      </aside>
    </div>
  );
}
