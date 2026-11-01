import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import AingelOrb from "../components/aingel/AingelOrb";
import type { translator, Locale } from "../i18n";
import type { Territory } from "../types";

export type Who = "me" | "other";
type Props = {
  t: ReturnType<typeof translator>;
  locale: Locale;
  setLocale: (l: Locale) => void;
  busy: boolean;
  error: string;
  mfaRequired: boolean;
  onLogin: (data: Record<string, FormDataEntryValue>) => void;
  onRegister: (data: Record<string, FormDataEntryValue | boolean>, extra: { name: string; who: Who }) => void;
  onMfa: (code: string) => void;
  /** Meta's Restricted Territories from the server's session (backend care.territory): version and list. */
  territories: TerritoryPolicy;
};
export type TerritoryPolicy = { version: string; list: Record<string, string> };

/** The fields the server expects for the account's answer about Meta's Restricted Territories. */
export function territoryFields(answer: Territory, version: string) {
  return { territory: answer, territory_version: version };
}

/**
 * Meta does not allow its AI to be offered to people located in some territories (backend care.territory). The
 * person answers; only the answer is kept, never the country. A radio group so both choices are read aloud.
 */
export function TerritoryChoice({ value, onChange, es, list, account = false }: {
  value: Territory | null; onChange: (v: Territory) => void; es: boolean; list: string; account?: boolean;
}) {
  const name = useId();
  const hint = useId();
  const option = (answer: Territory, label: string) => (
    <label className="consent-row">
      <input type="radio" name={name} required checked={value === answer} onChange={() => onChange(answer)} aria-describedby={hint} />
      <span><b>{label}</b></span>
    </label>
  );
  return (
    <fieldset className="adult-check territory-check">
      <legend><b>{es ? "¿Dónde estás?" : "Where are you?"}</b></legend>
      {option("outside_restricted", es ? "No estoy en ninguno de estos territorios" : "I am not in any of these territories")}
      {option("inside_restricted", es ? "Estoy en uno de ellos" : "I am in one of them")}
      <small id={hint}>{es
        ? `Meta no permite usar su IA en: ${list}. Es tu propia declaración; no guardamos tu país ni tu ubicación.`
        : `Meta does not allow its AI to be used in: ${list}. It is your own declaration; we do not keep your country or location.`}</small>
      {value === "inside_restricted" && (
        <p role="alert" className="form-error">{es
          ? `AINGEL usa la IA de Meta, así que no puede ofrecerse en esos territorios. ${account ? "Tu cuenta seguirá cerrada mientras estés allí." : "No se creará la cuenta."}`
          : `AINGEL uses Meta's AI, so it cannot be offered in those territories. ${account ? "Your account stays closed while you are there." : "The account will not be created."}`}</p>
      )}
    </fieldset>
  );
}

/**
 * Accounts from before the territory policy answer once; someone who declared being in one of those territories
 * sees why AINGEL is closed and can update the answer when they are no longer there.
 */
