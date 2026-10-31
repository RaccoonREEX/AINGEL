# Third-party components — local prototype inventory

The application currently uses Django, Django REST Framework, Pillow, httpx, Channels/Daphne, websockets, cryptography, PyOTP, qrcode, OpenCV, NumPy, React, Vite and TypeScript, with exact resolved dependencies in the Python and npm lockfiles. Preserve their bundled licenses/notices when packaging a distributable; this inventory is not a completed transitive-license audit.

Additional assets/material:

- Meta SAM parser: **SAM License**; copied from the installed package to `licenses/meta_sam_parser.txt`. Do not label it MIT.
- YuNet model: MIT license, copied to `licenses/face_detection_yunet.txt`.
- SFace model: Apache-2.0 license from OpenCV Zoo model directory, copied to `licenses/face_recognition_sface.txt`. Pinned source and weight hashes: `FACE_MODELS.json`. Upstream training provenance and downstream biometric deployment conditions are not fully audited.
- VizWiz VQA annotations: CC BY 4.0 according to the official task page. Attribution, source and archive hash in `DATASET_MANIFEST.json`. Thirty annotations remain in ignored local evaluation storage; no corpus images or training dataset are bundled in this repository.

Project source license selection and a complete transitive inventory must be finalized before public hackathon repository publication. Nothing in this file grants rights to private family photos or consent for biometric enrollment.


## Revisión del 28 de octubre de 2026 (conversación, visión y señas)

Inventario de licencias declaradas de npm (solo `react`, `react-dom`, `scheduler` y `three`, MIT, se
distribuyen en la web; corregido el 30-10), Android (120 artefactos del classpath de release, Apache-2.0, tras
añadir `lifecycle-service`) y Python (43, con `psycopg`, `psycopg-binary` y `redis`):
[`THIRD_PARTY_INVENTORY.md`](THIRD_PARTY_INVENTORY.md), generado con `backend/scripts/license_inventory.py`.

Componentes y material revisados:

- **Thinking Orbs** (MIT, Copyright (c) 2026 Yogesh): aviso completo en `THIRD_PARTY_NOTICES.md` de la raíz,
  copiado en `web/public/THIRD_PARTY_NOTICES.txt` y en el APK (`assets/licenses/`).
- **Montserrat** (SIL OFL 1.1): la fuente va dentro del APK, así que el texto de la licencia viaja con él
  (`assets/licenses/Montserrat_OFL.txt`, `docs/licenses/Montserrat_OFL.txt`). En la web se carga de Google Fonts.
- **Meta SAM parser** (SAM License): `licenses/meta_sam_parser.txt`; solo en el servidor.
- **YuNet** (MIT) y **SFace** (Apache-2.0): `licenses/face_detection_yunet.txt`, `licenses/face_recognition_sface.txt`;
  solo en el servidor. Sin cambios en el reconocimiento facial.
- **Corpus LSEC** (CC BY 4.0): ningún clip en uso. Los dos clips de investigación (`LSEC_RESEARCH_SAMPLES.json`)
  nunca se versionaron en Git (verificado en todo el historial el 30-10); siguen solo en `.local/datasets/`, ignorado.
- **Manos de AINGEL** (paquete *AINGEL Manos y Señas* v1.0.0, propio del proyecto): el motor 3D (`sign-language/engine`, v0.1.1) está en `web/src/components/aingel/hands3d/` con dos cambios marcados «AINGEL» (escala por mano y biblioteca en memoria) y se usa en web; Android lo reimplementa en OpenGL nativo (`Hands3D.kt`) con las mismas señas exportadas (`assets/hands3d/signs3d.json`). Las señas se convierten en ejecución desde el catálogo 2D (`aingel-signer.js` → `signData.ts`). El motor 2D portado (`AingelSigner.tsx` / `AingelSigner.kt`) queda como respaldo sin WebGL. Geometría generada en código, sin modelos 3D externos.
- **three.js 0.184.0** (MIT, © three.js authors): instalado desde npm con versión fija e incluido en la web (no se carga de unpkg); la app Android no lo incluye. Aviso completo en `THIRD_PARTY_NOTICES.md`; la cabecera `@license` se conserva en los bundles.
  Personas identificables: revisar derechos de imagen para cada uso concreto.
- **MedlinePlus**: resúmenes de dominio público en EE. UU.; se muestran con atribución. Otros materiales del
  sitio (imágenes, A.D.A.M.) no se usan.
- **Pautas de comunicación**: se resumen con palabras propias a partir de NIA y W3C COGA (referencias en
  `KNOWLEDGE_AND_SIGNS.md`); no se copian textos. iSupport (OMS, CC BY-NC-SA) no se incorpora.

Pendiente o a revisar antes de publicar:

- Pantalla de licencias visible en el APK. *Actualizado 30-10:* el aviso del APK
  (`assets/licenses/THIRD_PARTY_NOTICES.md`) ya incluye Apache-2.0, libyuv (BSD-3-Clause) y la Public Suffix List
  (MPL-2.0) con sus textos completos; falta mostrarlo desde la app (cambio de código pendiente).
