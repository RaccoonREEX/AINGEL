import { speakLocally } from "./aingel/browserSpeech";
import { useId } from "react";
import type { Purpose } from "../types";

/** Reads [text] with a local browser voice only (browserSpeech.ts): network voices would send the text. */
export function speak(text: string, lang: string, rate = 1) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = rate;
  speakLocally(u);
}

/** Purposes grouped by where the data goes, so a transfer to Meta is never mixed with local use. */
export function groups<T extends Purpose>(items: T[], es: boolean): [string, T[]][] {
  return [
    [es ? "Se queda en tu teléfono o en AINGEL" : "Stays on your phone or in AINGEL", items.filter((p) => p.to !== "meta")],
    [es ? "Se envía a Meta" : "Sent to Meta", items.filter((p) => p.to === "meta")],
  ];
}

export function ListenButton({ purpose, lang, es }: { purpose: Purpose; lang: string; es: boolean }) {
  return (
    <button type="button" className="btn btn-outline btn-sm listen-btn" aria-label={`${es ? "Escuchar" : "Listen to"}: ${purpose.title}`}
      onClick={() => speak(`${purpose.title}. ${purpose.detail}`, lang)}>
      <span aria-hidden="true">🔊</span> {es ? "Escuchar" : "Listen"}
    </button>
  );
}

/**
 * The person's own choices when they set up AINGEL for themselves: one checkbox per purpose, none checked by
 * default (no «accept all»). Sent as `grants`; later decisions are made in Personalizar (ConsentPanel).
 */
export default function Consents({ purposes, notice, value, onChange, lang, es, disabled = false }: {
  purposes: Purpose[]; notice: string; value: string[]; onChange: (ids: string[]) => void; lang: string; es: boolean; disabled?: boolean;
}) {
  const hint = useId();
  return (
    <fieldset className="consents" disabled={disabled} aria-describedby={hint}>
      <legend>{es ? "Qué permites" : "What you allow"}</legend>
      <p className="hint" id={hint}>{es
        ? "Cada permiso es aparte y ninguno viene marcado. Marca solo los que quieras; puedes cambiarlos cuando quieras en Personalizar."
        : "Each permission is separate and none is checked. Check only the ones you want; you can change them at any time in Personalize."}</p>
      {groups(purposes, es).map(([title, items]) => items.length > 0 && (
        <fieldset key={title} className="consent-group">
          <legend>{title}</legend>
          {items.map((p) => (
            <div className="consent-item" key={p.id}>
              <label className="consent-row">
                <input type="checkbox" checked={value.includes(p.id)}
                  onChange={(e) => onChange(e.target.checked ? [...value, p.id] : value.filter((x) => x !== p.id))} />
                <span><b>{p.title}</b><small>{p.detail}</small></span>
              </label>
              <ListenButton purpose={p} lang={lang} es={es} />
            </div>
          ))}
        </fieldset>
      ))}
      <p className="hint">{notice}</p>
    </fieldset>
  );
}
