# Cuenta `prueba.persona` creada por error en producción (30-10-2026)

**Estado:** eliminada. Según el informe de la segunda auditoría de Astra, Astra la eliminó en producción con la
autorización del propietario, después de hacer una copia de seguridad y de verificar el resultado.

**Qué está verificado y qué no.**
- Esta eliminación **no la ha verificado** quien redacta este documento: no tiene acceso a producción. Es lo que
  informa Astra.
- Desde esta rama no se ha ejecutado ninguna eliminación ni ninguna otra operación sobre producción, y no debe
  volver a ejecutarse.
- Los pasos de abajo se conservan solo como registro del procedimiento.
- Los registros de acceso del proxy y de Daphne siguen su propia rotación; no consta que se hayan tocado.

## Qué pasó

Durante las pruebas de la rama `feat/consent-persona-video`, el APK de pruebas usó el servidor por defecto,
`https://aingel.mapatechstudio.com/`, en lugar del backend local de la rama. El commit `ee54c5b` migra las direcciones
locales guardadas a producción.

Desde el teléfono se hicieron estas peticiones, todas sin datos de salud, fotos ni audio:

1. `GET auth/session/`, anónima.
2. `POST auth/register/` con `username = prueba.persona`, una contraseña aleatoria de prueba (guardada solo en
   `.local/` de la rama, fuera de git) y los campos `adult` y `terms_version`. El código de producción ignora estos
   dos últimos.
3. La app nueva vio la cuenta sin declaración de mayoría de edad, porque el servidor antiguo no devuelve ese campo. Por
   eso mostró la pantalla de declaración y **no pidió perfiles ni ninguna otra cosa**.
4. `POST auth/logout/`: «Cerrar sesión».
5. `GET auth/session/`, anónima.

Hora aproximada: 30-10-2026, entre las 20:15 y las 20:25 (UTC-5).

## Qué registros pudo crear

Esto se dedujo del código de `origin/main` (`care/auth.py` en `75e05a8`). No se ha comprobado en el servidor.

| Dónde | Qué | Estado esperado |
|---|---|---|
| `auth_user` | 1 fila: `prueba.persona`, hash de contraseña, `date_joined`, `last_login`, sin staff ni superusuario | Existe |
| `django_session` | 1 fila al iniciar sesión (`login`) | Borrada por `logout()` |
| Redis | Contador de límite de acceso por IP (`auth:<ip>`) | Caducado (5 min) |
| Registros de acceso del proxy y de Daphne | Las líneas de las peticiones de arriba (ruta, hora, estado, IP) | Según su retención |
| `care_*`: perfil, miembros, rutinas, recuerdos, mensajes, auditoría, MFA, invitaciones | Nada: no hay código que los cree al registrarse y la app no los pidió | No existen |

No hay señales `post_save` ni `user_logged_in` en el backend que escriban más datos.

## 1. Comprobar sin modificar nada (solo lectura)

Desde el contenedor del backend de producción:

```bash
docker compose -f deploy/compose.yaml exec -T backend python manage.py shell -c "
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
u = get_user_model().objects.get(username='prueba.persona')
print('user', u.pk, u.date_joined, u.last_login, 'staff', u.is_staff, 'super', u.is_superuser)
live = [s.session_key[:6] for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == str(u.pk)]
print('sessions', len(live))
c = NestedObjects(using='default'); c.collect([u])
print('would delete:', c.nested(lambda o: f'{o._meta.label}:{o.pk}'))
print('protected (block deletion):', [f'{o._meta.label}:{o.pk}' for o in c.protected])
"
```

**Resultado esperado:**
- Una sola entrada `auth.User:<id>` en «would delete».
- `sessions 0`.
- Nada en «protected».

Si aparece cualquier otra cosa, **no borrar** y revisarlo primero.

## 2. Eliminar (solo con aprobación expresa del propietario)

Primero, una copia de seguridad, que se guarda fuera del repositorio:

```bash
docker compose -f deploy/compose.yaml exec -T db pg_dump -U aingel -Fc aingel > "aingel-$(date +%Y%m%d-%H%M%S).dump"
```

Después:

```bash
docker compose -f deploy/compose.yaml exec -T backend python manage.py shell -c "
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
with transaction.atomic():
    u = get_user_model().objects.select_for_update().get(username='prueba.persona', is_staff=False, is_superuser=False)
    c = NestedObjects(using='default'); c.collect([u])
    others = [o for o in c.data if o._meta.label not in ('auth.User',)]
    assert not c.protected and not others, (others, c.protected)
    for s in Session.objects.all():
        if s.get_decoded().get('_auth_user_id') == str(u.pk): s.delete()
    u.delete()
    print('deleted prueba.persona')
"
```

**Alternativa reversible:** desactivar la cuenta en lugar de borrarla:

```bash
docker compose -f deploy/compose.yaml exec -T backend python manage.py shell -c "from django.contrib.auth import get_user_model as g; print(g().objects.filter(username='prueba.persona').update(is_active=False))"
```

Las líneas de los registros de acceso se eliminan por su propia rotación. Si hay que borrarlas antes, es una tarea de
infraestructura (Astra).
