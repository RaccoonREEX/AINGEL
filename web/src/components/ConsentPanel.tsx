import { useEffect, useId, useRef, useState } from "react";
import { api, errorKey } from "../api";
import Field from "./Field";
import { groups, ListenButton, speak } from "./Consents";
import type { Context, WithProfile } from "../ui";
import type { ConsentState, Purpose, PurposeStatus } from "../types";

type Decision = "grant" | "decline" | "revoke";

/** Status in words with a symbol (never colour alone). */
function StatusTag({ status, es }: { status: PurposeStatus; es: boolean }) {
  const [mark, text] = {
    granted: ["✓", es ? "Permitido" : "Allowed"],
    declined: ["✕", es ? "No permitido" : "Not allowed"],
    revoked: ["↺", es ? "Revocado" : "Revoked"],
    pending: ["…", es ? "Sin decidir" : "Not decided"],
  }[status];
  return <span className={`consent-status consent-status--${status}`}><span aria-hidden="true">{mark}</span> {text}</span>;
}

/**
 * One-time code so the person can link their own account to a profile someone else set up for them, and decide
 * there. Generating a new one invalidates the earlier code (backend consent_views.invite).
 */
export function SubjectCode({ profileId, name, locale, busy, run, date }: Pick<Context, "locale" | "busy" | "run" | "date"> & { profileId: string; name: string }) {
  const es = locale !== "en-US";
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null);
  const generate = () => void run(async () => setCode(await api<{ code: string; expires_at: string }>(`profiles/${profileId}/consent/invite/`, "POST")));
  return (
    <div className="subject-code">
      <h3>{es ? `Código para ${name}` : `Code for ${name}`}</h3>
      <p className="hint">{es
        ? `${name} entra con su propia cuenta de AINGEL (18 años o más), elige «Tengo un código de AINGEL» y escribe este código. Después decide por sí misma, permiso por permiso. El código sirve una sola vez.`
        : `${name} signs in with their own AINGEL account (18 or older), chooses "I have an AINGEL code" and types this code. Then they decide for themselves, one permission at a time. The code works only once.`}</p>
      <div role="status" aria-live="polite">
        {code && <>
          <p className="code-big"><span aria-hidden="true">{code.code.slice(0, 4)} {code.code.slice(4)}</span><span className="sr-only">{code.code.split("").join(" ")}</span></p>
          <p className="hint">{es ? "Vence: " : "Expires: "}{date(code.expires_at)}</p>
        </>}
      </div>
      <div className="actions">
        {code && <button type="button" className="btn btn-outline btn-pill" onClick={() => speak(code.code.split("").join(", "), locale, 0.8)}><span aria-hidden="true">🔊</span> {es ? "Leer el código" : "Read the code"}</button>}
        <button type="button" className={`btn btn-pill ${code ? "btn-outline" : "btn-primary"}`} disabled={busy} onClick={generate}>
          {code ? (es ? "Generar otro código" : "Generate another code") : (es ? "Generar código" : "Generate code")}
        </button>
      </div>
      {code && <p className="hint">{es ? "Si generas otro, este deja de funcionar." : "If you generate another one, this one stops working."}</p>}
    </div>
  );
}

/** «Tengo un código de AINGEL»: the person links their own adult account to the profile prepared for them. */
export function RedeemCode({ t, locale, busy, run, onRedeemed }: Pick<Context, "t" | "locale" | "busy" | "run"> & { onRedeemed: (id: string) => Promise<void> }) {
  const es = locale !== "en-US";
  const [code, setCode] = useState(""), [error, setError] = useState("");
  const hint = useId();
  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      setError("");
      void run(async () => {
        try {
          const linked = await api<{ profile: string }>("consent/redeem/", "POST", { code });
          setCode("");
          await onRedeemed(linked.profile);
        } catch (err) {
          // Shown next to the field, where the person is looking.
          setError(t(errorKey(err)));
        }
      });
    }}>
      <p className="hint" id={hint}>{es
        ? "Si alguien preparó un AINGEL para ti, te dio un código de 8 números. Escríbelo aquí, en tu propia cuenta, para decidir tú qué permites."
        : "If someone set up an AINGEL for you, they gave you an 8-digit code. Type it here, in your own account, to decide what you allow."}</p>
      <Field label={es ? "Código de 8 números" : "8-digit code"}>
        <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 8))} inputMode="numeric" pattern="[0-9]{8}"
          autoComplete="one-time-code" required aria-describedby={hint} aria-invalid={error ? true : undefined} className="code-input" />
      </Field>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="btn btn-primary btn-pill" disabled={busy || code.length !== 8}>{es ? "Usar el código" : "Use the code"}</button>
    </form>
  );
}

