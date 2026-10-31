import { useEffect, useState } from "react";
import { api } from "../api";

/** A question written by the server (assistance.synthetic): the only content a synthetic test may send to Meta. */
export type SyntheticQuestion = { id: string; "es-EC": string; "en-US": string };

/**
 * Synthetic demo: the person picks one of the server's example questions. Nothing typed or spoken is sent as
 * synthetic, and the server answers it with a fictitious profile, never this person's.
 */
export default function SyntheticConversationConsent({
  es, checked, disabled, onChange, onPick,
}: {
  es: boolean; checked: boolean; disabled: boolean;
  onChange: (checked: boolean) => void; onPick: (question: SyntheticQuestion) => void;
}) {
  const [questions, setQuestions] = useState<SyntheticQuestion[] | null>(null);
  useEffect(() => {
    if (!checked || questions) return;
    api<{ enabled: boolean; questions: SyntheticQuestion[] }>("synthetic/")
      .then((catalog) => setQuestions(catalog.enabled ? catalog.questions : []))
      .catch(() => setQuestions([]));
  }, [checked, questions]);
  return (
    <div className="synthetic-conversation">
      <label className="switch-line">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
        {es ? "Probar conversación con ejemplos inventados" : "Try conversation with fictional examples"}
      </label>
      <p className="mic-privacy">{es
        ? "Elige una pregunta de ejemplo: AINGEL la envía a Meta con un perfil ficticio, sin tus datos. En esta prueba no se envía a Meta nada que escribas o digas. Cambiar esta opción borra la conversación."
        : "Pick an example question: AINGEL sends it to Meta with a fictitious profile, without your data. In this test nothing you type or say is sent to Meta. Changing this option clears the conversation."}</p>
      {checked && (
        <div className="synthetic-questions">
          {questions === null && <span className="muted">{es ? "Cargando ejemplos…" : "Loading examples…"}</span>}
          {questions?.length === 0 && <span className="muted">{es ? "Este servidor no tiene pruebas sintéticas." : "This server has no synthetic tests."}</span>}
          {questions?.map((q) => (
            <button type="button" key={q.id} className="pill" disabled={disabled} onClick={() => onPick(q)}>{es ? q["es-EC"] : q["en-US"]}</button>
          ))}
        </div>
      )}
    </div>
  );
}
