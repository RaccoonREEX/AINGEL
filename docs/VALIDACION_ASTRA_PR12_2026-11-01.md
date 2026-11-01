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

## Pendiente antes de integrar o desplegar

- Probar migraciones y restauración en PostgreSQL aislado, sin datos personales de producción; comprobar clientes, usuarios nuevos, consentimiento y revocación en staging.
- Desktop: la revisión anterior encontró que solo se excluía la ventana principal. La rama de validación añade una comprobación antes de ambas rutas de captura: excluye todas las ventanas visibles de la aplicación y rechaza la captura si Windows no puede proteger alguna. Las comprobaciones locales consultan la afinidad de captura de dos ventanas reales y el rechazo de un identificador inválido. La prueba integral de capturas y sesiones en staging aún falta.
- Finalizar y verificar Android en un dispositivo, los flujos de Meta Standard y el procedimiento de reversión.
- Verificar el tratamiento efectivo del proveedor, las condiciones geográficas y las cuotas antes de abrir datos reales.

No se han fusionado PR ni se han aplicado migraciones o cambios de servicios en producción durante esta validación.
