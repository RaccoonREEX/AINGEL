import type { Profile } from "../types";

/** A separate, one-use declaration. The server still checks ownership and saved permissions. */
export function canTestPrivateMedia(profile: Profile, kind: "image" | "audio") {
  return profile.role === "owner" && profile.consents?.meta_data === true &&
    profile.consents?.[kind === "image" ? "camera" : "microphone"] === true;
}

/** Only an explicit, eligible private declaration can set private_test. */
export function imageTestFields(profile: Profile, confirmed: boolean, synthetic: boolean) {
  return { synthetic, ...(confirmed && !synthetic && canTestPrivateMedia(profile, "image") ? { private_test: true } : {}) };
}

/** Synthetic and private audio are separate, explicit declarations. */
export function audioTestFields(profile: Profile, confirmed: boolean, synthetic: boolean) {
  if (confirmed && canTestPrivateMedia(profile, "audio")) return { private_test: true };
  if (synthetic) return { synthetic: true };
  return {};
}

export default function PrivateMediaConsent({ profile, kind, checked, onChange, disabled = false }: {
  profile: Profile;
  kind: "image" | "audio";
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  const es = profile.locale.toLowerCase().startsWith("es");
  const allowed = canTestPrivateMedia(profile, kind);
  return <fieldset className="consents" disabled={disabled || !allowed}>
    <legend>{es ? "Prueba privada de material propio" : "Private test of your own material"}</legend>
    <p className="hint">{es
      ? "Solo para una prueba privada autorizada. La imagen o el audio se envían a Meta. Usa solo material propio, sin datos de salud ni de otras personas, también en el texto de búsqueda; la aplicación no detecta automáticamente ese contenido."
      : "For an authorized private test only. The image or audio is sent to Meta. Use only your own material, without health information or other people, including in search text; the app does not detect this content automatically."}</p>
    {!allowed && <p className="hint">{es
      ? "Se requiere ser titular del perfil y autorizar por separado Meta y la cámara o el micrófono correspondiente en Personalizar."
      : "You must own the profile and enable both Meta and the relevant camera or microphone permission in Personalize."}</p>}
    <label className="consent-row">
      <input type="checkbox" checked={checked && allowed} onChange={(e) => onChange(e.target.checked)} />
      <span>{es
        ? "Autorizo esta prueba de mi propio material, sin datos de salud ni de otras personas."
        : "I authorize this test using my own material, without health information or other people."}</span>
    </label>
    <p className="hint">{es ? "Esta confirmación se usa una vez y debe repetirse para cada envío." : "This confirmation applies once and must be repeated for each submission."}</p>
  </fieldset>;
}
