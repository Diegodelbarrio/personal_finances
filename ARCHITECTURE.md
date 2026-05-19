# FinOrbit Architecture Docs

The operational topics are intentionally split:

- [`DB_BACKUP_STRATEGY.md`](DB_BACKUP_STRATEGY.md): how to avoid losing PostgreSQL data, how often to back it up, and how to restore it.
- [`APPLICATION_ROLLOUT_ARCHITECTURE.md`](APPLICATION_ROLLOUT_ARCHITECTURE.md): how to expose the Django app to friends first, then grow toward a public product.

Short version:

- For data safety, do not rely on local PostgreSQL as the only copy. Use `pg_dump`, off-laptop encrypted storage, restore tests, and managed PostgreSQL backups when deployed.
- For access by friends, do not expose your local database. Deploy one cloud-hosted Django web app behind HTTPS and connect it to managed PostgreSQL.
