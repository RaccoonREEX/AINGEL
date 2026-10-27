# Privacidad de la versión local

Los perfiles, horarios, alergias comunicadas y mensajes se guardan en la base local. Este flujo de configuración no los envía a Meta. La base SQLite no tiene cifrado de campos de salud: es una configuración de desarrollo que no debe exponerse a Internet.

Las memorias requieren confirmación del usuario principal. Sus fotos opcionales se normalizan sin metadatos, se guardan en almacenamiento privado y se sirven solo tras comprobar permisos. Se pueden borrar; la retención es siete días. Se conserva procedencia y se distingue observación humana de ubicación actual.

La función facial está desactivada inicialmente. El principal debe optar por ella y cada familiar adulto registra únicamente su propia foto con consentimiento. Se descarta la foto y se conserva una plantilla cifrada por treinta días. Comparación local, sin envío a Meta. Revocar miembro, retirar consentimiento o desactivar la función elimina las plantillas correspondientes. Precisión real y requisitos regulatorios siguen pendientes de evaluación.

Los secretos TOTP están cifrados; los códigos de recuperación se conservan como hashes de un solo uso. Las claves locales y credenciales de demostración están fuera de Git. El historial de accesos no copia salud, imágenes ni texto de memorias.

Visión/SAM y subtítulos usan Meta mediante el backend, con indicadores y afirmación de material sintético. El aviso de uso de contenido asociado a créditos gratuitos sigue sin reconciliarse para datos personales: no usar fotos o audio privados en estos flujos todavía. La función facial local es distinta y no utiliza Meta. Los subtítulos no se guardan en el relay.

La limpieza física de vencidos se ejecuta al arrancar o con el comando de retención; la planificación diaria y los respaldos seguros deben completarse antes de producción. Cámara/micrófono no se activan en silencio; la grabación se inicia por acción del usuario y se detiene al salir. No hay vigilancia continua ni funciones de emergencia automáticas.
