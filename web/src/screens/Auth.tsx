import { useState, type FormEvent } from "react";
import AingelOrb from "../components/aingel/AingelOrb";
import type { translator, Locale } from "../i18n";

export type Who = "me" | "other";
type Props = {
  t: ReturnType<typeof translator>;
  locale: Locale;
  setLocale: (l: Locale) => void;
  busy: boolean;
  error: string;
  mfaRequired: boolean;
  onLogin: (data: Record<string, FormDataEntryValue>) => void;
  onRegister: (data: Record<string, FormDataEntryValue>, extra: { name: string; who: Who }) => void;
  onMfa: (code: string) => void;
};

export function Brand({ size = 32 }: { size?: number }) {
  return (
    <div className="brand">
      <img src="/aingel-isotipo.png" alt="" width={size} height={size} />
      <span>AINGEL</span>
    </div>
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
  const register = mode === "register";
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    if (register) {
      const { name, ...rest } = data;
      props.onRegister(rest, { name: String(name || "").trim(), who });
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
              </>
            ) : (
              <>
                <button type="button" className="auth-link auth-forgot" onClick={() => setForgot(!forgot)}>{es ? "¿Olvidaste tu contraseña?" : "Forgot your password?"}</button>
                {forgot && <p className="auth-hint" role="status">{es ? "Esta versión local no envía correos. Pide a quien administra AINGEL que restablezca tu contraseña." : "This local version sends no email. Ask whoever manages AINGEL to reset your password."}</p>}
              </>
            )}
            {error && <p role="alert" className="form-error">{error}</p>}
            <button className="btn btn-primary btn-lg" disabled={busy}>
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
