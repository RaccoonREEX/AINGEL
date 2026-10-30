import type { Consents as Value } from "../types";

/**
 * Authorizations given once, when the account is created (and changeable in Personalizar). The apps do not ask
 * again per action: the server checks them (backend care.consent).
 */
export default function Consents({ value, onChange, es, disabled = false }: { value: Value; onChange: (v: Value) => void; es: boolean; disabled?: boolean }) {
  const L = (a: string, b: string) => (es ? a : b);
  const rows: [keyof Value, string, string][] = [
    ["camera", L("Cámara: ver por la persona", "Camera: see for the person"),
      L("AINGEL abre la cámara cuando se lo piden (describir, buscar objetos; la vigilancia continua es de la app AINGEL para Android). Las imágenes no se guardan.", "AINGEL opens the camera when asked (describe, find objects; continuous watching is in the AINGEL Android app). Images are not stored.")],
    ["microphone", L("Micrófono: escuchar", "Microphone: listen"),
      L("AINGEL escucha para conversar, traducir a señas y subtitular; responder a «Hola AINGEL» es de la app para Android. El audio no se guarda.", "AINGEL listens to talk, translate to signs and caption; answering «Hola AINGEL» is in the Android app. Audio is not stored.")],
    ["meta_data", L("Enviar datos a Meta para responder", "Send data to Meta to answer"),
      L("Las preguntas, las imágenes y el audio que AINGEL necesita analizar, y los apoyos indicados y alergias (para recomendaciones adaptadas), se envían a Meta Muse Spark. Puede buscar en la web cuando la pregunta lo necesite. Mientras la cuenta use créditos gratuitos, Meta advierte que puede usar ese contenido para mejorar sus productos. No se envían nombres, rutinas, mensajes ni recuerdos.",
        "The questions, images and audio AINGEL needs to analyse, and the support needs and allergies (for tailored recommendations), are sent to Meta Muse Spark. It may search the web when a question needs it. While the account uses free credits, Meta warns it may use that content to improve its products. Names, routines, messages and memories are not sent.")],
  ];
  return (
    <fieldset className="consents" disabled={disabled}>
      <legend>{L("Autorizaciones", "Authorizations")}</legend>
      {rows.map(([key, title, detail]) => (
        <label className="consent-row" key={key}>
          <input type="checkbox" checked={!!value[key]} onChange={(e) => onChange({ ...value, [key]: e.target.checked })} />
          <span><b>{title}</b><small>{detail}</small></span>
        </label>
      ))}
      <p className="hint">{L("Sin estas autorizaciones AINGEL sigue funcionando con lo que se resuelve en el propio servicio (rutinas, mensajes, recuerdos). Se pueden cambiar en Personalizar.",
        "Without these, AINGEL still works with what the service resolves itself (routines, messages, memories). They can be changed in Personalize.")}</p>
    </fieldset>
  );
}
