# FinOrbit Application Rollout Architecture

This document covers how to expose the Django application to other people, starting with 5-10 friends and growing toward a publicly accessible app. Database backup details are intentionally separated in [`DB_BACKUP_STRATEGY.md`](DB_BACKUP_STRATEGY.md).

## Current App Readiness

The codebase already has several production-friendly pieces:

- Django app with multiple finance modules.
- User accounts through `django-allauth`.
- Per-user data ownership in the core finance, investment, holdings, and settings models.
- PostgreSQL support through `DATABASE_URL` or `DB_*`.
- `gunicorn` start command in `Procfile`.
- Static file serving with `whitenoise`.
- Environment-driven security settings.
- Email configuration through environment variables.

The biggest architecture decisions left are:

- Where the app runs.
- Where PostgreSQL runs.
- How users reach the app over HTTPS.
- How media uploads are stored.
- How email, logs, monitoring, and deployment are handled as usage grows.

## Core Principle

Friends and public users should access FinOrbit through a browser.

They should not:

- Connect to your laptop.
- Connect directly to PostgreSQL.
- Use your local network.
- Depend on your machine being awake.

The public shape should be:

```text
Users' browsers
      |
      | HTTPS
      v
Cloud web app running Django + Gunicorn
      |
      | DATABASE_URL
      v
Managed PostgreSQL
```

Optional services are added as the rollout grows:

```text
Object storage -> avatars and future uploads
SMTP provider  -> verification, password reset, notifications
Error tracking -> production exceptions
Monitoring     -> uptime and performance
Queue/worker   -> background jobs when needed
```

## Architecture Stage 0: Local Only

Use this only for development.

```text
Your browser -> localhost Django -> local PostgreSQL
```

Good for:

- Building features.
- Testing migrations.
- Importing your own data.
- Running the app privately.

Not good for:

- Friends outside your network.
- Reliable public access.
- Real shared beta testing.

A tunnel such as Cloudflare Tunnel can expose your local app temporarily, but treat that as a short demo path only. It still depends on your laptop and local database.

## Architecture Stage 1: Friends Pilot, 5-10 Users

Goal: let a small group of known friends use the app from their own laptops through the internet.

Recommended architecture:

```text
Friends' browsers
      |
      | HTTPS provider domain
      v
Single cloud web service
Django + Gunicorn + Whitenoise
      |
      v
Managed PostgreSQL
```

Recommended providers:

- Render
- Railway
- Fly.io
- Heroku-style platforms

Keep it simple:

- One web service.
- One managed PostgreSQL database.
- Provider-generated HTTPS domain.
- `DEBUG=False`.
- `ALLOWED_HOSTS` restricted to the provider domain.
- `CSRF_TRUSTED_ORIGINS` set to the provider HTTPS URL.
- `whitenoise` for static files.
- No direct object storage required yet if avatars are not important.

Important warning about media:

- Uploaded avatars currently go to `media/`.
- Many cloud web services have ephemeral filesystems.
- Avatar uploads can disappear after redeploy or restart.

For this first stage, choose one:

- Accept that avatars are experimental.
- Disable avatar upload.
- Move media storage to object storage earlier.

Minimum environment variables:

```env
SECRET_KEY=long-random-production-secret
DEBUG=False
DATABASE_URL=postgres://user:password@host:5432/dbname
DB_SSL_REQUIRE=True
ALLOWED_HOSTS=your-provider-domain.com
CSRF_TRUSTED_ORIGINS=https://your-provider-domain.com
SITE_URL=https://your-provider-domain.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
USE_X_FORWARDED_HOST=True
ACCOUNT_EMAIL_VERIFICATION=optional
```

Build command:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Start command:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

First deployment steps:

1. Create a managed PostgreSQL database.
2. Create the web service from this repo.
3. Add environment variables.
4. Deploy.
5. Run `python manage.py migrate`.
6. Run `python manage.py createsuperuser`.
7. Test signup and login.
8. Create two users and verify data isolation.
9. Invite 5-10 friends.

Operational expectations:

- You manually monitor logs.
- You manually apply migrations during deploy.
- You keep signups limited to people you know.
- You use the backup plan in `DB_BACKUP_STRATEGY.md`.

## Architecture Stage 2: Private Beta, 10-100 Users

Goal: make the app feel stable enough for a larger but still controlled group.

Architecture:

```text
Users
  |
  | HTTPS custom domain
  v
Cloud web service
  |
  +--> Managed PostgreSQL
  +--> SMTP provider
  +--> Object storage for media
  +--> Error tracking
```

Add:

- Custom domain.
- Real SMTP provider.
- Password reset email.
- Optional or mandatory email verification.
- Object storage for avatars and future uploads.
- Error tracking such as Sentry or equivalent.
- Basic uptime monitoring.
- A staging environment.
- A repeatable deployment checklist.

Recommended environment changes:

```env
ALLOWED_HOSTS=app.your-domain.com
CSRF_TRUSTED_ORIGINS=https://app.your-domain.com
SITE_URL=https://app.your-domain.com
ACCOUNT_EMAIL_VERIFICATION=mandatory
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=True
```

At this stage, you should add object storage for media. Static files can stay on `whitenoise`.

Add a simple release workflow:

1. Deploy to staging.
2. Run migrations on staging.
3. Smoke test login, signup, finance, investments, holdings, reports.
4. Create a production backup.
5. Deploy production.
6. Run migrations.
7. Smoke test production.
8. Watch logs.

