# Third-party components — local prototype inventory

The application currently uses Django, Django REST Framework, Pillow, httpx, Channels/Daphne, websockets, cryptography, PyOTP, qrcode, OpenCV, NumPy, React, Vite and TypeScript, with exact resolved dependencies in the Python and npm lockfiles. Preserve their bundled licenses/notices when packaging a distributable; this inventory is not a completed transitive-license audit.

Additional assets/material:

- Meta SAM parser: **SAM License**; copied from the installed package to `licenses/meta_sam_parser.txt`. Do not label it MIT.
- YuNet model: MIT license, copied to `licenses/face_detection_yunet.txt`.
- SFace model: Apache-2.0 license from OpenCV Zoo model directory, copied to `licenses/face_recognition_sface.txt`. Pinned source and weight hashes: `FACE_MODELS.json`. Upstream training provenance and downstream biometric deployment conditions are not fully audited.
- VizWiz VQA annotations: CC BY 4.0 according to the official task page. Attribution, source and archive hash in `DATASET_MANIFEST.json`. Thirty annotations remain in ignored local evaluation storage; no corpus images or training dataset are bundled in this repository.

Project source license selection and a complete transitive inventory must be finalized before public hackathon repository publication. Nothing in this file grants rights to private family photos or consent for biometric enrollment.


## Revisión del 28 de octubre de 2026 (conversación, visión y señas)

Inventario de licencias declaradas de npm (69 paquetes; solo `react`, `react-dom` y `scheduler`, MIT, se
distribuyen en la web), Android (119 artefactos del classpath de release, Apache-2.0) y Python (40):
[`THIRD_PARTY_INVENTORY.md`](THIRD_PARTY_INVENTORY.md), generado con `backend/scripts/license_inventory.py`.

Componentes y material revisados:

- **Thinking Orbs** (MIT, Copyright (c) 2026 Yogesh): aviso completo en `THIRD_PARTY_NOTICES.md` de la raíz,
  copiado en `web/public/THIRD_PARTY_NOTICES.txt` y en el APK (`assets/licenses/`).
- **Montserrat** (SIL OFL 1.1): la fuente va dentro del APK, así que el texto de la licencia viaja con él
  (`assets/licenses/Montserrat_OFL.txt`, `docs/licenses/Montserrat_OFL.txt`). En la web se carga de Google Fonts.
- **Meta SAM parser** (SAM License): `licenses/meta_sam_parser.txt`; solo en el servidor.
- **YuNet** (MIT) y **SFace** (Apache-2.0): `licenses/face_detection_yunet.txt`, `licenses/face_recognition_sface.txt`;
  solo en el servidor. Sin cambios en el reconocimiento facial.
- **Corpus LSEC** (CC BY 4.0): ningún clip en uso; los dos que se probaron se retiraron de la app y del repositorio.
- **Manos de AINGEL** (paquete *AINGEL Manos y Señas* v1.0.0, propio del proyecto): el motor 3D (`sign-language/engine`, v0.1.1) está en `web/src/components/aingel/hands3d/` con dos cambios marcados «AINGEL» (escala por mano y biblioteca en memoria) y se usa en web; Android lo reimplementa en OpenGL nativo (`Hands3D.kt`) con las mismas señas exportadas (`assets/hands3d/signs3d.json`). Las señas se convierten en ejecución desde el catálogo 2D (`aingel-signer.js` → `signData.ts`). El motor 2D portado (`AingelSigner.tsx` / `AingelSigner.kt`) queda como respaldo sin WebGL. Geometría generada en código, sin modelos 3D externos.
- **three.js 0.184.0** (MIT, © three.js authors): instalado desde npm con versión fija e incluido en la web (no se carga de unpkg); la app Android no lo incluye. Aviso completo en `THIRD_PARTY_NOTICES.md`; la cabecera `@license` se conserva en los bundles.
  Personas identificables: revisar derechos de imagen para cada uso concreto.
- **MedlinePlus**: resúmenes de dominio público en EE. UU.; se muestran con atribución. Otros materiales del
  sitio (imágenes, A.D.A.M.) no se usan.
- **Pautas de comunicación**: se resumen con palabras propias a partir de NIA y W3C COGA (referencias en
  `KNOWLEDGE_AND_SIGNS.md`); no se copian textos. iSupport (OMS, CC BY-NC-SA) no se incorpora.

Pendiente o a revisar antes de publicar:

- Pantalla de licencias en el APK con el texto Apache-2.0 y los ficheros NOTICE de AndroidX, CameraX y OkHttp
  (p. ej. con el plugin `oss-licenses`); hoy el APK incluye solo los avisos de Thinking Orbs y Montserrat.
- `qrcode` declara un clasificador «Other/Proprietary License» además de BSD: confirmar su licencia efectiva.
- Varios POM de AndroidX/Kotlin/OkHttp no estaban en la caché local: su licencia Apache-2.0 es la publicada por
  cada proyecto y debe confirmarse con una descarga completa de metadatos.
- Condiciones de uso de Meta para datos reales (texto, imágenes, audio) y aviso del uso de créditos gratuitos.
- **VoiceStudio / clonación de voz: no integrado.** No se ha identificado el proyecto exacto ni verificado
  las licencias de la aplicación, los modelos y su uso comercial; no se ha descargado nada.
- No se han incorporado datasets de terceros nuevos, modelos de reconocimiento de señas ni el alfabeto ASL;
  el artículo LACCEI con vocales LSEC (CC BY-NC-SA) queda fuera del producto.

Esta revisión no constituye una auditoría legal completa.
