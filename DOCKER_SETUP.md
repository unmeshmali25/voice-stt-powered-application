# Docker Setup Guide for XYZCare

This guide covers setting up PostgreSQL for local development using Docker.

## Prerequisites

- Docker Desktop installed ([download here](https://www.docker.com/products/docker-desktop))
- Docker Compose (included with Docker Desktop)
- Python 3.11+ with pip

## Quick Start

### 1. Start PostgreSQL

```bash
# Start PostgreSQL in the background
docker-compose up -d

# Verify it's running
docker-compose ps
```

Expected output:
```
NAME                IMAGE                COMMAND                  SERVICE   CREATED         STATUS         PORTS
xyzcare-postgres    postgres:15-alpine   "docker-entrypoint.s…"   postgres  5 seconds ago   Up 4 seconds   0.0.0.0:5432->5432/tcp
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set:
# - OPENAI_API_KEY=your_actual_openai_api_key
# - DATABASE_URL=postgresql://postgres:dev@localhost:5432/xyzcare (should already be set)
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Ingest Manuals

```bash
# This will create the database schema and ingest PDFs
python -m app.ingestion.ingest_manuals --rebuild
```

### 5. Start the Application

```bash
# Start the FastAPI server
./start_server.sh

# Or manually:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit http://localhost:8000 in your browser.

## Docker Commands Reference

### Basic Operations

```bash
# Start PostgreSQL
docker-compose up -d

# Stop PostgreSQL (keeps data)
docker-compose stop

# Start again after stopping
docker-compose start

# View logs
docker-compose logs -f postgres

# Stop and remove (WARNING: deletes all data!)
docker-compose down -v
```

### Database Access

```bash
# Connect to PostgreSQL CLI
docker-compose exec postgres psql -U postgres -d xyzcare

# Common psql commands:
# \dt          - List all tables
# \d tablename - Describe table structure
# \q           - Quit psql
```

### Troubleshooting

```bash
# Check if container is running
docker-compose ps

# View recent logs
docker-compose logs --tail=100 postgres

# Restart PostgreSQL
docker-compose restart postgres

# Complete reset (deletes data!)
docker-compose down -v
docker-compose up -d
```

## Database Connection Details

When PostgreSQL is running via Docker Compose:

- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `xyzcare`
- **Username**: `postgres`
- **Password**: `dev`
- **Connection String**: `postgresql://postgres:dev@localhost:5432/xyzcare`

## Data Persistence

The PostgreSQL data is stored in a Docker volume named `xyzcare_postgres_data`. This means:

✅ **Data persists** when you:
- Stop the container (`docker-compose stop`)
- Restart your computer
- Update the Docker image

❌ **Data is deleted** when you:
- Run `docker-compose down -v` (the `-v` flag removes volumes)
- Manually delete the volume: `docker volume rm xyzcare_postgres_data`

## Connection Pooling

The application is configured with connection pooling:
- **pool_size**: 5 persistent connections
- **max_overflow**: 10 additional connections when needed
- **pool_pre_ping**: Verifies connections before use
- **pool_recycle**: Recycles connections after 1 hour

This configuration is optimized for local development and Heroku's 20-connection limit.

## Switching Between SQLite and PostgreSQL

### To use PostgreSQL (recommended):
```bash
# In .env file:
DATABASE_URL=postgresql://postgres:dev@localhost:5432/xyzcare
```

### To use SQLite (not recommended):
```bash
# In .env file:
DATABASE_URL=sqlite:///./data/sqlite/manuals.db
```

Note: SQLite has limited full-text search capabilities compared to PostgreSQL.

## Common Issues

### Port 5432 Already in Use

If you have PostgreSQL installed locally:

**Option 1**: Stop local PostgreSQL
```bash
# macOS
brew services stop postgresql

# Linux
sudo systemctl stop postgresql
```

**Option 2**: Change Docker port in `docker-compose.yml`
```yaml
ports:
  - "5433:5432"  # Use port 5433 instead

# Then update DATABASE_URL in .env:
DATABASE_URL=postgresql://postgres:dev@localhost:5433/xyzcare
```

### Container Won't Start

```bash
# Check logs
docker-compose logs postgres

# Common fix: remove old container
docker-compose down
docker-compose up -d
```

### Can't Connect to Database

1. Verify container is running:
   ```bash
   docker-compose ps
   ```

2. Check DATABASE_URL in `.env` matches the connection details

3. Test connection directly:
   ```bash
   docker-compose exec postgres psql -U postgres -d xyzcare -c "SELECT version();"
   ```

## Production Deployment

For Heroku deployment:
- Heroku automatically provides `DATABASE_URL` via the Postgres addon
- No Docker needed on Heroku
- Connection pooling is pre-configured for Heroku's limits
- See `DEPLOYMENT.md` for complete Heroku setup

## Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
