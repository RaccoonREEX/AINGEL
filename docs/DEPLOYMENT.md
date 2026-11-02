# Despliegue (2-11-2026)

Sustituye la versión que decía que no existía despliegue público.

## Estado

AINGEL 3.0 está desplegado en <https://aingel.mapatechstudio.com>.

**Comprobado de forma pasiva el 2-11-2026** (solo peticiones de lectura, sin cuentas ni datos):
- la web y `/api/health/` responden 200 por HTTPS con un certificado válido;
- la sesión anónima ya expone `territory_version` y `restricted_territories`, es decir, el código de acceso público
  con territorios.

**No comprobado:**
- qué commit exacto corre en el servidor;
- si incluye `screen_media` y la prioridad de expresiones, añadidas el 2-11-2026 en esta rama.

Este repositorio no despliega nada por sí mismo. El despliegue lo hace el operador en el VPS.

## Cómo se despliega

1. **Arquitectura y requisitos:** [`deploy/README.md`](../deploy/README.md) describe Docker Compose detrás del Caddy
   existente, la red interna y PostgreSQL y Redis solo por TLS.
2. **Despliegue coordinado:** [`docs/VPS_RECONCILIATION.md`](VPS_RECONCILIATION.md) cubre la inspección de solo
   lectura, las variables de producción, el respaldo con `pg_dump`, las migraciones (solo añaden), el reinicio solo
   del backend y la reversión.
3. **Cuotas:** las pruebas con Redis real se ejecutan aislado ([`docs/REDIS_REAL_VALIDATION.md`](REDIS_REAL_VALIDATION.md)),
   y la CI de GitHub también las ejecuta con un Redis desechable.

## Correcciones de imágenes incluidas en esta rama

| Imagen | Problema | Corrección |
|---|---|---|
| Backend | `manage.py` tenía permisos 600 y el usuario 10001 no podía leerlo | `chmod -R a+rX /app /web` antes de `USER 10001:10001` |
| Backend | Faltaban las huellas de las señas | Se copia `signFingerprints.json` a `/web/...` |
| Web | La imagen `nginx-unprivileged` (UID 101) no podía leer `default.conf`: HTTP 502 | `COPY --chmod=644`; un `RUN chmod` posterior falla porque se ejecuta como ese mismo usuario |

La web además ejecuta `nginx -t` durante la construcción, como el usuario de ejecución.

`deploy/tests/` y el trabajo `images` de la CI comprueban estas correcciones: construyen las dos imágenes, arrancan
la web y comprueban que el backend corre como 10001.

## Antes de desplegar esta rama

- **Respaldo:** respaldar la base de datos y conservar la etiqueta de la imagen anterior.
- **Construcción:** construir desde el commit fusionado.
- **Migraciones:** aplicar `assistance.0002` y `care.0010` si faltan.
- **Datos reales:** no copiar `.local/` ni archivos `.env` a una imagen. Mantener `AINGEL_FACE_RECOGNITION_ENABLED=0`
  y `AINGEL_VIDEO_REAL=0`.
- **Prueba de humo:**
  - HTTPS y WebSocket;
  - dos cuentas nuevas;
  - la declaración de territorio de una cuenta existente;
  - el consumo registrado.
