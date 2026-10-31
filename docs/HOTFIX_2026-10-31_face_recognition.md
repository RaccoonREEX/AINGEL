# Hotfix 31-10-2026: reconocimiento facial desactivado

**Rama:** `hotfix/face-recognition-off`, creada desde `main` en `25d964c`, la versión desplegada.

**Motivo.** Astra detectó que el procesamiento facial podía seguir después de una revocación. El VPS está fuera de
servicio (502) hasta que esto se despliegue.

## Variable nueva

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `AINGEL_FACE_RECOGNITION_ENABLED` | `0` (cualquier valor distinto de exactamente `1`) | Activa el módulo facial |

**Con el módulo desactivado:**
- `faces/recognize/`, la inscripción (`POST faces/`) y activar la función (`POST faces/consent/` con
  `enabled: true`) responden `503 face_recognition_disabled`, antes de leer la imagen.
- La descripción de escenas no consulta el reconocimiento: `people` siempre vale `[]`.
- `embeddings()` y `family_matches()` se niegan antes de cargar ningún modelo.

**Lo que sigue funcionando:**
- Consultar el estado: `GET faces/` muestra `available: false`, y sí `enabled` y las inscripciones.
- Desactivar la función.
- Que un familiar borre su propia inscripción.
- Retirar el permiso `face_local`.

**Plantillas biométricas existentes:** no se borran automáticamente; solo cuando alguien lo pide.

**Resto del producto:** conversación, Meta con datos sintéticos, autenticación, cámara no biométrica, audio,
accesibilidad y los demás módulos no cambian.

## Revocación, para una futura reactivación

**Causa.**
- `family_matches()` ejecutaba OpenCV antes de volver a comprobar el consentimiento.
- Después solo revisaba el interruptor del perfil y las versiones de cada familiar, nunca el permiso `face_local` de
  la persona.
- `recognize_family()` no exigía ese permiso.

**Ahora, antes de procesar,** se lee de la base de datos:
- el interruptor del servidor;
- el del perfil;
- el permiso `face_local` de la persona;
- su `consent_epoch`;
- la versión de cada familiar.

Si algo no autoriza, no se detecta ningún rostro.

**Después de procesar,** con la fila del perfil bloqueada (serializada con las revocaciones), se vuelve a leer todo.
Si algo cambió, se descarta el resultado:
- `recognize_family` responde `409 face_consent_changed`, sin resultado ni auditoría de coincidencia;
- la descripción de escenas no nombra a nadie.

## Evidencia

**`care/test_face_hotfix.py` (10 pruebas):**
- **Módulo desactivado:**
  - OpenCV (`FaceDetectorYN.create`, `FaceRecognizerSF.create`) y la lectura de imágenes se sustituyen por espías que
    hacen fallar la prueba si se usan.
  - Ninguna ruta los usa: reconocer, inscribir, activar ni la descripción de escenas por la ruta real autorizada con
    `family=true`.
  - El interruptor solo se enciende con `1` exacto.
  - Consultar y retirar funcionan, y la plantilla no se borra sin que se pida.
- **Módulo activado:**
  - Sin `face_local` no se procesa.
  - La revocación de `face_local`, de la cámara o de la función durante el procesamiento descarta el resultado (409).
  - La descripción de escenas no nombra a nadie si se revoca durante el procesamiento.
  - **Revocación concurrente real:** un segundo hilo revoca mientras el primero está dentro del procesamiento, y el
    resultado se descarta.
- **Comprobación contra el código desplegado:** el procesamiento corría sin ningún interruptor, y con la misma
  revocación concurrente devolvía la coincidencia «Familiar ficticio».
- **Pruebas faciales anteriores:** se ejecutan con el interruptor en `1`, porque cubren el módulo activado.

**Suites:**
- **Django:** 226 pruebas, con 6 de Redis real omitidas.
- **Web:** `tsc`, build y 4 scripts. `test:revocation` ahora normaliza los finales de línea, porque fallaba en
  checkouts con CRLF.
- **Android:** compilación, 73 pruebas unitarias y lint con 0 errores.

**Clientes:** web y Android muestran un mensaje claro para `face_recognition_disabled` y `face_consent_changed`.

## Despliegue (lo decide el propietario; no hay despliegue automático)

1. Desplegar esta rama sin definir `AINGEL_FACE_RECOGNITION_ENABLED`, o con `0`.
2. No requiere migraciones.
3. Comprobación rápida: `POST /api/v1/profiles/<id>/faces/recognize/` debe responder
   `503 {"error": "face_recognition_disabled"}`.
