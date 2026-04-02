# Docker & nginx Production Deployment

This document describes the production Docker setup for EduFlow AI Assistant.

## Architecture

The deployment consists of three services orchestrated via Docker Compose:

1. **PostgreSQL Database** (`db`): postgres:15-alpine
   - Persistent volume: `postgres_data`
   - Health check: PostgreSQL readiness probe
   - Network: `eduflow_network` (bridge)

2. **FastAPI Application** (`webhook`): custom Python image
   - Built from multi-stage Dockerfile
   - Non-root user: `appuser:1000`
   - Health check: HTTP GET /health endpoint
   - Networks: `eduflow_network`
   - Depends on: `db` service (waits for health)

3. **nginx Reverse Proxy** (`nginx`): nginx:alpine
   - Port mapping: 80 → webhook:8000, 443 (SSL) → webhook:8000
   - SSL certificate paths (configurable via Let's Encrypt)
   - Health check: HTTP GET /health through proxy
   - Networks: `eduflow_network`

## Files Created

- **Dockerfile** (42 lines)
  - Multi-stage build: builder (installs deps) + runtime (minimal)
  - Non-root user: appuser:1000 (security hardening)
  - Health check: Python httpx call to /health
  - Base image: python:3.11-slim (~150MB base)

- **.dockerignore** (63 lines)
  - Excludes: .git, __pycache__, .venv, tests, .env, etc.
  - Keeps: application code, data/chroma_db

- **docker-compose.prod.yml** (97 lines)
  - Three services: db, webhook, nginx
  - Environment variables from .env file
  - Health checks with appropriate intervals
  - Persistent volume for PostgreSQL
  - Custom bridge network for service isolation

- **deployment/nginx/conf.d/default.conf** (78 lines)
  - HTTP → HTTPS redirect
  - SSL configuration (TLSv1.2+)
  - Security headers (HSTS, X-Frame-Options, etc.)
  - Upstream proxy to webhook:8000
  - Support for Let's Encrypt ACME challenges

- **deployment/.env.example** (81 lines)
  - Template for all required environment variables
  - Sections: LLM, Integrations, Database, Application
  - Comments explaining each variable
  - Security reminder

## Quick Start

### 1. Setup Environment

```bash
cp deployment/.env.example .env
# Edit .env with actual API keys and credentials
```

### 2. Build Docker Image

```bash
docker compose -f docker-compose.prod.yml build
```

### 3. Start Services

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 4. Verify Health

```bash
# Check all services are running
docker compose -f docker-compose.prod.yml ps

# Check logs
docker compose -f docker-compose.prod.yml logs -f webhook

# Health check
curl -v http://localhost:8000/health
```

### 5. Configure SSL (optional)

For production, set up Let's Encrypt SSL:

```bash
# 1. Create required directories
mkdir -p data/certbot/conf data/certbot/www

# 2. Update domain in deployment/nginx/conf.d/default.conf
#    Replace DOMAIN_NAME with actual domain

# 3. Run certbot to generate certificate
docker run --rm \
  -v ./data/certbot/conf:/etc/letsencrypt \
  -v ./data/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot -d your-domain.com

# 4. Reload nginx
docker compose -f docker-compose.prod.yml restart nginx
```

## Key Features

### Security
- Non-root user (appuser:1000)
- Multi-stage build (minimal attack surface)
- SSL/TLS 1.2+
- Security headers (HSTS, CSP, X-Frame-Options)
- No secrets in Dockerfile or images
- All credentials via .env file

### Reliability
- Health checks for all services
- Database connection pooling (min=2, max=10)
- Service restart policy: unless-stopped
- Graceful shutdown handling

### Performance
- Multi-stage build reduces image size (~182MB)
- Alpine Linux for smaller footprint
- Nginx buffering and timeouts configured
- Connection pooling for database

### Monitoring
- Container health checks (30s interval)
- Service startup checks (40s grace period)
- Access/error logs in nginx
- Structured logging from FastAPI (JSON format)

## Common Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs webhook
docker compose -f docker-compose.prod.yml logs -f nginx

# Restart service
docker compose -f docker-compose.prod.yml restart webhook

# Stop all services
docker compose -f docker-compose.prod.yml down

# View running containers
docker compose -f docker-compose.prod.yml ps

# Execute command in container
docker compose -f docker-compose.prod.yml exec webhook bash
```

## Database Management

### Backup

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U postgres ai_assistant_eduflow > backup.sql
```

### Restore

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U postgres ai_assistant_eduflow < backup.sql
```

### Run Migrations

```bash
docker compose -f docker-compose.prod.yml exec webhook \
  alembic upgrade head
```

## Troubleshooting

### Container fails to start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs webhook

# Common issues:
# - Missing .env file or variables
# - Database not yet initialized
# - Port already in use
```

### Health check failing

```bash
# Test manually
docker compose -f docker-compose.prod.yml exec webhook \
  python -c "import httpx; httpx.get('http://localhost:8000/health')"
```

### Database connection error

```bash
# Verify database is running
docker compose -f docker-compose.prod.yml logs db

# Check connectivity
docker compose -f docker-compose.prod.yml exec webhook \
  python -c "import asyncpg; print('OK')"
```

## Image Size Analysis

- Base image: python:3.11-slim (~150MB)
- Dependencies: ~32MB (after pip install)
- Application code: <1MB
- **Total: ~182MB**

This is minimal for a production Python application with all dependencies.

## Network Isolation

All services communicate via custom Docker bridge network `eduflow_network`:
- Database: `db:5432` (only accessible from webhook)
- Application: `webhook:8000` (accessible from nginx)
- nginx: `0.0.0.0:80,443` (exposed to host)

External access requires going through nginx reverse proxy.
