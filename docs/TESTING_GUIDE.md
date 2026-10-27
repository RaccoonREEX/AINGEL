# AINGEL · guía de pruebas locales

Esta versión permite probar la web y el backend. No es la APK ni una versión publicada. Usa datos sintéticos; las restricciones de privacidad de los créditos Meta siguen pendientes para contenido real.

## Entrar

1. Abre `http://127.0.0.1:5173/`. Si no responde, ejecuta `Start-Aingel.ps1` desde la raíz del proyecto.
2. Consulta las contraseñas de prueba en `.local/demo-accounts.json`; no las publiques. `aingel.demo` es el principal, `familia.demo` su cuidador y `externo.demo` no está vinculado.
3. Alternativamente, crea cuentas propias desde la interfaz. La cuenta principal crea su perfil; la cuenta cuidadora acepta una invitación.

## Círculo de 1–4 cuidadores

Desde el principal, entra en Círculo de cuidado. Invita el nombre de usuario de una cuenta existente, indica su relación y elige si puede configurar y si puede consultar recuerdos. Comparte el código privado con esa persona. Cierra sesión y acepta el código desde la cuenta destinataria. No hay envío de email.

Comprueba que el cuidador ve el perfil después de aceptar, que el quinto puesto se rechaza y que los permisos de recuerdos son independientes de configuración. El principal puede cambiar permisos, cancelar invitaciones y revocar miembros. El familiar puede salir. Quitar al último cuidador es posible y devuelve el perfil a borrador; nunca se bloquea una revocación por el mínimo de uno.

## Personalización y horarios

Desde familia.demo, guarda preferencias de apoyo, alergias sintéticas, zona horaria y accesibilidad. Añade o edita rutinas de sueño, medicinas, baño, comidas, agua o citas. Comprueba los días y el estado activo/pausado. Vuelve al principal y verifica los cambios.

Una confirmación manual muestra quién la registró y puede retirarse. Un recordatorio de medicina no es una prescripción ni prueba de ingesta. Los avisos solo aparecen si Hoy está abierto; no hay notificaciones de fondo.

## Memoria y mensajes

Desde el principal, guarda una observación sintética con objeto, ubicación, fecha y confirmación explícita. Una foto de evidencia es opcional y privada. Busca ese objeto en Preguntar y verifica ubicación, autor y fecha; busca otro que no exista y comprueba la respuesta sin evidencia. Elimina el recuerdo y comprueba que deja de recuperarse.

familia.demo no tiene acceso a recuerdos inicialmente. Puede enviar mensajes y configurar rutinas. Comprueba que los mensajes muestran texto original, autor y fecha. El historial del principal registra accesos/cambios sin copiar contenido sensible.

## Meta: visión, objetos y subtítulos

En Ver, pulsa Usar imagen sintética incluida y Describir imagen. El resultado debe indicar inferencia real, modelo y latencia. Después busca `círculo rojo` o `cuadrado azul` para probar SAM: verifica recuadro, máscara y dirección dentro de la imagen. Un objeto ausente debe devolver cero coincidencias. El modo mock nunca debe presentarse como detección real.

En Escuchar, lee la advertencia y confirma que leerás una frase de prueba sin datos personales. Inicia subtítulos y concede el micrófono tú mismo. Lee una frase breve, revisa los parciales/finales y detén el micrófono. No hay grabación. Se admite una sesión por cuenta por hasta 10 minutos. La prueba automatizada ya usó una voz sintética a través del relay, sin abrir el micrófono.

## Google Authenticator

En Seguridad, introduce la contraseña actual, genera el QR y escanéalo con Google Authenticator u otra aplicación TOTP. Introduce un código para activar. Guarda los ocho códigos de recuperación en privado antes de cerrar; cada uno sirve una sola vez. Cierra sesión, verifica que la contraseña sola no basta y completa el segundo factor.

Un código ya usado se rechaza, aunque siga visible durante su ventana de 30 segundos: espera el siguiente. Para desactivar se requieren contraseña y código válido/recuperación. Cada familiar configura su propia cuenta. No hay recuperación administrativa ni email de restablecimiento implementados; no pierdas el Authenticator y los códigos a la vez.

## Rostros: prueba experimental separada

No hay fotos familiares registradas por defecto. El principal debe habilitar el apoyo con su contraseña y consentimiento. Cada familiar adulto entra con su propia cuenta y registra **su propia foto**, confirmando que es él y que autoriza este uso. El principal no puede cargar una foto para consentir por otra persona.

Luego, el principal puede analizar localmente una foto autorizada. El resultado es “podría ser”, o ninguna coincidencia clara. Puede leerlo en voz alta. Comprueba la eliminación al retirar consentimiento, revocar al cuidador o desactivar la función. Las plantillas cifradas vencen a los 30 días; las fotos no se conservan ni se envían a Meta.

La precisión positiva todavía no está validada con familiares reales. No uses el resultado para decisiones sensibles, acceso, seguridad o confirmación de identidad. No hay liveness ni reconocimiento de personas fuera del círculo.

## Comprobaciones técnicas

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py test
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
Set-Location ..\web
npm run build
```

La configuración es local. No expongas estos servidores a Internet. Los próximos hitos son validación con usuarios, Android, permisos/privacidad de datos reales, despliegue HTTPS y cierre de brechas de accesibilidad.

## APK nativo

[Guía Android y conexión USB para la última fase](ANDROID_TESTING.md). El celular Samsung ya se conectó y pasó una prueba instrumentada de sesión y MFA contra el backend. Faltan cámara, micrófono, escaneo real de Authenticator y TalkBack.

## Comunicación y fuentes locales

1. En Personalizar, el principal o familiar con permiso configura nombre preferido, trato, ritmo y presentación. La opción LSEC/ASL guarda la preferencia, pero no activa traducción ni avatar.
2. En Preguntar, comprueba el saludo, el botón de apoyo y el paso por las rutinas o mensajes uno a uno. La respuesta es local y no ejecuta llamadas automáticas.
3. Busca un tema general en MedlinePlus. Comprueba título, fuente, fecha y enlace. Si el índice no está instalado, ejecuta `python backend/scripts/import_medlineplus.py` usando el entorno virtual. El resumen es información general y no cambia el plan de cuidados.
4. En Escuchar, comprueba el aviso de que la traducción en señas aún no está disponible. La transcripción Meta de esta fase usa exclusivamente voz sintética.