Private beta readiness checklist:

- Password reset works.
- Email delivery works.
- Backups are tested.
- App logs are visible.
- Production errors are captured.
- Admin access is limited.
- Friends know this is an experimental finance app.
- Users are told not to enter sensitive banking secrets such as account passwords.

## Architecture Stage 3: Public Beta, 100-1000 Users

Goal: open the app beyond friends while still labeling it beta.

Architecture:

```text
Public users
    |
    | HTTPS + custom domain
    v
Web app service, scalable vertically or horizontally
    |
    +--> Managed PostgreSQL with stronger backup policy
    +--> Object storage for media
    +--> SMTP provider
    +--> Error tracking
    +--> Uptime and performance monitoring
```

Add:

- Public landing or signup flow.
- Privacy policy and terms.
- Consent language appropriate for finance data.
- Rate limiting for login and signup.
- Better admin controls.
- Better logging around imports and data changes.
- Health check endpoint.
- Provider alerts for high error rates and app downtime.
- Database performance monitoring.
- A clear support/contact email.

Consider adding:

- Redis cache if pages become slow.
- Background worker if email, imports, notifications, or market data calls become slow.
- CDN for static/media files if traffic grows.
- Separate staging and production databases.

At this stage, you should review user data isolation carefully. The app already filters most business data by `request.user`, but public rollout deserves a dedicated security review and tests for cross-user access.

Public beta readiness checklist:

- `python manage.py check --deploy` passes or every warning is understood.
- Email verification is mandatory.
- Password reset is tested.
- HTTPS is enforced.
- Cookies are secure.
- Database backups are tested.
- Restore process is documented.
- Error alerts go somewhere you actually read.
- You have a privacy policy.
- You have a deletion/export approach for user data.

## Architecture Stage 4: Public Production

Goal: make the app generally accessible as a real service.

Architecture:

```text
Users
  |
  | HTTPS
  v
CDN / edge / managed platform routing
  |
  v
Django web service, multiple instances if needed
  |
  +--> Managed PostgreSQL with PITR
  +--> Object storage
  +--> Redis cache or queue
  +--> Background workers
  +--> SMTP provider
  +--> Monitoring, alerting, error tracking
```

Add when the usage justifies it:

- Horizontal scaling for the web service.
- Background worker service for slow tasks.
- Redis for cache, sessions, rate limits, or task broker.
- Database connection pooling if the platform needs it.
- More formal incident response.
- Rollback plan for bad deploys.
- Structured logging.
- Audit trails for sensitive account actions.
- Data export and account deletion flows.
- Security headers review.
- Dependency vulnerability checks.

Do not add all of this on day one. Add it as each bottleneck becomes real.

## Suggested Rollout Timeline

### Step 1: This Week

- Keep developing locally.
- Create the DB backup process from `DB_BACKUP_STRATEGY.md`.
- Push the repo to a private remote.
- Choose a cloud provider for the pilot.

### Step 2: First Internet Pilot

- Deploy the web app.
- Use managed PostgreSQL.
- Keep the provider HTTPS URL.
- Invite 5-10 friends.
- Watch logs manually.
- Fix obvious usability and data isolation issues.

### Step 3: Controlled Beta

- Add custom domain.
- Configure SMTP.
- Require email verification.
- Add object storage for media.
- Add error tracking and uptime monitoring.
- Create staging.

### Step 4: Public Beta

- Publish the app URL more broadly.
- Add privacy policy and support contact.
- Add rate limiting and stronger observability.
- Review GDPR and finance-data obligations.
- Test backup restore monthly.

### Step 5: Public Production

- Scale web/database resources based on actual traffic.
- Add background workers and cache when needed.
- Formalize incident response and rollback process.
- Add user data export/deletion operations.

## Provider Choice Guidance

For your next step, optimize for simplicity:

- Use a platform that can deploy Django from Git.
- Use the same provider for managed PostgreSQL if possible.
- Use provider HTTPS domain first.
- Add custom domain later.

Good first deployment shape:

```text
Render/Railway/Fly web service
        |
        v
Managed PostgreSQL from same provider
```

Avoid this for anything beyond a quick demo:

```text
Friends -> tunnel -> your laptop -> local PostgreSQL
```

That setup is fragile and depends on your laptop, local network, and local database.

## Cost And Complexity By Stage

Stage 1, 5-10 users:

- One small web service.
- One small managed PostgreSQL database.
- Provider HTTPS URL.
- Manual monitoring.
- Lowest complexity.

Stage 2, 10-100 users:

- Add custom domain.
- Add SMTP.
- Add object storage.
- Add error tracking.
- Add staging.

Stage 3, 100-1000 users:

- Add monitoring and alerts.
- Add rate limiting.
- Tune database.
- Consider cache and workers.
- Add support/privacy workflows.

Stage 4, public production:

- Scale services.
- Add PITR and stronger disaster recovery.
- Add formal incident response.
- Add auditability and compliance work.

## Final Recommendation

For the next real milestone, use Stage 1:

- Deploy one Django web service to a cloud platform.
- Connect it to managed PostgreSQL.
- Keep access limited to 5-10 friends.
- Use HTTPS from the provider.
- Do not expose your laptop or local PostgreSQL.
- Treat avatars as temporary until object storage is configured.
- Use the backup strategy before inviting anyone.
