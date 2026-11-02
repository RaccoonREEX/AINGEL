# AINGEL 3.0 · Fase 3: documentos y libros (31-10-2026)

Rama `feat/aingel3-documents`, apilada sobre `feat/aingel3-desktop` (PR #7). No está fusionada ni desplegada.

## Qué hace

- **Leer sin inventar.** El servidor lee el texto que el propio PDF contiene, página por página y en orden, sin
  llamar a Meta. Une las palabras partidas con guion al final de línea y junta las líneas de un mismo párrafo para
  la voz, sin reescribir nada.
- **Páginas escaneadas.**
  - Una página sin texto se dibuja como imagen (PDFium) y la transcribe Meta, solo cuando la persona lo pide.
  - La transcripción se marca como hecha con IA, se guarda para ese documento y entra en las búsquedas.
  - Una foto de una página se convierte en un PDF de una página escaneada.
- **Navegar:**
  - página anterior y siguiente, e ir a una página;
  - capítulos desde el índice (marcadores) del propio PDF, y el capítulo de la página actual;
  - búsqueda en todo el texto, sin distinguir tildes ni mayúsculas.
- **Entender (Meta):**
  - «Explicar esta página»: separa lo que dice la página de la explicación.
  - «Resumir esta página».
  - «Describir figuras y tablas»: tipo, título, ejes y valores.
  - «Resumir todo el documento», con todo el texto si tiene 60.000 caracteres o menos.
  - Preguntas que solo se responden con el documento, que dicen cuándo no está la respuesta y citan las páginas.
- **API:**
  - `POST /api/v1/documents/`
  - `GET|DELETE /api/v1/documents/<token>/`
  - `GET …/pages/<n>/`
  - `POST …/pages/<n>/transcribe/`
  - `GET …/search/?q=`
  - `POST …/ask/`
- **Clientes:**
  - **Web:** en la pantalla «Ver», «Leer un documento».
  - **Escritorio:** «Abrir documento» (Ctrl+Alt+O) abre una ventana de lectura que se maneja entera con teclado y
    nombres accesibles.

### Privacidad y consentimiento

- **Autorización para abrir:** abrir un documento propio exige la misma autorización que describir una foto:
  - los permisos de imágenes de la persona;
  - en el servidor de pruebas privadas, la declaración de prueba privada.

  Las capturas, las fotos y los documentos usan los mismos permisos; un permiso propio para documentos queda a tu
  decisión.
- **Almacenamiento:** el documento se guarda cifrado en la caché (`assistance.sealed`) hasta 2 horas, para una sola
  cuenta. «Cerrar documento» lo borra en el acto.
- **Llamadas a Meta:**
  - Cada transcripción o explicación vuelve a comprobar los permisos.
  - Una revocación cierra el documento. Si ocurre mientras Meta lee, se descarta la respuesta y también se cierra.
- **Documentos sintéticos:** solo aceptan acciones fijas, sin texto escrito.
- **Límites:** 20 MB y 1000 páginas. Un PDF protegido con contraseña se rechaza: AINGEL no rompe protecciones.

### Cambio importante en todas las llamadas de visión

Las instrucciones de AINGEL ahora viajan en el campo `instructions` de la API y no dentro del mensaje del usuario.
El motivo: en la prueba E, una página escaneada que solo tenía un gráfico se respondió con «Hey there! I'm Muse
Spark…», en inglés y fuera del papel de AINGEL. Con el cambio, la misma página se responde en español y con los
valores exactos. La visión de la fase 1 se volvió a comprobar en vivo: el perro sigue identificándose primero.

## Dependencias nuevas, con tu autorización

Instaladas desde PyPI:

| Paquete | Versión | Licencia | Para qué |
|---|---|---|---|
| `pypdf` | 6.21.4 | BSD-3-Clause | Leer el texto de los PDF |
| `pypdfium2` | 4.30.0 | Apache-2.0 o BSD-3-Clause, con PDFium BSD-3-Clause | Convertir las páginas escaneadas en imagen |

Se añadieron a `requirements.txt` y `requirements.lock.txt`. La próxima imagen del backend las incluirá; Astra
debe reconstruirla. Inventario: `docs/THIRD_PARTY_INVENTORY.md`.

## Pruebas

- **Backend:** 270 correctas, con 6 de Redis real omitidas. Las nuevas están en `assistance/test_documents.py` (16):
  - **Lectura:** texto, índice y la palabra partida unida; páginas escaneadas sin texto que se convierten en
    imagen; búsqueda; archivos inválidos.
  - **Prueba D:** leer y navegar sin llamar a Meta; figuras con el texto y la imagen de la página; resumen del libro
    con las 4 páginas.
  - **Prueba E:** la transcripción se hace una vez, se guarda y se puede buscar.
  - **Contenido libre:** los documentos sintéticos lo rechazan y no llevan marcadores privados.
  - **Cuentas:** el documento es de una sola cuenta y se cierra.
  - **Documento propio:** necesita autorización; se puede preguntar sobre él; una foto pasa a página escaneada; las
    revocaciones lo cierran antes de Meta y durante la llamada; está cifrado en la caché.
- **Web:**
  - `typecheck` y `build`;
  - `test:documents`, que es nuevo;
  - `test:vision`.
- **Escritorio:** compilación sin avisos y 71 comprobaciones. De ellas, 9 son de documentos contra el servidor local
  en modo de prueba:
  - libro con capítulos;
  - texto unido;
  - búsqueda;
  - explicación;
  - texto libre rechazado;
  - cierre;
  - página escaneada sin texto;
  - transcripción.

### Pruebas D y E en vivo con Meta, solo con PDF sintéticos del servidor

Segunda ronda, después del cambio a `instructions`:

| Caso | Latencia | Coste | Resultado |
|---|---|---|---|
| D: figuras de la página 3 | 9,6 s | 0,0163 USD | Lee el texto exacto, describe el gráfico de barras con S1 a S5 y los valores 4, 6, 5, 8 y 7, y dice cuál es el máximo y cuál el mínimo. |
| D: explicar la página 2 | 7,8 s | 0,0128 USD | Separa «lo que dice la página» de «mi explicación». |
| D: resumen del libro | 9,0 s | 0,0100 USD | Título, tres capítulos y hechos clave, sin añadir nada. |
| E: página escaneada 1 | 7,3 s | 0,0121 USD | Transcripción palabra por palabra, incluido el número de página 42. |
| E: página escaneada 2 (solo un gráfico) | 8,7 s | 0,0117 USD | En español y con los valores exactos. Lo describe en lugar de dar una transcripción línea por línea. |

Primera ronda, antes del cambio: 5 llamadas por 0,069 USD. Desde el inicio de la fase 1, el registro local suma 0,37 USD
en pruebas en vivo.

## Despliegue (lo hace Astra)

1. Fusionar #4, #5, #6, #7 y esta rama, en ese orden.
2. Reconstruir la imagen del backend, porque hay dependencias nuevas, y desplegar. No hay migraciones nuevas: la de
   consumo es de la fase 1.
3. Si hay un proxy con límite de tamaño, permitir 21 MB en `POST /api/v1/documents/`.

**Reversión:** revertir el commit. Los documentos en la caché caducan solos en 2 horas como máximo.

## Límites y pendientes

- **Android:** todavía no abre PDF. Ya puede leer una página fotografiada con la cámara, porque la visión profunda
  detecta la tarea «documento». Abrir PDF desde Android, con el selector de archivos del sistema, queda pendiente.
- **Lectura:**
  - Las tablas de un PDF digital se leen como texto plano, en el orden en que el PDF las guarda.
  - Las columnas múltiples dependen del orden interno del PDF.
- **Navegación:** si el PDF no tiene índice, no hay lista de capítulos. Se puede navegar por página y búsqueda.
- **Coste de las transcripciones:** cada página escaneada transcrita cuesta alrededor de 0,012 USD y tarda unos 7–9
  s.
- **NVDA:** no se probó, porque no está instalado aquí.
