# Pombo CDN

[Read in Portuguese (Brasil)](README.pt-br.md)

**Version**: `v0.0.1` | **Status**: Production Ready | **License**: MIT

Pombo CDN is a self-hosted, lightweight, and high-performance content delivery network (CDN), file delivery, and distribution system packaged in a single all-in-one Docker container. Designed for speed and simplicity, it pairs Nginx `X-Accel-Redirect` for direct-to-disk line-speed streaming with Django 5.1, an intuitive dark-themed management dashboard, flexible database support (out-of-the-box SQLite with WAL mode, or external PostgreSQL/MySQL), granular link expiration rules, and a full built-in audit log.

---

## Architecture Overview

Pombo CDN runs all required services within a single, highly-optimized Docker container orchestrated by Supervisor:

```
[ Client Request ]
       |
       v
[ Nginx (Port 80) ]
   ├── Static Files (/static/) ───────────────> Served directly from /app/staticfiles/
   ├── Rate Limiting Zones ────────────────────> 30r/m (Login), 40r/s (Downloads), 60r/s (API)
   ├── Security Headers & Dotfile Blockers
   └── Reverse Proxy (Port 8000)
              |
              v
       [ Gunicorn / Django 5.1 ]
          ├── Authentication & User Permissions
          ├── Link Expiration & Token Verification
          ├── Anti-Brute-Force Cache Lockout
          ├── Audit Logging
          └── Response: HTTP 200 with "X-Accel-Redirect: /_protected/..."
              |
              v (Internal Handoff)
[ Nginx X-Accel-Redirect Engine ]
   ├── Reads requested file directly from disk (C/C++ sendfile kernel pipeline)
   ├── Handles HTTP Range Requests (smooth audio/video seeking with 206 Partial Content)
   └── Streams payload to client with near-zero Python memory overhead
```

---

## Key Features

- **All-in-One Docker Container**: Nginx, Gunicorn, Django, and SQLite orchestrated seamlessly via Supervisor in a single lightweight image (`python:3.12-slim-bookworm`).
- **Direct-to-Disk Acceleration (`X-Accel-Redirect`)**: Django verifies tokens, permissions, and download counters in microseconds; Nginx streams the file directly from disk via kernel `sendfile`. Python worker RAM usage remains flat even with multi-gigabyte files.
- **Dual Storage Architecture**:
  - `storage/uploads`: Local directory where newly uploaded files from the web UI are stored.
  - `storage/external`: Pre-existing host directories mapped directly into the container (read-only by default) to index, browse, and generate links without copying or duplicating files.
- **Shareable Link Engine**:
  - **Infinite links**: No download count limit and no expiration date.
  - **Download count limits**: Link expires automatically after a specified number of downloads (e.g., single-use links).
  - **Time expiration**: Link expires after 1 hour, 24 hours, 7 days, 30 days, or a custom target date and time.
  - **Combined rules**: Link expires as soon as either time elapses OR the download count is reached.
  - **Delivery modes**: Direct download / raw CDN stream (`/d/<token>/`) or web landing page (`/s/<token>/`) with media player preview and download button.
- **Mobile Responsive Design**:
  - Full mobile viewport support with an off-canvas slide-out navigation drawer.
  - Accessible top navigation bar with hamburger menu toggle.
  - Responsive tables, file upload dropzones, and modals optimized for touch screens.
- **Remember Login ("Salvar login")**:
  - Opt-in 30-day persistent session cookie or session expiry on browser close.
  - Local browser storage caches the username for quick 1-click re-authentication.
- **Full-Screen & Localized Preloaders**:
  - Full-screen preloader on initial page load, F5 refresh, login submission, logout, and language switching.
  - Localized spinner for seamless asynchronous tab navigation (Overview, Upload, Explorer, Links, Users, Logs).
- **Real Physical File Deletion**:
  - Deleting an uploaded file deletes it from the host filesystem immediately, freeing real disk storage.
- **Built-in Audit Logs**:
  - Tracks Link Creation, Downloads, Uploads, Deletions, Authentication attempts, and System Errors.
  - 1-click "Copy Logs" to clipboard and "Clear Logs" with custom modal confirmation.
- **Real-Time Bilingual Support (EN-US / PT-BR)**:
  - Default language configurable via `DEFAULT_LANGUAGE=en` or `DEFAULT_LANGUAGE=pt-br`.
  - 1-click real-time language switcher (`EN-US | PT-BR`) on login, dashboard, and public download screens.
