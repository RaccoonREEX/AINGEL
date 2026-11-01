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
- La imagen activa del VPS corresponde al hotfix de `main` más un parche de `care/consent.py` que restringe funcionalidades reales de pruebas a una cuenta y perfil concretos. Se ha preservado la imagen y una copia del código; se debe verificar su sustitución funcional por las reglas generales del PR, no copiar la excepción permanente.
- Se creó un `pg_dump` protegido y se comprobó que `pg_restore` puede leer el archivo completo. Esto **no equivale** a una restauración real verificada; esa prueba sigue pendiente.

## Pendiente antes de integrar o desplegar

- Probar migraciones y restauración en PostgreSQL aislado, sin datos personales de producción; comprobar clientes, usuarios nuevos, consentimiento y revocación en staging.
- Verificar que Desktop excluye **todas** sus ventanas con contenido sensible de las capturas, incluido el comportamiento cuando Windows no pueda aplicar la exclusión. La revisión anterior encontró que solo se excluye la ventana principal. El PR #12 no modifica esa parte; no se debe dar por corregida.
- Finalizar y verificar Android en un dispositivo, los flujos de Meta Standard y el procedimiento de reversión.
- Verificar el tratamiento efectivo del proveedor, las condiciones geográficas y las cuotas antes de abrir datos reales.

No se han fusionado PR ni se han aplicado migraciones o cambios de servicios en producción durante esta validación.
