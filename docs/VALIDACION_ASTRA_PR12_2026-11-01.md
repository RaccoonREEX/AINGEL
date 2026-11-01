# Validación independiente del PR #12

Estado: **en curso; no aprobado para despliegue**. Versión candidata: `5011033e966a7b297889cd8a419314a5ef18d1a3`.

## Redis real aislado

Se construyó una imagen del backend desde el commit indicado y se ejecutó `assistance.test_meta_quota_redis -v 2` contra Redis **7.4.12**, en una red Docker interna distinta de las redes de producción. El contenedor de prueba usó SQLite en memoria, modo `mock`, `AINGEL_REAL_DATA=0` y ninguna clave de Meta ni archivo de entorno de producción.

Resultado: **11 pruebas aprobadas, 0 omitidas**, incluidas las 7 de `RealRedisTests`: límites globales por minuto y día; concurrencia; caducidad; aislamiento por usuario; combinación de límites por cuenta y global; y fallo cerrado cuando Redis deja de responder. No hubo solicitudes a Meta ni conexión a PostgreSQL o Redis de producción.

El primer intento no ejecutó pruebas porque los permisos de la copia privada del código impidieron leer `manage.py` dentro de la imagen. Se corrigieron los permisos de lectura del árbol aislado, se reconstruyó la imagen y se ejecutó toda la batería sin reducirla.

## Otras comprobaciones

- Backend local: 321 pruebas ejecutadas; correctas, con 7 omitidas para Redis real. Las siete se ejecutaron aparte como se describe arriba.
- Web: compilación y nueve scripts de pruebas correctos.
- Desktop: 98 comprobaciones locales correctas; pruebas contra backend omitidas al no haberse configurado uno de prueba.
- Android del candidato `5011033`: compilación y 85 pruebas unitarias correctas; lint con 0 errores y 69 avisos. No se verificó en un dispositivo. Java necesitó un directorio temporal local corto para poder abrir su conexión de loopback.
- La imagen activa del VPS corresponde al hotfix de `main` más un parche de `care/consent.py` que restringe funcionalidades reales de pruebas a una cuenta y perfil concretos. Se ha preservado la imagen y una copia del código; se debe verificar su sustitución funcional por las reglas generales del PR, no copiar la excepción permanente.
- Se creó un `pg_dump` protegido y se comprobó que `pg_restore` puede leer el archivo completo. Esto **no equivale** a una restauración real verificada; esa prueba sigue pendiente.
- PostgreSQL 16 aislado: se preparó el esquema antiguo `care.0008` con una cuenta y un consentimiento ficticios; se verificó el plan y se aplicaron `assistance.0001`, `assistance.0002`, `care.0009` y `care.0010`. La cuenta y el consentimiento se conservaron y no se inventó una declaración territorial. Un respaldo sintético se restauró en otra base aislada; la imagen anterior pudo leer esos registros y crear un perfil ficticio sobre el esquema nuevo. Esta es una prueba limitada, no la restauración del respaldo de producción ni una prueba completa de reversión.
- Teléfono Samsung SM-F721B: una variante de pruebas con identificador distinto pasó el flujo instrumentado de registro, perfil propio, datos ficticios, inicio y cierre de sesión y MFA contra un backend local; una prueba separada pasó sesión anónima y CSRF sobre el HTTPS público. La primera ejecución del test falló porque no indicaba `for_self`; se corrigió el test para que use la misma declaración explícita que la interfaz. No se sustituyó la aplicación principal instalada.
- Con el backend candidato, PostgreSQL y Redis temporales y la clave existente del servidor, varias cuentas ficticias accedieron mediante registro y consentimiento ordinarios. La conversación y una imagen generada de prueba respondieron mediante `muse-spark-1.3`; una negativa de fotografías y una revocación de conversación bloquearon solicitudes posteriores. La configuración de staging usó límites de 5 llamadas por minuto y 10 por día, sin redes de bases de producción. Solo se enviaron ejemplos ficticios.
- Una solicitud de visión profunda no completó la síntesis: el límite global deliberadamente bajo de staging devolvió `meta_quota_exceeded` tras iniciar las llamadas previas. Es una protección de cuota esperada con ese límite; no demuestra que el flujo profundo completo funcione. No se elevó ni se eludió el límite para hacer pasar la prueba.
- La clave del archivo local de escritorio recibió HTTP 401 del proveedor. La clave ya configurada en el VPS sí funcionó en la prueba ficticia aislada; no se mostraron claves.

## Pendiente antes de integrar o desplegar

- Probar migraciones y restauración en PostgreSQL aislado, sin datos personales de producción; comprobar clientes, usuarios nuevos, consentimiento y revocación en staging.
- Desktop: la revisión anterior encontró que solo se excluía la ventana principal. La rama de validación añade una comprobación antes de ambas rutas de captura: excluye todas las ventanas visibles de la aplicación y rechaza la captura si Windows no puede proteger alguna. Las comprobaciones locales consultan la afinidad de captura de dos ventanas reales y el rechazo de un identificador inválido. La prueba integral de capturas y sesiones en staging aún falta.
- Finalizar y verificar Android en un dispositivo, los flujos de Meta Standard y el procedimiento de reversión.
- Verificar el tratamiento efectivo del proveedor, las condiciones geográficas y las cuotas antes de abrir datos reales.

No se han fusionado PR ni se han aplicado migraciones o cambios de servicios en producción durante esta validación.