export function TerritoryDeclaration({ t, locale, setLocale, busy, error, username, current, territories, onDeclare, onLogout }: Pick<Props, "t" | "locale" | "setLocale" | "busy" | "error" | "territories"> & {
  username: string; current: Territory | null; onDeclare: (answer: Territory) => void; onLogout: () => void;
}) {
  const es = locale === "es-EC";
  const [answer, setAnswer] = useState<Territory | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => title.current?.focus(), []);
  const inside = current === "inside_restricted";
  return (
    <main id="main" className="gate">
      <div className="auth-top">
        <Brand />
        <label className="auth-locale">
          <span className="sr-only">{t("language")}</span>
          <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
            <option value="es-EC">Español</option>
            <option value="en-US">English</option>
          </select>
        </label>
      </div>
      <form className="auth-form gate-card" onSubmit={(e) => { e.preventDefault(); if (answer) onDeclare(answer); }}>
        <div className="auth-heading">
          <h1 ref={title} tabIndex={-1}>{inside ? (es ? "AINGEL no está disponible aquí" : "AINGEL is not available here") : (es ? "Antes de continuar" : "Before you continue")}</h1>
          <p>{inside
            ? (es ? "Dijiste que estás en un territorio donde Meta no permite su IA. Si ya no estás allí, actualiza tu respuesta." : "You said you are in a territory where Meta does not allow its AI. If you are no longer there, update your answer.")
            : (es ? "AINGEL usa la IA de Meta. Indica si estás en alguno de los territorios donde Meta no la permite." : "AINGEL uses Meta's AI. Say whether you are in one of the territories where Meta does not allow it.")}</p>
        </div>
        <TerritoryChoice value={answer} onChange={setAnswer} es={es} account list={territories.list[locale] ?? territories.list["es-EC"] ?? ""} />
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="btn btn-primary btn-lg" disabled={busy || !answer || !territories.version}>{busy ? t("working") : es ? "Guardar y continuar" : "Save and continue"}</button>
        <button type="button" className="auth-link" onClick={onLogout}>{t("logout")} · {username}</button>
      </form>
    </main>
  );
}

export function Brand({ size = 32 }: { size?: number }) {
  return (
    <div className="brand">
      <img src="/aingel-isotipo.png" alt="" width={size} height={size} />
      <span>AINGEL</span>
    </div>
  );
}

/**
 * The explicit 18+ self-declaration, separate from everything else. Meta's AI terms require adult users; no ID is
 * asked for (backend care.consent.adult_statement).
 */
export function AdultCheck({ checked, onChange, es }: { checked: boolean; onChange: (v: boolean) => void; es: boolean }) {
  const hint = useId();
  return (
    <div className="adult-check">
      <label className="consent-row">
        <input type="checkbox" required checked={checked} onChange={(e) => onChange(e.target.checked)} aria-describedby={hint} />
        <span><b>{es ? "Tengo 18 años o más" : "I am 18 or older"}</b></span>
      </label>
      <small id={hint}>{es
        ? "AINGEL es solo para personas adultas porque usa la IA de Meta. Es tu propia declaración: no pedimos documentos."
        : "AINGEL is for adults only because it uses Meta's AI. It is your own declaration: no ID is needed."}</small>
    </div>
  );
}

/** Accounts created before the age policy: the declaration comes before anything else. */
export function AdultDeclaration({ t, locale, setLocale, busy, error, username, onDeclare, onLogout }: Pick<Props, "t" | "locale" | "setLocale" | "busy" | "error"> & {
  username: string; onDeclare: () => void; onLogout: () => void;
}) {
  const es = locale === "es-EC";
  const [adult, setAdult] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => title.current?.focus(), []);
  return (
    <main id="main" className="gate">
      <div className="auth-top">
        <Brand />
        <label className="auth-locale">
          <span className="sr-only">{t("language")}</span>
          <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
            <option value="es-EC">Español</option>
            <option value="en-US">English</option>
          </select>
        </label>
      </div>
      <form className="auth-form gate-card" onSubmit={(e) => { e.preventDefault(); if (adult) onDeclare(); }}>
        <div className="auth-heading">
          <h1 ref={title} tabIndex={-1}>{es ? "Antes de continuar" : "Before you continue"}</h1>
          <p>{es ? "AINGEL ahora es solo para personas adultas. Confirma tu edad para seguir usando tu cuenta." : "AINGEL is now for adults only. Confirm your age to keep using your account."}</p>
        </div>
        <AdultCheck checked={adult} onChange={setAdult} es={es} />
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="btn btn-primary btn-lg" disabled={busy || !adult}>{busy ? t("working") : es ? "Confirmar y continuar" : "Confirm and continue"}</button>
        <button type="button" className="auth-link" onClick={onLogout}>{t("logout")} · {username}</button>
      </form>
    </main>
  );
}

