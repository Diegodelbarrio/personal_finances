# FinOrbit DB Backup Strategy

This document is only about protecting PostgreSQL data. It does not define the public application architecture; that is covered in [`APPLICATION_ROLLOUT_ARCHITECTURE.md`](APPLICATION_ROLLOUT_ARCHITECTURE.md).

## Goal

Avoid losing finance data if:

- Your laptop breaks, is stolen, or the disk fails.
- A local PostgreSQL folder is deleted.
- A migration or manual command corrupts data.
- A cloud provider has an outage.
- You need to move the database to another machine or provider.

The backup strategy should answer four questions:

- What data is backed up?
- How often is it backed up?
- Where is the backup stored?
- Can you restore it when needed?

## Current Risk Assessment

If your PostgreSQL database is running locally, the database files live on your laptop disk. PostgreSQL is reliable as a database engine, but local storage is still a single point of failure.

You can ask PostgreSQL where it stores data:

```bash
psql "$DATABASE_URL" -c "SHOW data_directory;"
```

or, if you use separate variables:

```bash
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SHOW data_directory;"
```

If the laptop dies and there is no external backup, the app data can be lost.

## Data In Scope

The PostgreSQL backup includes:

- Users and authentication data.
- Finance transactions, categories, subcategories, and locations.
- Investment assets, transactions, and history.
- Holdings accounts and balance snapshots.
- User settings and profile metadata.
- Knowledge/report data stored in database tables.

The PostgreSQL backup does not include:

- Uploaded avatar files under `media/`.
- `.env` secrets.
- Source code.
- Generated static files under `staticfiles/`.

Those should be protected separately. For now, the only user media identified in the app is avatar upload via `users.User.avatar`.

## Backup Types

### Logical Backup With `pg_dump`

Use this as your main portable backup.

Benefits:

- Easy to move across machines and providers.
- Good for small and medium databases.
- Can be restored into a fresh PostgreSQL database.
- Works well with Django apps.

Recommended format:

```bash
pg_dump "$DATABASE_URL" --format=custom --file "backups/finorbit_$(date +%Y%m%d_%H%M).dump"
```

The custom format is better than plain SQL because it supports `pg_restore`, compression, and more flexible restore options.

### Managed Provider Backups

When deployed, use managed PostgreSQL automated backups from your hosting provider.

Benefits:

- Automated.
- Usually easy to restore from the provider dashboard.
- Often includes daily snapshots.
- Some providers offer point-in-time recovery.

Risk:

- The backup is tied to the provider.
- You may lose access if there is an account or provider issue.

That is why provider backups should be combined with your own `pg_dump` exports.

### Point-In-Time Recovery

Point-in-time recovery, often called PITR, lets you restore the database to a specific time before an incident.

Use PITR when:

- The app becomes public.
- Real users enter important finance data.
- You need lower data-loss risk than daily backups.

PITR is usually a managed database feature. You do not need it for the first 5-10 friend test, but it becomes important later.

## Backup Targets By Stage

### Stage 1: Local Development

Purpose: protect your own data while building.

Suggested target:

- Recovery Point Objective: lose at most 1 week of local work.
- Recovery Time Objective: restore within a few hours.

Minimum strategy:

- Run `pg_dump` weekly.
- Run `pg_dump` before risky migrations or data imports.
- Keep backups in `backups/`, which is ignored by Git.
- Copy encrypted backups to cloud storage or an external drive.
- Test restore once after setting this up.

Better strategy:

- Run `pg_dump` daily.
- Automate it with a local scheduled job.
- Keep the last 7 daily backups and last 4 weekly backups.

Example:

```bash
mkdir -p backups
pg_dump "$DATABASE_URL" --format=custom --file "backups/finorbit_local_$(date +%Y%m%d_%H%M).dump"
```

### Stage 2: Friends Pilot With 5-10 Users

Purpose: protect early user data without overengineering.

Suggested target:

- Recovery Point Objective: lose at most 24 hours.
- Recovery Time Objective: restore the app within half a day.

Minimum strategy:

- Use managed PostgreSQL.
- Enable automated provider backups.
- Take your own `pg_dump` at least weekly.
- Take a manual backup before every deployment that includes migrations.
- Store backups outside the provider account when possible.

Recommended retention:

- 7 daily provider backups.
- 4 weekly logical backups.
- 3 monthly logical backups.

### Stage 3: Private Beta

Purpose: protect a growing group of real users.

