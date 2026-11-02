import { useState } from "react";
import { api } from "../api";
import { localFingerprint } from "./aingel/signRegistry";

/**
 * A correction of one sign by a Deaf user or an expert (backend care.sign_registry.feedback). It reaches the
 * reviewers and changes nothing by itself: validation is recorded by people, for an exact animation.
 */
export default function SignFeedbackForm({ es, signs, name }: { es: boolean; signs: string[]; name: (id: string) => string }) {
  const L = (spanish: string, english: string) => (es ? spanish : english);
  const unique = [...new Set(signs)];
  const [sign, setSign] = useState(unique[0] ?? ""),
    [verdict, setVerdict] = useState("incorrect"),
    [role, setRole] = useState("deaf_signer"),
    [region, setRegion] = useState(""),
    [comment, setComment] = useState(""),
    [state, setState] = useState<"" | "sending" | "sent" | "failed">("");
  if (!unique.length) return null;
  // The form exists before any sign is shown: the choice falls back to the first sign of what is on screen now.
  const chosen = unique.includes(sign) ? sign : unique[0];
  return (
    <details className="sign-feedback">
      <summary>{L("Corregir una seña (para quienes signan LSEC)", "Correct a sign (for LSEC signers)")}</summary>
      <form onSubmit={(e) => {
        e.preventDefault();
        setState("sending");
        const fingerprint = localFingerprint(chosen);
        void api("signs/feedback/", "POST", { sign: chosen, verdict, role, region: region.trim(), comment: comment.trim(), ...(fingerprint ? { fingerprint } : {}) })
          .then(() => { setState("sent"); setComment(""); }).catch(() => setState("failed"));
      }}>
        <label>{L("Seña", "Sign")}
          <select value={chosen} onChange={(e) => setSign(e.target.value)}>{unique.map((id) => <option key={id} value={id}>{name(id)}</option>)}</select>
        </label>
        <label>{L("¿Cómo está?", "How is it?")}
          <select value={verdict} onChange={(e) => setVerdict(e.target.value)}>
            <option value="correct">{L("Correcta", "Correct")}</option>
            <option value="incorrect">{L("Incorrecta", "Incorrect")}</option>
            <option value="unclear">{L("No se entiende", "Unclear")}</option>
            <option value="regional_variant">{L("Es una variante regional", "It's a regional variant")}</option>
          </select>
        </label>
        <label>{L("Tú eres", "You are")}
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="deaf_signer">{L("Persona sorda que signa LSEC", "Deaf LSEC signer")}</option>
            <option value="interpreter">{L("Intérprete de LSEC", "LSEC interpreter")}</option>
            <option value="hearing_signer">{L("Oyente que signa LSEC", "Hearing LSEC signer")}</option>
            <option value="learner">{L("Estoy aprendiendo LSEC", "LSEC learner")}</option>
            <option value="other">{L("Otro", "Other")}</option>
          </select>
        </label>
        <label>{L("Región o variante (opcional)", "Region or variant (optional)")}
          <input maxLength={100} value={region} onChange={(e) => setRegion(e.target.value)} />
        </label>
        <label>{L("Cómo debería ser (opcional)", "How it should be (optional)")}
          <textarea maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        <button className="btn btn-pill btn-outline" disabled={state === "sending"}>{L("Enviar corrección", "Send correction")}</button>
        <p role="status">{state === "sent" ? L("Gracias. La revisarán personas que signan LSEC; no cambia la seña por sí sola.", "Thank you. LSEC signers will review it; it does not change the sign by itself.")
          : state === "failed" ? L("No se pudo enviar. Inténtalo de nuevo.", "It couldn't be sent. Please try again.") : ""}</p>
      </form>
    </details>
  );
}
