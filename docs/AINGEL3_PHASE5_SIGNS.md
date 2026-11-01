# AINGEL 3.0 · Fase 5: registro de señas validadas (31-10-2026)

Rama `feat/aingel3-validated-signs`, apilada sobre `feat/aingel3-system-audio` (PR #9). No está fusionada ni
desplegada.

## Auditoría (pasos 1 y 2 del pliego, §16)

Las manos 3D de AINGEL, en web y Android, animan **81 señas**:

- **43 palabras:** agua, ayer, ayuda, ayudar, baño, beber, bien, caminar, casa, comer, comida, doctor, dolor, dormir,
  esperar, familia, gracias, hija, hijo, hola, hoy, ir, jugar, leer, libro, llamar, mal, mamá, mañana, medicina,
  necesitar, no, papá, parque, pelota, por favor, pregunta, querer, sí, tener, tú, venir y yo.
- **27 letras** del alfabeto manual, con la ñ.
- **11 números.**

Todas son **diseño propio de AINGEL** (AINGEL_Manos_y_Senas v1.0.0, catálogo v1.5.0). **Ninguna está validada** por
personas sordas que signan LSEC. Tampoco hay reglas gramaticales de LSEC con fuente ni componentes no manuales. El
catálogo de clips grabados sigue vacío, y el reconocimiento por cámara (#5) compara con estos mismos diseños.

## Qué se construyó

- **Huella de cada animación** (`web/src/components/aingel/signFingerprint.ts`):
  - Es el SHA-256 de los fotogramas clave de la seña más las formas de mano que usa.
  - `npm run export:android-hands` la escribe para la web y para Android.
- **Registro** (`backend/care/data/sign_registry.json` y `care/sign_registry.py`):
  - Cada seña tiene tipo, fuente, licencia, variante regional, componentes no manuales y revisiones. La lengua es
    `lsec`; el registro rechaza otra.
  - **Una seña queda validada solo** con:
    - dos aprobaciones **de la misma huella**;
    - al menos una de ellas de una **persona sorda que signa**;
    - ninguna objeción posterior.
  - Si se cambia la animación, la validación deja de valer y la seña vuelve a revisión.
  - Las reglas gramaticales exigen fuente. Hoy no hay ninguna, así que no se aplica ninguna transformación
    gramatical.
- **API y comandos:**
  - **API:**
    - `GET /api/v1/signs/registry/`: estado de cada seña y resumen. Sin nombres de revisores.
    - `POST /api/v1/signs/feedback/`: correcciones de usuarios sordos y expertos. No cambian nada por sí solas.
  - **Comandos:**
    - `sync_sign_registry`: añade señas nuevas como pendientes y nunca valida.
    - `record_sign_review`: registra una revisión con la huella actual. Se hace en persona y se sube como cambio
      revisado.
    - `export_sign_feedback`: correcciones para los revisores, sin datos de cuenta.
- **Reconocimiento por cámara:** cada seña reconocida indica `validated: true/false`.
- **Web (Traductor de señas) y Android (Traductor de señas y «Escuchar y traducir»):**
  - **Por defecto, solo señas validadas.** Si una frase necesita alguna seña no validada:
    - las manos no se mueven;
    - se muestra el **texto completo**;
    - el aviso dice «Interpretación en señas no disponible», o «parcial: solo N de M».
  - Nunca se anima parte de una frase, porque omitir señas cambia lo que se dijo.
  - **Opción explícita «Mostrar también las señas de diseño AINGEL que aún no están validadas»:**
    - las anima con la etiqueta «Ilustrativo · diseño AINGEL, no es una traducción validada en LSEC»;
    - se recuerda en el dispositivo.
  - **Deletreo:** las letras tampoco están validadas, así que el deletreo manual queda sujeto a la misma regla.
  - **Velocidad:** se ajusta igual que antes (1,5×, 1×, 0,75× y 0,5×).
  - **Correcciones (web):** el formulario «Corregir una seña (para quienes signan LSEC)» pide la seña, cómo está
    (correcta, incorrecta, no se entiende o variante regional), quién eres, la región y un comentario.

## Pruebas (prueba H)

- **Backend:** 280 correctas, con 6 de Redis omitidas. Las 10 de `care/test_sign_registry.py` cubren:
  - nada validado hoy;
  - el registro coincide con las animaciones;
  - hacen falta 2 aprobaciones con una persona sorda;
  - una animación cambiada vuelve a revisión;
  - una objeción posterior bloquea;
  - registros inválidos: otra lengua, regla sin fuente, revisión sin huella o con un rol inventado;
  - registrar dos revisiones valida la seña;
  - la sincronización no duplica;
  - el endpoint;
  - las correcciones se guardan, no cambian el estado y se exportan sin cuenta.

  En el reconocimiento, cada seña lleva `validated: false`.
- **Web:** `test:sign-registry`, que es nuevo:
  - las huellas que se distribuyen son las de las animaciones actuales;
  - Android tiene las mismas huellas;
  - el registro cubre exactamente las señas animadas;
  - las reglas de reproducción.

  Además pasan `typecheck` y `build`.
- **Android:** 82 pruebas unitarias, 3 nuevas en `SignRegistryTest`, y 0 errores de lint.
- **En el navegador, contra el backend local:**
  1. «Hola, gracias» en modo texto: las manos no se mueven, aparece el aviso y el texto completo, y hay 0 señas en
     la tira.
  2. Con la opción ilustrativa activada: se animan «hola» y «gracias» con la etiqueta «Ilustrativo».
  3. Corrección: el primer envío falló, porque el formulario empezaba sin seña elegida; se corrigió. El segundo
     envío se guardó y se borró después.

## Cómo se valida una seña (para hacerlo con personas sordas)

1. Mostrar la animación actual a una persona sorda que signa LSEC, y a una segunda persona: otra persona sorda, un
   intérprete o un lingüista.
2. Con su permiso para ser acreditadas, ejecutar con el nombre o seudónimo de la persona y la región, por ejemplo
   «Sierra (Quito)»:
   ```
   python manage.py record_sign_review hola --reviewer "<nombre o seudónimo acordado>" --role deaf_signer --region "Sierra (Quito)" --decision approve
   ```
3. Subir `care/data/sign_registry.json` como un cambio revisado y desplegar. Los clientes la mostrarán como validada
   solo si su animación tiene esa misma huella.
4. Para corregir una seña: cambiar la animación, ejecutar `npm run export:android-hands` y
   `python manage.py sync_sign_registry`, y volver a revisarla.

## Cambio visible para las personas usuarias

**Hasta ahora**, el traductor animaba siempre los diseños de AINGEL, con la etiqueta «pendiente de validar».
**Ahora**, por defecto muestra el texto y explica que la interpretación en señas no está disponible. Quien quiera
ver los diseños ilustrativos los activa con un toque. Así se cumple el pliego («no generar secuencias arbitrarias
de manos para aparentar traducción») y no se pierde la opción de verlos.

## Pendiente

- **Lo esencial:** validar con personas sordas usuarias de LSEC. Ninguna seña está validada hoy, así que la
  interpretación en señas no está disponible.
- **Android:** todavía no tiene formulario de corrección; se usa el de la web.
- **Gramática y componentes no manuales:** sin material con fuente, no se implementan.
- **Escritorio:** no tiene traductor de señas.

## Despliegue y reversión

- **Despliegue:** `migrate` aplica `care.0009_sign_feedback`. El registro viaja con el código.
- **Reversión:**
  - revertir el commit;
  - `migrate care 0008` elimina la tabla de correcciones; guarda antes una exportación si hay datos.