/** 2a / 2b on the web, 1e / 2d / 2e on phones. */
export default function Auth(props: Props) {
  const { t, locale, busy, error, mfaRequired } = props;
  const es = locale === "es-EC";
  const [mode, setMode] = useState<"welcome" | "login" | "register">("welcome");
  const [who, setWho] = useState<Who>("other");
  const [show, setShow] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [adult, setAdult] = useState(false);
  const [territory, setTerritory] = useState<Territory | null>(null);
  const register = mode === "register";
  // Only someone outside Meta's Restricted Territories can create an account (the server checks it too).
  const eligible = adult && territory === "outside_restricted" && !!props.territories.version;
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    if (register) {
      if (!eligible) return;
      const { name, ...rest } = data;
      props.onRegister({ ...rest, adult: true, ...territoryFields("outside_restricted", props.territories.version) }, { name: String(name || "").trim(), who });
    } else props.onLogin(data);
  };
  const disclaimer = <p className="auth-disclaimer">{t("prototype")}</p>;
  const whoCard = (value: Who, title: string, text: string) => (
    <label className={`radio-card${who === value ? " is-on" : ""}`}>
      <input type="radio" name="who" className="sr-only" checked={who === value} onChange={() => setWho(value)} />
      <span className="radio-dot" aria-hidden="true" />
      <span className="radio-text"><b>{title}</b><small>{text}</small></span>
    </label>
  );
  return (
    <div className={`auth auth--${mode}`}>
      <section className="auth-welcome" aria-label="AINGEL">
        <AingelOrb size={232} />
        <span className="auth-wordmark">AINGEL</span>
        <span className="auth-rule" />
        <p className="auth-tagline">{t("tagline")}</p>
        <p className="auth-intro">{es ? "Un compañero para ver, comunicar y recordar, con tu círculo de apoyo cerca." : "A companion to see, communicate and remember, with your support circle close by."}</p>
        <div className="auth-welcome-actions">
          <button className="btn btn-primary btn-lg" onClick={() => setMode("login")}>{t("login")}</button>
          <button className="btn btn-outline btn-lg" onClick={() => setMode("register")}>{t("register")}</button>
          {disclaimer}
        </div>
      </section>
      <main id="main" className="auth-form-col">
        <div className="auth-top">
          <Brand />
          <label className="auth-locale">
            <span className="sr-only">{t("language")}</span>
            <select value={locale} onChange={(e) => props.setLocale(e.target.value as Locale)}>
              <option value="es-EC">Español</option>
              <option value="en-US">English</option>
            </select>
          </label>
        </div>
        <button className="auth-back" aria-label={es ? "Volver" : "Back"} onClick={() => setMode("welcome")}>‹</button>
        {mfaRequired ? (
          <form className="auth-form" onSubmit={(e) => { e.preventDefault(); props.onMfa(String(new FormData(e.currentTarget).get("code") || "")); }}>
            <div className="auth-heading"><h1>{t("mfaVerify")}</h1><p>{es ? "Escribe el código de tu aplicación de autenticación." : "Enter the code from your authenticator app."}</p></div>
            <label className="input-field"><span>{t("mfaCode")}</span><input required name="code" autoComplete="one-time-code" maxLength={32} /></label>
            {error && <p role="alert" className="form-error">{error}</p>}
            <button className="btn btn-primary btn-lg" disabled={busy}>{t("mfaVerify")}</button>
          </form>
        ) : (
          <form className={`auth-form${register ? " is-register" : ""}`} onSubmit={submit}>
            {register ? <h1>{t("register")}</h1> : (
              <div className="auth-heading"><h1>{t("login")}</h1><p>{es ? "Entra para hablar con tu AINGEL." : "Sign in to talk to your AINGEL."}</p></div>
            )}
            {register && (
              <label className="input-field"><span>{es ? "Tu nombre" : "Your name"}</span><input name="name" autoComplete="name" maxLength={100} /></label>
            )}
            <div className={register ? "auth-pair" : "auth-stack"}>
              <label className="input-field"><span>{t("username")}</span><input name="username" autoComplete="username" required maxLength={150} /></label>
              <label className="input-field">
                <span>{t("password")}</span>
                <span className="input-with-action">
                  <input name="password" type={show ? "text" : "password"} autoComplete={register ? "new-password" : "current-password"} required minLength={register ? 10 : 1} maxLength={256} />
                  {!register && <button type="button" className="input-action" onClick={() => setShow(!show)}>{show ? (es ? "Ocultar" : "Hide") : (es ? "Mostrar" : "Show")}</button>}
                </span>
              </label>
            </div>
            {register ? (
              <>
                <span className="auth-hint">{es ? "Mínimo 10 caracteres. Usa una contraseña única y evita datos personales." : "At least 10 characters. Use a unique password and avoid personal details."}</span>
                <span className="auth-label">{es ? "¿Para quién es este AINGEL?" : "Who is this AINGEL for?"}</span>
                <div className="radio-grid">
                  {whoCard("me", es ? "Para mí" : "For me", es ? "Yo usaré AINGEL" : "I will use AINGEL")}
                  {whoCard("other", es ? "Para alguien a quien cuido" : "For someone I care for", es ? "Seré su familiar o cuidador" : "I am their family or caregiver")}
                </div>
                <AdultCheck checked={adult} onChange={setAdult} es={es} />
                <TerritoryChoice value={territory} onChange={setTerritory} es={es} list={props.territories.list[locale] ?? props.territories.list["es-EC"] ?? ""} />
              </>
            ) : (
              <>
                <button type="button" className="auth-link auth-forgot" onClick={() => setForgot(!forgot)}>{es ? "¿Olvidaste tu contraseña?" : "Forgot your password?"}</button>
                {forgot && <p className="auth-hint" role="status">{es ? "Esta versión local no envía correos. Pide a quien administra AINGEL que restablezca tu contraseña." : "This local version sends no email. Ask whoever manages AINGEL to reset your password."}</p>}
              </>
            )}
            {error && <p role="alert" className="form-error">{error}</p>}
            <button className="btn btn-primary btn-lg" disabled={busy || (register && !eligible)}>
              {busy ? t("working") : register ? (es ? "Crear cuenta y configurar AINGEL" : "Create account and set up AINGEL") : (es ? "Entrar" : "Sign in")}
            </button>
            {register ? (
              <button type="button" className="auth-link auth-switch" onClick={() => setMode("login")}>{es ? "¿Ya tienes cuenta? Iniciar sesión" : "Already have an account? Sign in"}</button>
            ) : (
              <>
                <div className="auth-divider"><span />{es ? "¿No tienes cuenta?" : "No account yet?"}<span /></div>
                <button type="button" className="btn btn-outline btn-lg" onClick={() => setMode("register")}>{t("register")}</button>
                <button type="button" className="auth-link auth-switch-mobile" onClick={() => setMode("register")}>{es ? "¿No tienes cuenta? Crear cuenta" : "No account? Create one"}</button>
              </>
            )}
          </form>
        )}
        {disclaimer}
      </main>
      <aside className="auth-visual" aria-hidden={false}>
        <AingelOrb size={380} configured={!register} />
        {register ? (
          <>
            <p className="auth-visual-title is-small">{es ? "Tu AINGEL aún no está configurado" : "Your AINGEL is not set up yet"}</p>
            <p className="auth-visual-text">{es ? "En el siguiente paso nos cuentas qué apoyos necesita la persona para preparar su configuración." : "Next, tell us what support the person needs so we can prepare their setup."}</p>
          </>
        ) : (
          <>
            <p className="auth-visual-title">{t("tagline")}</p>
            <p className="auth-visual-text">{es ? "Un compañero para ver, comunicar y recordar, con tu círculo de apoyo cerca." : "A companion to see, communicate and remember, with your support circle close by."}</p>
          </>
        )}
      </aside>
    </div>
  );
}
