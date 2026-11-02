# Descripción de personas: primero la expresión aparente (2-11-2026)

Rama `feat/vision-expressions-first`, sobre `fix/desktop-screen-media-focus` (`7b375a3`). No está fusionada ni
desplegada.

## Problema

Ante el retrato de un hombre que aparentaba tristeza, AINGEL describió la forma del rostro, el cabello y la barba,
pero no la expresión.

**Causa:** la regla compartida `PEOPLE` prohibía «inferir emociones» de cualquier forma, y la tarea `face` pedía
recorrer los rasgos «parte por parte».

## Cambio: en las instrucciones que recibe Meta, no en un filtro de la respuesta

**Nueva política compartida `expressions` («PEOPLE AND EXPRESSIONS»)** en `backend/assistance/persona.py`. Cuando el
contenido principal es una persona, un rostro, un retrato o una selfie, ordena:

1. **La expresión aparente y el lenguaje corporal,** dichos como apariencia: «Parece triste», «Su expresión transmite
   alegría».
   - Un rostro neutro se describe como neutro.
   - Una expresión ambigua se describe como tal, con sus lecturas posibles.
2. **Las señales visibles que la justifican:** cejas, apertura de los ojos, boca, labios, líneas de expresión, mirada,
   inclinación de la cabeza y postura. Solo las que se ven.
3. **La apariencia:** cabello, rasgos, tono de piel visible, ropa, accesorios y postura. La edad aproximada solo
   cuando sea útil y con cautela.
4. **El contexto,** cuando ayuda: fondo, iluminación, posición, objetos cercanos e interacciones.

Además:
- **Varias personas:** cada una por separado, según su posición, sin mezclar expresiones.
- **Pregunta concreta** (sobre el cabello o la ropa, por ejemplo): se responde primero.
- **Niveles:** la expresión va primero en Breve, Estándar, Detallado y Profundo; cambia solo el alcance.
- **Límites:**
  - una expresión no prueba lo que la persona siente;
  - nunca se afirman emociones confirmadas, estados mentales, intenciones, diagnósticos ni personalidad;
  - una foto o un fotograma es un solo momento.
- **Tono:** natural, sin encabezados como «Emoción principal» ni introducciones como «Procederé a analizar».

**Reglas que se ajustan:**
- **`people`:** sigue prohibiendo identificar a desconocidos e inferir identidad, salud o intenciones. Ahora permite
  describir una expresión solo como apariencia.
- **`faces`:** empieza por la expresión. Mantiene sin cambios las prohibiciones de diagnósticos, origen étnico,
  atributos sensibles e identidad por parecido.

**Dónde se aplica:**

| Flujo | Cómo |
|---|---|
| Visión (`vision/`: web, Android, Desktop) | Tareas `general`, `face` y `screen_media` |
| Visión profunda | Las dos notas intermedias anotan primero la expresión y sus señales finas; la síntesis empieza por ella |
| Preguntas de seguimiento | Mantienen las mismas reglas |
| «Ver y describir» de Android (`scene/`) | `VISION_RULES` incluye la política; si hay una persona, la primera frase da su expresión aparente (respuesta breve, tres frases) |
| Vigilancia por vídeo (`video.py`) | Recibe las mismas reglas mediante `VISION_RULES` |

- **Preguntas reconocidas como sobre una persona:** «¿Cómo se ve la persona que tengo delante?», «¿Qué expresión
  tiene su rostro?», «Descríbeme a detalle su apariencia» y «¿Qué señales ves en su expresión?».
- **`screen_media` se mantiene:** una persona en un vídeo o una foto en pantalla se describe por su expresión, sin
  narrar Windows, el navegador ni el reproductor.
- **Lo que no cambia:**
  - el reconocimiento facial sigue desactivado; `AINGEL_FACE_RECOGNITION_ENABLED` no se tocó;
  - el modelo sigue siendo `muse-spark-1.3` Standard;
  - los niveles, el esfuerzo de razonamiento y los presupuestos de tokens son los mismos.

## Pruebas

`backend/assistance/test_expressions.py` usa las rutas reales y simula a Meta en el cliente HTTP. Comprueba **qué
instrucciones recibe Meta** en los diez casos obligatorios:
1. Tristeza antes que la anatomía.
2. Alegría y sus señales.
3. Expresión ambigua.
4. Expresión neutra.
5. Varias personas.
6. Pregunta concreta.
7. Modo Profundo en notas, síntesis y seguimiento.
8. `screen_media` sin interfaz.
9. Sin diagnósticos ni estados confirmados.
10. Consentimiento, sesión cifrada, cuota y revocación.

Además cubre «Ver y describir» de Android y que el reconocimiento facial sigue apagado.

Trece de las quince pruebas fallan con el código anterior. Las otras dos protegen comportamientos que ya existían.

**Estas pruebas no miden la precisión con la que Meta lee expresiones.** Eso requiere una evaluación real con fotos
consentidas.

## Despliegue

**Basta con reconstruir y desplegar el backend.** Las instrucciones viven en el servidor, así que la APK, la web y
AINGEL Desktop no necesitan actualizarse.