/**
 * Personalizar › permissions, from GET profiles/<id>/consent/. Only the person decides, one purpose per action;
 * everyone else sees statuses, the code for the person, or the legal-review state.
 */
export default function ConsentPanel({ profile, autoFocus = false, ...ctx }: WithProfile & { autoFocus?: boolean }) {
  const { locale, busy, run, refresh } = ctx;
  const es = locale !== "en-US";
  const L = (a: string, b: string) => (es ? a : b);
  const [state, setState] = useState<ConsentState | null>(null);
  const [live, setLive] = useState("");
  const [confirm, setConfirm] = useState(false);
  const title = useRef<HTMLHeadingElement>(null), confirmTitle = useRef<HTMLHeadingElement>(null), seen = useRef(false);
  const ids = useId();
  const path = `profiles/${profile.id}/consent/?locale=${locale}`;
  const status = state?.subject_status;
  const name = profile.display_name;
  useEffect(() => { void run(async () => setState(await api<ConsentState>(path))); }, [path]);
  // Focus follows the panel's state: opened after a code, or changed after asking for legal review.
  useEffect(() => { if (status && (seen.current || autoFocus)) title.current?.focus(); if (status) seen.current = true; }, [status]);
  useEffect(() => { if (confirm) confirmTitle.current?.focus(); }, [confirm]);
  const word = (s: PurposeStatus) => ({ granted: L("permitido", "allowed"), declined: L("no permitido", "not allowed"), revoked: L("revocado", "revoked"), pending: L("sin decidir", "not decided") })[s];
  const decide = (p: Purpose, decision: Decision) => void run(async () => {
    const next = await api<ConsentState>(path, "POST", { purpose: p.id, decision });
    setState(next);
    setLive(`${p.title}: ${word(next.purposes.find((x) => x.id === p.id)?.status ?? "pending")}.`);
  });
  const legal = () => void run(async () => {
    setState(await api<ConsentState>(`profiles/${profile.id}/consent/legal-review/`, "POST"));
    setConfirm(false);
    setLive(L("Se pidió la revisión legal. No se activa nada hasta entonces.", "Legal review requested. Nothing is enabled until then."));
    await refresh();
  });
  const action = (p: Purpose, decision: Decision, text: string, primary = false) => (
    <button type="button" className={`btn btn-pill ${primary ? "btn-primary" : "btn-outline"}`} disabled={busy} aria-label={`${text}: ${p.title}`} onClick={() => decide(p, decision)}>{text}</button>
  );
  const list = (canDecide: boolean) => state && groups(state.purposes, es).map(([heading, items]) => items.length > 0 && (
    <section key={heading} className="consent-group">
      <h3>{heading}</h3>
      <ul className="consent-list">
        {items.map((p) => (
          <li key={p.id} className="consent-item">
            <div className="consent-text">
              <b id={`${ids}-${p.id}`}>{p.title}</b>
              <small>{p.detail}</small>
              <StatusTag status={p.status} es={es} />
            </div>
            <div className="consent-actions" role="group" aria-labelledby={`${ids}-${p.id}`}>
              {canDecide && p.status === "pending" && <>{action(p, "grant", L("Permitir", "Allow"), true)}{action(p, "decline", L("No permitir", "Don't allow"))}</>}
              {canDecide && p.status === "granted" && action(p, "revoke", L("Revocar", "Revoke"))}
              {canDecide && (p.status === "declined" || p.status === "revoked") && action(p, "grant", L("Permitir", "Allow"), true)}
              <ListenButton purpose={p} lang={locale} es={es} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  ));
  const notice = state && <p className="hint">{state.credits_notice}</p>;
  return (
    <section className="panel consent-panel" aria-labelledby={`${ids}-title`}>
      <h2 ref={title} tabIndex={-1} id={`${ids}-title`}>{state?.is_subject ? L("Lo que permites", "What you allow") : L("Permisos de la persona", "The person's permissions")}</h2>
      <p className="consent-live" role="status" aria-live="polite">{live}</p>
      {!state ? <p className="hint">{ctx.t("loading")}</p>
        : status === "requires_legal_review" ? (
          <div className="callout">
            <p className="consent-state"><span aria-hidden="true">⚖</span> {L("En revisión legal", "Under legal review")}</p>
            <p>{L(`Se indicó que ${name} no puede dar su consentimiento. Para proteger sus datos, AINGEL no activa nada que dependa de un permiso hasta que el equipo de AINGEL registre una base legal revisada. Esto no se deduce de ningún diagnóstico.`,
              `It was indicated that ${name} cannot give consent. To protect their data, AINGEL enables nothing that depends on a permission until the AINGEL team records a reviewed legal basis. This does not follow from any diagnosis.`)}</p>
          </div>
        ) : state.is_subject ? (
          <>
            <p className="hint">{L("Tú decides, uno por uno. Cada botón cambia solo ese permiso y puedes cambiarlo cuando quieras.", "You decide, one at a time. Each button changes only that permission, and you can change it whenever you want.")}</p>
            {list(true)}
            {notice}
          </>
        ) : status === "pending_consent" ? (
          <>
            <p className="consent-state"><span aria-hidden="true">⏳</span> {L("Esperando la decisión de la persona", "Waiting for the person's decision")}</p>
            <p className="hint">{L(`${name} decide desde su propia cuenta, permiso por permiso. Hasta entonces no se activa nada que dependa de un permiso. Ayudarle a usar una pantalla no es decidir por ella.`,
              `${name} decides from their own account, one permission at a time. Until then nothing that depends on a permission is enabled. Helping them use a screen is not deciding for them.`)}</p>
            {profile.permissions.configure && <>
              <SubjectCode {...ctx} profileId={profile.id} name={name} />
              {confirm ? (
                <div className="consent-confirm" role="group" aria-labelledby={`${ids}-confirm`}>
                  <h3 ref={confirmTitle} tabIndex={-1} id={`${ids}-confirm`}>{L(`¿Confirmas que ${name} no puede dar su consentimiento?`, `Do you confirm that ${name} cannot give consent?`)}</h3>
                  <p>{L("AINGEL no activará nada que dependa de un permiso hasta que el equipo de AINGEL registre una base legal revisada (por ejemplo, una representación legal reconocida). Ningún diagnóstico implica esto: es una decisión sobre esta situación concreta. Después ya no se podrá generar un código para la persona.",
                    "AINGEL will enable nothing that depends on a permission until the AINGEL team records a reviewed legal basis (for example, a recognized legal representative). No diagnosis implies this: it is a decision about this specific situation. Afterwards, no code can be generated for the person.")}</p>
                  <div className="actions">
                    <button type="button" className="btn btn-pill danger" disabled={busy} onClick={legal}>{L("Sí, pedir revisión legal", "Yes, request legal review")}</button>
                    <button type="button" className="btn btn-outline btn-pill" onClick={() => setConfirm(false)}>{L("Cancelar", "Cancel")}</button>
                  </div>
                </div>
              ) : (
                <button type="button" className="link-button" onClick={() => setConfirm(true)}>{L("La persona no puede dar su consentimiento", "The person cannot give consent")}</button>
              )}
            </>}
          </>
        ) : (
          <>
            <p className="hint">{L(`Solo ${name} puede cambiar estos permisos, desde su propia cuenta.`, `Only ${name} can change these permissions, from their own account.`)}</p>
            {list(false)}
            {notice}
          </>
        )}
    </section>
  );
}
