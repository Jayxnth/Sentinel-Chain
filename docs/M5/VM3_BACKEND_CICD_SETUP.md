# VM3 Backend CI/CD Setup Guide (CLI only)

This guide sets up Issue #6 end-to-end for branch `feat/fastapi-scaffold`:
1. CI test run on every push/PR to that branch.
2. CD deploy to VM3 on push (or manual dispatch).
3. PostgreSQL hardening and schema creation from SQLAlchemy models.

No GUI is required in any step.

---

## 1. What was added in this repo

- Workflow: `.github/workflows/backend-vm3-cicd.yml`
- Deployment script: `fast-api-deploy/deploy.sh`
- Systemd template: `fast-api-deploy/sentinel-api.service.template`

The deployment script is parameterized:
- `--app-dir` for application location.
- `--venv-path` for Python virtualenv location.
- `--database-url` for the SQLAlchemy async PostgreSQL URL.

---

## 2. VM3 base setup (clean Ubuntu VM)

Run on VM3 as a sudo-capable user:

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential libpq-dev \
  postgresql postgresql-contrib
```

Optional firewall baseline (if UFW is used):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000/tcp
sudo ufw --force enable
```

---

## 3. PostgreSQL secure setup

### 3.1 Create least-privilege DB role + DB

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE sentinel_app WITH LOGIN PASSWORD '<STRONG_LONG_PASSWORD>';
CREATE DATABASE sentinel_chain OWNER sentinel_app;
REVOKE ALL ON DATABASE sentinel_chain FROM PUBLIC;
GRANT CONNECT, TEMP ON DATABASE sentinel_chain TO sentinel_app;
SQL
```

### 3.2 Harden postgres authentication and listeners

Find config paths:

```bash
sudo -u postgres psql -t -P format=unaligned -c "SHOW config_file; SHOW hba_file;"
```

Edit `postgresql.conf` (path returned above):

```conf
listen_addresses = '127.0.0.1'
password_encryption = scram-sha-256
```

Edit `pg_hba.conf` (path returned above) to use SCRAM and deny broad trust:

```conf
local   all             postgres                                peer
local   all             all                                     scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
```

Reload:

```bash
sudo systemctl restart postgresql
```

### 3.3 DATABASE_URL format for this backend

The backend uses SQLAlchemy async engine + `asyncpg`, so URL must be:

```text
postgresql+asyncpg://<db_user>:<url_encoded_password>@<db_host>:5432/<db_name>
```

Examples:

- Local postgres on VM3:
  `postgresql+asyncpg://sentinel_app:<ENCODED_PASSWORD>@127.0.0.1:5432/sentinel_chain`
- Remote/TLS-required postgres:
  `postgresql+asyncpg://sentinel_app:<ENCODED_PASSWORD>@db.example.com:5432/sentinel_chain?ssl=require`

Use URL encoding for special characters in passwords. In CI/CD, this repository reads DB parts directly from the `VM3_DB_*` GitHub secrets and URL-encodes `VM3_DB_PASSWORD_RAW` in the deploy step before assembling `DATABASE_URL`.

---

## 4. GitHub Secrets setup (repository-level)

From your local machine (or any trusted admin shell with `gh` authenticated):

```bash
gh auth login
gh repo set-default Jayxnth/Sentinel-Chain
```

Set required secrets:

```bash
gh secret set VM3_HOST --body "<VM3_IP_OR_DNS>"
gh secret set VM3_SSH_USER --body "<SSH_USERNAME>"
gh secret set VM3_SSH_PORT --body "22"
gh secret set VM3_SSH_PRIVATE_KEY --body "$(cat ~/.ssh/<private_key_file>)"
gh secret set VM3_SSH_KNOWN_HOSTS --body "$(ssh-keyscan -H <VM3_IP_OR_DNS> 2>/dev/null)"
gh secret set VM3_DB_USER --body "sentinel_app"
gh secret set VM3_DB_PASSWORD_RAW --body "<RAW_DATABASE_PASSWORD>"
gh secret set VM3_DB_HOST --body "127.0.0.1"
gh secret set VM3_DB_NAME --body "sentinel_chain"
gh secret set VM3_API_KEY --body "<SENTINEL_BACKEND_API_KEY>"
gh secret set VM3_GOOGLE_API_KEY --body "<GOOGLE_API_KEY>"
gh secret set VM3_GEMINI_MODEL --body "gemini-2.5-flash"
```

Security notes:
- Use a dedicated deploy SSH key pair.
- Prefer a dedicated VM user with limited sudo rights.
- Rotate `VM3_API_KEY` and DB password periodically.
- Never commit `.env` files or plaintext secrets.

---

## 5. CI/CD behavior

Workflow file: `.github/workflows/backend-vm3-cicd.yml`

Triggers:
- `push` on `feat/fastapi-scaffold`
- `pull_request` targeting `feat/fastapi-scaffold`
- `workflow_dispatch` (manual)

Stages:
1. **tests**: `pytest -q backend/tests`
2. **deploy** (push/manual only): copies repository tarball to VM3, builds `DATABASE_URL` from `VM3_DB_*` secrets (with Python URL encoding), and runs `fast-api-deploy/deploy.sh` to write that resolved `DATABASE_URL` into the service env file.

It does not run on `main`.

---

## 6. Manual workflow run (CLI only)

Run manual deploy (same branch only):

```bash
gh workflow run backend-vm3-cicd.yml \
  --ref feat/fastapi-scaffold \
  -f app_dir=/opt/sentinel-chain \
  -f venv_path=/opt/sentinel-chain/.venv \
  -f app_host=0.0.0.0 \
  -f app_port=8000
```

Watch run:

```bash
gh run list --workflow backend-vm3-cicd.yml --limit 5
gh run watch <run-id>
```

---

## 7. Deployment script usage directly on VM3

When code already exists on VM3:

```bash
cd /opt/sentinel-chain
sudo ./fast-api-deploy/deploy.sh \
  --app-dir /opt/sentinel-chain \
  --venv-path /opt/sentinel-chain/.venv \
  --database-url "postgresql+asyncpg://sentinel_app:<ENCODED_PASSWORD>@127.0.0.1:5432/sentinel_chain" \
  --api-key "<SENTINEL_BACKEND_API_KEY>" \
  --google-api-key "<GOOGLE_API_KEY>" \
  --gemini-model "gemini-2.5-flash" \
  --service-user "sentinel" \
  --host "0.0.0.0" \
  --port "8000"
```

The script will:
- create/refresh virtualenv and install dependencies,
- write protected env file at `/etc/sentinel-chain/sentinel-api.env`,
- apply schema from SQLAlchemy models,
- install/restart `sentinel-api.service`.

---

## 8. Applying schema directly from SQLAlchemy models

This repo already uses SQLAlchemy metadata creation (`Base.metadata.create_all`) via `backend.db.database.init_db()`.

CLI command (same behavior used by deploy script):

```bash
cd /opt/sentinel-chain
DATABASE_URL="postgresql+asyncpg://sentinel_app:<ENCODED_PASSWORD>@127.0.0.1:5432/sentinel_chain" \
  /opt/sentinel-chain/.venv/bin/python -c "import asyncio; from backend.db.database import init_db; asyncio.run(init_db())"
```

References:
- SQLAlchemy async docs: `AsyncConnection.run_sync()` for DDL.
- SQLAlchemy metadata docs: `MetaData.create_all()`.

---

## 9. Rollout and post-deploy checks

```bash
sudo systemctl status sentinel-api --no-pager
sudo journalctl -u sentinel-api -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://10.0.0.4:8000/health
```

Expected response:

```json
{"status":"ok"}
```
