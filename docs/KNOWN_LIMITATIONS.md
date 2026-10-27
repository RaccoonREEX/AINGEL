# Límites actuales — 2026-10-26

- Esta entrega es una web local con backend funcional. No hay APK ni despliegue público todavía.
- 55 pruebas pasan y tres llamadas Meta reales se han verificado con material sintético. No equivalen a una evaluación general de precisión ni a un producto clínico certificado.
- Los datos reales siguen fuera de los flujos Meta hasta aclarar el uso de contenido asociado a créditos gratuitos. La casilla de material sintético es una declaración del usuario, no un detector de datos sensibles.
- Preguntar usa herramientas estructuradas locales para buscar recuerdos, rutinas y mensajes; aún no hay conversación libre con selección autónoma de herramientas por un agente.
- Rutinas: los avisos requieren la pantalla Hoy abierta. No hay alarmas de fondo, push, llamadas automáticas ni verificación de ingesta de medicinas.
- Memorias: observaciones comunicadas por el usuario, búsqueda exacta por objeto y retención de siete días. No hay extracción automática de sucesos ni vídeo continuo.
- Reconocimiento facial local experimental: consentimiento individual, un registro por cuidador, máximo cuatro en el círculo, plantillas cifradas por treinta días. Falta medir precisión con familiares reales, falsos positivos, sesgos e iluminación; no hay liveness. No sirve para confirmar identidad ni autenticar.
- Google Authenticator: flujo TOTP/QR/recuperación/replay validado en pruebas automatizadas. Falta probar el escaneo con un teléfono real. No hay recuperación administrativa ni restablecimiento por correo.
- Subtítulos: relay real verificado con WAV sintético. El micrófono del navegador y la lectura de voz necesitan prueba manual en los dispositivos objetivo. AudioContext debe soportar 24 kHz; ante incompatibilidad, se muestra error.
- Solo hay interfaz implementada en español e inglés. Otros idiomas están auditados/planificados; Android TTS, RTL completo y TalkBack no están validados.
- SQLite, HTTP loopback y límites por proceso son configuración de pruebas. La base local de perfiles/rutinas contiene texto sin cifrado de campo; solo los secretos TOTP y plantillas faciales tienen cifrado de aplicación. No exponer a Internet.
- El borrado físico de registros vencidos se ejecuta al arrancar localmente o mediante el comando de limpieza. Programar y verificar limpieza diaria, respaldo seguro y restauración antes de producción.
- VizWiz: treinta anotaciones preparadas para evaluación, sin fotos, entrenamiento ni precisión publicada. LSEC, corpus clínicos y recursos restringidos siguen sin incorporarse.
- Repositorio aún local, sin publicación, licencia propia por decidir y revisión completa de terceros pendiente. Track de inscripción no verificado; no se ha enviado ninguna candidatura ni aceptado términos nuevos.