- **Database Flexibility**:
  - Default: Built-in SQLite stored in `/app/data/pombo.sqlite3` with Write-Ahead Logging (WAL) enabled for high concurrent throughput.
  - External: Pass `DATABASE_URL=postgres://...` or `DATABASE_URL=mysql://...` to connect to external databases without changing application code.

---

## Quick Start (Production)

### 1. Clone the Repository

```bash
git clone https://github.com/thalison-dev/pombo.git
cd pombo
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set your production values:

```ini
SECRET_KEY=generate-a-strong-random-secret-key-for-production
DEBUG=0
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8080,https://cdn.yourdomain.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_strong_admin_password
ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_LANGUAGE=en
USE_X_ACCEL=1
```

### 3. Start the Container

```bash
docker compose up -d --build
```

### 4. Access the Dashboard

Open your web browser and navigate to:
```
http://localhost:8080/
```

- **Username**: `admin` (or the value set in `ADMIN_USERNAME`)
- **Password**: configured in `ADMIN_PASSWORD`

---

## Configuration Reference: Environment Variables

| Variable | Default Value | Allowed Values | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | `pombo-insecure-production-secret-key...` | Any string (min 32 chars) | Django cryptographic secret key. Must be unique and kept secret in production. |
| `DEBUG` | `0` | `0` (False), `1` (True) | Debug mode. Set to `0` in production. Only use `1` for local development. |
| `ALLOWED_HOSTS` | `*` | Comma-separated domains or `*` | Host/domain names that this site can serve (e.g. `cdn.yourdomain.com,localhost`). |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated full URLs | Full URLs with scheme (`http://` or `https://`) allowed for form submissions. Essential when using a reverse proxy or SSL. |
| `ADMIN_USERNAME` | `admin` | Alphanumeric string | Username for the initial super administrator account created on container startup. |
| `ADMIN_PASSWORD` | `adminpassword123` | String (min 8 chars) | Password for the initial super administrator account. |
| `ADMIN_EMAIL` | `admin@pombo.local` | Valid email address | Email address for the initial super administrator account. |
| `DEFAULT_LANGUAGE` | `en` | `en`, `pt-br` | System-wide default interface language (`en` for US English, `pt-br` for Brazilian Portuguese). |
| `USE_X_ACCEL` | `1` | `1` (True), `0` (False) | Enables Nginx `X-Accel-Redirect` direct streaming. Keep `1` in Docker. Only set `0` if running outside Docker without Nginx. |
| `DATABASE_URL` | *(empty - uses SQLite)* | `postgres://...`, `mysql://...` | Optional connection string to an external database. If omitted, Pombo uses high-performance SQLite WAL. |
| `UPLOAD_STORAGE_DIR` | `/app/storage/uploads` | Absolute filesystem path | Path where files uploaded via the web interface will be stored. |
| `EXTERNAL_STORAGE_DIR` | `/app/storage/external` | Absolute filesystem path | Path where pre-existing host files are mounted for browsing and link sharing. |

---

## Storage & Volume Mappings

The `docker-compose.yml` mounts three primary storage volumes:

```yaml
volumes:
  # 1. Database & State Persistence:
  - ./data:/app/data

  # 2. Uploaded Files Storage:
  - ./storage/uploads:/app/storage/uploads

  # 3. External Host Files (Read-Only):
  - /path/to/your/existing/files:/app/storage/external:ro
```

- **`./data:/app/data`**: Stores the SQLite database file (`pombo.sqlite3`) and SQLite Write-Ahead Logging (`.sqlite3-wal`, `.sqlite3-shm`) journals. Retains all users, links, access records, and audit logs across container recreations.
- **`./storage/uploads:/app/storage/uploads`**: Stores all files uploaded via the web dashboard. Requires write permissions for user `www-data` (UID 33).
- **`./storage/external:/app/storage/external:ro`**: Mount any host directory (e.g. photos, archives, video libraries). Pombo indexes and serves files directly without copying them. The `:ro` flag ensures Pombo cannot accidentally modify or delete your original files.

---

## Reverse Proxy Setup (HTTPS / SSL)

