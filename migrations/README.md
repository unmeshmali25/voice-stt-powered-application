# Database Migrations

This directory contains SQL migrations for the VoiceOffers platform database.

## Files

- `postgres_schema.sql` - Complete database schema with tables, indexes, and triggers
- `seed_dev.sql` - Sample data for development environment
- `seed_staging.sql` - Realistic test data for staging environment

## Setup Instructions

### For Supabase Projects

1. **Create three Supabase projects**:
   - `voiceoffers-dev` (Development)
   - `voiceoffers-staging` (Staging)
   - `voiceoffers-prod` (Production)

2. **Apply the schema** to each project:
   - Go to Supabase Dashboard → SQL Editor
   - Copy contents of `postgres_schema.sql`
   - Run the SQL

3. **Apply seed data** (optional, for dev/staging only):
   - For development: Run `seed_dev.sql`
   - For staging: Run `seed_staging.sql`
   - For production: DO NOT run seed data

### For Local Development (Docker PostgreSQL)

```bash
# Start PostgreSQL
docker run -d \
  --name voiceoffers-postgres \
  -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=voiceoffers \
  -p 5432:5432 \
  postgres:15

# Apply schema
psql -h localhost -U postgres -d voiceoffers -f migrations/postgres_schema.sql

# Apply seed data
psql -h localhost -U postgres -d voiceoffers -f migrations/seed_dev.sql
```

## Schema Version

Current version: **v1.0** (Initial release)

## Future Migrations

When making schema changes:
1. Create a new migration file: `migrations/YYYY-MM-DD_description.sql`
2. Document the changes in this README
3. Apply to dev → staging → production (in that order)
4. Consider using Alembic for automated migration management (see future plans)
