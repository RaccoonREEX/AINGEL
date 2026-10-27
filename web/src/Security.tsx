import { useEffect, useState } from "react";
import { api } from "./api";
import type { translator } from "./i18n";

export default function Security({
  t,
  busy,
  run,
}: {
  t: ReturnType<typeof translator>;
  busy: boolean;
  run: (task: () => Promise<void>) => Promise<void>;
}) {
  const [enabled, setEnabled] = useState(false),
    [setup, setSetup] = useState<{ secret: string; qr_png: string } | null>(
      null,
    ),
    [recovery, setRecovery] = useState<string[]>([]);
  const status = async () => {
    setEnabled((await api<{ enabled: boolean }>("auth/mfa/status/")).enabled);
  };
  useEffect(() => {
    void run(status);
  }, []);
  return (
    <section className="panel">
      <h1>{t("security")}</h1>
      <h2>{t("mfaTitle")}</h2>
      <p>{t("mfaIntro")}</p>
      <span className="badge">{t(enabled ? "mfaOn" : "mfaOff")}</span>
      {!enabled && !setup && (
        <form
          className="spaced"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            void run(async () => {
              setSetup(
                await api("auth/mfa/setup/", "POST", {
                  password: data.get("password"),
                }),
              );
              form.reset();
            });
          }}
        >
          <label className="field">
            {t("currentPassword")}
            <input
              required
              type="password"
              name="password"
              autoComplete="current-password"
            />
          </label>
          <button disabled={busy} className="primary">
            {t("setupMfa")}
          </button>
        </form>
      )}
      {setup && (
        <div className="mfa-setup">
          <p>{t("mfaSetupHint")}</p>
          <img
            src={setup.qr_png}
            alt={t("setupMfa")}
            width={230}
            height={230}
          />
          <code>{setup.secret}</code>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void run(async () => {
                const result = await api<{ recovery_codes: string[] }>(
                  "auth/mfa/enable/",
                  "POST",
                  { code: data.get("code") },
                );
                setRecovery(result.recovery_codes);
                setSetup(null);
                await status();
              });
            }}
          >
            <label className="field">
              {t("mfaCode")}
              <input
                name="code"
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                minLength={6}
                maxLength={6}
              />
            </label>
            <button className="primary" disabled={busy}>
              {t("enableMfa")}
            </button>
          </form>
          <button onClick={() => setSetup(null)}>{t("cancel")}</button>
        </div>
      )}
      {recovery.length > 0 && (
        <div className="callout">
          <h3>{t("recoveryCodes")}</h3>
          <p>{t("recoveryHint")}</p>
          <div className="recovery-codes">
            {recovery.map((code) => (
              <code key={code}>{code}</code>
            ))}
          </div>
          <button onClick={() => setRecovery([])}>{t("close")}</button>
        </div>
      )}
      {enabled && !recovery.length && (
        <form
          className="spaced"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            void run(async () => {
              await api("auth/mfa/disable/", "POST", Object.fromEntries(data));
              form.reset();
              await status();
            });
          }}
        >
          <label className="field">
            {t("currentPassword")}
            <input
              required
              type="password"
              name="password"
              autoComplete="current-password"
            />
          </label>
          <label className="field">
            {t("mfaCode")}
            <input
              name="code"
              required
              maxLength={32}
              autoComplete="one-time-code"
            />
          </label>
          <button disabled={busy} className="danger">
            {t("disableMfa")}
          </button>
        </form>
      )}
    </section>
  );
}
