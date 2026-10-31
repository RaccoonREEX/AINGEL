import { speakLocally } from "./components/aingel/browserSpeech";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { WithProfile } from "./ui";
import Auth, { AdultDeclaration, Brand, type Who } from "./screens/Auth";
import { RedeemCode } from "./components/ConsentPanel";
import Onboarding, { AcceptInvite } from "./screens/Onboarding";
import Home from "./screens/Home";
import SignTranslator from "./screens/SignTranslator";
import Settings from "./screens/Settings";
import CirclePanel from "./screens/CirclePanel";
import Routines from "./screens/Routines";
import Messages from "./screens/Messages";
import Memories from "./screens/Memories";
import Ask from "./screens/Ask";
import See from "./screens/See";
import Activity from "./screens/Activity";
import { api, errorKey } from "./api";
import Security from "./Security";
import Hear from "./Hear";
import FamilyFaces from "./FamilyFaces";
import { useCommunication } from "./Communication";
import { initials } from "./today";
import { translator, type Key, type Locale } from "./i18n";
import type { Profile, Session, User } from "./types";

type Tab =
  | "ask"
  | "dashboard"
  | "see"
  | "hear"
  | "memory"
  | "messages"
  | "circle"
  | "settings"
  | "security"
  | "familyFaces"
  | "activity"
  | "tools"
  | "signs"
  | "more";
const primaryTabs: Tab[] = ["ask", "dashboard", "signs", "see", "hear", "memory", "messages", "circle"];
const accountTabs: Tab[] = ["settings", "security", "familyFaces", "tools", "activity"];
const mobileTabs: Tab[] = ["ask", "dashboard", "memory", "circle", "more"];
type Task = () => Promise<void>;