When deploying Pombo CDN behind an external reverse proxy (such as Cloudflare, Traefik, Caddy, or Nginx Proxy Manager), ensure your proxy forwards the standard headers and configure `CSRF_TRUSTED_ORIGINS`:

### Sample External Nginx Configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name cdn.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # Allow large file uploads
    client_max_body_size 0;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 1800s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 1800s;
        proxy_request_buffering off;
    }
}
```

In `.env`, set:
```ini
CSRF_TRUSTED_ORIGINS=https://cdn.yourdomain.com
ALLOWED_HOSTS=cdn.yourdomain.com
```

---

## Security & Hardening

Pombo CDN includes multi-layered enterprise-grade protection:

1. **Multi-Tiered Rate Limiting**:
   - **Login Endpoint (`/auth/login/`)**: Throttled in Nginx to `30r/m` with `burst=20 nodelay`.
   - **Django In-App Lockout**: 5 consecutive failed login attempts lock the offending IP address for 5 minutes (returns HTTP 429 and logs the lockout to audit records).
   - **Download & Stream Endpoints (`/d/`, `/s/`)**: Throttled in Nginx to `40r/s` with `burst=30 nodelay` to prevent automated scraping or token guessing.
   - **API & Uploads (`/storage/api/`)**: Throttled in Nginx to `60r/s` with `burst=50 nodelay`.

2. **Path Traversal Defense**:
   - Every file access is validated via `resolve_safe_path()`, verifying that the canonical resolved path strictly resides within the authorized storage roots before serving or deleting. Attempts to access outside files via `../` or symlinks are blocked with HTTP 403.

3. **Stored XSS & Content Type Protection**:
   - Safe media types (`image/jpeg`, `image/png`, `image/webp`, `video/mp4`, `video/webm`, `audio/mpeg`, `application/pdf`) are allowed inline presentation.
   - Untrusted and executable types (`.html`, `.svg`, `.js`, `.sh`, `.exe`, `.bat`) always force `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff` to prevent browser script execution.

4. **Hardened HTTP Headers**:
   - `X-Frame-Options: SAMEORIGIN` (prevents clickjacking)
   - `X-Content-Type-Options: nosniff` (prevents MIME type sniffing)
   - `X-XSS-Protection: 1; mode=block`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `server_tokens off` (hides Nginx version disclosure)
   - Blocks dotfiles (`.env`, `.git`) and sensitive source files (`.sqlite3`, `.py`, `.sh`, `.log`).

---

## Operations & Maintenance

### Checking Container Health

Pombo CDN includes a built-in Docker `HEALTHCHECK` probing `http://localhost/health/` every 30 seconds:

```bash
docker inspect --format='{{json .State.Health}}' pombo
```

### Viewing Logs

```bash
# View combined container logs (Nginx + Gunicorn + Supervisor)
docker compose logs -f pombo

# View Django/Gunicorn application logs specifically
docker compose exec pombo supervisorctl tail -f gunicorn

# View Nginx access & error logs specifically
docker compose exec pombo supervisorctl tail -f nginx
```

### Creating or Resetting Superuser Password

```bash
docker compose exec pombo python manage.py initadmin
# or interactively:
docker compose exec pombo python manage.py createsuperuser
```

### Backing Up the System

To back up your entire Pombo instance, simply copy the `./data` and `./storage/uploads` folders:

```bash
# Backup database (SQLite is safe to copy when idle, or use sqlite3 .backup)
docker compose exec pombo sqlite3 /app/data/pombo.sqlite3 ".backup /app/data/pombo_backup.sqlite3"
cp data/pombo_backup.sqlite3 /path/to/backup/
tar -czvf uploads_backup.tar.gz storage/uploads/
```

---

## Version History

### `v0.0.1` (Initial Production Release)
- All-in-one Docker container with Nginx, Gunicorn, Django 5.1, and Supervisor.
- High-performance direct-to-disk `X-Accel-Redirect` file delivery engine.
- Complete responsive dark theme with mobile slide-out drawer navigation.
- Persistent "Remember Login" functionality with client username caching.
- Multi-tier rate limiting and automated anti-brute-force lockout.
- Granular link expiration engine (download limits, time limits, combined rules).
- Live audit log system with 1-click clipboard copy and safe log purge.
- Real-time bilingual toggle (`EN-US` / `PT-BR`).
- Dual storage mapping support (`uploads` and `external:ro`).