- ~~`qrcode` «Other/Proprietary License»~~ *Resuelto 30-10:* su LICENSE es BSD-3-Clause (Lincoln Loop) más MIT
  (parte pyqrnative); el clasificador no corresponde al texto. Solo servidor.
- ~~POM de AndroidX/Kotlin/OkHttp ausentes~~ *Resuelto 30-10:* los 35 POM se leyeron en Google Maven / Maven
  Central: todos Apache-2.0.
- Condiciones de uso de Meta para datos reales (texto, imágenes, audio) y aviso del uso de créditos gratuitos.
- **VoiceStudio / clonación de voz: no integrado.** No se ha identificado el proyecto exacto ni verificado
  las licencias de la aplicación, los modelos y su uso comercial; no se ha descargado nada.
- No se han incorporado datasets de terceros nuevos, modelos de reconocimiento de señas ni el alfabeto ASL;
  el artículo LACCEI con vocales LSEC (CC BY-NC-SA) queda fuera del producto.

Esta revisión no constituye una auditoría legal completa.

## Revisión del 30 de octubre de 2026 (preparación para publicar)

Detalle completo en [`PUBLICATION_READINESS.md`](PUBLICATION_READINESS.md). Cambios respecto a la revisión anterior:

| Componente | Licencia (SPDX) | ¿Se distribuye? | Obligación | Estado del aviso |
|---|---|---|---|---|
| React, ReactDOM, scheduler 19.3.1 / 0.28.0 | MIT | Sí, bundle web | Copyright + permiso | **Faltaba**; añadido en `THIRD_PARTY_NOTICES.md` y `licenses/React_MIT.txt`. Copiar a `web/public/THIRD_PARTY_NOTICES.txt` |
| three.js 0.184.0 | MIT | Sí, bundle web | Copyright + permiso | Correcto; texto también en `licenses/three.js_MIT.txt` |
| Thinking Orbs (yogesharc/thinking-orbs) | MIT, © 2026 Yogesh (verificado en el LICENSE del repositorio) | Sí (web y APK, como inspiración/adaptación del orb) | Copyright + permiso | Correcto; `licenses/Thinking_Orbs_MIT.txt`. El grado de copia no está verificado: el código se declara portado del paquete AINGEL UI v1.1.1 |
| AndroidX / Compose / CameraX / Kotlin / OkHttp / Okio | Apache-2.0 | Sí, APK | Copia de la licencia; NOTICE si existe (no hay) | Texto completo en `licenses/Apache-2.0.txt` y en el aviso del APK |
| libyuv (en `camera-core`) | BSD-3-Clause | Sí, APK (código nativo) | Reproducir copyright y condiciones | **Faltaba**; añadido (`licenses/libyuv_BSD-3-Clause.txt`) |
| Public Suffix List (en OkHttp) | MPL-2.0 | Sí, APK (datos) | Informar de la licencia y del acceso a la fuente | **Faltaba**; añadido (`licenses/MPL-2.0.txt`) |
| Montserrat | OFL-1.1 (sin nombre reservado) | Sí, APK; web vía Google Fonts | Licencia con la fuente; no vender la fuente sola | Correcto |
| YuNet / SFace (OpenCV Zoo `48b10fa5`) | MIT / Apache-2.0 | No: se descargan en el servidor, ni en Git ni en imágenes | Conservar licencias si se redistribuyen | Correcto |
| meta-sam-parser 0.1.0 | SAM License (no OSI) | No (servidor) | Incluir el acuerdo al redistribuir; restricciones de uso y de control de exportaciones | Correcto |
| psycopg / psycopg-binary 3.2.10 | LGPL-3.0-only | No (servidor) | Solo si se publica imagen del backend | Añadido al inventario |
| redis-py 6.4.0 | MIT | No (servidor) | — | Añadido al inventario |
| Corpus LSEC (Zenodo 10.5281/zenodo.21627229) | CC-BY-4.0 + derechos de imagen de los signantes | No | Atribución; revisar derechos de personalidad antes de cualquier uso | Correcto |
| VizWiz VQA (anotaciones) | CC-BY-4.0 | No (30 anotaciones locales ignoradas) | Atribución | Correcto |
| MedlinePlus | Dominio público (EE. UU.) para resúmenes | Índice local del servidor; extractos mostrados en la app | Atribución pedida por NLM | Correcto |
| Logotipo / isotipo AINGEL | Propio (sin licencia declarada) | Sí, web y APK | — | El SVG contiene un manifiesto C2PA de Anthropic/Claude: confirmar autoría y derechos del diseño |
| Señas 2D/3D (*AINGEL Manos y Señas* v1.0.0, catálogo v1.5.0) y paquete AINGEL UI v1.1.1 | Propio (declarado) | Sí, web y APK | — | Confirmar autor y fecha de creación (posible trabajo previo al evento) |

No se usa MediaPipe (solo se sigue su convención de 21 puntos en `landmarksToPose.js`).