export default function App() {
  const [locale, setLocale] = useState<Locale>("es-EC");
  const t = translator(locale);
  const es = locale === "es-EC";
  const L = (a: string, b: string) => (es ? a : b);
  const [user, setUser] = useState<User | null>(null),
    [initial, setInitial] = useState(true);
  const [profiles, setProfiles] = useState<Profile[]>([]),
    [selected, setSelected] = useState("");
  const [tab, setTab] = useState<Tab>("ask"),
    [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  // The terms the 18+ declaration refers to; sent back as-is (the server rejects a stale version).
  const [termsVersion, setTermsVersion] = useState("");
  const [speechVersion, setSpeechVersion] = useState("");
  const [focusConsent, setFocusConsent] = useState(false);
  const [version, setVersion] = useState(0);
  const [homeKey, setHomeKey] = useState(0);
  const [question, setQuestion] = useState<string | undefined>();
  const [signup, setSignup] = useState<{ who: Who; name: string }>({ who: "other", name: "" });
  const [supportOpen, setSupportOpen] = useState(false);
  const profile = profiles.find((x) => x.id === selected);
  /** `notFound` names what a 404 means for this task (an invitation code, an account to invite…); generic otherwise. */
  const run = async (task: Task, notFound: Key = "errorGeneric") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      setError(t(errorKey(e, notFound)));
    } finally {
      setBusy(false);
    }
  };
  const loadProfiles = async (preferred?: string) => {
    const result = await api<Profile[]>("profiles/");
    setProfiles(result);
    setSelected((old) => preferred || (result.some((x) => x.id === old) ? old : result[0]?.id || ""));
    setVersion((v) => v + 1);
  };
  useEffect(() => {
    api<Session>("auth/session/")
      .then(async (result) => {
        setUser(result.user);
        setTermsVersion(result.terms_version ?? "");
        setSpeechVersion(result.speech_service_version ?? "");
        setMfaRequired(!!result.mfa_required);
        if (result.user) await loadProfiles();
      })
      .catch(() => setError(t("errorGeneric")))
      .finally(() => setInitial(false));
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = "AINGEL · " + t("welcome");
  }, [locale]);
  const signedIn = async (session: Session) => {
    if (session.mfa_required) { setMfaRequired(true); return; }
    setMfaRequired(false);
    setUser(session.user);
    if (session.terms_version) setTermsVersion(session.terms_version);
    if (session.speech_service_version) setSpeechVersion(session.speech_service_version);
    await loadProfiles();
  };
  /** After a code: the profile is now this account's own (role subject); open its permissions. */
  const redeemed = async (id: string) => {
    await loadProfiles(id);
    go("settings");
    setFocusConsent(true);
  };
  const logout = () =>
    void run(async () => {
      await api("auth/logout/", "POST");
      setUser(null);
      setProfiles([]);
      setSelected("");
      setTab("ask");
      setMfaRequired(false);
      setNotice("");
      window.speechSynthesis?.cancel();
    });
  const date = (value: string) =>
    new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: profile?.timezone || "America/Guayaquil",
    }).format(new Date(value));
  const context = {
    t,
    locale,
    busy,
    run,
    date,
    currentUser: user?.username,
    speech: {
      identity: `${user?.id ?? ""}:${profile?.id ?? ""}`,
      accepted: !!user?.speech_service,
      decide: async (accept: boolean) => {
        const session = await api<Session>("auth/speech-service/", "POST", { accept, version: speechVersion });
        setUser(session.user);
        return !!session.user?.speech_service;
      },
    },
    refresh: async () => {
      await loadProfiles();
      setNotice(t("saved"));
    },
  };
  const go = (next: Tab, ask?: string) => {
    if (next === "ask" && (tab === "ask" || ask)) setHomeKey((k) => k + 1);
    setQuestion(ask);
    setFocusConsent(false);
    setTab(next);
    setError("");
    setNotice("");
    window.scrollTo({ top: 0 });
  };
  const label = (x: Tab) =>
    x === "ask" ? L("Asistente", "Assistant") : x === "more" ? L("Más", "More") : x === "tools" ? L("Conversación IA", "AI chat") : x === "signs" ? L("Traductor de señas", "Sign translator") : t(x);
  const visible = (x: Tab) =>
    (x !== "activity" || profile?.role === "owner") &&
    !(x === "see" && profile?.preferences.visual_assistance === false) &&
    !(x === "hear" && profile?.preferences.hearing_assistance === false) &&
    !(x === "memory" && profile?.preferences.memory_assistance === false);
  const prefs = profile?.preferences;
  const rootClass = `${prefs?.large_text ? "large-text " : ""}${prefs?.high_contrast ? "high-contrast " : ""}${prefs?.reduced_motion ? "reduced-motion " : ""}`;

  if (initial) return <main className="loading" role="status">{t("loading")}</main>;

  if (!user)
    return (
      <div className={rootClass}>
        <a href="#main" className="skip">{L("Saltar al contenido", "Skip to content")}</a>
        <Auth
          t={t} locale={locale} setLocale={setLocale} busy={busy} error={error} mfaRequired={mfaRequired}
          onLogin={(data) => void run(async () => signedIn(await api<Session>("auth/login/", "POST", data)))}
          onRegister={(data, extra) => void run(async () => { setSignup(extra); await signedIn(await api<Session>("auth/register/", "POST", { ...data, terms_version: termsVersion })); })}
          onMfa={(code) => void run(async () => signedIn(await api<Session>("auth/mfa/verify/", "POST", { code })))}
        />
      </div>
    );

  // Accounts from before the age policy declare it before anything else (Meta endpoints refuse them until then).
  if (!user.adult_declared)
    return (
      <div className={rootClass}>
        <a href="#main" className="skip">{L("Saltar al contenido", "Skip to content")}</a>
        <AdultDeclaration t={t} locale={locale} setLocale={setLocale} busy={busy} error={error} username={user.username} onLogout={logout}
          onDeclare={() => void run(async () => {
            const session = await api<Session>("auth/adult/", "POST", { adult: true, terms_version: termsVersion });
            setTermsVersion(session.terms_version ?? termsVersion);
            setUser(session.user);
          })} />
      </div>
    );

  if (!profile && tab !== "security")
    return (
      <div className={rootClass}>
        <a href="#main" className="skip">{L("Saltar al contenido", "Skip to content")}</a>
        {error && <p className="toast toast--error" role="alert">{error}</p>}
        <Onboarding {...context} who={signup.who} ownName={signup.name} username={user.username} onLogout={logout} onCreated={async (id) => { await loadProfiles(id); go("ask"); }} onRedeemed={redeemed} />
      </div>
    );

  const navButton = (x: Tab, cls: string) => (
    <button key={x} type="button" className={cls} disabled={(!profile && x !== "security") || busy} aria-current={tab === x || (x === "more" && !mobileTabs.includes(tab)) ? "page" : undefined} onClick={() => go(x)}>
      {cls === "tab" ? <span>{x === "ask" ? "AINGEL" : x === "circle" ? L("Círculo", "Circle") : label(x)}</span> : label(x)}
    </button>
  );
  return (
    <div className={`shell ${rootClass}`}>
      <a href="#main" className="skip">{L("Saltar al contenido", "Skip to content")}</a>
      <aside className="sidebar">
        <Brand />
        <nav aria-label={L("Navegación principal", "Main navigation")} className="side-nav">
          {primaryTabs.filter(visible).map((x) => navButton(x, "side-link"))}
          <span className="side-sep" role="separator" />
          {accountTabs.filter(visible).map((x) => navButton(x, "side-link"))}
        </nav>
        <div className="side-bottom">
          <button type="button" className="btn btn-outline-navy" onClick={() => setSupportOpen(true)} disabled={!profile}>{t("supportButton")}</button>
          {profile && <UserBlock profile={profile} t={t} />}
          {profiles.length > 1 && (
            <label className="side-select">
              <span className="sr-only">{t("selectProfile")}</span>
              <select value={selected} onChange={(e) => { setSelected(e.target.value); setNotice(""); setError(""); setHomeKey((k) => k + 1); }}>
                {profiles.map((p) => <option key={p.id} value={p.id}>{p.display_name} · {t(p.role)}</option>)}
              </select>
            </label>
          )}
          <div className="side-meta">
            <label><span className="sr-only">{t("language")}</span>
              <select value={locale} onChange={(e) => { setLocale(e.target.value as Locale); setNotice(""); setError(""); }}>
                <option value="es-EC">Español</option>
                <option value="en-US">English</option>
              </select>
            </label>
            <button type="button" className="text-btn" onClick={logout} disabled={busy}>{t("logout")}</button>
          </div>
        </div>
      </aside>
      <main id="main" className={`main main--${tab}`}>
        <div className="toasts" aria-live="polite">
          {notice && <p className="toast toast--ok">{notice}</p>}
          {error && <p className="toast toast--error" role="alert">{error}</p>}
        </div>
        {tab === "security" ? (
          <Page title={t("security")} subtitle={user.username}><Security {...context} /></Page>
        ) : !profile ? null : tab === "ask" ? (
          <Home key={`${profile.id}:${homeKey}`} {...context} profile={profile} initialQuestion={question} onOpenToday={() => go("dashboard")} onOpenSigns={() => go("signs")} />
        ) : tab === "signs" ? (
          <div className="page page--wide"><SignTranslator key={profile.id} {...context} profile={profile} onBack={() => go("ask")} /></div>
        ) : tab === "dashboard" ? (
          <div className="page page--wide"><Routines key={profile.id} {...context} profile={profile} version={version} onAsk={(q) => go("ask", q)} /></div>
        ) : tab === "more" ? (
          <MorePage tabs={([...primaryTabs.filter((x) => !mobileTabs.includes(x)), "familyFaces", "tools"] as Tab[]).filter(visible)} account={["settings", "security", "activity"].filter((x) => visible(x as Tab)) as Tab[]} label={label} es={es} onGo={go} onSupport={() => setSupportOpen(true)} t={t} locale={locale} setLocale={setLocale} onLogout={logout} />
        ) : (
          <Page title={label(tab)} subtitle={`${profile.display_name} · ${t(profile.role)}`} badge={profile.ready ? undefined : t("draft")}>
            {!profile.ready && tab === "circle" && <p className="callout">{t("incomplete")}</p>}
            <ProfileContent key={`${profile.id}:${tab}`} {...context} profile={profile} tab={tab} version={version} focusConsent={focusConsent} />
            {tab === "settings" && (
              <section className="panel join-extra">
                <h2>{L("Tengo un código de AINGEL", "I have an AINGEL code")}</h2>
                <RedeemCode {...context} onRedeemed={redeemed} />
              </section>
            )}
            {tab === "circle" && (
              <section className="panel join-extra">
                <h2>{t("acceptInvite")}</h2>
                <AcceptInvite {...context} onAccepted={async (id) => { await loadProfiles(id); }} />
              </section>
            )}
          </Page>
        )}
      </main>
      <nav className="tabbar" aria-label={L("Navegación", "Navigation")}>
        {mobileTabs.filter(visible).map((x) => navButton(x, "tab"))}
      </nav>
      {supportOpen && profile && <SupportDialog profile={profile} t={t} onClose={() => setSupportOpen(false)} />}
    </div>
  );
}

