import Field from "./components/Field";
import type { WithProfile } from "./ui";
import Onboarding, { AcceptInvite } from "./screens/Onboarding";
import Settings from "./screens/Settings";
import CirclePanel from "./screens/CirclePanel";
import Routines from "./screens/Routines";
import Messages from "./screens/Messages";
import Memories from "./screens/Memories";
import Ask from "./screens/Ask";
import See from "./screens/See";
import Activity from "./screens/Activity";
import { useEffect, useState, type FormEvent } from "react";
import { api, APIError } from "./api";
import Security from "./Security";
import Hear from "./Hear";
import FamilyFaces from "./FamilyFaces";
import { translator, type Key, type Locale } from "./i18n";
import type { Profile, Session, User } from "./types";

type Tab =
  | "dashboard"
  | "ask"
  | "see"
  | "memory"
  | "messages"
  | "circle"
  | "settings"
  | "activity"
  | "familyFaces"
  | "security"
  | "hear";
const tabs: Tab[] = [
  "dashboard",
  "ask",
  "see",
  "hear",
  "memory",
  "messages",
  "circle",
  "settings",
  "familyFaces",
  "security",
  "activity",
];
type Task = () => Promise<void>;

export default function App() {
  const [locale, setLocale] = useState<Locale>("es-EC");
  const t = translator(locale);
  const [user, setUser] = useState<User | null>(null),
    [initial, setInitial] = useState(true);
  const [profiles, setProfiles] = useState<Profile[]>([]),
    [selected, setSelected] = useState("");
  const [tab, setTab] = useState<Tab>("dashboard"),
    [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const [register, setRegister] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [version, setVersion] = useState(0);
  const profile = profiles.find((x) => x.id === selected);
  const run = async (task: Task) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      let key: Key = "errorGeneric";
      if (e instanceof APIError) {
        const detail = JSON.stringify(e.detail);
        if (detail.includes("mfa_")) key = "mfaError";
        else if (detail.includes("face_") || detail.includes("self_enrollment"))
          key = "faceError";
        else if (detail.includes("credentials_invalid")) key = "errorAuth";
        else if (detail.includes("registration_invalid")) key = "errorRegister";
        else if (detail.includes("care_circle_full")) key = "errorFull";
        else if (detail.includes("image_")) key = "errorImage";
        else if (
          detail.includes("meta_") ||
          detail.includes("sam_") ||
          detail.includes("privacy_review")
        )
          key = "errorMeta";
        else if (detail.includes("observation_")) key = "errorFuture";
        else if (e.status === 403) key = "noAccess";
        else if (e.status === 404)
          key = tab === "circle" ? "errorTarget" : "errorInvite";
        else if (e.status === 429) key = "errorGeneric";
      }
      setError(t(key));
    } finally {
      setBusy(false);
    }
  };
  const loadProfiles = async (preferred?: string) => {
    const result = await api<Profile[]>("profiles/");
    setProfiles(result);
    setSelected(
      (old) =>
        preferred ||
        (result.some((x) => x.id === old) ? old : result[0]?.id || ""),
    );
    setVersion((v) => v + 1);
  };
  useEffect(() => {
    api<Session>("auth/session/")
      .then(async (result) => {
        setUser(result.user);
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
  const submitAuth = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void run(async () => {
      const session = await api<Session>(
        `auth/${register ? "register" : "login"}/`,
        "POST",
        Object.fromEntries(data),
      );
      if (session.mfa_required) {
        setMfaRequired(true);
        return;
      }
      setMfaRequired(false);
      setUser(session.user);
      await loadProfiles();
    });
  };
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
    refresh: async () => {
      await loadProfiles();
      setNotice(t("saved"));
    },
  };
  if (initial)
    return (
      <main className="loading" role="status">
        {t("loading")}
      </main>
    );
  return (
    <div
      className={`${profile?.preferences.large_text ? "large-text " : ""}${profile?.preferences.high_contrast ? "high-contrast " : ""}${profile?.preferences.reduced_motion ? "reduced-motion " : ""}`}
    >
      <a href="#main" className="skip">
        {t("welcome")}
      </a>
      <header className="topbar">
        <a className="brand" href="#" aria-label="AINGEL">
          <span className="brand-mark">A</span>
          <span>
            <b>AI</b>NGEL
          </span>
        </a>
        <span className="badge">{t("local")}</span>
        <label className="locale">
          <span className="sr-only">{t("language")}</span>
          <select
            value={locale}
            onChange={(e) => {
              setLocale(e.target.value as Locale);
              setNotice("");
              setError("");
            }}
          >
            <option value="es-EC">Español</option>
            <option value="en-US">English</option>
          </select>
        </label>
        {user && (
          <>
            <span className="account-name">{user.username}</span>
            <button disabled={busy} onClick={() => setTab("security")}>
              {t("security")}
            </button>
            <button
              className="quiet"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await api("auth/logout/", "POST");
                  setUser(null);
                  setProfiles([]);
                  setSelected("");
                  setTab("dashboard");
                  setMfaRequired(false);
                  setNotice("");
                  window.speechSynthesis?.cancel();
                })
              }
            >
              {t("logout")}
            </button>
          </>
        )}
      </header>
      {!user ? (
        <main id="main" className="auth-layout">
          <section className="auth-story">
            <p className="eyebrow">AINGEL CARE</p>
            <h1>{t("tagline")}</h1>
            <p>{t("intro")}</p>
            <div className="story-points">
              <span>01 · {t("see")}</span>
              <span>02 · {t("memory")}</span>
              <span>03 · {t("circle")}</span>
            </div>
            <p className="muted">{t("prototype")}</p>
          </section>
          <section className="panel auth-panel">
            <h2>
              {t(mfaRequired ? "mfaVerify" : register ? "register" : "login")}
            </h2>
            {mfaRequired ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  void run(async () => {
                    const session = await api<Session>(
                      "auth/mfa/verify/",
                      "POST",
                      Object.fromEntries(data),
                    );
                    setMfaRequired(false);
                    setUser(session.user);
                    await loadProfiles();
                  });
                }}
              >
                <Field label={t("mfaCode")}>
                  <input
                    required
                    name="code"
                    autoComplete="one-time-code"
                    maxLength={32}
                  />
                </Field>
                <button className="primary" disabled={busy}>
                  {t("mfaVerify")}
                </button>
              </form>
            ) : (
              <form onSubmit={submitAuth}>
                <Field label={t("username")}>
                  <input
                    name="username"
                    autoComplete="username"
                    required
                    maxLength={150}
                  />
                </Field>
                <Field label={t("password")}>
                  <input
                    name="password"
                    type="password"
                    autoComplete={
                      register ? "new-password" : "current-password"
                    }
                    required
                    minLength={register ? 10 : 1}
                    maxLength={256}
                  />
                </Field>
                {register && <p className="hint">{t("passwordHint")}</p>}
                <button disabled={busy} className="primary">
                  {busy ? t("working") : t(register ? "register" : "login")}
                </button>
              </form>
            )}
            <button
              disabled={busy}
              className="link-button"
              onClick={() => {
                setRegister(!register);
                setMfaRequired(false);
                setError("");
              }}
            >
              {t(register ? "login" : "register")}
            </button>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
          </section>
        </main>
      ) : (
        <div className="app-layout">
          <aside className="sidebar">
            <p className="eyebrow">{t("welcome")}</p>
            {profiles.length > 0 && (
              <Field label={t("selectProfile")}>
                <select
                  value={selected}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setNotice("");
                    setError("");
                  }}
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name} · {t(p.role)}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <nav aria-label={t("welcome")}>
              {tabs
                .filter(
                  (x) =>
                    (x !== "activity" || profile?.role === "owner") &&
                    !(
                      x === "see" &&
                      profile?.preferences.visual_assistance === false
                    ) &&
                    !(
                      x === "hear" &&
                      profile?.preferences.hearing_assistance === false
                    ) &&
                    !(
                      x === "memory" &&
                      profile?.preferences.memory_assistance === false
                    ),
                )
                .map((x, i) => (
                  <button
                    disabled={(!profile && x !== "security") || busy}
                    key={x}
                    aria-current={tab === x ? "page" : undefined}
                    onClick={() => {
                      setTab(x);
                      setError("");
                      setNotice("");
                    }}
                  >
                    <span aria-hidden="true">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {t(x)}
                  </button>
                ))}
            </nav>
            <div className="sidebar-bottom">
              <p>{t("privacyLocal")}</p>
              <p className="muted">{t("prototype")}</p>
            </div>
          </aside>
          <main id="main" className="content">
            <div aria-live="polite">
              {notice && <p className="success">{notice}</p>}
              {busy && (
                <p className="processing" role="status">
                  {t("working")}
                </p>
              )}
            </div>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            {tab === "security" ? (
              <Security {...context} />
            ) : !profile ? (
              <section className="panel">
                <h1>{t("noProfiles")}</h1>
                <Onboarding
                  {...context}
                  onCreated={async (id) => {
                    await loadProfiles(id);
                  }}
                />
              </section>
            ) : (
              <>
                <div className="page-heading">
                  <div>
                    <p className="eyebrow">
                      {t(profile.role)} · {profile.display_name}
                    </p>
                    <h1>{t(tab)}</h1>
                  </div>
                  <span className={`badge ${profile.ready ? "ready" : ""}`}>
                    {profile.ready ? t("ready") : t("draft")}
                  </span>
                </div>
                {!profile.ready && (
                  <p className="callout">
                    {t("incomplete")}{" "}
                    <button
                      className="link-button"
                      onClick={() => setTab("circle")}
                    >
                      {t("circle")}
                    </button>
                  </p>
                )}
                <ProfileContent
                  key={`${profile.id}:${tab}`}
                  {...context}
                  profile={profile}
                  tab={tab}
                  version={version}
                />
              </>
            )}
            {profile && tab === "circle" && (
              <section className="panel join-extra">
                <h2>{t("acceptInvite")}</h2>
                <AcceptInvite
                  {...context}
                  onAccepted={async (id) => {
                    await loadProfiles(id);
                  }}
                />
              </section>
            )}
          </main>
        </div>
      )}
    </div>
  );
}

function ProfileContent(props: WithProfile & { tab: Tab; version: number }) {
  switch (props.tab) {
    case "settings":
      return <Settings {...props} />;
    case "familyFaces":
      return <FamilyFaces {...props} />;
    case "security":
      return <Security {...props} />;
    case "circle":
      return <CirclePanel {...props} />;
    case "dashboard":
      return <Routines {...props} />;
    case "messages":
      return <Messages {...props} />;
    case "memory":
      return <Memories {...props} />;
    case "ask":
      return <Ask {...props} />;
    case "see":
      return <See {...props} />;
    case "hear":
      return <Hear {...props} />;
    case "activity":
      return <Activity {...props} />;
  }
}
