# Validación de cuotas con Redis real: pendiente, a cargo de Astra en el VPS

**Estado (31-10-2026):** en local, `manage.py test` ejecuta 297 pruebas: **290 correctas y 7 omitidas**. Las 7 omitidas necesitan un
Redis real desechable. La auditoría de código del PR #12 se aprueba con ellas pendientes.

**Condición obligatoria:** deben pasar en un entorno aislado **antes de activar el acceso público multiusuario en
producción**, es decir, antes de `AINGEL_META_ACCESS=public` con `AINGEL_REAL_DATA=1`.

No se pueden borrar ni debilitar estas pruebas ni los controles de cuota para que pasen. Si alguna falla, se corrige
el código.

## Las 7 pruebas (`backend/assistance/test_meta_quota_redis.py`, clase `RealRedisTests`)

| Prueba | Qué demuestra |
|---|---|
| `test_global_minute_limit` | Con 3 llamadas por minuto, la cuarta se rechaza: `meta_quota_exceeded` |
| `test_global_day_limit` | Con 5 llamadas por día, la sexta se rechaza |
| `test_concurrent_reservations_never_exceed_the_limit` | Con 40 hilos simultáneos y un límite de 10, se aceptan exactamente 10. El script Lua es atómico. |
| `test_counters_expire_and_the_window_slides` | Los contadores caducan (TTL de 61 s y de 1 día), y las entradas de más de un minuto dejan de contar |
| `test_per_account_limits_are_per_account` | Una cuenta que supera su límite de conversación recibe 429; otra cuenta no se ve afectada |
| `test_meta_quota_per_account_on_real_redis` | Con varias cuentas, cada una tiene sus contadores y el límite de plataforma es común: `meta_account_quota_exceeded` y luego `meta_quota_exceeded` |
| `test_losing_redis_mid_run_keeps_failing_closed` | Si Redis cae a mitad de ejecución, se rechaza (`meta_quota_unavailable`) y no se cuenta nada de más |

## Por qué no consumen créditos ni tocan datos de usuarios

- **Meta:** ninguna prueba llama a Meta.
  - Solo reservan cuota en Redis. La de conversación fuerza `AINGEL_AI_MODE=mock`.
  - Aun así, el procedimiento de abajo arranca el contenedor **sin la clave de Meta** y en modo `mock`, como segunda
    barrera.
- **Base de datos:** sin `AINGEL_ENV=production`, Django usa SQLite, y la base de pruebas se crea **en memoria** y se
  descarta al terminar.
  - El procedimiento no carga `env_file`, así que el contenedor no conoce la base de producción.
  - **No ejecutar las pruebas dentro del contenedor de producción.** Ahí se usaría Postgres de producción para crear
    la base de pruebas.
- **Redis:** se usa un Redis **nuevo y desechable**, nunca `redis` ni `quota_redis` de producción.
  - Además, cada prueba usa un prefijo aleatorio, borra solo sus claves y nunca ejecuta `FLUSHDB`.
- **Límites:** las pruebas los fijan bajos dentro del propio proceso. No cambian la configuración del servidor.

## Procedimiento aislado (no modifica producción ni borra volúmenes)

Se ejecuta en el VPS, con la imagen del backend construida desde la rama revisada.

```bash
docker network create aingel-redis-test
docker run -d --rm --name aingel-redis-test --network aingel-redis-test redis:7-alpine
docker run --rm --network aingel-redis-test \
  -e AINGEL_AI_MODE=mock -e AINGEL_SYNTHETIC_TESTS_ONLY=1 -e AINGEL_REAL_DATA=0 \
  -e DJANGO_SECRET_KEY=solo-pruebas \
  -e AINGEL_TEST_REDIS_URL=redis://aingel-redis-test:6379/15 -e AINGEL_TEST_REDIS_ISOLATED=1 \
  <imagen-backend-de-la-rama> python manage.py test assistance.test_meta_quota_redis -v 2
docker stop aingel-redis-test && docker network rm aingel-redis-test
```

En el comando de prueba no aparecen `--env-file`, `MODEL_API_KEY`, `AINGEL_ENV=production`, ni las redes `data` o
`app` de compose.

**Resultado esperado:** `OK`, sin pruebas omitidas en ese módulo; las 7 de `RealRedisTests` aparecen como `ok`.

Opcionalmente, la suite completa en el mismo contenedor debe dar **297 correctas y 0 omitidas**:
`python manage.py test`.

## Registro del resultado

Astra anota en el PR #12, o en el issue de despliegue:
- el commit probado;
- la versión de Redis;
- la salida de `-v 2`.

Hasta entonces, el acceso público multiusuario sigue **desactivado en producción**.