Suggested target:

- Recovery Point Objective: 24 hours or less.
- Recovery Time Objective: 2-4 hours.

Minimum strategy:

- Managed PostgreSQL automated backups.
- Daily logical `pg_dump`.
- Monthly restore test.
- Document the restore steps.
- Keep backups encrypted.
- Keep backups in a different provider or storage account.

Recommended addition:

- Enable PITR if the provider offers it at reasonable cost.

### Stage 4: Public App

Purpose: protect production data for public users.

Suggested target:

- Recovery Point Objective: less than 1 hour if feasible.
- Recovery Time Objective: less than 2 hours for critical incidents.

Minimum strategy:

- Managed PostgreSQL with PITR.
- Automated daily snapshots.
- Independent logical exports.
- Tested restore playbook.
- Access controls around who can restore or delete backups.
- Monitoring alerts for backup failure.
- Incident checklist for accidental deletes, bad migrations, and provider outage.

At this stage, backup and restore is part of product reliability, not just a developer habit.

## Local Backup Commands

Create backup:

```bash
mkdir -p backups
pg_dump "$DATABASE_URL" --format=custom --file "backups/finorbit_$(date +%Y%m%d_%H%M).dump"
```

List backups:

```bash
ls -lh backups
```

Restore into the current target database:

```bash
pg_restore --clean --if-exists --dbname "$DATABASE_URL" "backups/finorbit_YYYYMMDD_HHMM.dump"
```

Restore into a test database:

```bash
createdb finorbit_restore_test
pg_restore --clean --if-exists --dbname finorbit_restore_test "backups/finorbit_YYYYMMDD_HHMM.dump"
```

Run migrations after restore:

```bash
python manage.py migrate
```

Check that the restored app boots:

```bash
python manage.py check
python manage.py runserver
```

## Backup Before Risky Operations

Always create a fresh backup before:

- Running a migration in production.
- Importing a large CSV.
- Deleting user data.
- Changing database credentials.
- Moving providers.
- Running a manual SQL command.

Command:

```bash
pg_dump "$DATABASE_URL" --format=custom --file "backups/before_change_$(date +%Y%m%d_%H%M).dump"
```

## Encryption

Backups contain personal finance data. Treat them as sensitive.

At minimum:

- Do not commit backups to Git.
- Do not put unencrypted dumps in shared folders.
- Protect cloud storage with strong account security.

Better:

- Encrypt backups before uploading.
- Use a password manager for encryption keys.
- Store encryption keys separately from the backup files.

Example with `gpg`:

```bash
gpg --symmetric --cipher-algo AES256 backups/finorbit_YYYYMMDD_HHMM.dump
```

This produces:

```text
backups/finorbit_YYYYMMDD_HHMM.dump.gpg
```

## Restore Test Checklist

A backup is not real until you have restored it.

Test at least once locally:

1. Create a fresh test database.
2. Restore the dump into it.
3. Point `.env` or `DATABASE_URL` to the test database.
4. Run `python manage.py migrate`.
5. Run `python manage.py check`.
6. Log in with a test user or create a superuser.
7. Confirm finance, investment, and holdings pages load.

For cloud environments, test restore into a non-production database.

## Suggested Retention

For local development:

- Keep 7 daily backups.
- Keep 4 weekly backups.
- Keep 3 monthly backups if you are using the app for real personal data.

For friends pilot:

- Keep 7 daily provider backups.
- Keep 4 weekly exported dumps.
- Keep 3 monthly exported dumps.

For public production:

- Use provider PITR.
- Keep at least 30 days of recoverability.
- Keep monthly archives for longer if legal/privacy requirements allow it.

## What To Do If The Laptop Breaks

If you have a backup:

1. Install PostgreSQL on a new machine or create a managed PostgreSQL database.
2. Restore the latest `.dump` file with `pg_restore`.
3. Set `DATABASE_URL` to the restored database.
4. Run `python manage.py migrate`.
5. Start the app.

If you do not have a backup:

- Recovering the data depends on whether the laptop disk can be repaired or recovered.
- Git will recover the source code only if pushed remotely.
- Git will not recover PostgreSQL data, `.env`, or local media.

## Immediate Action Items

Do these now:

1. Confirm the app is using PostgreSQL and not SQLite.
2. Run one manual `pg_dump`.
3. Restore it into a test database.
4. Encrypt a copy.
5. Store the encrypted copy outside the laptop.

After that, automate the process.
