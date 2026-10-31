/** Only an explicit opt-in marks a general conversation as a synthetic demo. */
export function conversationTestFields(confirmed: boolean) {
  return confirmed ? { synthetic: true as const } : {};
}

export default function SyntheticConversationConsent({
  es, checked, disabled, onChange,
}: { es: boolean; checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="synthetic-conversation">
      <label className="switch-line">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
        {es ? "Probar conversación con ejemplos inventados" : "Try conversation with fictional examples"}
      </label>
      <p className="mic-privacy">{es
        ? "Las preguntas generales y el historial de esta prueba se envían a Meta. No incluyas nombres, datos personales ni de salud: AINGEL no los detecta automáticamente. Al hablar, el navegador también puede usar su propio servicio de reconocimiento de voz. Cambiar esta opción borra la conversación y el texto escrito."
        : "General questions and this test's history are sent to Meta. Do not include names, personal or health information: AINGEL does not detect them automatically. When speaking, the browser may also use its own speech recognition service. Changing this option clears the conversation and typed text."}</p>
    </div>
  );
}