function UserBlock({ profile, t }: { profile: Profile; t: ReturnType<typeof translator> }) {
  return (
    <div className="user-block">
      <span className="avatar">{initials(profile.display_name)}</span>
      <div><b>{profile.display_name}</b><small>{t(profile.role)}</small></div>
    </div>
  );
}

function Page({ title, subtitle, badge, children }: { title: string; subtitle?: string; badge?: string; children: ReactNode }) {
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>{title}</h1>
          {subtitle && <span>{subtitle}</span>}
        </div>
        {badge && <span className="status-badge"><span className="dot dot--gold" />{badge}</span>}
      </header>
      {children}
    </div>
  );
}

/** 1j: the rest of the functions on phones. */
function MorePage({ tabs, account, label, es, onGo, onSupport, t, locale, setLocale, onLogout }: {
  tabs: Tab[]; account: Tab[]; label: (x: Tab) => string; es: boolean; onGo: (x: Tab) => void; onSupport: () => void;
  t: ReturnType<typeof translator>; locale: Locale; setLocale: (l: Locale) => void; onLogout: () => void;
}) {
  const desc: Partial<Record<Tab, string>> = es
    ? { signs: "Voz a señas y señas a voz o texto", see: "Describir lo que tienes delante", hear: "Subtítulos y lengua de señas", messages: "Mensajes de tu círculo", familyFaces: "Reconocimiento experimental", tools: "Preguntas y fuentes de salud" }
    : { signs: "Voice to signs and signs to voice or text", see: "Describe what’s in front of you", hear: "Captions and sign language", messages: "Messages from your circle", familyFaces: "Experimental recognition", tools: "Questions and health sources" };
  return (
    <div className="more">
      <h1>{es ? "Más" : "More"}</h1>
      <span className="overline">{es ? "ASISTENCIA" : "ASSISTANCE"}</span>
      <div className="more-list">
        {tabs.map((x) => (
          <button type="button" key={x} className="more-row" onClick={() => onGo(x)}>
            <span><b>{label(x)}</b>{desc[x] && <small>{desc[x]}</small>}</span><span className="chev" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
      <span className="overline">{es ? "CUENTA" : "ACCOUNT"}</span>
      <div className="more-list">
        {account.map((x) => (
          <button type="button" key={x} className="more-row" onClick={() => onGo(x)}><span><b>{label(x)}</b></span><span className="chev" aria-hidden="true">›</span></button>
        ))}
        <label className="more-row more-row--select">
          <span><b>{t("language")}</b></span>
          <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)}><option value="es-EC">Español</option><option value="en-US">English</option></select>
        </label>
        <button type="button" className="more-row" onClick={onLogout}><span><b>{t("logout")}</b></span><span className="chev" aria-hidden="true">›</span></button>
      </div>
      <div className="more-support">
        <button type="button" className="btn btn-outline-navy btn-lg" onClick={onSupport}>{t("supportButton")}</button>
        <span>{t("supportNoCall")}</span>
      </div>
    </div>
  );
}

function SupportDialog({ profile, t, onClose }: { profile: Profile; t: ReturnType<typeof translator>; onClose: () => void }) {
  const { value } = useCommunication(profile.id);
  const ref = useRef<HTMLDialogElement>(null);
  const text = t(value?.distress === "contact_caregiver" ? "supportCaregiverResponse" : "supportQuietResponse");
  useEffect(() => { ref.current?.showModal(); return () => window.speechSynthesis?.cancel(); }, []);
  const read = () => {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = profile.locale;
    u.rate = value?.pace === "slow" ? 0.8 : 1;
    speakLocally(u);
  };
  return (
    <dialog ref={ref} className="support-dialog" onClose={onClose} aria-labelledby="support-title">
      <h2 id="support-title">{t("supportButton")}</h2>
      <p className="support-text" aria-live="polite">{text}</p>
      <p className="hint">{t("supportNoCall")}</p>
      <div className="actions">
        <button type="button" className="btn btn-outline btn-pill" onClick={read}>{t("readAnswer")}</button>
        <button type="button" className="btn btn-primary btn-pill" onClick={() => ref.current?.close()}>{t("close")}</button>
      </div>
    </dialog>
  );
}

function ProfileContent(props: WithProfile & { tab: Tab; version: number; focusConsent: boolean }) {
  switch (props.tab) {
    case "settings":
      return <Settings {...props} />;
    case "familyFaces":
      return <FamilyFaces {...props} />;
    case "security":
      return <Security {...props} />;
    case "circle":
      return <CirclePanel {...props} />;
    case "messages":
      return <Messages {...props} />;
    case "memory":
      return <Memories {...props} />;
    case "tools":
      return <Ask {...props} />;
    case "see":
      return <See {...props} />;
    case "hear":
      return <Hear {...props} />;
    case "activity":
      return <Activity {...props} />;
    default:
      return null;
  }
}
