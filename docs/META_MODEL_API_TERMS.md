# Condiciones de Meta Model API que aplican a AINGEL (verificado el 31-10-2026)

Fuentes oficiales, leídas directamente:
- [Condiciones del servicio de la API de modelos de Meta](https://dev.meta.ai/legal/terms-of-service), versión del 2
  de octubre de 2026, leída en español.
- [Política de designación de modelos y uso geográfico](https://dev.meta.ai/legal/geographic-use-policy), versión del
  12 de octubre de 2026.
- [Precios y límites](https://dev.meta.ai/docs/pricing-rate-limits).

Esto es un resumen técnico, no asesoría legal.

## Modalidades: Standard y Contributor (o «con descuento»)

| | Servicios Standard | Servicios Contributor o con descuento |
|---|---|---|
| Entrenamiento | Meta **no usa el contenido para entrenar** sus modelos (§5.1) | Meta puede usar el contenido para entrenar, desarrollar, evaluar y mejorar sus productos (§6.1) |
| Papel de Meta | Encargado del tratamiento o proveedor de servicios, según las Condiciones globales para encargados del tratamiento | — |
| Información personal | Permitida dentro de las condiciones | **«No debes enviar información delicada, confidencial o personal»** (§6.2) |
| Conservación | Según §4.4 (ver abajo) | La de §4.4, más la que corresponde a su uso para entrenamiento (§6.1) |

**La modalidad la determina el modelo, no la forma de pago.** Los créditos promocionales (§13.3) no cambian la
designación. Solo excluyen la indemnización por propiedad intelectual de §17.2.

## Designación de los modelos que usa AINGEL

| Función de AINGEL | Modelo usado en el código | Designación oficial |
|---|---|---|
| Conversación, visión, documentos, señas por cámara | `muse-spark-1.3` | **Standard** |
| Subtítulos en vivo, voz propia y audio del equipo | `muse-voice-transcribe-1.0` | **Standard**. Contributor no existe para Voice. |
| Buscar un objeto | `sam-3.1` | **Standard** |

Los modelos Contributor son `muse-spark-1.2-contributor` y `muse-spark-1.3-contributor`, y **AINGEL no los usa**.
`assistance/test_meta_modality.py` falla si alguno de ellos, o cualquier modelo que no sea Standard, aparece en el
código que construye peticiones.

## Conservación por parte de Meta (§4.4, aplica también a Standard)

Meta conserva el contenido y los datos de uso cuando es necesario:
1. para dar el servicio;
2. por ley;
3. para ejercer sus derechos según las condiciones;
4. si sus sistemas lo marcan por una posible infracción;
5. por seguridad, prevención de abusos y mejora de políticas.

Además, usa los **datos de uso**, como metadatos, recuentos de tokens y latencia, para mejorar la API (§4.2).
AINGEL **no promete retención cero**. La retención cero (ZDR) existe para Voice Transcribe, pero no está contratada
ni verificada.

## Obligaciones de AINGEL como integrador

- **Política de privacidad:** publicar una que describa con claridad qué se recopila y cómo se usa y se comparte
  (§6.2). El texto de los permisos y `docs/PUBLIC_ACCESS.md` lo cubren. La política pública del sitio debe
  enlazarlos.
- **Territorios restringidos:** no ofrecer el servicio a personas ubicadas en territorios restringidos (§3 de la
  política geográfica): Afganistán, Bielorrusia, Camboya, China (incluidos Hong Kong y Macao), Cuba, Eritrea,
  Etiopía, Haití, Irán, Irak, Libia, Myanmar, Nicaragua, Corea del Norte, Pakistán, Rusia, Somalia, Siria, Crimea,
  Donetsk y Luhansk, Venezuela y Sáhara Occidental. **Cómo lo aplica AINGEL:**
  - una autodeclaración obligatoria en el registro y para las cuentas existentes, con bloqueo en el servidor;
  - un control opcional por el país de la conexión.

  Detalles y límites en «Territorios restringidos» de `docs/PUBLIC_ACCESS.md`.
- **Disponibilidad por modelo (§2.2):** Muse Image no está disponible en India. AINGEL no usa Muse Image.
- **Política de uso aceptable** de Meta Model API: cumplirla.
- **Contenido generado con IA:** etiquetarlo cuando la ley lo exija. Las respuestas de AINGEL ya se marcan como
  generadas por IA.
