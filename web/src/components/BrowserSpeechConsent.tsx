import type { RecognitionPlace } from "./aingel/browserSpeech";

/** What the microphone line says while listening: where the voice is recognized, without claiming more. */
export function micPrivacyLine(es: boolean, place: RecognitionPlace) {
  return place === "device"
    ? (es ? "Micrófono activo · tu voz se reconoce en este dispositivo y el audio no se guarda." : "Microphone on · your voice is recognized on this device and the audio is not stored.")
    : (es ? "Micrófono activo · el navegador reconoce tu voz con su propio servicio; AINGEL no guarda el audio." : "Microphone on · the browser recognizes your voice with its own service; AINGEL does not store the audio.");
}

/** Asked of each account before the browser's recognition service is used for it; typing is always the alternative. */
export default function BrowserSpeechConsent({ es, onAccept, onDecline }: { es: boolean; onAccept: () => void; onDecline: () => void }) {
  return (
    <div className="synthetic-conversation" role="group" aria-labelledby="browser-speech-title">
      <p id="browser-speech-title"><strong>{es ? "Reconocimiento de voz del navegador" : "Browser speech recognition"}</strong></p>
      <p className="mic-privacy">{es
        ? "Para convertir tu voz en texto, este navegador puede enviar el audio del micrófono al servicio de su fabricante (por ejemplo, Google en Chrome). AINGEL no controla ese servicio ni puede confirmar dónde se procesa, y no guarda el audio. El texto reconocido sigue tus autorizaciones de AINGEL. La decisión queda registrada solo para tu cuenta y puedes retirarla; otra persona que use este navegador tendrá que decidir por sí misma. Puedes escribir en su lugar."
        : "To turn your voice into text, this browser may send the microphone audio to its vendor's service (for example, Google in Chrome). AINGEL does not control that service, cannot confirm where it is processed, and does not store the audio. The recognized text follows your AINGEL authorizations. The decision is recorded for your account only and you can withdraw it; anyone else using this browser decides for themselves. You can type instead."}</p>
      <div className="actions">
        <button type="button" className="primary" onClick={onAccept}>{es ? "Aceptar y usar la voz" : "Accept and use voice"}</button>
        <button type="button" onClick={onDecline}>{es ? "Prefiero escribir" : "I'd rather type"}</button>
      </div>
    </div>
  );
}

/** Withdraws the account's acceptance. */
export function BrowserSpeechRevoke({ es, onRevoke }: { es: boolean; onRevoke: () => void }) {
  return (
    <button type="button" className="text-btn" onClick={onRevoke}>
      {es ? "Dejar de usar el reconocimiento del navegador" : "Stop using the browser's recognition"}
    </button>
  );
}
