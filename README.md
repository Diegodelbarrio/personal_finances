# FinOrbit - Finanzas Personales

Aplicacion Django para gestion de finanzas, inversiones, cuentas bancarias y reportes anuales por usuario.

## Estado del proyecto

- Multiusuario con autenticacion (`django-allauth`).
- Aislamiento de datos por usuario en modelos y vistas.
- Preparado para despliegue con `gunicorn` y static files via `whitenoise`.
- Configuracion de seguridad por variables de entorno.

## Requisitos

- Python 3.9+
- PostgreSQL (recomendado en produccion)

## Instalacion local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tus valores reales (clave secreta y base de datos).

## Comandos de arranque

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

App local:

- `http://127.0.0.1:8000/accounts/signup/`
- `http://127.0.0.1:8000/accounts/login/`

## Variables de entorno importantes

- `SECRET_KEY`: obligatoria en produccion.
- `DEBUG`: `False` en produccion.
- `ALLOWED_HOSTS`: hosts permitidos separados por coma.
- `CSRF_TRUSTED_ORIGINS`: orígenes CSRF permitidos separados por coma.
- `DATABASE_URL`: conexion completa recomendada para cloud.
- `DB_*`: fallback si no usas `DATABASE_URL`.
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`.

## Bank sync experiment

This branch includes an Open Banking sync spike for account balances. It keeps the
manual CSV flow and adds an optional provider flow that writes into the existing
`BankAccount` and `AccountBalanceSnapshot` models.

For local testing without real bank data:

```bash
BANK_SYNC_ENABLED=True
BANK_SYNC_PROVIDER=mock
```

Then open:

- `http://127.0.0.1:8000/holdings/bank-sync/`

The mock provider creates sample accounts and balance snapshots. No bank
credentials are needed.

For Yapily sandbox testing, create provider credentials in the Yapily Console
and set them only in your local `.env` or production environment:

```bash
BANK_SYNC_ENABLED=True
BANK_SYNC_PROVIDER=yapily
BANK_SYNC_COUNTRY_CODE=ES
YAPILY_APPLICATION_ID=...
YAPILY_APPLICATION_SECRET=...
YAPILY_BASE_URL=https://api.yapily.com
```

Use `modelo-sandbox` as the institution ID for the first sandbox connection.
To connect a real account, first register the real bank/institution for the
Yapily application in Yapily Console. The bank sync page will list institutions
that the Yapily API returns for this application and country. If your bank is
not listed, it is not available to this application yet; activate/register it in
Yapily Console or contact Yapily for live banking data access.

Do not paste personal bank credentials, provider secrets, access tokens, or
refresh tokens into chat or commit them to git. The bank login happens on the
provider consent page, not inside FinOrbit.

To sync linked connections from the terminal:

```bash
python manage.py sync_bank_balances --user your-username
python manage.py sync_bank_balances --all-users
```

## Configuracion profesional de email

La app ya queda preparada para dos canales:

- **Transaccional**: verificacion de email, reset/cambio de contrasena, alertas de cuenta.
- **Marketing**: newsletters y envios masivos desacoplados del canal transaccional.

### 1. Recomendado para produccion

Define SMTP real por variables de entorno:

- `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS` (normalmente `True`)
- `EMAIL_TRANSACTIONAL_FROM_EMAIL`
- `EMAIL_TRANSACTIONAL_REPLY_TO`
- `NEW_USER_NOTIFICATION_ENABLED`: activa el aviso transaccional cuando se crea un usuario nuevo.
- `NEW_USER_NOTIFICATION_RECIPIENTS`: emails destino separados por coma para recibir el aviso.
- `NEW_USER_WELCOME_EMAIL_ENABLED`: activa el correo de bienvenida al email del usuario registrado.

Para separar newsletters del trafico critico:

- `EMAIL_MARKETING_ENABLED=True`
- `EMAIL_MARKETING_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_MARKETING_FROM_EMAIL`
- `EMAIL_MARKETING_REPLY_TO`
- `EMAIL_MARKETING_*` (host/port/user/password/tls/ssl/timeout)
- `EMAIL_MARKETING_BATCH_SIZE` (tamano de lote por envio)

### 2. Entorno local

Si `DEBUG=True` y no defines `EMAIL_BACKEND`, el sistema usa consola para evitar errores de SMTP.

### 3. Prueba operativa

Puedes validar la infraestructura con:

```bash
python manage.py send_test_email --to you@example.com --category transactional
python manage.py send_test_email --to you@example.com --category marketing
```

Si el backend es de consola, veras el email impreso en la terminal. Con SMTP real se envia por red.

## Despliegue (general)

1. Crear servicio web (Render, Railway, Fly.io, etc.).
2. Configurar variables de entorno de `.env.example`.
3. Instalar dependencias con `pip install -r requirements.txt`.
4. Ejecutar en build/release:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```
5. Comando de arranque web:
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

`Procfile` incluido:

```txt
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

## Acceso para familia/amigos

### Opcion 1: Misma red Wi-Fi (pruebas rapidas)

```bash
python manage.py runserver 0.0.0.0:8000
```

Compartan `http://TU_IP_LOCAL:8000` dentro de la misma red.

### Opcion 2: Internet temporal con tunnel

```bash
python manage.py runserver 0.0.0.0:8000
cloudflared tunnel --url http://localhost:8000
```

Comparte la URL `https://...trycloudflare.com`.

### Opcion 3: Produccion estable (recomendada)

Desplegar en proveedor cloud + dominio propio + HTTPS.

## Checklist de seguridad antes de abrir a terceros

- `DEBUG=False`.
- `ALLOWED_HOSTS` cerrado (sin comodines).
- HTTPS activo.
- Cookies seguras activadas.
- Secretos y credenciales fuera del repositorio.
- Base de datos gestionada (backups habilitados).
