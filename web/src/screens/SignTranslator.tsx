import { useEffect, useRef, useState, type ReactNode } from "react";
import AingelOrb, { type OrbState } from "../components/aingel/AingelOrb";
import AingelSigner from "../components/aingel/AingelSigner";
import AingelHands3D from "../components/aingel/AingelHands3D";
import { HANDS_SPEED } from "../components/aingel/signData";
import { HandIcon } from "../components/aingel/HandIcon";
import { BOARD, GLOSS_VOCABULARY, PICTOGRAM, buildSentence, glossSeq, signName, type Built, type SignId } from "../components/aingel/signLexicon";
import { api } from "../api";
import { useSpeechInput, type SpeechOutcome } from "../components/aingel/useSpeechInput";
import BrowserSpeechConsent, { BrowserSpeechRevoke, micPrivacyLine } from "../components/BrowserSpeechConsent";
import { useSpeechSynthesisLevel } from "../components/aingel/useOutputAudioLevel";
import { useCamera } from "../components/aingel/useCamera";
import { useCommunication } from "../Communication";
import { useMediaQuery } from "../useMediaQuery";
import type { WithProfile } from "../ui";

type Mode = "voice-to-sign" | "text-to-sign" | "sign-to-voice" | "sign-to-text";

const Icon = ({ d, size = 22 }: { d: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
);
const MIC = "M9 3h6v11H9zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21";
const SPEAKER = "M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11";
const TEXT = "M5 6h14M12 6v13M9 19h6";
const ARROW = "M5 12h14M13 6l6 6-6 6";
const CHEVRON = "M6 9l6 6 6-6";
const NOT_AVAILABLE = "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M5.6 5.6l12.8 12.8";
/** Orb expression while a sign plays, as in the catalogue. */
const EXPRESSION: Record<string, OrbState> = { hola: "happy", gracias: "happy", bien: "happy", si: "happy", jugar: "happy", hija: "happy", mal: "retrying", dolor: "retrying", dormir: "thinking", pregunta: "confused" };
const SPEEDS = [HANDS_SPEED, 1, 0.75, 0.5];
const EXAMPLES = ["Mañana quiero ir al parque con mi hija", "¿Tienes hambre?", "Me llamo Rosa", "Necesito mi medicina, por favor", "¿Dónde está el baño?"];

/**
 * Sign translator: AINGEL signs with its floating hands (signs catalogue v1.5.0, AINGEL design pending LSEC
 * validation). Voice or text → signs uses the catalogue's sentence rule: words with a sign are signed, the
 * rest is fingerspelled and articles are dropped. Signs → voice / text: no automatic recognition exists yet,
 * so the signer builds the message on a pictogram board and AINGEL says it or shows it.
 */
export default function SignTranslator({ profile, locale, onBack }: WithProfile & { onBack: () => void }) {
  const es = locale === "es-EC";
  const L = (a: string, b: string) => (es ? a : b);
  const name = (id: SignId) => signName(id, es);
  // Board and message labels: capitalised, without the question marks of «¿pregunta?».
  const label = (id: SignId) => { const n = name(id).replace(/[¿?]/g, ""); return n.charAt(0).toUpperCase() + n.slice(1); };
  const mobile = useMediaQuery("(max-width: 760px)");
  const { value: communication } = useCommunication(profile.id);
  const speech = useSpeechInput(profile.locale);
  const [askSpeech, setAskSpeech] = useState(false);
  const tts = useSpeechSynthesisLevel(profile.locale, communication?.pace === "slow" ? 0.8 : 1);
  const camera = useCamera();
  const [mode, setMode] = useState<Mode>("voice-to-sign");
  const [menu, setMenu] = useState(false);
  const [seq, setSeq] = useState<SignId[]>([]);
  const [built, setBuilt] = useState<Built["words"]>([]);
  const [byMeaning, setByMeaning] = useState(false); // signs chosen by Meta from the meaning, not word by word
  const glossCache = useRef(new Map<string, SignId[]>());
  const latest = useRef("");
  const [playKey, setPlayKey] = useState(0);
  const [current, setCurrent] = useState(-1);
  const [speed, setSpeed] = useState(communication?.pace === "slow" ? 1 : HANDS_SPEED);
  // three.js hands; the 2D signer takes over when WebGL is not available.
  const [hands3d, setHands3d] = useState(true);
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [orb, setOrb] = useState<OrbState>("idle");
  const [result, setResult] = useState<"" | "thinking" | "signing" | "unsupported" | "no-speech" | "unavailable">("");
  const [message, setMessage] = useState<SignId[]>([]);
  const [text, setText] = useState("");
  const [shown, setShown] = useState(false);
  const timer = useRef(0);
  const reduced = !!profile.preferences.reduced_motion;
  const signsOut = mode === "voice-to-sign" || mode === "text-to-sign";
  useEffect(() => () => clearTimeout(timer.current), []);
  // The communication settings load after the first render: apply a slow pace when it arrives.
  useEffect(() => { if (communication?.pace === "slow") setSpeed(1); }, [communication?.pace]);
  // latest is reset so a Meta gloss still in flight for the previous mode can't sign afterwards.
  useEffect(() => { latest.current = ""; if (signsOut) camera.stop(); speech.cancel(); setShown(false); setSeq([]); setBuilt([]); setByMeaning(false); setHeard(""); setResult(""); setOrb("idle"); }, [mode]);

  const settle = (state: OrbState, ms: number) => { setOrb(state); clearTimeout(timer.current); timer.current = window.setTimeout(() => setOrb("idle"), ms); };
  const sign = (ids: SignId[]) => { clearTimeout(timer.current); setOrb("idle"); setSeq(ids); setCurrent(-1); setPlayKey((k) => k + 1); };
  const onSign = (i: number) => {
    setCurrent(i);
    // Expression of the sign being made; happy at the end of the phrase ("Entendido").
    if (i >= 0) setOrb(EXPRESSION[seq[i]] ?? "idle"); else settle("happy", 2200);
  };
  /** Signs by meaning (Meta, backend assistance.gloss), or null to use the local rule: test mode, no authorization
   * from sign-up, no connection, slow answer or an unusable gloss. */
  const signsByMeaning = async (value: string): Promise<SignId[] | null> => {
    const key = value.trim().toLowerCase().slice(0, 300);
    const cached = glossCache.current.get(key);
    if (cached) return cached;
    const asked = api<{ gloss: unknown }>(`profiles/${profile.id}/signs/gloss/`, "POST", { text: value.trim().slice(0, 300), vocabulary: GLOSS_VOCABULARY })
      .then((reply) => glossSeq(reply.gloss)).catch(() => null);
    const seq = await Promise.race([asked, new Promise<null>((done) => window.setTimeout(() => done(null), 6000))]);
    if (seq) { glossCache.current.set(key, seq); if (glossCache.current.size > 64) glossCache.current.delete(glossCache.current.keys().next().value!); }
    return seq;
  };
  const interpret = async (value: string) => {
    latest.current = value;
    setHeard(value); setBuilt([]); setByMeaning(false); setSeq([]); setResult("thinking"); clearTimeout(timer.current); setOrb("thinking");
    // By meaning first (Meta); the word-by-word rule when Meta is not available.
    const meant = await signsByMeaning(value);
    if (latest.current !== value) return; // a newer sentence came in meanwhile
    if (meant?.length) { setByMeaning(true); setResult("signing"); sign(meant); return; }
    const b = buildSentence(value);
    setBuilt(b?.words ?? []);
    if (!b) { setResult("unsupported"); settle("confused", 3500); return; }
    setResult("signing"); sign(b.seq);
  };
  const onHeard = (outcome: SpeechOutcome) => {
    if (outcome.kind === "heard") { interpret(outcome.text); return; }
    setResult(outcome.kind === "unavailable" ? "unavailable" : "no-speech"); settle("confused", 3000);
  };
  const listen = async () => {
    if (speech.listening) { speech.finish(); return; }
    latest.current = ""; setSeq([]); setBuilt([]); setByMeaning(false); setResult(""); setHeard(""); tts.stop();
    const started = await speech.start(onHeard);
    if (started === "consent") { setAskSpeech(true); return; }
    if (started) setOrb("listening");
    else if (started === false) { setResult("unavailable"); settle("retrying", 2000); }
  };
  const say = (value: string) => { if (value.trim() && tts.speak(value, () => setOrb("idle"))) setOrb("speaking"); };
  const add = (id: SignId) => { const next = [...message, id]; setMessage(next); sign([id]); setText(next.map(label).join(" ")); };
  const removeAt = (i: number) => { const next = message.filter((_, j) => j !== i); setMessage(next); setText(next.map(label).join(" ")); };
  const choose = (m: Mode) => { setMode(m); setMenu(false); };

  const MODES: { id: Mode; label: string; from: ReactNode; to: ReactNode }[] = [
    { id: "voice-to-sign", label: L("Voz a señas", "Voice to signs"), from: <Icon d={MIC} />, to: <HandIcon /> },
    { id: "text-to-sign", label: L("Texto a señas", "Text to signs"), from: <Icon d={TEXT} />, to: <HandIcon /> },
    { id: "sign-to-voice", label: L("Señas a voz", "Signs to voice"), from: <HandIcon />, to: <Icon d={SPEAKER} /> },
    { id: "sign-to-text", label: L("Señas a texto", "Signs to text"), from: <HandIcon />, to: <Icon d={TEXT} /> },
  ];
  const active = MODES.find((m) => m.id === mode)!;

  const statusText = (() => {
    if (speech.listening) return L("AINGEL está escuchando", "AINGEL is listening");
    if (orb === "speaking") return L("AINGEL lo dice en voz alta", "AINGEL is saying it aloud");
    if (signsOut) {
      if (result === "signing") return current >= 0 ? L("AINGEL lo dice en señas", "AINGEL is signing it") : L("Listo. Toca ↻ para verlo otra vez.", "Done. Tap ↻ to see it again.");
      if (result === "thinking") return L("Entendiendo la frase…", "Understanding the sentence…");
      if (result === "unsupported") return L("No encontré palabras para signar", "I found no words to sign");
      if (result === "no-speech") return L("No escuché nada. Toca para intentarlo otra vez.", "I heard nothing. Tap to try again.");
      if (result === "unavailable") return L("El reconocimiento de voz no está disponible aquí", "Speech recognition isn't available here");
      return mode === "voice-to-sign" ? L("Toca el micrófono y habla", "Tap the microphone and speak") : L("Escribe una frase y AINGEL la signa", "Type a sentence and AINGEL signs it");
    }
    return camera.active ? L("Cámara abierta · AINGEL aún no reconoce señas por sí solo", "Camera open · AINGEL can't recognise signs on its own yet") : L("Toca las señas para formar tu mensaje", "Tap the signs to build your message");
  })();

  // Stage proportions from the catalogue (orb 300 px, r 87 → r ≈ 0.29 × orb; hands span ≈ 6 r).
  const r = mobile ? 46 : 68, S = Math.round(r / 0.29), W = r * 6, H = Math.round(r * 5.3), cy = r * 2;
  const level = speech.listening ? speech.level : orb === "speaking" ? tts.level : undefined;
  const seeing = !signsOut && camera.active;
  const WORD_CLASS = { sign: "word--sign", spell: "word--spell", skip: "word--skip" } as const;

  return (
    <div className="signs">
      <header className="signs-head">
        <button type="button" className="text-btn" onClick={() => { speech.cancel(); camera.stop(); tts.stop(); onBack(); }}>‹ {L("Asistente", "Assistant")}</button>
        <h1><span className="signs-hand"><HandIcon size={26} color="#092E66" /></span>{L("Traductor de señas", "Sign translator")}</h1>
      </header>

      <section className="signs-stage" aria-live="polite">
        <div className="sign-avatar" style={{ width: W, height: H }}>
          <div className={`orb-window${seeing ? " is-vision" : ""}`} style={{ width: S, height: S, left: (W - S) / 2, top: cy - S / 2 }}>
            <video ref={camera.bind} className="orb-camera orb-camera--mirror" muted playsInline aria-hidden="true" />
            <AingelOrb size={S} state={speech.listening ? "listening" : orb} audioLevel={level} reducedMotion={reduced}
              vision={seeing} background={seeing ? "#ffffff" : undefined} />
          </div>
          {hands3d
            ? <AingelHands3D width={W} height={H} cx={W / 2} cy={cy} r={r} seq={seq} playKey={playKey} speed={speed} reducedMotion={reduced} onSign={onSign} onUnavailable={() => setHands3d(false)} />
            : <AingelSigner width={W} height={H} cx={W / 2} cy={cy} r={r} seq={seq} playKey={playKey} speed={speed} reducedMotion={reduced} onSign={onSign} />}
        </div>
        <p role="status" className="signs-status">{result === "unsupported" && <Icon d={NOT_AVAILABLE} size={20} />} {statusText}</p>
        {/* On the board the controls stay put, so tapping a sign never moves the board. */}
        {(seq.length > 0 || !signsOut) && (
          <>
            {signsOut && <div className="sign-strip" aria-label={L("Señas", "Signs")}>
              {seq.map((id, i) => <span key={i} className={`sign-chip${i === current ? " is-on" : ""}`}>{name(id)}</span>)}
            </div>}
            <div className="sign-controls">
              <button type="button" className="round-btn" aria-label={L("Repetir señas", "Repeat signs")} title={L("Repetir", "Repeat")} disabled={!seq.length} onClick={() => sign(seq)}>↻</button>
              <button type="button" className="speed-btn" aria-label={L("Velocidad", "Speed")} onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}>{speed}×</button>
              <span className="validation validation--illustrative">{L("Diseño AINGEL · pendiente de validar en LSEC", "AINGEL design · pending LSEC validation")}</span>
            </div>
          </>
        )}
      </section>

      <div className="translate-menu">
        <button type="button" className={`translate-btn${menu ? " is-open" : ""}`} aria-expanded={menu} aria-haspopup="menu" onClick={() => setMenu((v) => !v)}>
          <span className="eyes-glyph"><i /><i /></span>
          <span className="translate-label"><small>{L("Traducir", "Translate")}</small>{active.label}</span>
          <Icon d={CHEVRON} size={20} />
        </button>
        {menu && (
          <div className="translate-options" role="menu" aria-label={L("Modo de traducción", "Translation mode")}>
            {MODES.map((m) => (
              <button key={m.id} type="button" role="menuitemradio" aria-checked={mode === m.id} className={`translate-option${mode === m.id ? " is-on" : ""}`} onClick={() => choose(m.id)}>
                <span className="mode-icons">{m.from}<Icon d={ARROW} size={14} />{m.to}</span>
                <span>{m.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {mode === "voice-to-sign" && (
        <section className="signs-panel">
          <button type="button" className="mic-btn mic-btn--lg" onClick={() => void listen()} aria-label={speech.listening ? L("Toca para terminar", "Tap to finish") : L("Toca para hablar", "Tap to talk")}>
            {speech.listening ? <span className="mic-stop" /> : <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0" /><path d="M12 17.5V21" /></svg>}
          </button>
          {speech.listening && <span className="mic-privacy">{micPrivacyLine(es, speech.place)}</span>}
          {askSpeech && <BrowserSpeechConsent es={es} onAccept={() => { speech.accept(true); setAskSpeech(false); void listen(); }} onDecline={() => setAskSpeech(false)} />}
          {speech.accepted && speech.place === "browser_service" && !speech.listening && <BrowserSpeechRevoke es={es} onRevoke={() => speech.accept(false)} />}
          {heard && <p className="heard"><span className="chip">{L("Escuché", "I heard")}</span> {heard}</p>}
        </section>
      )}
      {mode === "text-to-sign" && (
        <section className="signs-panel">
          <form className="sign-type" onSubmit={(e) => { e.preventDefault(); if (typed.trim()) interpret(typed.trim()); }}>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} maxLength={200} placeholder={L("Escribe una frase", "Type a sentence")} aria-label={L("Frase para signar", "Sentence to sign")} />
            <button className="btn btn-primary btn-pill" disabled={!typed.trim()}>{L("Signar", "Sign")}</button>
          </form>
          {es && (
            <div className="sign-examples">
              {EXAMPLES.map((x) => <button key={x} type="button" className="example-chip" onClick={() => { setTyped(x); interpret(x); }}>{x}</button>)}
            </div>
          )}
        </section>
      )}
      {signsOut && byMeaning && seq.length > 0 && (
        <p className="sign-words"><small>{L("Señas elegidas por el sentido de la frase (Meta), con el vocabulario de AINGEL.", "Signs chosen from the meaning of the sentence (Meta), with AINGEL's vocabulary.")}</small></p>
      )}
      {signsOut && built.length > 0 && (
        <div className="sign-words">
          <div>{built.map((w, i) => <span key={i} className={`word ${WORD_CLASS[w.k]}`}>{w.t}</span>)}</div>
          <small>{L("Azul: tiene seña · Dorado: se deletrea · Tachado: se omite. El tiempo va al inicio y la pregunta al final.", "Blue: has a sign · Gold: fingerspelled · Struck out: dropped. Time goes first and the question last.")}</small>
        </div>
      )}

      {!signsOut && (
        <section className="signs-panel signs-panel--board">
          <button type="button" className={`btn btn-pill ${camera.active ? "btn-primary" : "btn-outline"}`} aria-pressed={camera.active} onClick={() => void (camera.active ? camera.stop() : camera.start("user"))}>
            {camera.active ? L("Cerrar cámara", "Close camera") : L("Abrir cámara para signar", "Open camera to sign")}
          </button>
          {camera.active && <span className="mic-privacy">{L("Cámara activa · la imagen no se guarda ni se envía", "Camera on · the image is not stored or sent")}</span>}
          {camera.error && <span className="home-notice">{L("No se pudo abrir la cámara.", "Couldn't open the camera.")}</span>}
          <p className="recognizer-note"><Icon d={NOT_AVAILABLE} size={18} /> {L("AINGEL aún no reconoce señas por la cámara. Toca las señas de tu mensaje.", "AINGEL can't recognise signs from the camera yet. Tap the signs of your message.")}</p>
          <div className="sign-board" role="list" aria-label={L("Señas", "Signs")}>
            {BOARD.map((id) => (
              <button type="button" role="listitem" key={id} className="sign-card" onClick={() => add(id)} aria-label={label(id)}>
                <Icon d={PICTOGRAM[id]} size={28} /><span>{label(id)}</span>
              </button>
            ))}
          </div>
          {message.length > 0 && (
            <div className="sign-message" aria-label={L("Tu mensaje", "Your message")}>
              {message.map((id, i) => (
                <button type="button" key={i} className="sign-chip" onClick={() => removeAt(i)} aria-label={`${L("Quitar", "Remove")} ${label(id)}`}>
                  <Icon d={PICTOGRAM[id]} size={18} /> {label(id)} ×
                </button>
              ))}
              <button type="button" className="text-btn" onClick={() => sign(message)}>↻ {L("Ver en señas", "See in signs")}</button>
              <button type="button" className="text-btn muted" onClick={() => { setMessage([]); setText(""); }}>{L("Borrar", "Clear")}</button>
            </div>
          )}
          {mode === "sign-to-voice" && (
            <div className="actions sign-say">
              <button type="button" className="btn btn-primary btn-pill" disabled={!text.trim()} onClick={() => say(text)}><Icon d={SPEAKER} size={18} /> {L("Decir en voz alta", "Say it aloud")}</button>
              {orb === "speaking" && <button type="button" className="btn btn-outline btn-pill" onClick={() => { tts.stop(); setOrb("idle"); }}>{L("Detener", "Stop")}</button>}
            </div>
          )}
          {mode === "sign-to-text" && (
            <div className="sign-text">
              <label className="input-field"><span>{L("Texto para la otra persona (puedes corregirlo)", "Text for the other person (you can correct it)")}</span>
                <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} rows={3} /></label>
              <div className="actions">
                <button type="button" className="btn btn-primary btn-pill" disabled={!text.trim()} onClick={() => setShown(true)}>{L("Mostrar en grande", "Show large")}</button>
                <button type="button" className="btn btn-outline btn-pill" disabled={!text.trim()} onClick={() => say(text)}>{L("Leer en voz alta", "Read aloud")}</button>
              </div>
            </div>
          )}
        </section>
      )}
      {shown && (
        <div className="big-text" role="dialog" aria-label={L("Texto en grande", "Large text")} onClick={() => setShown(false)}>
          <p>{text}</p>
          <span className="muted">{L("Toca para cerrar", "Tap to close")}</span>
        </div>
      )}
      <footer className="signs-credits">
        <p>{L("Señas diseñadas por AINGEL (alfabeto, números, 43 palabras y acciones), pendientes de validar con personas sordas señantes de LSEC. Las frases se interpretan con una regla simple, no con la gramática completa de LSEC. AINGEL no sustituye a una persona intérprete.",
          "Signs designed by AINGEL (alphabet, numbers, 43 words and actions), pending validation with Deaf LSEC signers. Sentences use a simple rule, not full LSEC grammar. AINGEL does not replace an interpreter.")}</p>
      </footer>
    </div>
  );
}
