import type { Profile } from "../types";

/**
 * A separate, one-use declaration, only for the person's own profile. The legacy flags no longer authorize
 * anything: the server checks the person's grants for [kind] (camera_local + meta_photos, microphone_local + meta_voice).
 */
export function canTestPrivateMedia(profile: Profile, _kind: "image" | "audio") {
  return profile.role === "owner" && profile.subject_status === "self";
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
      ? "Solo para tu propio perfil. Además debes permitir, en Personalizar, la cámara y «Enviar fotos a Meta», o el micrófono y «Enviar voz a Meta»."
      : "Only for your own profile. You must also allow, in Personalize, the camera and “Send photos to Meta”, or the microphone and “Send voice to Meta”."}</p>}
    <label className="consent-row">
      <input type="checkbox" checked={checked && allowed} onChange={(e) => onChange(e.target.checked)} />
      <span>{es
        ? "Autorizo esta prueba de mi propio material, sin datos de salud ni de otras personas."
        : "I authorize this test using my own material, without health information or other people."}</span>
    </label>
    <p className="hint">{es ? "Esta confirmación se usa una vez y debe repetirse para cada envío." : "This confirmation applies once and must be repeated for each submission."}</p>
  </fieldset>;
}
