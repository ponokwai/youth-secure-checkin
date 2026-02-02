# Quick Start Guide - Docker

## Production Deployment

```bash
# Create a directory for your instance
mkdir youth-checkin && cd youth-checkin

# Create required directories
mkdir -p data uploads

# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/ponokwai/youth-secure-checkin/master/docker-compose.yml

# Create .env file with your secrets
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
echo "DEVELOPER_PASSWORD=your-secure-password-here" >> .env

# Start production instance
docker compose up -d

# View logs (verify database initialized)
docker compose logs -f

# Access at http://localhost:5000
```

## Demo Mode

```bash
# Start demo instance (with auto-reset)
docker compose --profile demo up -d

# View logs
docker compose --profile demo logs -f

# Access at http://localhost:5000
```

## Test Credentials (Demo Mode)

**Admin Login:**
- Password: `demo123`

**Test Families (Phone Lookup):**
- 555-0101 - Johnson family (2 kids)
- 555-0102 - Smith family (1 kid)  
- 555-0103 - Williams family (2 kids)
- 555-0105 - Garcia family (3 kids)

## Common Commands

```bash
# View logs
docker compose logs

# Stop
docker compose down

# Restart
docker compose restart

# Update to latest version
docker compose pull
docker compose up -d
```

## Troubleshooting

**"No such table" error:**
```bash
# Database wasn't initialized - delete and restart
docker compose down
rm -f data/checkin.db
docker compose up -d
```

**Command not found (docker-compose):**
Use `docker compose` (with space) instead of `docker-compose` (with hyphen).

## Full Documentation

See [DOCKER.md](DOCKER.md) for complete instructions.
