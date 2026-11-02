# Reconciliación controlada del VPS (para Astra)

**Situación:** el Git del VPS está en `25d964c`, pero la imagen Docker activa contiene cambios adicionales. Nada de
este procedimiento modifica producción hasta el paso 6, que se hace solo después de la revisión independiente del PR
#12. **No borrar volúmenes ni bases de datos.**

## 1. Inspeccionar lo que se ejecuta (solo lectura)

```bash
docker compose -f deploy/compose.yaml ps
docker inspect --format '{{.Image}} {{.Created}}' <contenedor-backend>
mkdir -p /tmp/aingel-running && docker cp <contenedor-backend>:/app /tmp/aingel-running/
docker exec <contenedor-backend> env | grep -E '^AINGEL_|^DJANGO_DEBUG' | sed -E 's/(KEY|PASSWORD|SECRET|TOKEN)=.*/\1=<oculto>/'
docker exec <contenedor-backend> python manage.py showmigrations care assistance
```

## 2. Comparar con el repositorio

```bash
git -C /ruta/repo fetch origin && git -C /ruta/repo worktree add /tmp/aingel-pr12 origin/feat/aingel3-public-access
diff -ru --exclude=__pycache__ /tmp/aingel-pr12/backend /tmp/aingel-running/app > /tmp/aingel-running.diff
```

## 3. Clasificar cada diferencia

| Tipo | Qué hacer |
|---|---|
| Corrección válida, como la de reconocimiento facial (#3), la de captura de Android (#4) o la de señas (#5) | Comprobar que ya está en el PR. Si falta, enviarla como commit. |
| Excepción temporal por usuario, como `AINGEL_META_ALLOWED_USER_IDS=3` o el código que habilitaba una cuenta concreta | **Quitar.** El PR #12 lo sustituye por el acceso público con consentimiento. |
| Prueba privada (`AINGEL_PRIVATE_OWN_MEDIA_TEST=1`) | Pasar a `0` en producción pública. Se puede mantener en un entorno de pruebas aparte. |
| Valores antiguos de cuota (10 por minuto y 100 por día, globales) | Subirlos (ver `docs/PUBLIC_ACCESS.md`) y añadir los límites por cuenta |

## 4. Probar fuera de producción

1. Construir la imagen desde la rama fusionada, en un entorno de staging con Postgres y Redis propios, nunca los de
   producción.
2. Ejecutar:
   - `python manage.py test`;
   - las 7 pruebas de Redis real, en un contenedor aislado sin clave de Meta ni base de producción, según
     `docs/REDIS_REAL_VALIDATION.md`. **Es obligatorio antes de activar el acceso público multiusuario.**
   - `python manage.py migrate --plan`.
3. En la web y la APK contra staging, repetir:
   - usuario nuevo;
   - permisos parciales;
   - revocación;
   - edad;
   - dos cuentas a la vez.

## 5. Variables de producción objetivo

```
AINGEL_AI_MODE=meta
AINGEL_REAL_DATA=1
AINGEL_SYNTHETIC_TESTS_ONLY=0
AINGEL_PRIVATE_OWN_MEDIA_TEST=0
AINGEL_META_ACCESS=public
# sin AINGEL_META_ALLOWED_USER_IDS
AINGEL_FACE_RECOGNITION_ENABLED=0
AINGEL_VIDEO_REAL=0
AINGEL_META_LIMIT_PER_MINUTE=60
AINGEL_META_LIMIT_PER_DAY=5000
AINGEL_META_USER_LIMIT_PER_MINUTE=12
AINGEL_META_USER_LIMIT_PER_DAY=300
AINGEL_META_USER_DAILY_USD=2.00   # opcional; ajustar a los créditos
AINGEL_META_BUDGET_USD=140        # opcional; deja margen sobre los 150 USD
# AINGEL_GEO_COUNTRY_HEADER=X-AINGEL-Country   # solo si Caddy añade el país desde una fuente GeoIP de confianza
```

Los topes monetarios son una estimación parcial; la referencia es la consola de facturación de Meta (ver
`docs/PUBLIC_ACCESS.md`, «Registro de consumo»). Tras el despliegue, **todas las cuentas existentes responden una vez
a la pregunta de territorio** en la web o en Android antes de volver a usar Meta.

## 6. Despliegue, coordinado y después de la revisión

1. Respaldar la base de datos con `pg_dump` y guardar la etiqueta de la imagen actual.
2. Fusionar los PR en orden: #4 → #5 → #6 → #7 → #8 → #9 → #10 → #11 → #12.
3. Construir la imagen nueva, reproducible y etiquetada con el commit.
4. Ejecutar `migrate`. Migraciones nuevas desde `25d964c`:
   - `assistance.0001_initial`: consumo de Meta;
   - `care.0009_sign_feedback`: correcciones de señas;
   - `assistance.0002_metausage_billed_units`: imágenes, segundos de audio y búsquedas facturadas;
   - `care.0010_account_territory`: respuesta sobre territorios restringidos.

   **Todas solo añaden; ninguna borra datos.**
5. Cambiar las variables del paso 5 y reiniciar solo el servicio backend; los demás servicios del VPS no se tocan.
6. Hacer una prueba de humo con una cuenta nueva.

## 7. Reversión

1. Volver a la etiqueta de imagen anterior y a las variables anteriores.
2. **Base de datos:** las tablas nuevas pueden quedar, porque el código anterior no las usa. Si hace falta, ejecutar
   `migrate care 0008` y `migrate assistance zero`, después de exportar las correcciones de señas.
   Para revertir solo este PR basta con `migrate care 0009` y `migrate assistance 0001`.
3. **Sesiones en caché:** caducan solas (15 min y 2 h).
