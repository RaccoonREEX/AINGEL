# Tipo de imagen y dibujos descritos en dos capas (2-11-2026)

Rama `feat/vision-content-type`, sobre `release/hackathon-submission-2026` (`628e1f8`), que ya incluye
`feat/vision-expressions-first`. No está fusionada ni desplegada.

## Retroalimentación que lo motivó

Una persona con discapacidad visual pidió descripciones más completas del perfil y de los rasgos visibles de las
figuras, y que se distinguiera **lo que un dibujo representa** de **los trazos con que está hecho**.

## Intención y tipo de imagen, por separado

- **Intención** (lo que la persona quiere saber): se sigue leyendo de la pregunta o de los campos explícitos, como
  antes. «Describe este dibujo» da la tarea `drawing`; «¿Cómo es su cara?», `face`.
- **Tipo de contenido visual:** ahora lo decide Meta **a partir de la propia imagen**, en la misma llamada, sin
  llamadas de clasificación adicionales. La nueva política compartida `content_type` («CONTENT TYPE») le pide
  distinguir entre:
  - fotografía;
  - dibujo o boceto;
  - ilustración digital, aunque sea realista;
  - pintura;
  - imagen mixta;
  - **fotografía de una hoja con un dibujo**, cuyo contenido principal es el dibujo;
  - gráfico, diagrama o documento;
  - tipo indeterminado, que se dice como tal.
- **Ninguno de los dos fija el otro:** que la pregunta diga «imagen» no convierte la imagen en dibujo, y que venga de
  la cámara no la convierte en fotografía.

## Qué cambia en las instrucciones

- **Fotografías:** se describen los objetos y rasgos observados, nunca con vocabulario de líneas o trazos.
- **Dibujos, ilustraciones y pinturas (política `drawings` reescrita):**
  1. Primero lo representado: figura reconocible, silueta, **orientación** (frente, perfil izquierdo o derecho, tres
     cuartos, de espaldas), partes, proporciones, relaciones espaciales, gestos y rasgos distintivos.
  2. Después la técnica: material, líneas, grosor, trazos continuos, interrumpidos, repetidos o superpuestos,
     sombreado, colores y disposición en la hoja.

  Además:
  - una línea de construcción, un sombreado o un contorno nunca se toman por un rasgo anatómico;
  - la narración es natural, sin «Capa A» ni «Capa B»;
  - nunca se sustituye la figura por «se observan numerosos trazos»;
  - si la figura es ambigua, primero lo observable y luego las lecturas posibles;
  - nunca se atribuyen personalidad, enfermedad, estado psicológico ni intenciones al autor.
- **Perfil de las personas:**
  - `faces` y `expressions` piden la orientación de la cabeza y describir solo lo que esa vista muestra;
  - **un ojo o una oreja ocultos en un perfil nunca se describen como observados**;
  - se describen el perfil de la frente, la nariz, los labios, el mentón y la mandíbula, y las orejas visibles;
  - en un retrato dibujado son rasgos representados, no de una persona real.
- **Se mantiene la prioridad de la expresión aparente.**
- **Qué tareas reciben las reglas:**

| Tarea | Recibe ahora | Para qué |
|---|---|---|
| `general` | `drawings` | Una foto de un dibujo tomada sin decir «dibujo» se describe en dos capas |
| `face` | `drawings` | Un retrato dibujado |
| `document` | `drawings` | Una ilustración dentro de un documento |
| `drawing` | `faces` y `expressions` | «¿Y su cara?» después de un retrato dibujado |

  Además, «perfil», «de lado» y «profile» se reconocen como preguntas sobre una persona.
- **Visión profunda:**
  - las notas registran primero el tipo de imagen;
  - en un dibujo, las notas separan lo representado de los trazos;
  - la síntesis sigue el mismo orden.

  Las preguntas de seguimiento conservan las reglas.
- **Android, «Ver y describir» (`scene/`):** recibe `content_type` mediante `VISION_RULES`. Su instrucción dice
  ahora «una imagen de la cámara» en lugar de «una foto».
- **`screen_media`:** se mantiene sin cambios.

No se añadieron modelos, dependencias ni servicios. El modelo sigue siendo `muse-spark-1.3` Standard, con los mismos
niveles y presupuestos de tokens.

## Pruebas

`backend/assistance/test_content_type.py`: 18 pruebas por las rutas reales, con Meta interceptado en el cliente
HTTP. Cubren los trece casos pedidos:
1. Foto de una persona.
2. Perfil.
3. Animal dibujado.
4. Figura humana dibujada.
5. Foto de una hoja con un dibujo.
6. Ilustración digital realista.
7. Imagen ambigua.
8. Líneas superpuestas.
9. Pregunta por los trazos después de la figura.
10. Pregunta por la cara después de un retrato dibujado.
11. `screen_media`.
12. Compatibilidad:
    - los fixtures de servidor (como los que usan web y Desktop) responden con los mismos campos;
    - `scene/` de Android lleva la regla.
13. Consentimiento, sesión cifrada y revocación.

También cubren la visión profunda en sus tres pasos. **Quince de las dieciocho fallan con el código anterior.**

Dos aserciones de `test_vision.py` se actualizaron porque buscaban la redacción antigua de la regla de dibujos. La
protección es la misma: decir primero lo representado y nunca responder solo «hay trazos en una hoja».

**Límite:** estas pruebas verifican las instrucciones que recibe Meta, **no** que Meta distinga correctamente
fotografías de dibujos. Eso requiere probar con imágenes reales autorizadas en staging.

## Despliegue

**Basta con reconstruir el backend.** Las instrucciones viven en el servidor; la APK, la web y Desktop no cambian.
