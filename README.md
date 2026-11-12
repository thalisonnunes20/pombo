# Pombo CDN

[Read in Portuguese (Brasil)](README.pt-br.md)

**Repository**: [https://github.com/thalisonnunes20/pombo](https://github.com/thalisonnunes20/pombo)  
**Docker Image**: `ghcr.io/thalisonnunes20/pombo:latest` (or `:v1.0.0`)  
**Version**: `v1.0.0` | **Status**: Production Ready | **License**: MIT

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

## How to Install & Run via Docker

You can run Pombo CDN using either the official pre-built image from GitHub Container Registry or by building from source.

### Method 1: Using Pre-Built Docker Image (Fastest - Recommended)

No git clone or source code required. Create a directory and a `docker-compose.yml` file:

```yaml
services:
  pombo:
    image: ghcr.io/thalisonnunes20/pombo:latest
    container_name: pombo
    entrypoint: ["/bin/sh", "/app/entrypoint.sh"]
    restart: unless-stopped
    ports:
      - "8080:80"
    environment:
      - SECRET_KEY=pombo-change-this-to-a-secure-random-token-in-production
      - DEBUG=0
      - ALLOWED_HOSTS=*
      - CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=adminpassword123
      - ADMIN_EMAIL=admin@pombo.local
      - DEFAULT_LANGUAGE=en
      - USE_X_ACCEL=1
    volumes:
      - ./data:/app/data
      - ./storage/uploads:/app/storage/uploads
      - ./storage/external:/app/storage/external:ro
```

Then start the container:

```bash
docker compose up -d
```

#### Or Run with a Single `docker run` Command:

```bash
docker run -d \
  --name pombo \
  -p 8080:80 \
  -e SECRET_KEY="your-production-secret-token" \
  -e ADMIN_USERNAME="admin" \
  -e ADMIN_PASSWORD="adminpassword123" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/storage/uploads:/app/storage/uploads \
  -v $(pwd)/storage/external:/app/storage/external:ro \
  --restart unless-stopped \
  ghcr.io/thalisonnunes20/pombo:latest
```

---

### Method 2: Building from Source via Git Clone

If you want to inspect or modify the source code:

```bash
# 1. Clone the repository
git clone https://github.com/thalisonnunes20/pombo.git
cd pombo

# 2. Configure environment file
cp .env.example .env
# Edit .env and customize SECRET_KEY, ADMIN_PASSWORD, etc.

# 3. Build and launch the container
docker compose up -d --build
```

---

### Accessing the Dashboard

Once the container is running:
```
http://localhost:8080/
```

- **Default Username**: `admin` (or your configured `ADMIN_USERNAME`)
- **Default Password**: `adminpassword123` (or your configured `ADMIN_PASSWORD`)

---

## Automated GitHub Actions CI/CD (Image Generation)

Pombo CDN includes an automated GitHub Actions workflow in `.github/workflows/docker-publish.yml`.

Whenever you push commits to `main` or publish release tags (`v*`), GitHub Actions automatically:
1. Builds the multi-layer Docker image.
2. Publishes and tags the image directly to GitHub Container Registry (`ghcr.io/thalisonnunes20/pombo:latest` and `ghcr.io/thalisonnunes20/pombo:v0.0.1`).
3. Enables manual build triggers via GitHub's "Actions" tab (`workflow_dispatch`).

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

        proxy_read_timeout 3600s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 3600s;
        send_timeout 3600s;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_max_temp_file_size 0;
    }
}
```

### Nginx Proxy Manager (NPM) Setup (Crucial for Large Downloads & Uploads)

If you are using **Nginx Proxy Manager**, large downloads (e.g., 5GB+ videos or archives) or uploads will terminate after 60 seconds with `504 Gateway Timeout` or `413 Request Entity Too Large` unless you configure the **Advanced** tab.

In your Nginx Proxy Manager dashboard:
1. Edit your **Proxy Host** (e.g., `pombo.yourdomain.com`).
2. In the **Details** tab:
   - Forward Hostname/IP: your server IP or container name (e.g. `pombo`).
   - Forward Port: `8080`.
   - Enable **Websockets Support**.
3. In the **Advanced** tab, paste the following **Custom Nginx Configuration**:

```nginx
# Allow unlimited upload size (no 413 Payload Too Large)
client_max_body_size 0;

# Disable proxy buffering to stream large files instantly without disk spooling
proxy_buffering off;
proxy_request_buffering off;
proxy_max_temp_file_size 0;

# Increase timeouts to 1 hour (prevents 504 Gateway Timeout on slow/long downloads)
proxy_connect_timeout 300s;
proxy_send_timeout 3600s;
proxy_read_timeout 3600s;
send_timeout 3600s;

# Preserve HTTP Range Requests for video/audio seeking and resumable downloads
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Range $http_range;
proxy_set_header If-Range $http_if_range;
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

See [CHANGELOG.md](CHANGELOG.md) for full release details.

### `v1.0.0` (Official Production Release)
- All-in-one Docker container with Nginx, Gunicorn, Django 5.1, and Supervisor.
- Automated GitHub Actions build pipeline to GitHub Container Registry (`ghcr.io/thalisonnunes20/pombo`).
- High-performance direct-to-disk `X-Accel-Redirect` file delivery engine.
- Complete responsive dark theme with mobile slide-out drawer navigation and visual `v1.0.0` branding.
- Persistent "Remember Login" functionality with client username caching.
- Multi-tier rate limiting and automated anti-brute-force lockout.
- Granular link expiration engine (download limits, time limits, combined rules).
- Live audit log system with 1-click clipboard copy and safe log purge.
- Real-time bilingual toggle (`EN-US` / `PT-BR`).
- Dual storage mapping support (`uploads` and `external:ro`).
